"""Pre-filter raw candidates into a fact-density shortlist.

Reads corpus-v2/candidates.jsonl, scores each event line for fact density
(numbers, named entities, percents, currency, quotes, length), and writes
corpus-v2/shortlist.md grouped by month for the curation pass.

The shortlist is a superset: the curation step (human) picks the final
candidate pool with domain spread, self-containment, and verbatim-availability
judgment that a density score cannot make.
"""

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "corpus-v2" / "candidates.jsonl"
OUT = ROOT / "corpus-v2" / "shortlist.md"

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
# 2+ consecutive Capitalized words = probable named entity / organisation
ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b")
THRESHOLD = 5.0
LONG_KEEP = 250  # chars: long events keep even at low score


def score(text: str) -> float:
    nums = len(NUM_RE.findall(text))
    ents = len(ENTITY_RE.findall(text))
    pct = text.count("%")
    cur = text.count("$") + text.count("\u20ac")
    quotes = text.count("\u201c") + text.count('"')
    s = nums + 2 * ents + 2 * pct + cur + 2 * quotes
    if len(text) >= 200:
        s += 1
    if len(text) >= 120:
        s += 0.5
    return s


def main() -> None:
    evs = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines() if line]
    kept = []
    for e in evs:
        sc = score(e["text"])
        if sc >= THRESHOLD or len(e["text"]) >= LONG_KEEP:
            kept.append((sc, e))

    by_month = defaultdict(list)
    for sc, e in kept:
        by_month[e["date"][:7]].append((sc, e))

    # Per-month cap: curation needs a reviewable list, not a firehose.
    # Keep everything scoring >= FLOOR plus the top CAP by score.
    CAP, FLOOR = 200, 10.0
    for month in list(by_month):
        rows = sorted(by_month[month], key=lambda x: x[0], reverse=True)
        if len(rows) <= CAP:
            continue
        keep = set(id(r) for r in rows[:CAP])
        keep.update(id(r) for r in rows if r[0] >= FLOOR)
        by_month[month] = [r for r in rows if id(r) in keep]

    lines = [
        "# v2 shortlist (fact-density pre-filter)",
        "",
        f"{len(kept)} of {len(evs)} raw events pass the density threshold "
        f"({THRESHOLD} score or {LONG_KEEP}+ chars). Curate down to ~250 "
        "candidates with domain spread and self-containment.",
        "",
    ]
    for month in sorted(by_month):
        rows = sorted(by_month[month], key=lambda x: (x[1]["date"], -x[0]))
        lines.append(f"## {month} ({len(rows)} events)")
        lines.append("")
        cur_date = None
        for sc, e in rows:
            if e["date"] != cur_date:
                cur_date = e["date"]
                lines.append(f"### {cur_date}")
                lines.append("")
            lines.append(f"- [{sc:.1f}] **{e['topic']}**: {e['text']}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    # stats for threshold tuning
    scores = sorted(score(e["text"]) for e in evs)
    print(
        f"kept {len(kept)}/{len(evs)}; "
        f"score p25={scores[len(scores) // 4]:.1f} "
        f"p50={statistics.median(scores):.1f} "
        f"p75={scores[3 * len(scores) // 4]:.1f}"
    )
    for month in sorted(by_month):
        print(f"  {month}: {len(by_month[month])}")


if __name__ == "__main__":
    main()
