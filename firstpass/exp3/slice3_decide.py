"""Derive slice 3's DECISIONS.md entry from the measured artifact and the verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file and os.replace.

    DECISIONS.md is the project's durable record. A direct write_text that is
    interrupted leaves it truncated, destroying entries this session cannot
    reconstruct. os.replace is atomic within a filesystem.
    """
    import os
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)

MARK = "V3 SLICE 3 OUTCOME"
FP = "slice3-fingerprint"


def _load(root: Path):
    return (json.loads((root / "out/slice3/availability.json").read_text()),
            json.loads((root / "out/slice3/verdict.json").read_text()))


def fingerprint(root: Path) -> str:
    art, v = _load(root)
    # everything the entry renders: omitting measured_at or the rationale let a NEW
    # measurement leave the OLD entry reporting itself current
    quoted = [v["n_families_pinned_ok"], v["n_families_reachable"], v["margin"],
              v["registrable"], v["rationale"], v["n_m3_subsets"],
              sorted(v["families_pinned_ok"]), sorted(v["families_reachable"]),
              sorted(v["reachable_only_via_non_pinned_id"]),
              sorted((c["agent"], c["family"], c.get("backend"), c.get("model"),
                      c.get("tier", "pinned"), c["status"],
                      (c.get("error") or c.get("note") or "")[:60])
                     for c in art["candidates"]),
              json.dumps(v.get("panel_reproducibility") or {}, sort_keys=True),
              sorted(v.get("families_identity_verified") or []),
              art["spend"].get("is_upper_bound"),
              art["measured_at"], art["source_commit"], art.get("source_tree_dirty"),
              art["spend"]["usd"], art["spend"]["paid_calls"],
              art["registration_sha256"]]
    return hashlib.sha256(json.dumps(quoted, sort_keys=True).encode()).hexdigest()[:16]


def build(root: Path) -> str:
    art, v = _load(root)
    fp = fingerprint(root)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = "\n".join(
        f"| {c['agent']} | {c['family']} | {c['backend']} | **{c['status']}** | "
        f"{(c.get('error') or c.get('note') or '')[:60].splitlines()[0] if (c.get('error') or c.get('note')) else ''} |"
        for c in art["candidates"])
    reprobed = [c for c in art["candidates"] if c.get("superseded_by_reprobe")]
    L = [f"## {ts} - {MARK}: only {v['n_families_pinned_ok']} of 6 PINNED ids still answer, "
         f"but {v['n_families_reachable']} families are reachable; {v['registrable']}.",
         "", f"<!-- {FP}: {fp} -->", "",
         f"Measured {art['measured_at']} at commit `{art['source_commit']}`, one attempt per "
         f"endpoint, no automatic retry. Registration digest "
         f"`{art['registration_sha256'][:12]}`. Paid spend: USD {art['spend']['usd']} across "
         f"{art['spend']['paid_calls']} call(s)"
         f"{' (upper bound)' if art['spend']['is_upper_bound'] else ''}.", "",
         "| agent | family | backend | status | detail |", "|---|---|---|---|---|", rows, "",
         "**Which registered panels still run.** " + "; ".join(
             f"{n}: " + ("reproducible" if d["reproducible"]
                         else f"NOT reproducible, broken by {', '.join(d['broken'])}")
             for n, d in (v.get("panel_reproducibility") or {}).items()) +
         ". prereg_v2's rule is 'exact pinned id or the panel is DROPPED', so a paid-tier "
         "twin does not restore a panel whose registered id has gone.", "",
         f"**Two counts, deliberately not merged.** Only "
         f"{v['n_families_pinned_ok']} of six REGISTERED ids answered "
         f"({', '.join(v['families_pinned_ok'])}), so not every cycle-2 panel is reproducible "
         f"as registered. "
         f"But {v['n_families_reachable']} distinct FAMILIES are reachable, "
         f"{', '.join(v['reachable_only_via_non_pinned_id'])} only via a paid-tier twin of a "
         f"withdrawn or rate-limited `:free` id. Cycle 3 pins its own panels and may pin "
         f"those ids directly.", "",
         f"**Verdict, by the rule recorded 2026-08-30 BEFORE the measurement.** Margin "
         f"{v['margin']:+d} against the five required, on the reachable count. "
         f"{v['rationale']}", "",
         f"**Cost consequence for slice 4.** Cycle 2 ran four of six models on free tiers; "
         f"{len(v['reachable_only_via_non_pinned_id'])} of those families now require a paid "
         f"tier. At 450 calls per panel that is a budget line for the registration, not a "
         f"mid-run discovery.", ""]
    if reprobed:
        L += [f"**Re-probed deliberately:** "
              f"{', '.join(c['agent'] for c in reprobed)}. A `fail` records one attempt at a "
              f"timestamp, not absence, so a human judged a second invocation warranted. The "
              f"superseded attempts are retained in the artifact: "
              + "; ".join(f"{c['agent']} was {h['status']} then {c['status']}"
                          for c in reprobed for h in c["superseded_by_reprobe"]) + ".", ""]
    runnable = v["n_families_reachable"] > v["required"]
    if runnable:
        conseq = (f"The M=3 -> M=5 dose-response IS runnable: "
                  f"{v['n_families_reachable']} families reachable with margin "
                  f"{v['margin']:+d}.")
    elif v["n_families_reachable"] == v["required"]:
        conseq = (f"The M=3 -> M=5 dose-response is runnable ONLY WITHOUT MARGIN: exactly "
                  f"{v['required']} families are reachable. Under the recorded rule slice 4 "
                  f"registers M=3/M=4 as primary with the fifth as a declared stretch arm.")
    else:
        conseq = (f"The M=3 -> M=5 dose-response CANNOT be run as designed: it needs "
                  f"{v['required']} families and {v['n_families_reachable']} are reachable. "
                  f"Slice 4 registers what exists or parks for a go/no-go.")
    L += [f"**Consequence for slice 4.** {conseq} Family-disjoint M=3 subsets available: "
          f"{v['n_m3_subsets']}. Slice 4 must pin the reachable ids (paid where the `:free` "
          f"tier has been withdrawn or is rate limited), price the paid tiers, and record "
          f"which registered panels survive (see above).", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    path = root / "DECISIONS.md"
    existing = path.read_text()
    if args.check:
        if MARK not in existing:
            print(f"ABSENT: '{MARK}'"); return 1
        want = fingerprint(root)
        if f"<!-- {FP}: {want} -->" not in existing:
            print(f"STALE: no '{MARK}' entry matches the current artifact "
                  f"(expected {FP} {want})")
            return 1
        print(f"present and CURRENT: '{MARK}' ({FP} {want})")
        return 0
    if MARK in existing:
        if f"<!-- {FP}: {fingerprint(root)} -->" in existing:
            print(f"{MARK} already present and current")
            return 0
        import re as _re
        blocks = _re.split(r"(?m)^(?=## )", existing)
        existing = "".join(b for b in blocks if MARK not in b.split("\n")[0]).rstrip() + "\n"
        print(f"superseding a stale {MARK} entry")
    _atomic_write(path, existing.rstrip() + "\n\n" + build(root) + "\n")
    print(f"appended {MARK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
