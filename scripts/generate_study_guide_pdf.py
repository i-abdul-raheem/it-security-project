#!/usr/bin/env python3
"""Build STUDY_GUIDE.pdf from STUDY_GUIDE.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "STUDY_GUIDE.md"
PDF_PATH = ROOT / "STUDY_GUIDE.pdf"

_REPLACEMENTS = {
    "Δ": "Delta",
    "⊕": "XOR",
    "→": "->",
    "…": "...",
    "–": "-",
    "—": "-",
    "≥": ">=",
    "×": "x",
    "·": ".",
    "“": '"',
    "”": '"',
    "’": "'",
}


def _sanitize(text: str) -> str:
    for a, b in _REPLACEMENTS.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


class StudyGuidePDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")


def _strip_md_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return _sanitize(text.strip())


def _mc(
    pdf: FPDF,
    height: float,
    text: str,
    *,
    family: str = "Helvetica",
    style: str = "",
    size: int = 10,
) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(family, style, size)
    if text:
        pdf.multi_cell(pdf.epw, height, text)


def build_pdf(md_text: str, out_path: Path) -> None:
    pdf = StudyGuidePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    in_code = False
    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            pdf.set_text_color(40, 40, 40)
            _mc(pdf, 4.5, _sanitize(line), family="Courier", size=9)
            pdf.set_text_color(0, 0, 0)
            continue

        if not line.strip() or re.match(r"^-{3,}$", line.strip()):
            pdf.ln(3)
            continue

        if line.startswith("# "):
            pdf.ln(2)
            pdf.set_text_color(30, 30, 120)
            _mc(pdf, 9, _strip_md_inline(line[2:]), style="B", size=16)
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("## "):
            pdf.ln(4)
            pdf.set_text_color(50, 50, 50)
            _mc(pdf, 8, _strip_md_inline(line[3:]), style="B", size=13)
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("### "):
            pdf.ln(3)
            _mc(pdf, 7, _strip_md_inline(line[4:]), style="B", size=11)
            continue

        if line.startswith("|") and "|" in line[1:]:
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            _mc(pdf, 5, _strip_md_inline("  |  ".join(cells)), size=9)
            continue

        if line.startswith("- ") or line.startswith("* "):
            _mc(pdf, 5, _strip_md_inline("  - " + line[2:]))
            continue

        if re.match(r"^\d+\.\s", line):
            _mc(pdf, 5, _strip_md_inline("  " + line))
            continue

        if line.startswith("**") and line.endswith("**"):
            _mc(pdf, 5, _strip_md_inline(line), style="B")
            continue

        _mc(pdf, 5, _strip_md_inline(line))

    pdf.output(str(out_path))


def main() -> int:
    if not MD_PATH.is_file():
        print(f"Missing {MD_PATH}", file=sys.stderr)
        return 1
    text = MD_PATH.read_text(encoding="utf-8")
    build_pdf(text, PDF_PATH)
    print(f"Wrote {PDF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
