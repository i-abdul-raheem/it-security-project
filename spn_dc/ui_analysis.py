from __future__ import annotations

import html
import math
from typing import Sequence

from spn_dc.sbox import SBox
from spn_dc.propagation import RoundSetState
from spn_dc.paths import DifferentialPath
from spn_dc.difference import DiffCell, cell_to_set
from spn_dc.linear import BinaryMatrix


def _svg_message(message: str, *, width: int = 640, height: int = 80) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<text x="16" y="42" font-family="system-ui,sans-serif" font-size="13" '
        f'fill="#475569">{html.escape(message)}</text></svg>'
    )


def render_ddt_heatmap_svg(
    ddt: Sequence[Sequence[int]],
    *,
    title: str = "Difference distribution table",
    selected_input: int | None = None,
) -> str:
    """Color-coded DDT counts. Rows are input differences and columns are outputs."""
    n = len(ddt)
    if n == 0 or any(len(row) != n for row in ddt):
        raise ValueError("DDT must be a non-empty square table")
    if selected_input is not None and not 0 <= selected_input < n:
        raise ValueError("selected input difference out of range")
    if n > 64:
        return _svg_message(f"DDT heatmap hidden for size {n}; use the numeric table.")
    cell = max(10, min(26, 520 // n))
    label = 46
    width = label + n * cell + 18
    height = label + n * cell + 35
    peak = max(max(int(v) for v in row) for row in ddt) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width / 2}" y="16" text-anchor="middle" font-size="12" '
        f'font-weight="700" fill="#1e293b">{html.escape(title)}</text>',
        f'<text x="{label + n * cell / 2}" y="30" text-anchor="middle" font-size="9" fill="#64748b">output difference Δy</text>',
    ]
    for col in range(n):
        parts.append(
            f'<text x="{label + col * cell + cell / 2}" y="{label - 4}" text-anchor="middle" '
            f'font-size="7" fill="#64748b">{col:X}</text>'
        )
    for row, values in enumerate(ddt):
        cy = label + row * cell + cell / 2
        parts.append(
            f'<text x="{label - 5}" y="{cy + 3}" text-anchor="end" font-size="7" fill="#64748b">{row:X}</text>'
        )
        for col, raw in enumerate(values):
            value = int(raw)
            intensity = value / peak
            lightness = int(96 - 49 * intensity)
            fill = f"hsl(245 72% {lightness}%)"
            text_fill = "#ffffff" if intensity >= 0.5 else "#334155"
            x = label + col * cell
            y = label + row * cell
            selected = selected_input == row
            stroke = "#f97316" if selected else "#e2e8f0"
            stroke_width = 2 if selected else 0.5
            opacity = 1.0 if selected_input is None or selected else 0.42
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity}">'
                f'<title>Δx={row:X}, Δy={col:X}, count={value}</title></rect>'
            )
            if n <= 20:
                parts.append(
                    f'<text x="{x + cell / 2}" y="{y + cell / 2 + 3}" text-anchor="middle" '
                    f'font-size="7" fill="{text_fill}">{value}</text>'
                )
    parts.append(
        f'<text x="12" y="{label + n * cell / 2}" font-size="9" fill="#64748b" '
        f'transform="rotate(-90 12,{label + n * cell / 2})">input difference Δx</text>'
    )
    if selected_input is not None:
        parts.append(
            f'<text x="{label + n * cell / 2}" y="{height - 4}" text-anchor="middle" '
            f'font-size="9" font-weight="700" fill="#ea580c">selected row: Δx = 0x{selected_input:X}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def render_sbox_differential_svg(
    sb: SBox,
    input_difference: int,
    *,
    title: str = "S-box differential transitions",
    max_nodes: int = 64,
) -> str:
    """Weighted Δx -> Δy diagram for one selected DDT row."""
    if not 0 <= input_difference < sb.n:
        raise ValueError("input difference out of range")
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    row = sb.ddt()[input_difference]
    all_outputs = [(dy, count) for dy, count in enumerate(row) if count]
    outputs = sorted(all_outputs, key=lambda item: (-item[1], item[0]))[:max_nodes]
    width = 720
    height = max(150, 65 + len(outputs) * 34)
    left_x, right_x = 120, 585
    source_y = height / 2
    peak = max(count for _, count in outputs)
    bits = sb.bits
    hex_w = max(1, (bits + 3) // 4)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="13" font-weight="700" '
        f'fill="#1e293b">{html.escape(title)}</text>',
        f'<circle cx="{left_x}" cy="{source_y}" r="30" fill="#e0e7ff" stroke="#4f46e5" stroke-width="2"/>',
        f'<text x="{left_x}" y="{source_y + 4}" text-anchor="middle" font-size="12" font-weight="700" '
        f'fill="#3730a3">Δx=0x{input_difference:0{hex_w}X}</text>',
    ]
    if len(all_outputs) > len(outputs):
        parts.append(
            f'<text x="{width - 8}" y="20" text-anchor="end" font-size="8" fill="#b45309">'
            f'showing strongest {len(outputs)} of {len(all_outputs)}</text>'
        )
    step = (height - 70) / max(1, len(outputs) - 1)
    for index, (dy, count) in enumerate(outputs):
        y = 45 + index * step if len(outputs) > 1 else source_y
        probability = count / sb.n
        stroke_width = 1.0 + 7.0 * count / peak
        parts.append(
            f'<path d="M{left_x + 30},{source_y} C300,{source_y} 400,{y} {right_x - 34},{y}" '
            f'fill="none" stroke="#7c3aed" stroke-width="{stroke_width:.2f}" opacity="0.65">'
            f'<title>count={count}, probability={probability:.6g}</title></path>'
        )
        parts.append(
            f'<rect x="{right_x - 34}" y="{y - 15}" width="68" height="30" rx="8" '
            f'fill="#faf5ff" stroke="#9333ea"/>'
        )
        parts.append(
            f'<text x="{right_x}" y="{y - 1}" text-anchor="middle" font-size="10" font-weight="700" '
            f'fill="#6b21a8">Δy=0x{dy:0{hex_w}X}</text>'
        )
        parts.append(
            f'<text x="{right_x}" y="{y + 10}" text-anchor="middle" font-size="8" '
            f'fill="#64748b">{count}/{sb.n} = {probability:.4g}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def ddt_transition_rows(sb: SBox, input_difference: int) -> list[dict[str, int | float | str]]:
    """Inspectable probability data used by the differential transition view."""
    if not 0 <= input_difference < sb.n:
        raise ValueError("input difference out of range")
    return [
        {
            "output difference": f"0x{dy:X}",
            "count": count,
            "probability": count / sb.n,
            "negative log2 probability": -math.log2(count / sb.n),
        }
        for dy, count in enumerate(sb.ddt()[input_difference])
        if count
    ]


def ddt_row_summary(sb: SBox, input_difference: int) -> dict[str, int | float]:
    """Statistics for the selected input-difference row."""
    if not 0 <= input_difference < sb.n:
        raise ValueError("input difference out of range")
    row = sb.ddt()[input_difference]
    strongest = max(row)
    return {
        "input_difference": input_difference,
        "feasible_outputs": sum(bool(count) for count in row),
        "strongest_count": strongest,
        "strongest_probability": strongest / sb.n,
    }


def ddt_summary(ddt: Sequence[Sequence[int]]) -> dict[str, int | float]:
    """Validate and summarize a DDT for display and regression checks."""
    n = len(ddt)
    if n == 0 or any(len(row) != n for row in ddt):
        raise ValueError("DDT must be a non-empty square table")
    if any(int(value) < 0 for row in ddt for value in row):
        raise ValueError("DDT counts cannot be negative")
    if any(sum(int(value) for value in row) != n for row in ddt):
        raise ValueError("every DDT row must sum to the S-box size")
    uniformity = max((int(value) for row in ddt[1:] for value in row), default=n)
    nonzero_transitions = sum(bool(value) for row in ddt[1:] for value in row)
    return {
        "size": n,
        "differential_uniformity": uniformity,
        "maximum_probability": uniformity / n,
        "nonzero_input_transitions": nonzero_transitions,
    }


def render_multiround_spn_svg(
    rounds: int, num_sboxes: int, sbox_bits: int, *, title: str = "Complete SPN"
) -> str:
    """Compact complete-cipher view: input, every S layer and P layer, then output."""
    if rounds < 1 or num_sboxes < 1 or sbox_bits < 1:
        raise ValueError("rounds, S-box count, and S-box width must be positive")
    round_w = max(170, num_sboxes * 52 + 55)
    width = max(720, 110 + rounds * round_w)
    height = max(240, 120 + num_sboxes * 38)
    mid_y = height / 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<defs><marker id="spn-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        '<path d="M0,0 L7,3 L0,6 Z" fill="#64748b"/></marker></defs>',
        f'<text x="{width / 2}" y="22" text-anchor="middle" font-size="14" font-weight="700" '
        f'fill="#1e293b">{html.escape(title)}</text>',
        f'<text x="18" y="{mid_y + 4}" font-size="11" fill="#334155">Input Δ ({num_sboxes * sbox_bits} bits)</text>',
    ]
    previous_x = 96
    for ri in range(rounds):
        base = 112 + ri * round_w
        sb_x = base + 12
        p_x = base + round_w - 50
        parts.append(
            f'<rect x="{base}" y="42" width="{round_w - 12}" height="{height - 76}" rx="12" '
            f'fill="#f8fafc" stroke="#cbd5e1"/><text x="{base + (round_w - 12) / 2}" y="59" '
            f'text-anchor="middle" font-size="11" font-weight="700" fill="#475569">Round {ri + 1}</text>'
        )
        for si in range(num_sboxes):
            y = 78 + si * 38
            parts.append(
                f'<rect x="{sb_x}" y="{y}" width="48" height="27" rx="6" fill="#e0e7ff" '
                f'stroke="#4f46e5"/><text x="{sb_x + 24}" y="{y + 18}" text-anchor="middle" '
                f'font-size="9" font-weight="700" fill="#3730a3">S{si} ({sbox_bits}b)</text>'
            )
        parts.append(
            f'<rect x="{p_x}" y="{mid_y - 35}" width="34" height="70" rx="7" fill="#f3e8ff" '
            f'stroke="#9333ea"/><text x="{p_x + 17}" y="{mid_y + 4}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="#6b21a8">P</text>'
        )
        parts.append(
            f'<line x1="{previous_x}" y1="{mid_y}" x2="{sb_x - 5}" y2="{mid_y}" stroke="#64748b" '
            f'marker-end="url(#spn-arrow)"/>'
        )
        parts.append(
            f'<line x1="{sb_x + 49}" y1="{mid_y}" x2="{p_x - 5}" y2="{mid_y}" stroke="#64748b" '
            f'marker-end="url(#spn-arrow)"/>'
        )
        previous_x = p_x + 35
    parts.append(
        f'<line x1="{previous_x}" y1="{mid_y}" x2="{width - 65}" y2="{mid_y}" stroke="#64748b" '
        f'marker-end="url(#spn-arrow)"/><text x="{width - 58}" y="{mid_y + 4}" font-size="11" fill="#334155">Output Δ</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render_activity_matrix_svg(
    trail: Sequence[RoundSetState], *, title: str = "S-box activity across rounds"
) -> str:
    """Activity grid: inactive, definitely active, or uncertain for every round/layer/slice."""
    if not trail:
        return _svg_message("No propagation trail available for an activity diagram.")
    num_sboxes = len(trail[0].before_sbox)
    if any(len(layer) != num_sboxes for state in trail for layer in (state.before_sbox, state.after_sbox, state.after_p)):
        raise ValueError("inconsistent slice counts in trail")
    cell, left, top = 34, 118, 48
    columns = len(trail) * 3
    width = left + columns * cell + 18
    height = top + num_sboxes * cell + 46
    layers = (("in", "before_sbox"), ("S", "after_sbox"), ("P", "after_p"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width / 2}" y="18" text-anchor="middle" font-size="13" font-weight="700" '
        f'fill="#1e293b">{html.escape(title)}</text>',
    ]
    for si in range(num_sboxes):
        parts.append(f'<text x="{left - 8}" y="{top + si * cell + 21}" text-anchor="end" font-size="9">S-box {si}</text>')
    for ri, state in enumerate(trail):
        for li, (label, attr) in enumerate(layers):
            col = ri * 3 + li
            x = left + col * cell
            parts.append(f'<text x="{x + cell / 2}" y="{top - 5}" text-anchor="middle" font-size="8">R{ri + 1} {label}</text>')
            for si, values in enumerate(getattr(state, attr)):
                if values == frozenset({0}):
                    fill, symbol, meaning = "#cbd5e1", "0", "inactive"
                elif 0 not in values:
                    fill, symbol, meaning = "#22c55e", "●", "active"
                else:
                    fill, symbol, meaning = "#f59e0b", "?", "possibly active"
                y = top + si * cell
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="#fff">'
                    f'<title>Round {ri + 1} {attr}, S-box {si}: {meaning}</title></rect>'
                    f'<text x="{x + cell / 2}" y="{y + 22}" text-anchor="middle" font-size="11" fill="#fff">{symbol}</text>'
                )
    parts.append(f'<text x="{left}" y="{height - 14}" font-size="9" fill="#64748b">gray: inactive · green: active · amber: may be active</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_concrete_sbox_pair_svg(sb: SBox, x: int, input_difference: int) -> str:
    """Show the two concrete S-box evaluations whose XORs form one DDT observation."""
    if not 0 <= x < sb.n or not 0 <= input_difference < sb.n:
        raise ValueError("value out of S-box range")
    xp = x ^ input_difference
    y, yp = sb.image(x), sb.image(xp)
    dy = y ^ yp
    width, height = 720, 190
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<text x="360" y="20" text-anchor="middle" font-size="13" font-weight="700">Concrete pair behind one DDT count</text>',
    ]
    for row, (label, iv, ov, color) in enumerate((("first", x, y, "#4f46e5"), ("paired", xp, yp, "#9333ea"))):
        cy = 62 + row * 62
        parts.extend([
            f'<text x="25" y="{cy + 4}" font-size="10" fill="#64748b">{label}</text>',
            f'<rect x="100" y="{cy - 18}" width="92" height="36" rx="8" fill="#f8fafc" stroke="{color}"/>',
            f'<text x="146" y="{cy + 4}" text-anchor="middle" font-size="12">x = 0x{iv:X}</text>',
            f'<line x1="192" y1="{cy}" x2="290" y2="{cy}" stroke="{color}" stroke-width="2"/>',
            f'<rect x="290" y="{cy - 23}" width="100" height="46" rx="9" fill="#fff" stroke="{color}" stroke-width="2"/>',
            f'<text x="340" y="{cy + 4}" text-anchor="middle" font-size="12" font-weight="700">S-box</text>',
            f'<line x1="390" y1="{cy}" x2="488" y2="{cy}" stroke="{color}" stroke-width="2"/>',
            f'<rect x="488" y="{cy - 18}" width="92" height="36" rx="8" fill="#f8fafc" stroke="{color}"/>',
            f'<text x="534" y="{cy + 4}" text-anchor="middle" font-size="12">S(x) = 0x{ov:X}</text>',
        ])
    parts.extend([
        f'<text x="620" y="76" font-size="11" fill="#334155">Δx = 0x{x ^ xp:X}</text>',
        f'<text x="620" y="138" font-size="11" fill="#334155">Δy = 0x{dy:X}</text>',
        "</svg>",
    ])
    return "\n".join(parts)


def _tuple_hex(values: Sequence[int]) -> str:
    return " ".join(f"{value:X}" for value in values)


def render_differential_trail_svg(path: DifferentialPath) -> str:
    """Connected before-S -> after-S -> after-P view of one concrete trail."""
    rounds = len(path.trace)
    if not rounds:
        return _svg_message("Selected trail has no rounds.")
    step_w = 205
    width = max(720, rounds * step_w + 70)
    height = 230
    y = 112
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<defs><marker id="trail-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        '<path d="M0,0 L7,3 L0,6 Z" fill="#64748b"/></marker></defs>',
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="13" font-weight="700">'
        f'Trail {path.path_id} · probability {path.probability:.6g}</text>',
    ]
    previous_x: float | None = None
    for ri, (before, after_sbox, after_p) in enumerate(path.trace):
        base = 30 + ri * step_w
        parts.append(f'<text x="{base + 87}" y="49" text-anchor="middle" font-size="10" font-weight="700">Round {ri + 1}</text>')
        boxes = (("before S", before, "#e0e7ff", "#4f46e5"), ("after S", after_sbox, "#f3e8ff", "#9333ea"), ("after P", after_p, "#dcfce7", "#16a34a"))
        for bi, (label, values, fill, stroke) in enumerate(boxes):
            x = base + bi * 58
            parts.append(
                f'<rect x="{x}" y="{y - 31}" width="50" height="62" rx="8" fill="{fill}" stroke="{stroke}"/>'
                f'<text x="{x + 25}" y="{y - 12}" text-anchor="middle" font-size="8" fill="#475569">{label}</text>'
                f'<text x="{x + 25}" y="{y + 8}" text-anchor="middle" font-size="11" font-weight="700">{html.escape(_tuple_hex(values))}</text>'
            )
            if bi:
                parts.append(f'<line x1="{x - 8}" y1="{y}" x2="{x}" y2="{y}" stroke="#64748b" marker-end="url(#trail-arrow)"/>')
        if previous_x is not None:
            parts.append(f'<path d="M{previous_x},{y + 34} C{previous_x + 20},{y + 66} {base - 20},{y + 66} {base},{y + 34}" fill="none" stroke="#64748b" marker-end="url(#trail-arrow)"/>')
        previous_x = base + 166
    parts.append('<text x="30" y="205" font-size="9" fill="#64748b">Values are S-box slices in hexadecimal; curved links feed the next round.</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_path_probability_svg(
    paths: Sequence[DifferentialPath], *, max_bars: int = 30
) -> str:
    """Rank the strongest stored trails in a horizontal probability chart."""
    if not paths:
        return _svg_message("No paths match the current filter.")
    ranked = sorted(paths, key=lambda p: (-p.probability, p.path_id))[:max_bars]
    width = 760
    row_h = 24
    height = 62 + len(ranked) * row_h
    left, chart_w = 118, 570
    peak = ranked[0].probability or 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<text x="380" y="18" text-anchor="middle" font-size="13" font-weight="700">Strongest differential trails</text>',
        f'<text x="{left}" y="37" font-size="9" fill="#64748b">bar length relative to strongest trail</text>',
    ]
    for index, path in enumerate(ranked):
        y = 47 + index * row_h
        bar_w = max(2.0, chart_w * path.probability / peak)
        parts.append(f'<text x="{left - 8}" y="{y + 12}" text-anchor="end" font-size="9">id {path.path_id}</text>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{bar_w}" height="16" rx="3" fill="#6366f1">'
            f'<title>path {path.path_id}: {path.probability:.12g}</title></rect>'
        )
        parts.append(f'<text x="{min(width - 65, left + bar_w + 5)}" y="{y + 12}" font-size="8" fill="#475569">{path.probability:.4g}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_path_search_tree_svg(
    paths: Sequence[DifferentialPath], *, max_paths: int = 80
) -> str:
    """Bounded prefix tree of concrete after-S choices across rounds."""
    if not paths:
        return _svg_message("No paths available for a search tree.")
    sample = sorted(paths, key=lambda p: (-p.probability, p.path_id))[:max_paths]
    depth = max(len(path.trace) for path in sample)
    levels: list[list[tuple[tuple[int, ...], ...]]] = [[()]]
    for level in range(depth):
        prefixes = {
            tuple(step[1] for step in path.trace[: level + 1])
            for path in sample
            if len(path.trace) > level
        }
        levels.append(sorted(prefixes))
    max_level = max(len(level) for level in levels)
    width = max(720, 170 * (depth + 1))
    height = max(180, 36 + max_level * 34)
    coords: dict[tuple[tuple[int, ...], ...], tuple[float, float]] = {}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<text x="360" y="18" text-anchor="middle" font-size="13" font-weight="700">Path-search prefix tree</text>',
    ]
    for li, level in enumerate(levels):
        x = 65 + li * (width - 130) / max(1, depth)
        spacing = (height - 48) / max(1, len(level))
        for ni, prefix in enumerate(level):
            y = 34 + (ni + 0.5) * spacing
            coords[prefix] = (x, y)
            if prefix:
                parent = prefix[:-1]
                px, py = coords[parent]
                parts.append(f'<line x1="{px + 30}" y1="{py}" x2="{x - 30}" y2="{y}" stroke="#c4b5fd"/>')
                label = _tuple_hex(prefix[-1])
            else:
                label = "input"
            parts.append(
                f'<rect x="{x - 30}" y="{y - 11}" width="60" height="22" rx="6" fill="#f5f3ff" stroke="#7c3aed"/>'
                f'<text x="{x}" y="{y + 3}" text-anchor="middle" font-size="8">{html.escape(label)}</text>'
            )
        parts.append(f'<text x="{x}" y="{height - 5}" text-anchor="middle" font-size="8" fill="#64748b">{"start" if li == 0 else f"round {li}"}</text>')
    if len(paths) > max_paths:
        parts.append(f'<text x="{width - 8}" y="18" text-anchor="end" font-size="8" fill="#b45309">showing strongest {max_paths} of {len(paths)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def constraint_conflict_indices(
    input_cells: Sequence[DiffCell], equality_groups: Sequence[Sequence[int]], n_values: int
) -> frozenset[int]:
    """Return positions belonging to equality groups with an empty common domain."""
    domains = [cell_to_set(cell, n_values) for cell in input_cells]
    bad: set[int] = set()
    for group in equality_groups:
        valid = [index for index in group if 0 <= index < len(domains)]
        if len(valid) != len(group) or not valid:
            bad.update(index for index in valid)
            continue
        common = set(domains[valid[0]])
        for index in valid[1:]:
            common.intersection_update(domains[index])
        if not common:
            bad.update(valid)
    return frozenset(bad)


def render_constraint_graph_svg(
    input_cells: Sequence[DiffCell],
    output_fixes: dict[int, int],
    equality_groups: Sequence[Sequence[int]],
    *,
    n_values: int,
) -> str:
    """Graph fixed/abstract/any inputs, round-one output fixes, and equality links."""
    if not input_cells:
        return _svg_message("No cipher inputs are configured.")
    count = len(input_cells)
    width = max(720, 90 + count * 105)
    height = 245
    bad = constraint_conflict_indices(input_cells, equality_groups, n_values)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="13" font-weight="700">Constraint relationships</text>',
    ]
    xs = [65 + i * (width - 130) / max(1, count - 1) for i in range(count)]
    for gi, group in enumerate(equality_groups):
        valid = [index for index in group if 0 <= index < count]
        if len(valid) < 2:
            continue
        y = 60 - min(gi, 2) * 11
        color = "#dc2626" if any(index in bad for index in valid) else "#0ea5e9"
        parts.append(f'<path d="M{xs[valid[0]]},92 V{y} H{xs[valid[-1]]} V92" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{sum(xs[i] for i in valid) / len(valid)}" y="{y - 4}" text-anchor="middle" font-size="8" fill="{color}">equal group {gi + 1}</text>')
    for index, cell in enumerate(input_cells):
        x = xs[index]
        domain = cell_to_set(cell, n_values)
        if len(domain) == n_values:
            label, fill = "ANY", "#dcfce7"
        elif len(domain) == n_values - 1 and 0 not in domain:
            label, fill = "≠ 0", "#fef3c7"
        elif len(domain) == 1:
            label, fill = f"0x{next(iter(domain)):X}", "#e0e7ff"
        else:
            label, fill = f"{len(domain)} opts", "#f3e8ff"
        stroke = "#dc2626" if index in bad else "#4f46e5"
        sw = 3 if index in bad else 1.5
        parts.append(f'<rect x="{x - 38}" y="92" width="76" height="48" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(f'<text x="{x}" y="108" text-anchor="middle" font-size="8" fill="#64748b">input S{index}</text>')
        parts.append(f'<text x="{x}" y="128" text-anchor="middle" font-size="12" font-weight="700">{html.escape(label)}</text>')
        if index in output_fixes:
            parts.append(f'<line x1="{x}" y1="140" x2="{x}" y2="168" stroke="#9333ea"/>')
            parts.append(f'<rect x="{x - 38}" y="168" width="76" height="38" rx="8" fill="#faf5ff" stroke="#9333ea"/>')
            parts.append(f'<text x="{x}" y="183" text-anchor="middle" font-size="8" fill="#64748b">after S{index}</text>')
            parts.append(f'<text x="{x}" y="198" text-anchor="middle" font-size="11" font-weight="700">0x{output_fixes[index]:X}</text>')
    status = "conflict: empty equality intersection" if bad else "constraints structurally compatible"
    color = "#dc2626" if bad else "#15803d"
    parts.append(f'<text x="{width / 2}" y="230" text-anchor="middle" font-size="10" font-weight="700" fill="{color}">{status}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_backward_differential_svg(
    sb: SBox, output_difference: int, *, max_nodes: int = 64
) -> str:
    """Inverse-DDT view: fixed Δy and all feasible Δx values with weights."""
    if not 0 <= output_difference < sb.n:
        raise ValueError("output difference out of range")
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    ddt = sb.ddt()
    all_inputs = [(dx, ddt[dx][output_difference]) for dx in range(sb.n) if ddt[dx][output_difference]]
    inputs = sorted(all_inputs, key=lambda item: (-item[1], item[0]))[:max_nodes]
    width = 720
    height = max(150, 65 + len(inputs) * 34)
    left_x, right_x = 135, 595
    target_y = height / 2
    peak = max(count for _, count in inputs)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<text x="360" y="20" text-anchor="middle" font-size="13" font-weight="700">Backward propagation through inverse DDT</text>',
        f'<rect x="{right_x - 42}" y="{target_y - 20}" width="84" height="40" rx="9" fill="#fee2e2" stroke="#dc2626"/>',
        f'<text x="{right_x}" y="{target_y + 4}" text-anchor="middle" font-size="11" font-weight="700">Δy=0x{output_difference:X}</text>',
    ]
    if len(all_inputs) > len(inputs):
        parts.append(
            f'<text x="{width - 8}" y="20" text-anchor="end" font-size="8" fill="#b45309">'
            f'showing strongest {len(inputs)} of {len(all_inputs)}</text>'
        )
    step = (height - 70) / max(1, len(inputs) - 1)
    for index, (dx, count) in enumerate(inputs):
        y = 45 + index * step if len(inputs) > 1 else target_y
        parts.append(f'<rect x="{left_x - 34}" y="{y - 14}" width="68" height="28" rx="7" fill="#e0e7ff" stroke="#4f46e5"/>')
        parts.append(f'<text x="{left_x}" y="{y + 4}" text-anchor="middle" font-size="10" font-weight="700">Δx=0x{dx:X}</text>')
        parts.append(
            f'<path d="M{left_x + 34},{y} C310,{y} 420,{target_y} {right_x - 42},{target_y}" '
            f'fill="none" stroke="#6366f1" stroke-width="{1 + 6 * count / peak:.2f}" opacity="0.6">'
            f'<title>count={count}, probability={count / sb.n:.6g}</title></path>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def render_cipher_configuration_svg(
    *, rounds: int, num_sboxes: int, sbox_bits: int, p_rows: tuple[int, ...]
) -> str:
    """At-a-glance configuration card for the currently initialized cipher."""
    dim = num_sboxes * sbox_bits
    if rounds < 1 or num_sboxes < 1 or sbox_bits < 1 or len(p_rows) != dim:
        raise ValueError("inconsistent cipher configuration")
    pure = all(row and not row & (row - 1) for row in p_rows) and len(set(p_rows)) == dim
    cards = (
        ("Rounds", str(rounds), "#e0e7ff", "#4338ca"),
        ("Block", f"{dim} bits", "#dcfce7", "#15803d"),
        ("S-box layer", f"{num_sboxes} × {sbox_bits}-bit", "#fef3c7", "#b45309"),
        ("P-layer", "bit shuffle" if pure else "GF(2) linear mix", "#f3e8ff", "#7e22ce"),
    )
    width, height = 760, 135
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        '<text x="380" y="18" text-anchor="middle" font-size="13" font-weight="700">Cipher configuration</text>',
    ]
    for index, (label, value, fill, color) in enumerate(cards):
        x = 18 + index * 184
        parts.append(f'<rect x="{x}" y="35" width="170" height="78" rx="12" fill="{fill}" stroke="{color}"/>')
        parts.append(f'<text x="{x + 85}" y="60" text-anchor="middle" font-size="10" fill="#64748b">{label}</text>')
        parts.append(f'<text x="{x + 85}" y="87" text-anchor="middle" font-size="15" font-weight="700" fill="{color}">{html.escape(value)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def p_layer_diffusion_profile(
    p_rows: tuple[int, ...], num_sboxes: int, sbox_bits: int
) -> tuple[list[dict[str, int]], int | None]:
    """Single-active-slice diffusion plus exact bundle branch number for blocks up to 16 bits."""
    dim = num_sboxes * sbox_bits
    if len(p_rows) != dim:
        raise ValueError("P-layer dimension mismatch")
    matrix = BinaryMatrix(dim, p_rows)
    mask = (1 << sbox_bits) - 1

    def weight(value: int) -> int:
        return sum(bool((value >> (index * sbox_bits)) & mask) for index in range(num_sboxes))

    rows: list[dict[str, int]] = []
    for source in range(num_sboxes):
        output_weights = []
        for dx in range(1, 1 << sbox_bits):
            output_weights.append(weight(matrix.apply(dx << (source * sbox_bits))))
        rows.append(
            {
                "input_sbox": source,
                "minimum_active_outputs": min(output_weights),
                "maximum_active_outputs": max(output_weights),
            }
        )
    branch: int | None = None
    if dim <= 16:
        branch = min(weight(value) + weight(matrix.apply(value)) for value in range(1, 1 << dim))
    return rows, branch


def render_p_diffusion_svg(
    p_rows: tuple[int, ...], num_sboxes: int, sbox_bits: int
) -> str:
    """Visualize output activity caused by each single active input bundle."""
    profile, branch = p_layer_diffusion_profile(p_rows, num_sboxes, sbox_bits)
    width = max(720, 150 + num_sboxes * 92)
    height = 160 + num_sboxes * 34
    left, top = 155, 55
    cell_w, cell_h = 82, 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="font-family:system-ui,sans-serif">',
        f'<text x="{width / 2}" y="18" text-anchor="middle" font-size="13" font-weight="700">P-layer bundle diffusion</text>',
    ]
    for out_index in range(num_sboxes):
        parts.append(f'<text x="{left + out_index * cell_w + cell_w / 2}" y="{top - 7}" text-anchor="middle" font-size="8">activity count</text>')
    for row_index, row in enumerate(profile):
        y = top + row_index * 34
        parts.append(f'<text x="{left - 10}" y="{y + 20}" text-anchor="end" font-size="9">only input S{row_index} active</text>')
        span = row["maximum_active_outputs"] - row["minimum_active_outputs"]
        fill = "#22c55e" if row["minimum_active_outputs"] > 1 else "#f59e0b"
        bar_w = max(cell_w, row["maximum_active_outputs"] * cell_w)
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w}" height="{cell_h}" rx="6" fill="{fill}" opacity="0.75"/>')
        text = f'{row["minimum_active_outputs"]}' if not span else f'{row["minimum_active_outputs"]}–{row["maximum_active_outputs"]}'
        parts.append(f'<text x="{left + bar_w / 2}" y="{y + 20}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">{text} active output slice(s)</text>')
    note = f"Exact bundle branch number: {branch}" if branch is not None else "Exact branch number skipped above 16 block bits; bars show single-slice diffusion."
    parts.append(f'<text x="{width / 2}" y="{height - 24}" text-anchor="middle" font-size="10" font-weight="700" fill="#475569">{html.escape(note)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
