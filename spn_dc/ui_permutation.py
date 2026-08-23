from __future__ import annotations

import html
from typing import Sequence


def _hex_w(bits: int) -> int:
    return max(1, (bits + 3) // 4)


def sbox_mapping_rows(table: Sequence[int], bits: int) -> list[dict[str, str | int]]:
    w = _hex_w(bits)
    return [
        {
            "input (dec)": x,
            "input (hex)": f"0x{x:0{w}X}",
            "output S(x) (dec)": int(table[x]),
            "output (hex)": f"0x{int(table[x]):0{w}X}",
        }
        for x in range(len(table))
    ]


def p_matrix_bit_grid(p_rows: tuple[int, ...]) -> list[list[int]]:
    """Grid[out_row][in_col] = 1 if M[out_row, in_col] = 1 (LSB = col 0)."""
    n = len(p_rows)
    return [[(p_rows[i] >> j) & 1 for j in range(n)] for i in range(n)]


def p_row_descriptions(p_rows: tuple[int, ...]) -> list[str]:
    n = len(p_rows)
    lines: list[str] = []
    for i in range(n):
        ins = [str(j) for j in range(n) if (p_rows[i] >> j) & 1]
        lines.append(f"y{i} = XOR of input bits {{{', '.join(ins) if ins else '(none)'}}}")
    return lines


def is_pure_bit_permutation(p_rows: tuple[int, ...]) -> bool:
    """True when each output bit copies exactly one input bit (permutation wiring)."""
    seen: set[int] = set()
    for r in p_rows:
        if r == 0 or r & (r - 1):
            return False
        seen.add(r)
    return len(seen) == len(p_rows)


def bit_permutation_wiring(p_rows: tuple[int, ...]) -> list[tuple[int, int]]:
    """If pure bit permutation: list (input_bit, output_bit) pairs."""
    if not is_pure_bit_permutation(p_rows):
        return []
    out: list[tuple[int, int]] = []
    for out_bit, mask in enumerate(p_rows):
        in_bit = mask.bit_length() - 1
        out.append((in_bit, out_bit))
    return sorted(out)


def render_sbox_permutation_svg(
    table: Sequence[int],
    bits: int,
    *,
    title: str = "S-box permutation",
    max_lines: int = 64,
) -> str:
    """Braid diagram: each input x wires to output S(x)."""
    n = len(table)
    if n > max_lines:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60">'
            f'<text x="10" y="30" font-size="12">{html.escape(title)}: table too large for diagram (n={n})</text></svg>'
        )

    w = _hex_w(bits)
    width, height = 300, max(120, 28 + n * 16)
    x_in, x_out = 52, 248
    top = 36
    step = (height - top - 24) / max(n - 1, 1)

    def y_at(v: int) -> float:
        return top + v * step

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width/2}" y="18" text-anchor="middle" font-size="12" font-weight="600" fill="#1e293b">'
        f"{html.escape(title)}</text>",
        f'<text x="{x_in}" y="{top - 8}" text-anchor="middle" font-size="10" fill="#64748b">input x</text>',
        f'<text x="{x_out}" y="{top - 8}" text-anchor="middle" font-size="10" fill="#64748b">S(x)</text>',
    ]

    palette = ["#6366f1", "#8b5cf6", "#a855f7", "#d946ef", "#ec4899", "#f43f5e"]
    for x in range(n):
        y1, y2 = y_at(x), y_at(int(table[x]))
        col = palette[x % len(palette)]
        mx = (x_in + x_out) / 2
        parts.append(
            f'<path d="M{x_in},{y1} C{mx},{y1} {mx},{y2} {x_out},{y2}" '
            f'fill="none" stroke="{col}" stroke-width="1.4" opacity="0.75"/>'
        )
        parts.append(f'<circle cx="{x_in}" cy="{y1}" r="4" fill="{col}"/>')
        parts.append(
            f'<text x="{x_in - 6}" y="{y1 + 3}" text-anchor="end" font-size="8" fill="#475569">'
            f"0x{x:0{w}X}</text>"
        )
        parts.append(f'<circle cx="{x_out}" cy="{y2}" r="4" fill="{col}"/>')
        parts.append(
            f'<text x="{x_out + 6}" y="{y2 + 3}" font-size="8" fill="#475569">0x{int(table[x]):0{w}X}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def render_p_matrix_svg(
    p_rows: tuple[int, ...],
    *,
    title: str = "P-layer GF(2) matrix",
    cell: int = 20,
) -> str:
    """Heatmap: rows = output bits y, columns = input bits x; dark = coefficient 1."""
    n = len(p_rows)
    label_w, label_h = 28, 22
    grid_w, grid_h = n * cell, n * cell
    width = label_w + grid_w + 40
    height = label_h + grid_h + 50
    ox, oy = label_w, label_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width/2}" y="16" text-anchor="middle" font-size="12" font-weight="600" fill="#1e293b">'
        f"{html.escape(title)}</text>",
        f'<text x="{ox + grid_w/2}" y="{oy - 6}" text-anchor="middle" font-size="10" fill="#64748b">input bit x (column)</text>',
        f'<text x="12" y="{oy + grid_h/2}" font-size="10" fill="#64748b" transform="rotate(-90 12,{oy + grid_h/2})">'
        f"output y (row)</text>",
    ]

    for j in range(n):
        cx = ox + j * cell + cell / 2
        parts.append(
            f'<text x="{cx}" y="{oy - 2}" text-anchor="middle" font-size="8" fill="#94a3b8">x{j}</text>'
        )
    for i in range(n):
        cy = oy + i * cell + cell / 2
        parts.append(
            f'<text x="{ox - 4}" y="{cy + 3}" text-anchor="end" font-size="8" fill="#94a3b8">y{i}</text>'
        )
        for j in range(n):
            on = (p_rows[i] >> j) & 1
            x0 = ox + j * cell
            y0 = oy + i * cell
            fill = "#4f46e5" if on else "#f1f5f9"
            stroke = "#4338ca" if on else "#e2e8f0"
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="0.5"/>'
            )
            if n <= 12:
                parts.append(
                    f'<text x="{x0 + cell/2}" y="{y0 + cell/2 + 3}" text-anchor="middle" '
                    f'font-size="8" fill="{"#fff" if on else "#cbd5e1"}">{on}</text>'
                )

    parts.append("</svg>")
    return "\n".join(parts)


def render_bit_perm_wiring_svg(p_rows: tuple[int, ...], *, title: str = "Bit permutation wiring") -> str:
    """When P is a pure bit reordering, show input pin -> output pin wires."""
    pairs = bit_permutation_wiring(p_rows)
    if not pairs:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="40">'
            '<text x="8" y="24" font-size="11">P is a general linear mix (not a simple bit shuffle).</text></svg>'
        )
    n = len(p_rows)
    width, height = 280, max(100, 24 + n * 18)
    x_in, x_out = 50, 230
    top = 30
    step = (height - top - 16) / max(n - 1, 1)

    def y(b: int) -> float:
        return top + b * step

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<text x="{width/2}" y="16" text-anchor="middle" font-size="11" font-weight="600">{html.escape(title)}</text>',
    ]
    for in_b, out_b in pairs:
        y1, y2 = y(in_b), y(out_b)
        col = "#0ea5e9"
        mx = (x_in + x_out) / 2
        parts.append(
            f'<path d="M{x_in},{y1} C{mx},{y1} {mx},{y2} {x_out},{y2}" stroke="{col}" fill="none" stroke-width="1.5"/>'
        )
        parts.append(f'<text x="{x_in - 4}" y="{y1 + 3}" text-anchor="end" font-size="8">x{in_b}</text>')
        parts.append(f'<text x="{x_out + 4}" y="{y2 + 3}" font-size="8">y{out_b}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
