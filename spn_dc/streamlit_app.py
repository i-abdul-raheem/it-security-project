"""
Streamlit UI for SPN differential analysis.

Run from the project root:
  pip install -e ".[ui]"
  streamlit run spn_dc/streamlit_app.py
"""

from __future__ import annotations

import os
import time

# Keep UI session separate from CLI on-disk state by default.
os.environ.setdefault("SPN_DC_NO_PERSIST", "1")

import streamlit as st
import streamlit.components.v1 as components

from spn_dc.difference import DiffKind
from spn_dc.linear import identity_matrix, is_permutation_matrix
from spn_dc.parsing import parse_int_list, parse_mapping, parse_matrix_rows
from spn_dc.session import SPNSession, random_permutation_matrix, random_sbox
from spn_dc.ui_diagram import render_frame_bit_diagram_svg, render_spn_bit_diagram_svg
from spn_dc.ui_permutation import (
    bit_permutation_wiring,
    is_pure_bit_permutation,
    p_matrix_bit_grid,
    p_row_descriptions,
    render_bit_perm_wiring_svg,
    render_p_matrix_svg,
    render_sbox_permutation_svg,
    sbox_mapping_rows,
)
from spn_dc.ui_viz import (
    PropFrame,
    frames_from_path_trace,
    frames_from_trail,
    render_propagation_frame_html,
)


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


def _format_round_sets(round_state) -> None:
    """`round_state` must be a RoundSetState; name avoids shadowing Streamlit's `st`."""
    st.markdown("**Before S-box**")
    st.json({str(i): sorted(s) for i, s in enumerate(round_state.before_sbox)})
    st.markdown("**After S-box**")
    st.json({str(i): sorted(s) for i, s in enumerate(round_state.after_sbox)})
    st.markdown("**After P**")
    st.json({str(i): sorted(s) for i, s in enumerate(round_state.after_p)})


def _store_viz_frames(frames: tuple[PropFrame, ...], sbox_bits: int, source: str) -> None:
    st.session_state.viz_frames = frames
    st.session_state.viz_sbox_bits = sbox_bits
    st.session_state.viz_source = source
    st.session_state.viz_step = 0


def _clear_viz_state() -> None:
    """Drop animation data derived from the previous cipher configuration."""
    for key in (
        "viz_frames",
        "viz_sbox_bits",
        "viz_source",
        "viz_step",
        "viz_current_step",
        "prop_trail",
    ):
        st.session_state.pop(key, None)


def _diagram_height(num_bits: int) -> int:
    step = max(16, min(24, 520 // max(num_bits, 1)))
    return int(max(300, min(920, (num_bits - 1) * step + 160)))


def _show_bit_diagram_svg(svg: str, *, num_bits: int) -> None:
    components.html(
        f'<div style="overflow:auto;width:100%">{svg}</div>',
        height=_diagram_height(num_bits),
        scrolling=True,
    )


def _show_perm_svg(svg: str, *, height: int) -> None:
    components.html(
        f'<div style="overflow:auto;width:100%">{svg}</div>',
        height=height,
        scrolling=True,
    )


def _render_bit_diagram(sess: SPNSession, frame: PropFrame | None = None) -> None:
    if not sess._p or not sess._sboxes:
        return
    n = sess._num_sboxes * sess._sbox_bits
    if frame is None:
        svg = render_spn_bit_diagram_svg(
            num_sboxes=sess._num_sboxes,
            sbox_bits=sess._sbox_bits,
            p_rows=sess._p.rows,
            title="Cipher wiring (all S-boxes, bit pins, P connections)",
        )
    else:
        if len(frame.slices) != sess._num_sboxes:
            st.warning(
                "This animation belongs to an earlier cipher configuration. "
                "Run propagation or generate a path again."
            )
            return
        svg = render_frame_bit_diagram_svg(
            num_sboxes=sess._num_sboxes,
            sbox_bits=sess._sbox_bits,
            p_rows=sess._p.rows,
            layer=frame.layer,
            slices=frame.slices,
            round_index=frame.round_index,
            layer_title=frame.layer_title,
        )
    _show_bit_diagram_svg(svg, num_bits=n)


def _render_propagation_animation(*, key_prefix: str = "viz", sess: SPNSession | None = None) -> None:
    frames: tuple[PropFrame, ...] | None = st.session_state.get("viz_frames")
    if not frames:
        return
    bits = int(st.session_state.get("viz_sbox_bits", 4))
    if sess is not None and (
        bits != sess._sbox_bits
        or any(len(frame.slices) != sess._num_sboxes for frame in frames)
    ):
        _clear_viz_state()
        st.warning(
            "The saved animation was cleared because the cipher configuration changed. "
            "Run propagation or generate a path again."
        )
        return
    source = st.session_state.get("viz_source", "propagation")
    total = len(frames)

    st.markdown("### Animated propagation")
    st.caption(f"Source: **{source}** · {total} steps (3 per round: before S-box → after S-box → after P)")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        delay = st.slider(
            "Seconds per step",
            min_value=0.15,
            max_value=2.5,
            value=0.65,
            step=0.05,
            key=f"{key_prefix}_delay",
        )
    with c2:
        play = st.button("▶ Play animation", key=f"{key_prefix}_play", type="primary")
    with c3:
        loop = st.checkbox("Loop once more after finish", value=False, key=f"{key_prefix}_loop")

    slider_key = f"{key_prefix}_step"
    pending_key = f"{key_prefix}_pending_step"
    # Apply deferred scrub position *before* the slider widget is created.
    if pending_key in st.session_state:
        st.session_state[slider_key] = int(st.session_state.pop(pending_key))
    step = st.slider(
        "Scrub step",
        min_value=0,
        max_value=total - 1,
        key=slider_key,
    )

    viz_slot = st.empty()
    bit_slot = st.empty()
    progress_slot = st.empty()

    def _draw(ix: int, *, pulse: bool) -> None:
        html_block = render_propagation_frame_html(
            frames[ix],
            sbox_bits=bits,
            frame_index=ix,
            total_frames=total,
            pulse=pulse,
        )
        viz_slot.markdown(html_block, unsafe_allow_html=True)
        if sess is not None:
            with bit_slot.container():
                st.markdown("#### Bit pins, S-boxes & P wiring")
                _render_bit_diagram(sess, frames[ix])

    if play:
        runs = 2 if loop else 1
        for _ in range(runs):
            prog = progress_slot.progress(0.0, text="Animating…")
            for ix in range(total):
                _draw(ix, pulse=True)
                prog.progress((ix + 1) / total, text=f"Step {ix + 1} / {total}")
                time.sleep(delay)
            time.sleep(0.25)
        progress_slot.empty()
        _draw(total - 1, pulse=False)
        # Cannot assign slider_key after the slider exists; queue for next run.
        st.session_state[pending_key] = total - 1
        st.session_state["viz_current_step"] = total - 1
        st.rerun()
    else:
        _draw(step, pulse=False)
        st.session_state["viz_current_step"] = step

    show_ix = int(st.session_state.get("viz_current_step", step))
    with st.expander("Raw set data (current step)", expanded=False):
        st.json({str(i): sorted(s) for i, s in enumerate(frames[show_ix].slices)})


def main() -> None:
    st.set_page_config(page_title="SPN Differential Lab", layout="wide")
    st.title("SPN differential lab")
    st.caption("Configurable S-box layer + bijective linear P-layer · DDT · propagation · trails")

    sess = _sess()

    # Some editor widgets are created before their action buttons. Queue their
    # new text for the next rerun, then apply it before any widget is rendered.
    pending_editor_values = st.session_state.pop("pending_editor_values", {})
    for key, value in pending_editor_values.items():
        st.session_state[key] = value
    editor_flash = st.session_state.pop("editor_flash", None)

    # Repair an in-memory P-layer created by an older app version, which allowed
    # general XOR matrices. Current P-layers are strictly one-to-one.
    repaired_legacy_p = False
    if sess._p is not None and not is_permutation_matrix(sess._p):
        dim = sess._num_sboxes * sess._sbox_bits
        sess._p = identity_matrix(dim)
        sess._paths = ()
        sess._paths_filtered = None
        _clear_viz_state()
        st.session_state[f"p_rows_{dim}"] = _p_rows_csv(sess)
        repaired_legacy_p = True

    with st.sidebar:
        st.header("Cipher")
        dimension_defaults = {
            "cipher_rounds": sess._rounds or 4,
            "cipher_num_sboxes": sess._num_sboxes or 2,
            "cipher_sbox_bits": sess._sbox_bits or 4,
        }
        for key, value in dimension_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
        rounds = st.number_input("Rounds", min_value=1, max_value=64, step=1, key="cipher_rounds")
        num_sb = st.number_input(
            "S-boxes per round", min_value=1, max_value=32, step=1, key="cipher_num_sboxes"
        )
        sbox_bits = st.number_input(
            "Bits per S-box", min_value=1, max_value=8, step=1, key="cipher_sbox_bits"
        )
        if st.button("Create / reset cipher", type="primary"):
            sess.create_spn(int(rounds), int(num_sb), int(sbox_bits))
            _clear_viz_state()
            for i, sb in enumerate(sess._sboxes):
                key = f"sbox_map_{i}_{sess._sbox_bits}_{sess._num_sboxes}"
                st.session_state[key] = ",".join(str(x) for x in sb.table)
            dim = sess._num_sboxes * sess._sbox_bits
            st.session_state[f"p_rows_{dim}"] = _p_rows_csv(sess)
            st.success("Cipher initialized (identity S-boxes + identity P).")
        if st.button("Full reset (clear cipher)"):
            sess.reset()
            _clear_viz_state()
            st.session_state.pop("spn", None)
            st.success("Cleared.")
        if st.button("Random P-layer"):
            try:
                sess._require_cipher()
            except RuntimeError:
                st.error("Create a cipher first.")
            else:
                dim = sess._num_sboxes * sess._sbox_bits
                m = random_permutation_matrix(dim)
                sess.set_permutation(m.rows)
                st.session_state[f"p_rows_{dim}"] = _p_rows_csv(sess)
                st.success("Random one-to-one bit permutation applied.")

        st.divider()
        st.subheader("Saved configuration")
        config_file = st.file_uploader("Config JSON", type=("json",), key="config_upload")
        if st.button("Import config", disabled=config_file is None):
            try:
                imported = SPNSession.from_json(config_file.getvalue().decode("utf-8"))
            except (UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
                st.error(f"Could not import configuration: {exc}")
            else:
                st.session_state.spn = imported
                _clear_viz_state()
                imported_dim = imported._num_sboxes * imported._sbox_bits
                pending = {
                    "cipher_rounds": imported._rounds,
                    "cipher_num_sboxes": imported._num_sboxes,
                    "cipher_sbox_bits": imported._sbox_bits,
                    f"p_rows_{imported_dim}": _p_rows_csv(imported),
                }
                pending.update(
                    {
                        f"sbox_map_{i}_{imported._sbox_bits}_{imported._num_sboxes}": ",".join(
                            str(x) for x in sb.table
                        )
                        for i, sb in enumerate(imported._sboxes)
                    }
                )
                st.session_state.pending_editor_values = pending
                st.session_state.editor_flash = "Configuration imported."
                st.rerun()

        if sess._sboxes:
            st.download_button(
                "Download current config",
                data=sess.to_json(),
                file_name="spn-config.json",
                mime="application/json",
            )

    if not sess._sboxes:
        st.info("Use the sidebar to **Create / reset cipher** to begin.")
        return

    if repaired_legacy_p:
        st.warning(
            "The previous many-connection P-layer was replaced with identity because "
            "P-layers are now required to be one-to-one. Click **Random P-layer** for a shuffle."
        )
    if editor_flash:
        st.success(editor_flash)

    dim = sess._num_sboxes * sess._sbox_bits
    tabs = st.tabs(
        [
            "S-boxes & P",
            "Permutations",
            "DDT",
            "Input & constraints",
            "Propagate",
            "Paths",
            "Check constraints",
            "Bit wiring",
        ],
        key="analysis_tab",
        on_change="rerun",
    )

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("S-boxes")
            for i in range(sess._num_sboxes):
                key = f"sbox_map_{i}_{sess._sbox_bits}_{sess._num_sboxes}"
                cur_csv = ",".join(str(x) for x in sess._sboxes[i].table)
                if key not in st.session_state:
                    st.session_state[key] = cur_csv
                txt = st.text_area(
                    f"S-box {i} mapping (comma-separated, length {1 << sess._sbox_bits})",
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
                st.session_state.pending_editor_values = {
                    f"sbox_map_{j}_{sess._sbox_bits}_{sess._num_sboxes}": ",".join(
                        str(x) for x in sess._sboxes[j].table
                    )
                    for j in range(sess._num_sboxes)
                }
                st.session_state.editor_flash = "All S-boxes randomized."
                st.rerun()
        with c2:
            st.subheader("P-layer (GF(2) rows)")
            st.caption(f"Provide **{dim}** comma-separated row integers (same convention as CLI).")
            p_rows_key = f"p_rows_{dim}"
            if p_rows_key not in st.session_state:
                st.session_state[p_rows_key] = _p_rows_csv(sess)
            prow = st.text_area(
                "Row bitmasks",
                height=min(200, 24 + dim * 14),
                key=p_rows_key,
            )
            if st.button("Apply P-layer"):
                try:
                    sess.set_permutation(parse_matrix_rows(prow.replace("\n", "")))
                    st.success("P-layer updated.")
                except Exception as e:
                    st.error(str(e))
            if st.button("Identity P"):
                sess.set_permutation(identity_matrix(dim).rows)
                st.session_state.pending_editor_values = {
                    f"p_rows_{dim}": _p_rows_csv(sess)
                }
                st.session_state.editor_flash = "P set to identity."
                st.rerun()

    with tabs[1]:
        st.subheader("Permutation views")
        st.caption(
            "An **S-box** is a permutation on 2^n values. The **P-layer** is an invertible GF(2) matrix "
            "(a bit permutation when each row has exactly one `1`)."
        )
        ptab_sb, ptab_p = st.tabs(["S-box permutations", "P-layer connections"])

        with ptab_sb:
            sid = st.selectbox("S-box", list(range(sess._num_sboxes)), key="perm_sbox_id")
            sb = sess._sboxes[sid]
            bits = sess._sbox_bits
            st.markdown(f"**S{sid}** — {bits}-bit permutation ({len(sb.table)} entries)")
            st.dataframe(
                sbox_mapping_rows(sb.table, bits),
                use_container_width=True,
                height=min(420, 40 + len(sb.table) * 22),
            )
            if len(sb.table) <= 64:
                h = max(140, 28 + len(sb.table) * 16)
                _show_perm_svg(
                    render_sbox_permutation_svg(
                        sb.table, bits, title=f"S{sid}: wire x -> S(x)"
                    ),
                    height=h,
                )
            else:
                st.info("Braid diagram hidden for large S-boxes; use the table above.")

        with ptab_p:
            if sess._p is None:
                st.warning("No P-layer configured.")
            else:
                rows = sess._p.rows
                n = len(rows)
                cols = [f"x{j}" for j in range(n)]
                idx = [f"y{i}" for i in range(n)]
                st.markdown("**Matrix M** — `M[y,x] = 1` means output bit y XORs input bit x")
                st.dataframe(
                    {cols[j]: [p_matrix_bit_grid(rows)[i][j] for i in range(n)] for j in range(n)},
                    use_container_width=True,
                    height=min(500, 40 + n * 24),
                )
                cell = 14 if n > 12 else 22
                _show_perm_svg(
                    render_p_matrix_svg(rows, title="P-layer heatmap (1 = connected)"),
                    height=min(520, 60 + n * cell),
                )
                if is_pure_bit_permutation(rows):
                    st.success("This P-layer is a **pure bit permutation** (wire shuffle).")
                    pairs = bit_permutation_wiring(rows)
                    st.write("Wiring:", ", ".join(f"x{inp}->y{out}" for inp, out in pairs))
                    _show_perm_svg(
                        render_bit_perm_wiring_svg(rows),
                        height=max(120, 24 + n * 18),
                    )
                else:
                    st.info("General linear mix: each output bit XORs **several** input bits.")
                with st.expander("Row equations (GF(2))"):
                    for line in p_row_descriptions(rows):
                        st.code(line, language=None)

    with tabs[2]:
        sid = st.selectbox("S-box index", list(range(sess._num_sboxes)), key="ddt_sbox_id")
        if st.button("Show DDT"):
            ddt = sess.compute_ddt(sid)
            st.dataframe(list(ddt), use_container_width=True, height=min(600, 40 + len(ddt) * 28))

    with tabs[3]:
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

    with tabs[4]:
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
                    st.session_state.prop_trail = trail
                    _store_viz_frames(frames_from_trail(trail), sess._sbox_bits, f"Δx = {packed}")
                    st.success(f"Propagated through {len(trail)} round(s). Use the animation below.")
        if st.session_state.get("viz_frames"):
            _render_propagation_animation(key_prefix="prop", sess=sess)
            prop_trail = st.session_state.get("prop_trail")
            if prop_trail:
                st.divider()
                st.markdown("**All rounds (detail)**")
                for ri, stt in enumerate(prop_trail):
                    with st.expander(f"Round {ri + 1}", expanded=False):
                        _format_round_sets(stt)

    with tabs[5]:
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
            if not pool:
                st.warning(
                    "No trails match the current probability filter. "
                    "Set the threshold lower and click **Apply filter**, or generate paths again."
                )
            else:
                labels = [f"id={p.path_id}  p={p.probability:.4g}" for p in pool]
                choice = st.selectbox("Select trail", range(len(pool)), format_func=lambda i: labels[i])
                p = pool[int(choice)]
                st.markdown(f"**Probability:** `{p.probability}`")
                st.markdown("**Round-by-round difference permutations**")
                st.dataframe(
                    [
                        {
                            "round": ri,
                            "before S-box": " ".join(f"{v:X}" for v in before),
                            "after S-box": " ".join(f"{v:X}" for v in after_sbox),
                            "after P": " ".join(f"{v:X}" for v in after_p),
                        }
                        for ri, (before, after_sbox, after_p) in enumerate(p.trace, start=1)
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                if st.button("Animate this trail", key="path_animate"):
                    _store_viz_frames(
                        frames_from_path_trace(p.trace),
                        sess._sbox_bits,
                        f"path id={p.path_id}  p={p.probability:.4g}",
                    )
                    st.session_state.prop_trail = None
                    st.success("Trail loaded — animation below.")
                if st.session_state.get("viz_source", "").startswith("path id"):
                    _render_propagation_animation(key_prefix="path", sess=sess)

    with tabs[6]:
        if st.button("Run constraint check", type="primary"):
            trail, err = sess.check_constraints()
            if err:
                if st.session_state.get("viz_source") == "constraint check":
                    _clear_viz_state()
                st.error(err)
            else:
                st.session_state.prop_trail = trail
                _store_viz_frames(frames_from_trail(trail), sess._sbox_bits, "constraint check")
                st.success("All constraints are compatible with propagation.")

        # Keep this outside the button branch: every animation control causes a
        # Streamlit rerun, while the generated frames live in session state.
        if st.session_state.get("viz_source") == "constraint check":
            _render_propagation_animation(key_prefix="chk", sess=sess)
            constraint_trail = st.session_state.get("prop_trail")
            if constraint_trail:
                st.divider()
                st.markdown("**Constraint-compatible rounds (detail)**")
                for ri, stt in enumerate(constraint_trail):
                    with st.expander(f"Round {ri + 1}"):
                        _format_round_sets(stt)

    with tabs[7]:
        st.subheader("Bit-level network diagram")
        st.caption(
            "Each pin **b0…b{n−1}** is one bit of the block (slice 0 = lowest bits). "
            "Wires: input → S-box → after-S bus → **P** (curves: output bit o XORs every input i with M[o,i]=1)."
        )
        frames = st.session_state.get("viz_frames")
        if frames:
            step = st.slider(
                "Highlight propagation step",
                0,
                len(frames) - 1,
                int(st.session_state.get("viz_current_step", 0)),
                key="bitwiz_step",
            )
            _render_bit_diagram(sess, frames[step])
        else:
            _render_bit_diagram(sess, None)
            st.info("Run **Propagate** or **Check constraints** to color active bit pins per layer.")


if __name__ == "__main__":
    main()
