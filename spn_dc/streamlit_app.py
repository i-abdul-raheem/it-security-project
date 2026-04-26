"""
Streamlit UI for SPN differential analysis.

Run from the project root:
  pip install -e ".[ui]"
  streamlit run spn_dc/streamlit_app.py
"""

from __future__ import annotations

import os

# Keep UI session separate from CLI on-disk state by default.
os.environ.setdefault("SPN_DC_NO_PERSIST", "1")

import streamlit as st

from spn_dc.difference import DiffKind
from spn_dc.linear import identity_matrix
from spn_dc.parsing import parse_int_list, parse_mapping, parse_matrix_rows
from spn_dc.session import SPNSession, random_bijective_matrix, random_sbox


def _input_mode_index(cell) -> int:
    if cell.kind in (DiffKind.CONCRETE, DiffKind.ZERO):
        return 1
    if cell.kind is DiffKind.NONZERO:
        return 2
    return 0


def _sess() -> SPNSession:
    if "spn" not in st.session_state:
        st.session_state.spn = SPNSession()
    return st.session_state.spn


def _identity_csv(bits: int) -> str:
    n = 1 << bits
    return ",".join(str(i) for i in range(n))


def _p_rows_csv(sess: SPNSession) -> str:
    if not sess._sboxes or sess._p is None:
        return ""
    return ",".join(str(r) for r in sess._p.rows)


def _parse_equality_groups(text: str) -> tuple[tuple[int, ...], ...]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    groups: list[tuple[int, ...]] = []
    for ln in lines:
        groups.append(tuple(parse_int_list(ln.replace(" ", ""))))
    return tuple(groups)


def _format_round_sets(st) -> None:
    st.markdown("**Before S-box**")
    st.json({str(i): sorted(s) for i, s in enumerate(st.before_sbox)})
    st.markdown("**After S-box**")
    st.json({str(i): sorted(s) for i, s in enumerate(st.after_sbox)})
    st.markdown("**After P**")
    st.json({str(i): sorted(s) for i, s in enumerate(st.after_p)})


def main() -> None:
    st.set_page_config(page_title="SPN Differential Lab", layout="wide")
    st.title("SPN differential lab")
    st.caption("Configurable S-box layer + bijective linear P-layer · DDT · propagation · trails")

    sess = _sess()

    with st.sidebar:
        st.header("Cipher")
        rounds = st.number_input("Rounds", min_value=1, max_value=64, value=4, step=1)
        num_sb = st.number_input("S-boxes per round", min_value=1, max_value=32, value=2, step=1)
        sbox_bits = st.number_input("Bits per S-box", min_value=1, max_value=8, value=4, step=1)
        if st.button("Create / reset cipher", type="primary"):
            sess.create_spn(int(rounds), int(num_sb), int(sbox_bits))
            st.success("Cipher initialized (identity S-boxes + identity P).")
        if st.button("Full reset (clear cipher)"):
            sess.reset()
            st.session_state.pop("spn", None)
            st.success("Cleared.")
        if st.button("Random P-layer"):
            try:
                sess._require_cipher()
            except RuntimeError:
                st.error("Create a cipher first.")
            else:
                dim = sess._num_sboxes * sess._sbox_bits
                m = random_bijective_matrix(dim)
                sess.set_permutation(m.rows)
                st.success("Random invertible P applied.")

    if not sess._sboxes:
        st.info("Use the sidebar to **Create / reset cipher** to begin.")
        return

    dim = sess._num_sboxes * sess._sbox_bits
    tabs = st.tabs(
        ["S-boxes & P", "DDT", "Input & constraints", "Propagate", "Paths", "Check constraints"]
    )

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("S-boxes")
            for i in range(sess._num_sboxes):
                key = f"sbox_map_{i}_{sess._sbox_bits}_{sess._num_sboxes}"
                cur_csv = ",".join(str(x) for x in sess._sboxes[i].table)
                txt = st.text_area(
                    f"S-box {i} mapping (comma-separated, length {1 << sess._sbox_bits})",
                    value=cur_csv,
                    height=88,
                    key=key,
                )
                if st.button(f"Apply S-box {i}", key=f"apply_sb_{i}"):
                    try:
                        sess.set_sbox(i, parse_mapping(txt.replace("\n", "")))
                        st.success(f"S-box {i} updated.")
                    except Exception as e:
                        st.error(str(e))
            if st.button("Randomize all S-boxes"):
                for j in range(sess._num_sboxes):
                    sess.set_sbox(j, random_sbox(sess._sbox_bits).table)
                st.success("All S-boxes randomized.")
        with c2:
            st.subheader("P-layer (GF(2) rows)")
            st.caption(f"Provide **{dim}** comma-separated row integers (same convention as CLI).")
            prow = st.text_area(
                "Row bitmasks",
                value=_p_rows_csv(sess),
                height=min(200, 24 + dim * 14),
                key=f"p_rows_{dim}",
            )
            if st.button("Apply P-layer"):
                try:
                    sess.set_permutation(parse_matrix_rows(prow.replace("\n", "")))
                    st.success("P-layer updated.")
                except Exception as e:
                    st.error(str(e))
            if st.button("Identity P"):
                sess.set_permutation(identity_matrix(dim).rows)
                st.success("P set to identity.")

    with tabs[1]:
        sid = st.selectbox("S-box index", list(range(sess._num_sboxes)))
        if st.button("Show DDT"):
            ddt = sess.compute_ddt(sid)
            st.dataframe(list(ddt), use_container_width=True, height=min(600, 40 + len(ddt) * 28))

    with tabs[2]:
        st.subheader("Round-1 input cells")
        st.caption("Per position: Any · fixed value · abstract (nonzero unknown) · round-1 output fix.")
        cols = st.columns(sess._num_sboxes)
        for i in range(sess._num_sboxes):
            with cols[i]:
                st.markdown(f"**S-box {i}**")
                cell = sess._input_cells[i]
                mode = st.radio(
                    "Input mode",
                    ("any", "fixed", "abstract"),
                    horizontal=True,
                    key=f"in_mode_{i}_{sess._num_sboxes}",
                    index=_input_mode_index(cell),
                    label_visibility="collapsed",
                )
                def_val = int(cell.value) if cell.kind in (DiffKind.CONCRETE, DiffKind.ZERO) else 0
                if mode == "fixed":
                    v = st.number_input(
                        f"Δin {i}",
                        min_value=0,
                        max_value=(1 << sess._sbox_bits) - 1,
                        value=def_val,
                        key=f"in_fix_{i}_{sess._num_sboxes}",
                    )
                    if st.button("Apply fixed", key=f"btn_in_fixed_{i}"):
                        sess.fix_input_difference(i, int(v))
                        st.success("Saved.")
                elif mode == "abstract":
                    if st.button("Set abstract", key=f"btn_in_abs_{i}"):
                        sess.set_abstract_difference(i)
                        st.success("Saved.")
                else:
                    if st.button("Set Any", key=f"btn_in_any_{i}"):
                        sess.set_input_any(i)
                        st.success("Saved.")
        st.divider()
        st.subheader("Round-1 output difference fixes (after S-box)")
        of_cols = st.columns(sess._num_sboxes)
        for i in range(sess._num_sboxes):
            with of_cols[i]:
                if st.checkbox(f"Fix out {i}", key=f"of_en_{i}"):
                    ov = st.number_input(
                        f"Δout {i}",
                        0,
                        (1 << sess._sbox_bits) - 1,
                        0,
                        key=f"of_v_{i}",
                    )
                    if st.button("Save", key=f"btn_out_fix_{i}"):
                        sess.fix_output_difference(i, int(ov))
                        st.success("Saved.")
        st.divider()
        st.subheader("Equality on inputs")
        st.caption("One group per line, comma-separated indices (e.g. `0,2`). Replaces all groups on apply.")
        eq_text = st.text_area(
            "Equality groups",
            value="\n".join(",".join(str(x) for x in g) for g in sess._equality_groups),
            height=120,
        )
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Apply equality groups"):
                try:
                    g = _parse_equality_groups(eq_text)
                    sess.replace_equality_groups(g)
                    st.success("Equality groups replaced.")
                except Exception as e:
                    st.error(str(e))
        with b2:
            if st.button("Clear equality groups"):
                sess.replace_equality_groups(())
                st.success("Cleared.")
        with b3:
            if st.button("Reset input cells to Any"):
                sess.reset_input_cells()
                st.success("Input cells cleared.")
        if st.button("Clear output fixes"):
            sess.clear_output_fixes()
            st.success("Output fixes cleared.")

    with tabs[3]:
        st.subheader("Propagate packed difference")
        packed = st.text_input("Packed Δx (hex or decimal)", value="0x11")
        if st.button("Propagate", type="primary"):
            try:
                dx = int(packed.strip(), 0)
            except ValueError:
                st.error("Invalid integer.")
            else:
                trail, err = sess.propagate_difference(dx)
                if err:
                    st.error(err)
                else:
                    for ri, stt in enumerate(trail):
                        with st.expander(f"Round {ri + 1}", expanded=(ri == 0)):
                            _format_round_sets(stt)

    with tabs[4]:
        st.subheader("Enumerate differential trails")
        p_in = st.text_input("Packed input difference", value="0x11", key="path_in")
        cap = st.number_input("Max paths", min_value=1, max_value=200_000, value=10_000, step=1000)
        if st.button("Generate paths"):
            try:
                dx = int(p_in.strip(), 0)
            except ValueError:
                st.error("Invalid integer.")
            else:
                msg, err = sess.generate_paths(dx, max_paths=int(cap))
                if err:
                    st.error(err)
                else:
                    st.success(msg)
        if sess._paths:
            st.metric("Paths stored", len(sess._paths))
            thr = st.number_input("Filter: keep probability >", min_value=0.0, max_value=1.0, value=0.0, step=1e-6)
            if st.button("Apply filter"):
                try:
                    sess.filter_paths(float(thr), strict=True)
                    n = len(sess._paths_filtered or ())
                    st.success(f"{n} path(s) after filter.")
                except Exception as e:
                    st.error(str(e))
            pool = list(sess._paths_filtered) if sess._paths_filtered is not None else list(sess._paths)
            labels = [f"id={p.path_id}  p={p.probability:.4g}" for p in pool]
            choice = st.selectbox("Select trail", range(len(pool)), format_func=lambda i: labels[i])
            if pool:
                p = pool[int(choice)]
                st.markdown(f"**Probability:** `{p.probability}`")
                for ri, step in enumerate(p.trace):
                    b, a, z = step
                    st.markdown(f"**Round {ri + 1}**  before={list(b)}  after S-box={list(a)}  after P={list(z)}")

    with tabs[5]:
        if st.button("Run constraint check", type="primary"):
            trail, err = sess.check_constraints()
            if err:
                st.error(err)
            else:
                st.success("All constraints are compatible with propagation.")
                for ri, stt in enumerate(trail):
                    with st.expander(f"Round {ri + 1}"):
                        _format_round_sets(stt)


if __name__ == "__main__":
    main()
