"""Render paper/draft-v4.md to a journal-style PDF via weasyprint.

Usage:
    uv run --with markdown --with weasyprint tools/paper_pdf.py [out.pdf]

Strips the DRAFT NOTES html comment, builds a centered title block,
and applies the paper stylesheet.
"""
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "paper" / "draft-v4.md"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper" / "draft-v4.pdf"

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
    content: "The Flip Was in the Instrument, Draft v4, 2026-08-29";
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
.authors { text-align: center; font-size: 11.5pt; margin: 0 0 0.15em; }
.affil { text-align: center; font-size: 9.5pt; color: #444; margin: 0 0 0.5em; }
.meta { text-align: center; font-size: 9pt; color: #555; margin: 0.1em 0; }
hr.rule { border: none; border-top: 1.3pt solid #141414; margin: 0.9em 0 1.1em; }
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


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    # Drop the DRAFT NOTES comment block (and any other html comments).
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()

    # Split off the title block: everything before the first "## " heading.
    idx = text.index("\n## ")
    head, body = text[: idx].strip(), text[idx + 1 :].strip()

    title = authors = affil = meta_lines = None
    for line in head.splitlines():
        s = line.strip()
        if not s or s == "---":
            continue
        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("**") and "Mannings" in s:
            authors = s
        elif s.startswith("\u00b9"):
            affil = s
        elif s:
            s = s.replace("`", "")  # plain text in the title block, no code spans
            s = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', s)
            meta_lines = s if not meta_lines else f"{meta_lines}<br>{s}"

    parts = []
    if title:
        parts.append(f'<div class="title">{title}</div>')
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
