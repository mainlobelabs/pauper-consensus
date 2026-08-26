#!/usr/bin/env python3
"""Generate corpus/pool/question_form/T##.md from corpus/pool/T##.md.

Mechanical polar conversion (frozen rule, prompts/jury_contract.md,
DECISIONS.md 2026-08-26): every proposition renders as
    "Is it true that {proposition, verbatim, minus trailing period}?"
No words are added, removed, or reworded beyond the prefix.

Usage: uv run python tools/make_question_form.py
Verifies the round-trip (proposition embedded verbatim) and fails on any
deviation. Re-running is idempotent.
"""

import re
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
POOL = CORPUS / "pool"
QF = POOL / "question_form"

PREFIX = "Is it true that "
PROPS = re.compile(r"^(\d+)\. (.+)$")


def parse_pool(path: Path) -> list[str]:
    props: list[str] = []
    for line in path.read_text().splitlines():
        m = PROPS.match(line.strip())
        if m:
            props.append(m.group(2).strip())
    return props


def render(prop: str) -> str:
    text = prop[:-1] if prop.endswith(".") else prop
    return f"{PREFIX}{text}?"


def main() -> int:
    pool_files = sorted(POOL.glob("T*.md"))
    if len(pool_files) != 30:
        print(f"expected 30 pool files, found {len(pool_files)}", file=sys.stderr)
        return 1
    QF.mkdir(exist_ok=True)
    total = 0
    for pf in pool_files:
        props = parse_pool(pf)
        if len(props) != 40:
            print(f"{pf.name}: expected 40 propositions, found {len(props)}", file=sys.stderr)
            return 1
        lines = [f"{pf.stem} pool, question form (40)", ""]
        for i, prop in enumerate(props, 1):
            q = render(prop)
            # round-trip check: the proposition must sit verbatim in the question
            expected_inner = prop[:-1] if prop.endswith(".") else prop
            if q.removeprefix(PREFIX).removesuffix("?") != expected_inner:
                print(f"{pf.name} #{i}: round-trip mismatch", file=sys.stderr)
                return 1
            lines.append(f"{i}. {q}")
        (QF / f"{pf.stem}.md").write_text("\n".join(lines) + "\n")
        total += len(props)
        print(f"{pf.stem}: 40 question forms written")
    print(f"done: {total} question forms across {len(pool_files)} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
