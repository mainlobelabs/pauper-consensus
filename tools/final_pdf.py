"""Render paper/final.md (the merged final paper) to a journal-style PDF.

Thin wrapper over paper_pdf.py: points the source at final.md, sets the
running-header string to the final-draft label, and defaults the output to
paper/final.pdf. Reuses paper_pdf's title-block parsing, figure injection,
stylesheet, and weasyprint call verbatim.

Usage:
    uv run --with markdown --with weasyprint tools/final_pdf.py [out.pdf]
"""
import os
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS))
os.environ.setdefault("PAPER_HEADER", "Pauper Consensus, final draft, 2026-08-31")

import paper_pdf  # noqa: E402

paper_pdf.SRC = paper_pdf.ROOT / "paper" / "final.md"
if len(sys.argv) <= 1:
    paper_pdf.OUT = paper_pdf.ROOT / "paper" / "final.pdf"

paper_pdf.main()
