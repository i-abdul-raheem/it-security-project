from __future__ import annotations

import html
from typing import FrozenSet, Sequence

# Pin state: 0, 1, ? (mixed), x (empty set), - (idle / no propagation data)
_PIN_FILL = {
    "0": "#94a3b8",
    "1": "#22c55e",
    "?": "#f59e0b",
    "x": "#ef4444",
    "-": "#e2e8f0",
}
_PIN_STROKE = {
    "0": "#475569",
    "1": "#15803d",
    "?": "#b45309",
    "x": "#b91c1c",
    "-": "#94a3b8",
}


def pin_state_at_bit(diff_set: FrozenSet[int], bit: int) -> str:
    """Per-bit difference on one S-box slice: all-zero, all-one, mixed, or impossible."""
    if not diff_set:
        return "x"
    bits = [(v >> bit) & 1 for v in diff_set]
    if all(b == 0 for b in bits):
        return "0"
    if all(b == 1 for b in bits):
        return "1"
    return "?"


def pin_states_from_slices(
    slices: Sequence[FrozenSet[int]], sbox_bits: int
) -> list[str]:
    """One state per global bit (LSB-first block: slice 0 = lowest bits)."""
    out: list[str] = []
    for sset in slices:
        for b in range(sbox_bits):
            out.append(pin_state_at_bit(sset, b))
    return out


def _matrix_connects(p_rows: tuple[int, ...], out_bit: int, in_bit: int) -> bool:
    if out_bit >= len(p_rows) or in_bit < 0:
        return False
    return bool((p_rows[out_bit] >> in_bit) & 1)


def render_spn_bit_diagram_svg(
    *,
    num_sboxes: int,
    sbox_bits: int,
    p_rows: tuple[int, ...],
    input_states: Sequence[str] | None = None,
    post_s_states: Sequence[str] | None = None,
    output_states: Sequence[str] | None = None,
    active_layer: str | None = None,
    title: str = "",
    width: int = 920,
) -> str:
    """
    SVG: input bit pins → S-boxes (with per-bit wires) → post-S pins → P wiring → output pins.

    `active_layer` is one of before_sbox | after_sbox | after_p (highlights that stage).
    """
    n = num_sboxes * sbox_bits
    if len(p_rows) != n:
        raise ValueError("P-layer row count must equal total block bits")

    def _states(seq: Sequence[str] | None) -> list[str]:
        if seq is None:
            return ["-"] * n
        if len(seq) != n:
            raise ValueError("pin state vector length mismatch")
        return list(seq)

    inp = _states(input_states)
    post = _states(post_s_states)
    out = _states(output_states)

    pin_step = max(16, min(24, 520 // max(n, 1)))
    top = 56
    bus_h = (n - 1) * pin_step
    height = top + bus_h + 100

    def y_pin(global_bit: int) -> float:
        return top + (n - 1 - global_bit) * pin_step  # MSB at top

    # x columns
    x_in, x_sb_in, x_sb_out, x_post, x_p, x_out = 50, 150, 250, 340, 520, 700

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        "<defs>",
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">',
        '<path d="M0,0 L6,3 L0,6 Z" fill="#6366f1"/></marker>',
        "</defs>",
    ]

    if title:
        parts.append(
            f'<text x="{width/2}" y="22" text-anchor="middle" font-size="14" font-weight="600" fill="#1e293b">'
            f"{html.escape(title)}</text>"
        )

    # Column labels
    for label, x in [
        ("Input Δ bits", x_in),
        ("S-boxes", (x_sb_in + x_sb_out) / 2),
        ("After S", x_post),
        ("P (GF₂)", x_p),
        ("After P", x_out),
    ]:
        parts.append(
            f'<text x="{x}" y="{top - 18}" text-anchor="middle" font-size="11" fill="#64748b">{html.escape(label)}</text>'
        )

    def draw_pin(cx: float, cy: float, state: str, *, glow: bool) -> None:
        fill = _PIN_FILL.get(state, _PIN_FILL["-"])
        stroke = _PIN_STROKE.get(state, _PIN_STROKE["-"])
        r = 7 if glow else 6
        sw = 2.5 if glow else 1.5
        if glow:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r+4}" fill="{fill}" opacity="0.25"/>')
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def draw_wire(x1: float, y1: float, x2: float, y2: float, *, active: bool, dashed: bool = False) -> None:
        col = "#6366f1" if active else "#cbd5e1"
        sw = 2.2 if active else 1.0
        op = 0.95 if active else 0.55
        dash = ' stroke-dasharray="4,3"' if dashed else ""
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{sw}" '
            f'opacity="{op}"{dash}/>'
        )

    # Bit labels (global index)
    for g in range(n):
        cy = y_pin(g)
        parts.append(
            f'<text x="{x_in - 12}" y="{cy + 4}" text-anchor="end" font-size="9" fill="#94a3b8">b{g}</text>'
        )

    # S-box boxes + internal slice wires
    for si in range(num_sboxes):
        g0 = si * sbox_bits
        g1 = g0 + sbox_bits - 1
        y_top = y_pin(g1) - 14
        y_bot = y_pin(g0) + 14
        box_h = y_bot - y_top
        sb_active = active_layer == "after_sbox"
        stroke = "#4f46e5" if sb_active else "#94a3b8"
        sw = 2.5 if sb_active else 1.5
        parts.append(
            f'<rect x="{x_sb_in - 8}" y="{y_top}" width="{x_sb_out - x_sb_in + 16}" height="{box_h}" '
            f'rx="8" fill="#f8fafc" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        parts.append(
            f'<text x="{(x_sb_in + x_sb_out)/2}" y="{y_top + 14}" text-anchor="middle" '
            f'font-size="11" font-weight="700" fill="#4338ca">S{si}</text>'
        )
        for local in range(sbox_bits):
            g = g0 + local
            cy = y_pin(g)
            in_glow = active_layer == "before_sbox"
            post_glow = active_layer == "after_sbox"
            out_glow = active_layer == "after_p"
            # input pin
            draw_pin(x_in, cy, inp[g], glow=in_glow)
            # wire in -> S-box
            draw_wire(x_in + 7, cy, x_sb_in - 8, cy, active=in_glow)
            # S-box output pin (same row = bit lane through substitution)
            draw_pin(x_sb_out, cy, post[g], glow=post_glow)
            draw_wire(x_sb_in + 8, cy, x_sb_out - 7, cy, active=post_glow)
            # post-S bus pin
            draw_pin(x_post, cy, post[g], glow=post_glow)
            draw_wire(x_sb_out + 7, cy, x_post - 7, cy, active=post_glow)
            # output pin
            draw_pin(x_out, cy, out[g], glow=out_glow)

    # P-layer cross-connections (output o <- XOR inputs i where M[o,i]=1)
    for o_bit in range(n):
        y_o = y_pin(o_bit)
        any_active = False
        for i_bit in range(n):
            if not _matrix_connects(p_rows, o_bit, i_bit):
                continue
            y_i = y_pin(i_bit)
            p_active = active_layer == "after_p"
            if p_active:
                any_active = True
            # curved wire post -> P hub -> out
            mx = x_p
            path = (
                f"M{x_post + 7},{y_i} C{mx},{y_i} {mx},{y_o} {x_out - 7},{y_o}"
            )
            col = "#7c3aed" if p_active else "#c4b5fd"
            sw = 1.8 if p_active else 0.7
            op = 0.85 if p_active else 0.35
            parts.append(
                f'<path d="{path}" fill="none" stroke="{col}" stroke-width="{sw}" opacity="{op}"/>'
            )
        if active_layer == "after_p" and any_active:
            parts.append(f'<circle cx="{x_p}" cy="{y_o}" r="3" fill="#7c3aed" opacity="0.5"/>')

    # Legend
    ly = height - 28
    lx = 40
    parts.append(f'<text x="{lx}" y="{ly}" font-size="10" fill="#64748b">Pin legend:</text>')
    for i, (sym, label) in enumerate(
        [("0", "bit=0"), ("1", "bit=1"), ("?", "mixed"), ("x", "impossible"), ("-", "idle")]
    ):
        cx = lx + 72 + i * 88
        draw_pin(cx, ly - 5, sym, glow=False)
        parts.append(
            f'<text x="{cx + 14}" y="{ly}" font-size="9" fill="#64748b">{html.escape(label)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def render_frame_bit_diagram_svg(
    *,
    num_sboxes: int,
    sbox_bits: int,
    p_rows: tuple[int, ...],
    layer: str,
    slices: tuple[FrozenSet[int], ...],
    round_index: int,
    layer_title: str,
) -> str:
    """Color the bus that matches the current propagation layer; others stay idle."""
    states = pin_states_from_slices(slices, sbox_bits)
    inp = post = out = None
    if layer == "before_sbox":
        inp = states
    elif layer == "after_sbox":
        post = states
    elif layer == "after_p":
        out = states
    return render_spn_bit_diagram_svg(
        num_sboxes=num_sboxes,
        sbox_bits=sbox_bits,
        p_rows=p_rows,
        input_states=inp,
        post_s_states=post,
        output_states=out,
        active_layer=layer,
        title=f"Round {round_index} · {layer_title}",
    )
