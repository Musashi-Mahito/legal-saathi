#!/usr/bin/env python
"""Render the 2-page solution document to PDF.

Uses ``fpdf2``, which is not an application dependency: run it as

    uv run --with fpdf2 python scripts/make_solution_pdf.py

Supported markdown subset: ``#``/``##`` headings, ``-`` bullets, pipe tables,
fenced code blocks (rendered monospace), ``**bold**`` (rendered bold), paragraphs.
ASCII only, because the built-in PDF fonts are Latin-1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "documentation" / "solution-doc-2page.md"
TARGET = ROOT / "documentation" / "legal-saathi-solution-doc.pdf"

PAGE_W = 210
PAGE_H = 297
MARGIN = 11
BODY_SIZE = 7.8
LINE_H = 3.45


def ascii_only(text: str) -> str:
    """Replace typographic characters the core fonts cannot render."""
    replacements = {
        "\u20b9": "Rs ",
        "\u2014": "-",
        "\u2013": "-",
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2192": "->",
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", "ignore").decode("ascii")


def split_bold(text: str) -> list[tuple[str, bool]]:
    """Split a line into (text, is_bold) runs."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    runs: list[tuple[str, bool]] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            runs.append((part[2:-2], True))
        else:
            runs.append((part, False))
    return runs


def parse_blocks(lines: list[str]) -> list[tuple[str, object]]:
    """Turn markdown lines into (block_type, payload) tuples."""
    blocks: list[tuple[str, object]] = []
    table: list[list[str]] = []
    code: list[str] = []

    def flush_table() -> None:
        nonlocal table
        if table:
            blocks.append(("table", table))
            table = []

    def flush_code() -> None:
        nonlocal code
        if code:
            blocks.append(("code", "\n".join(code)))
            code = []

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_table()
            if code:
                flush_code()
            else:
                code = []
                blocks.append(("code_start", None))
            continue
        if code:
            code.append(line)
            continue
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells if cell):
                continue
            table.append(cells)
            continue
        flush_table()
        blocks.append(("line", line))
    flush_table()
    flush_code()
    return [block for block in blocks if block[0] != "code_start"]


def render(source: Path, target: Path) -> int:
    """Write the PDF and return the page count."""
    from fpdf import FPDF

    text = ascii_only(source.read_text(encoding="utf-8"))
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=MARGIN + 4)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_title("Legal Saathi - solution document")
    pdf.add_page()

    usable = PAGE_W - 2 * MARGIN

    def row_height(cells: list[str], widths: list[int], size: float, bold: bool) -> float:
        """Height needed by the tallest cell in a row."""
        pdf.set_font("Helvetica", "B" if bold else "", size=size)
        tallest = 1
        for text, width in zip(cells, widths):
            try:
                lines = pdf.multi_cell(width, LINE_H, text, dry_run=True, output="LINES")
                tallest = max(tallest, len(lines))
            except TypeError:
                tallest = max(tallest, 1)
        return tallest * LINE_H

    def draw_table(rows: list[list[str]], widths: list[int]) -> None:
        """Draw a table with wrapping cells and a header row."""
        for index, row in enumerate(rows):
            header = index == 0
            cells = [ascii_only(cell) for cell in row[: len(widths)]]
            cells += [""] * (len(widths) - len(cells))
            size = 7.3
            height = row_height(cells, widths, size, header)
            if pdf.get_y() + height > PAGE_H - MARGIN - 6:
                pdf.add_page()
            x0, y0 = pdf.get_x(), pdf.get_y()
            pdf.set_font("Helvetica", "B" if header else "", size=size)
            pdf.set_fill_color(236, 238, 245) if header else pdf.set_fill_color(253, 253, 254)
            x = x0
            for text, width in zip(cells, widths):
                pdf.set_xy(x, y0)
                pdf.multi_cell(width, LINE_H, text, border=1, fill=True, new_x="RIGHT", new_y="TOP")
                x += width
            pdf.set_xy(x0, y0 + height)
        pdf.ln(1.8)

    for kind, payload in parse_blocks(text.split("\n")):
        if kind == "code":
            pdf.set_font("Courier", size=6.5)
            pdf.set_fill_color(244, 245, 248)
            for code_line in str(payload).split("\n"):
                if pdf.get_y() > PAGE_H - MARGIN - 8:
                    pdf.add_page()
                pdf.set_x(MARGIN + 2)
                pdf.cell(
                    usable - 4,
                    LINE_H,
                    code_line[:110],
                    new_x="LMARGIN",
                    new_y="NEXT",
                    fill=True,
                )
            pdf.ln(1.2)
            continue
        if kind == "table":
            rows: list[list[str]] = payload  # type: ignore[assignment]
            draw_table(rows, [56, 40, 92] if len(rows[0]) == 3 else [58, 130])
            continue

        line = str(payload)
        stripped = line.strip()
        if not stripped:
            pdf.ln(1.1)
            continue
        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", size=13)
            pdf.multi_cell(usable, 6.4, ascii_only(stripped[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.0)
            continue
        if stripped.startswith("## "):
            heading_height = 5.0 + 2 * LINE_H
            if pdf.get_y() > PAGE_H - MARGIN - heading_height - 8:
                pdf.add_page()
            else:
                pdf.ln(1.0)
            pdf.set_font("Helvetica", "B", size=9.6)
            pdf.multi_cell(usable, 5.0, ascii_only(stripped[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.6)
            continue
        if stripped.startswith("- "):
            size = BODY_SIZE
            pdf.set_font("Helvetica", size=size)
            pdf.set_x(MARGIN)
            for chunk, bold in split_bold(ascii_only("- " + stripped[2:])):
                pdf.set_font("Helvetica", "B" if bold else "", size=size)
                pdf.write(LINE_H, chunk)
            pdf.ln(LINE_H)
            pdf.set_x(MARGIN)
            continue
        pdf.set_font("Helvetica", size=BODY_SIZE)
        pdf.multi_cell(
            usable,
            LINE_H,
            ascii_only(stripped),
            new_x="LMARGIN",
            new_y="NEXT",
            markdown=True,
        )

    pdf.output(str(target))
    return pdf.page_no()


if __name__ == "__main__":
    pages = render(SOURCE, TARGET)
    print(f"wrote {TARGET.relative_to(ROOT)} ({pages} page(s))")
    sys.exit(0 if pages <= 2 else 1)
