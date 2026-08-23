from __future__ import annotations

import html
from dataclasses import dataclass
from typing import FrozenSet, Sequence

from spn_dc.propagation import RoundSetState


@dataclass(frozen=True)
class PropFrame:
    """One animation step: one layer in one round."""

    round_index: int  # 1-based
    layer: str  # short id: before_sbox | after_sbox | after_p
    layer_title: str
    slices: tuple[FrozenSet[int], ...]


_LAYER_TITLES = {
    "before_sbox": "Before S-box layer",
    "after_sbox": "After S-box layer (DDT)",
    "after_p": "After P-layer (linear mix)",
}


def frames_from_trail(trail: Sequence[RoundSetState]) -> tuple[PropFrame, ...]:
    out: list[PropFrame] = []
    for ri, st in enumerate(trail):
        r = ri + 1
        out.append(PropFrame(r, "before_sbox", _LAYER_TITLES["before_sbox"], st.before_sbox))
        out.append(PropFrame(r, "after_sbox", _LAYER_TITLES["after_sbox"], st.after_sbox))
        out.append(PropFrame(r, "after_p", _LAYER_TITLES["after_p"], st.after_p))
    return tuple(out)


def frames_from_path_trace(
    trace: Sequence[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]],
) -> tuple[PropFrame, ...]:
    """Concrete trail from path enumeration (one value per S-box per layer)."""
    out: list[PropFrame] = []
    for ri, (b, a, z) in enumerate(trace):
        r = ri + 1
        out.append(
            PropFrame(r, "before_sbox", _LAYER_TITLES["before_sbox"], tuple(frozenset({x}) for x in b))
        )
        out.append(
            PropFrame(r, "after_sbox", _LAYER_TITLES["after_sbox"], tuple(frozenset({x}) for x in a))
        )
        out.append(
            PropFrame(r, "after_p", _LAYER_TITLES["after_p"], tuple(frozenset({x}) for x in z))
        )
    return tuple(out)


def _fmt_val(v: int, bits: int) -> str:
    w = max(1, (bits + 3) // 4)
    return f"0x{v:0{w}X}"


def _cell_content(s: FrozenSet[int], bits: int) -> tuple[str, str, str]:
    """Return (main label, meta label, css class)."""
    n = 1 << bits
    if not s:
        return "∅", "impossible", "cell-empty"
    if len(s) == 1:
        (v,) = tuple(s)
        return _fmt_val(v, bits), "fixed", "cell-fixed"
    if len(s) == n:
        return "ANY", f"{n} values", "cell-any"
    if len(s) == n - 1 and 0 not in s:
        return "≠0", f"{len(s)} values", "cell-abstract"
    preview = ", ".join(_fmt_val(v, bits) for v in sorted(s)[:4])
    if len(s) > 4:
        preview += ", …"
    return f"{len(s)} opts", preview, "cell-set"


def _cell_color(v: int, bits: int) -> str:
    if bits <= 0:
        return "#6366f1"
    t = v / max(1, (1 << bits) - 1)
    r = int(99 + 120 * t)
    g = int(102 + 40 * (1 - t))
    b = int(241 - 160 * t)
    return f"rgb({r},{g},{b})"


def propagation_viz_css() -> str:
    return """
<style>
.prop-viz-wrap {
  font-family: system-ui, -apple-system, sans-serif;
  padding: 0.5rem 0 1rem 0;
}
.prop-viz-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.prop-viz-badge {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  font-weight: 700;
  font-size: 0.85rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
}
.prop-viz-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: #1e1b4b;
}
.prop-viz-sub {
  color: #64748b;
  font-size: 0.85rem;
}
.prop-sbox-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  margin: 0.5rem 0;
}
.prop-sbox-cell {
  min-width: 5.5rem;
  border-radius: 12px;
  padding: 0.65rem 0.5rem;
  text-align: center;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  transition: transform 0.35s ease, box-shadow 0.35s ease, border-color 0.35s ease;
}
.prop-sbox-cell.active {
  border-color: #6366f1;
  animation: prop-pulse 1.1s ease-in-out infinite;
}
@keyframes prop-pulse {
  0%, 100% { transform: scale(1); box-shadow: 0 4px 14px rgba(99,102,241,0.25); }
  50% { transform: scale(1.06); box-shadow: 0 8px 24px rgba(99,102,241,0.45); }
}
.prop-sbox-idx {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
  margin-bottom: 0.25rem;
}
.prop-sbox-val {
  font-size: 1.1rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}
.prop-sbox-meta {
  font-size: 0.68rem;
  color: #64748b;
  margin-top: 0.2rem;
  line-height: 1.2;
  word-break: break-all;
}
.cell-fixed .prop-sbox-val { color: #1d4ed8; }
.cell-set .prop-sbox-val { color: #7c3aed; }
.cell-any .prop-sbox-val { color: #059669; }
.cell-abstract .prop-sbox-val { color: #d97706; }
.cell-empty .prop-sbox-val { color: #dc2626; }
.prop-flow-arrow {
  text-align: center;
  color: #6366f1;
  font-size: 1.4rem;
  line-height: 1;
  margin: 0.35rem 0;
  opacity: 0.85;
}
.prop-flow-arrow.active {
  animation: prop-bounce 0.9s ease-in-out infinite;
}
@keyframes prop-bounce {
  0%, 100% { transform: translateY(0); opacity: 0.7; }
  50% { transform: translateY(5px); opacity: 1; }
}
.prop-round-divider {
  text-align: center;
  margin: 1.25rem 0 0.75rem 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.prop-timeline {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}
.prop-tick {
  height: 6px;
  flex: 1;
  min-width: 12px;
  border-radius: 3px;
  background: #e2e8f0;
  transition: background 0.2s;
}
.prop-tick.done { background: #a5b4fc; }
.prop-tick.current { background: #4f46e5; }
</style>
"""


def render_propagation_frame_html(
    frame: PropFrame,
    *,
    sbox_bits: int,
    frame_index: int,
    total_frames: int,
    show_timeline: bool = True,
    pulse: bool = True,
) -> str:
    parts = [propagation_viz_css()]
    parts.append('<div class="prop-viz-wrap">')
    parts.append('<div class="prop-viz-header">')
    parts.append(f'<span class="prop-viz-badge">Round {frame.round_index}</span>')
    parts.append(
        f'<div><div class="prop-viz-title">{html.escape(frame.layer_title)}</div>'
        f'<div class="prop-viz-sub">Step {frame_index + 1} of {total_frames}</div></div>'
    )
    parts.append("</div>")

    active_cls = " active" if pulse else ""
    parts.append('<div class="prop-sbox-row">')
    for i, s in enumerate(frame.slices):
        label, meta, css = _cell_content(s, sbox_bits)
        style = ""
        if len(s) == 1:
            (v,) = tuple(s)
            c = _cell_color(v, sbox_bits)
            style = f' style="border-color:{c}; background: linear-gradient(160deg, {c}22, #fff);"'
        parts.append(
            f'<div class="prop-sbox-cell {css}{active_cls}"{style}>'
            f'<div class="prop-sbox-idx">S-box {i}</div>'
            f'<div class="prop-sbox-val">{html.escape(label)}</div>'
            f'<div class="prop-sbox-meta">{html.escape(meta)}</div>'
            f"</div>"
        )
    parts.append("</div>")

    layer_flow = {
        "before_sbox": ("↓", "into S-box substitution"),
        "after_sbox": ("↓", "into P-layer (binary matrix)"),
        "after_p": ("⇢", "feeds next round"),
    }
    arrow, hint = layer_flow.get(frame.layer, ("↓", ""))
    arrow_cls = "prop-flow-arrow active" if pulse else "prop-flow-arrow"
    parts.append(f'<div class="{arrow_cls}">{html.escape(arrow)}</div>')
    if hint:
        parts.append(f'<div class="prop-viz-sub" style="text-align:center">{html.escape(hint)}</div>')

    if show_timeline:
        parts.append('<div class="prop-timeline">')
        for t in range(total_frames):
            cls = "prop-tick"
            if t < frame_index:
                cls += " done"
            elif t == frame_index:
                cls += " current"
            parts.append(f'<div class="{cls}"></div>')
        parts.append("</div>")

    parts.append("</div>")
    return "\n".join(parts)


def render_propagation_overview_html(
    frames: Sequence[PropFrame],
    *,
    sbox_bits: int,
    current_index: int,
) -> str:
    """Mini strip: all steps collapsed to timeline labels."""
    parts = [propagation_viz_css(), '<div class="prop-viz-wrap">', '<div class="prop-timeline">']
    for t, fr in enumerate(frames):
        cls = "prop-tick"
        if t < current_index:
            cls += " done"
        elif t == current_index:
            cls += " current"
        parts.append(
            f'<div class="{cls}" title="R{fr.round_index} {html.escape(fr.layer_title)}"></div>'
        )
    parts.append("</div></div>")
    return "\n".join(parts)
