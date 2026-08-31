"""Render paper/draft-v4.md to a journal-style PDF via weasyprint.

Usage:
    uv run --with markdown --with weasyprint tools/paper_pdf.py [out.pdf]

Strips the DRAFT NOTES html comment, builds a centered title block,
and applies the paper stylesheet.
"""
import os
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "paper" / "draft-v4.md"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper" / "draft-v4.pdf"
HEADER = os.environ.get("PAPER_HEADER", "The Flip Was in the Instrument, v5.2, 2026-08-31")

CSS = """
@page {
  size: A4;
  margin: 23mm 20mm 20mm 20mm;
  @bottom-center {
    content: counter(page);
    font-family: "Liberation Serif", serif;
    font-size: 8.5pt;
    color: #777;
  }
  @top-left {
    content: "/*HEADER*/";
    font-family: "Liberation Serif", serif;
    font-size: 8pt;
    color: #999;
  }
}
@page :first {
  @top-left { content: none; }
}
html { font-size: 10.5pt; }
body {
  font-family: "Liberation Serif", "Noto Serif", serif;
  font-size: 10.5pt;
  line-height: 1.52;
  color: #141414;
  text-align: justify;
  hyphens: auto;
}
.titleblock { margin-bottom: 0.4em; }
.title {
  text-align: center;
  font-size: 16.5pt;
  line-height: 1.32;
  font-weight: bold;
  margin: 0.2em 1.5em 0.7em;
  text-align: center;
}
.subtitle {
  text-align: center;
  font-size: 10.5pt;
  font-style: italic;
  color: #333;
  line-height: 1.4;
  margin: -0.35em 3em 0.8em;
}
.authors { text-align: center; font-size: 11.5pt; margin: 0 0 0.15em; }
.affil { text-align: center; font-size: 9.5pt; color: #444; margin: 0 0 0.5em; }
.meta { text-align: center; font-size: 9pt; color: #555; margin: 0.1em 0; }
hr.rule { border: none; border-top: 1.3pt solid #141414; margin: 0.9em 0 1.1em; }
h1 {
  font-size: 14pt;
  font-weight: bold;
  margin: 1.5em 0 0.7em;
  padding-bottom: 3pt;
  border-bottom: 1.4pt solid #141414;
  page-break-before: always;
  page-break-after: avoid;
  text-align: left;
}
h2 {
  font-size: 12.5pt;
  font-weight: bold;
  margin: 1.35em 0 0.5em;
  padding-bottom: 2pt;
  border-bottom: 0.7pt solid #bbb;
  page-break-after: avoid;
  text-align: left;
}
h3 {
  font-size: 11pt;
  font-weight: bold;
  margin: 1.05em 0 0.4em;
  page-break-after: avoid;
  text-align: left;
}
p { margin: 0 0 0.78em; }
ul, ol { margin: 0 0 0.8em 1.4em; }
li { margin-bottom: 0.3em; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.9em 0;
  font-size: 9.2pt;
  line-height: 1.35;
  page-break-inside: avoid;
}
th, td { border: 0.55pt solid #999; padding: 3.5pt 6pt; text-align: left; }
th { background: #f2f2f2; border-bottom: 1pt solid #555; font-weight: bold; }
blockquote {
  margin: 0.85em 1.1em;
  padding: 6pt 10pt;
  border-left: 2.6pt solid #888;
  background: #f7f7f7;
  font-size: 9.8pt;
  color: #333;
  page-break-inside: avoid;
}
blockquote p { margin: 0 0 0.5em; }
.figure { margin: 0.9em 0 1.2em; page-break-inside: avoid; }
.figure img { display: block; margin: 0 auto 0.45em; max-width: 100%; }
.figcap { text-align: center; font-size: 9pt; color: #444; line-height: 1.45; margin: 0 0.8em; }
code {
  font-family: "Liberation Mono", monospace;
  font-size: 8.8pt;
  background: #f4f4f4;
  padding: 0.5pt 3pt;
  border-radius: 2pt;
}
a { color: #1a4f8b; text-decoration: none; }
sup { font-size: 7.5pt; }
hr { border: none; border-top: 0.6pt solid #ccc; margin: 1.4em 0; }
"""

CSS = CSS.replace("/*HEADER*/", HEADER)


# Figures are PDF-only: injected at build time, never in draft-v4.md.
# Each entry is (unique anchor in the md source, figure html to insert after it).
FIGURES = [
    (
        "| content-only, **v2-refit (unregistered)** | reason_included | 0.15716 | 0.33963 | +0.18247 | (not computed) | sensitivity |",
        """<div class="figure">
<img src="figures/fig1-cells.png" alt="Calibrated delta over the frozen bar, all six pre-registered cells">
<div class="figcap">Figure 1. Calibrated delta over the frozen model-free bar, all six pre-registered cells (v2, 8,000 claims; calibration maps and bars frozen from v1, EM refit unsupervised on the v2 votes). Dashed line: the pre-registered GO threshold (+0.02 nats). All four test cells are green; the base_zeroshot cells are the reference arm. Numbers: eval_v2.json.</div>
</div>""",
    ),
    (
        "**Verdict: PASS (branch b).**",
        """<div class="figure">
<img src="figures/fig3-fcr.png" alt="False-claim rate by verification route">
<div class="figcap">Figure 2. False-claim rate by verification route on the 591 gateable claims. Both routes co-fail the same two unsupported claims (0/2 catch); the bootstrap CI of the difference, [0.0, 5e-05], spans zero, so the gate passes via the registered branch (b), cost, not catch. Numbers: gate_analysis.json.</div>
</div>""",
    ),
    (
        "excluded from the comparison, as registered.",
        """<div class="figure">
<img src="figures/fig2-cost.png" alt="Verification route cost relative to the 27B self-review route">
<div class="figcap">Figure 3. Verification-route cost per 8,000 claims (USD, token-proxy pricing), relative to the 27B self-review route (1.00x). The full 12-config panel is the reference run, not the gate arm; the gate arm is the reason_included panel at 0.96x (0.781x length-adjusted). Numbers: gate_analysis.json.</div>
</div>""",
    ),
]


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    # Drop the DRAFT NOTES comment block (and any other html comments).
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()

    # Inject the PDF-only figures after their unique anchors.
    for anchor, fig in FIGURES:
        if anchor not in text:
            raise SystemExit(f"figure anchor not found: {anchor[:60]!r}")
        text = text.replace(anchor, f"{anchor}\n\n{fig}", 1)

    # Split off the title block: everything before the first "## " heading.
    idx = text.index("\n## ")
    head, body = text[: idx].strip(), text[idx + 1 :].strip()

    title = authors = affil = subtitle = meta_lines = None
    for line in head.splitlines():
        s = line.strip()
        if not s or s == "---":
            continue
        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("**") and "Mannings" in s:
            authors = s
        elif s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            subtitle = s.strip("*")
        elif s.startswith("\u00b9"):
            affil = s
        elif s:
            s = s.replace("`", "")  # plain text in the title block, no code spans
            s = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', s)
            meta_lines = s if not meta_lines else f"{meta_lines}<br>{s}"

    parts = []
    if title:
        parts.append(f'<div class="title">{title}</div>')
    if subtitle:
        parts.append(f'<div class="subtitle">{subtitle}</div>')
    if authors:
        parts.append(
            '<div class="authors">'
            + re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", authors)
            + "</div>"
        )
    if affil:
        parts.append(f'<div class="affil">{affil}</div>')
    if meta_lines:
        parts.append(f'<div class="meta">{meta_lines}</div>')
    title_html = f'<div class="titleblock">{"".join(parts)}</div><hr class="rule">'

    body_html = markdown.markdown(body, extensions=["tables", "sane_lists"])

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{title_html}
{body_html}
</body>
</html>"""
    html_path = OUT.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    from weasyprint import HTML  # type: ignore

    HTML(string=html, base_url=str(html_path.parent)).write_pdf(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
