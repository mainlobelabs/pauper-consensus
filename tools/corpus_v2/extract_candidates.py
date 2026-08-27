"""Extract dated event candidates from Portal:Current events month files.

Parses corpus-v2/portals/*.txt (webfetch/tavily text dumps of
https://en.wikipedia.org/wiki/Portal:Current_events/<Month>_2026) into
dated, categorised event lines.

Window and exclusions (see NOTES.md Phase 5, v2 scope call):
- Keep: 2026-02-15 .. 2026-08-13 and 2026-08-26 .. 2026-08-27.
- Drop: 2026-08-14 .. 2026-08-25 (v1 window; those dates are v1's corpus).
- Topic exclusions: v1 keep-30 topics whose beats fall inside v2 dates,
  plus the DRC Ebola outbreak (ongoing Feb-Aug; covered by v1 T29).

Outputs (corpus-v2/):
- candidates.jsonl  one JSON object per event
- candidates.md     per-date listing for review
- stories.md        grouped by topic, for spotting ongoing vs one-off stories
"""

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTALS = ROOT / "corpus-v2" / "portals"
OUT = ROOT / "corpus-v2"

KEEP_RANGES = [
    ("2026-02-15", "2026-08-13"),
    ("2026-08-26", "2026-08-27"),
]

DATE_RE = re.compile(r"^([A-Z][a-z]+) (\d{1,2}), 2026 \((\d{4}-\d{2}-\d{2})\) \(([A-Za-z]+)\)$")
# Fixed top-level portal categories; seeing one resets the category stack.
TOP_CATEGORIES = {
    "Armed conflicts and attacks",
    "Arts and culture",
    "Business and economy",
    "Disasters and accidents",
    "Health and environment",
    "International relations",
    "Law and crime",
    "Politics and elections",
    "Science and technology",
    "Sience and technology",  # portal typo, seen in August 2026
    "Sports",
}
# Event lines end in a source parenthetical: "(AP)", "(AFP via RFI)",
# "(CNN) (Reuters)", or an unclosed one (tavily quirk): "(The Guardian"
EVENT_END_RE = re.compile(r"\([^()]*\)\s*$")
EVENT_UNCLOSED_RE = re.compile(r"\([A-Z][^()]{1,40}$")
# Inline wikilink annotations in tavily dumps: name "Full name (disambig)")
ANNOT_RE = re.compile(r'\s+"[^"]*"\)?\s*$')
SKIP_LINES = {"edithistorywatch", "edit history watch", "watch", "edit", "history"}

# v1 keep-30 topics with beats inside v2 dates + ongoing Ebola outbreak.
# Regex matched (case-insensitive) on topic path or event text.
# Optional date range restricts the match (e.g. "indiana" only means the
# August floods, not the Indy 500 or the NFL draft).
TOPIC_EXCLUDES = [
    ("T13 Lake Kariba (v1)", r"lake kariba", None, None),
    ("T02 Hurricane Lala (v1)", r"\blala\b", None, None),
    ("T03 USS Abraham Lincoln (v1)", r"abraham lincoln", None, None),
    ("T08 Lindell recount (v1)", r"lindell", None, None),
    ("T10 Indiana floods (v1)", r"indiana", "2026-08-01", "2026-08-13"),
    ("T16 Discord Brazil (v1)", r"discord", None, None),
    ("T29 DRC Ebola outbreak (v1, ongoing)", r"ebola", None, None),
]


def in_window(date: str) -> bool:
    return any(lo <= date <= hi for lo, hi in KEEP_RANGES)


def excluded(date: str, name_text: str) -> str | None:
    low = name_text.lower()
    for label, pat, lo, hi in TOPIC_EXCLUDES:
        if not re.search(pat, low):
            continue
        if lo is not None and not (lo <= date <= hi):
            continue
        return label
    return None


def clean(s: str) -> str:
    s = s.replace("\u00a0", " ")  # webfetch dumps use NBSP in headers
    s = s.strip()
    s = re.sub(r"^\+\s*", "", s)
    return s


MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def parse_file(path: Path):
    """Yield (date, day, section, topic, event_text) tuples.

    topic   = most specific portal heading seen before the event; consecutive
              events under the same heading inherit it (portal list structure).
    section = most recent top-level portal category, for context.
    """
    events = []
    date = None
    day = ""
    section = ""
    topic = ""
    in_section = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = clean(raw)
        if not s or s in SKIP_LINES:
            continue
        m = DATE_RE.match(s)
        if m:
            month, d, iso, day = m.groups()
            if MONTHS[int(iso[5:7]) - 1] != month or int(d) != int(iso[8:10]):
                print(f"WARN {path.name}: header mismatch: {s}")
            date, day = iso, day
            in_section = True
            section = ""
            topic = ""
            continue
        if not in_section:
            continue
        if EVENT_END_RE.search(s) or EVENT_UNCLOSED_RE.search(s):
            events.append((date, day, section, topic or section or "(uncategorised)", s))
        else:
            cat = ANNOT_RE.sub("", s).strip()
            if not cat:
                continue
            if cat in TOP_CATEGORIES:
                section = cat
                topic = ""
            else:
                topic = cat
    return events


def main() -> None:
    all_events = []
    for f in sorted(PORTALS.glob("*.txt")):
        evs = parse_file(f)
        kept = [e for e in evs if in_window(e[0])]
        dropped_window = len(evs) - len(kept)
        print(
            f"{f.name}: {len(evs)} events, {len(kept)} in window, {dropped_window} outside window"
        )
        all_events.extend(kept)

    # topic-level exclusions
    kept, excluded_rows = [], []
    for date, day, section, topic, text in all_events:
        hit = excluded(date, f"{section} {topic} {text}")
        if hit:
            excluded_rows.append((date, topic, text, hit))
        else:
            kept.append((date, day, section, topic, text))
    print(f"excluded by v1 topic match: {len(excluded_rows)}")

    # candidates.jsonl
    with (OUT / "candidates.jsonl").open("w", encoding="utf-8") as fh:
        for date, day, section, topic, text in kept:
            fh.write(
                json.dumps(
                    {"date": date, "day": day, "section": section, "topic": topic, "text": text},
                    ensure_ascii=False,
                )
                + "\n"
            )

    # candidates.md (per date)
    by_date = defaultdict(list)
    for date, _day, _section, topic, text in kept:
        by_date[date].append((topic, text))
    lines = [
        "# v2 corpus raw candidates (one row per portal event line)",
        "",
        f"Window: 2026-02-15..2026-08-13 + 2026-08-26..2026-08-27 "
        f"({len(kept)} events, {len(by_date)} days). "
        f"Excluded: v1 window 2026-08-14..25 ({len(excluded_rows)} v1-topic "
        f"beats dropped).",
        "",
    ]
    for date in sorted(by_date):
        lines.append(f"## {date}")
        lines.append("")
        for topic, text in by_date[date]:
            lines.append(f"- **{topic}**: {text}")
        lines.append("")
    (OUT / "candidates.md").write_text("\n".join(lines), encoding="utf-8")

    # stories.md (grouped by topic)
    by_topic = defaultdict(list)
    for date, _day, _section, topic, text in kept:
        by_topic[topic].append((date, text))
    lines = ["# v2 candidate stories, grouped by portal topic", ""]
    for topic in sorted(by_topic, key=lambda t: len(by_topic[t]), reverse=True):
        rows = by_topic[topic]
        dates = sorted({d for d, _ in rows})
        span = dates[0] if dates[0] == dates[-1] else f"{dates[0]}..{dates[-1]}"
        lines.append(f"## {topic}  [{len(rows)} beats, {span}]")
        lines.append("")
        for date, text in rows[:3]:
            lines.append(f"- {date}: {text[:200]}")
        if len(rows) > 3:
            lines.append(f"- ... {len(rows) - 3} more beats")
        lines.append("")
    (OUT / "stories.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {len(kept)} events across {len(by_date)} days; {len(by_topic)} topics")


if __name__ == "__main__":
    main()
