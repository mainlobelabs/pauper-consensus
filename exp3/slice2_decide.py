"""Derive slice 2's DECISIONS.md entry from the corrected paper and the artifacts."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from exp3.check_paper import EVIDENCE_COMMIT, MARKED, PANELS

MARK = "V3 SLICE 2 OUTCOME"
FP = "slice2-fingerprint"


def fingerprint(root: Path) -> str:
    """Hash of everything the entry quotes, so --check catches a STALE or hand-written
    entry rather than merely the presence of its heading."""
    import hashlib
    D = {p: json.loads((root / "out/v3" / f"reanalysis_{p}.json").read_text()) for p in PANELS}
    paper = (root / "paper.md").read_text()
    # the COUNT of marked regions is not enough: editing a corrected passage leaves the
    # count unchanged, so the entry would still report itself current while describing
    # prose that has since moved. Hash their content.
    quoted = [len(MARKED.findall(paper)),
              hashlib.sha256("\u0000".join(MARKED.findall(paper)).encode()).hexdigest()[:16]]
    for p in PANELS:
        m = D[p]["frozen_reproduction"]["map"]
        v = D[p]["panel_vs_single_best_calibration_selected"][m]["WCT-EM"]
        quoted.append([p, m, v["decision"], round(v["delta_log_loss"]["point"], 4),
                       {k: c["raw_auroc"] for k, c in D[p]["m6_2x2"]["cells"].items()}])
    return hashlib.sha256(json.dumps(quoted, sort_keys=True).encode()).hexdigest()[:16]


def build(root: Path) -> str:
    # derived from the CHECKER's verified output, not from an independent re-parse: two
    # separate readings of the same paper can disagree, and only one of them is gated
    chk = root / "out/slice2/paper_check.json"
    if not chk.exists():
        raise RuntimeError("out/slice2/paper_check.json missing — run exp3.check_paper first; "
                           "the entry must rest on a verified check, not a re-parse")
    verified = json.loads(chk.read_text())
    if not verified.get("ok"):
        raise RuntimeError("paper check did not pass; refusing to write an outcome entry")
    D = {p: json.loads((root / "out/v3" / f"reanalysis_{p}.json").read_text()) for p in PANELS}
    paper = (root / "paper.md").read_text()
    n_marked = len(MARKED.findall(paper))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fp = fingerprint(root)

    def sctx(p):
        m = D[p]["frozen_reproduction"]["map"]
        v = D[p]["panel_vs_single_best_calibration_selected"][m]["WCT-EM"]
        return v["decision"], v["delta_log_loss"]["point"]

    gos = [p for p in PANELS if sctx(p)[0] == "go"]
    inc = [p for p in PANELS if sctx(p)[0] != "go"]
    pts = [sctx(p)[1] for p in gos]
    umax = max(D[p]["m6_2x2"]["cells"][k]["raw_auroc"]
               for p in PANELS for k in ("capped_unsigned", "uncapped_unsigned"))
    deltas = [D[p]["m6_2x2"]["cells"]["uncapped_signed"]["raw_auroc"]
              - D[p]["m6_2x2"]["cells"]["capped_signed"]["raw_auroc"] for p in PANELS]
    n_beats = sum(1 for d in deltas if d > 0)
    worst = min(deltas)

    return "\n".join([
        f"## {ts} - {MARK}: paper.md corrected in {n_marked} marked passages; the refuted "
        f"claim was a LABEL error, not an arithmetic one.", "",
        f"<!-- {FP}: {fp} -->", "",
        f"Corrections derived from `out/v3/` at `{EVIDENCE_COMMIT}` and machine-checked by "
        f"`exp3/check_paper.py`, which requires every figure in a marked passage to equal an "
        f"artifact value or match a declared structural pattern. The figures below are "
        f"reported on the authority of that check ({len(verified['checks'])} checks: "
        f"{', '.join(verified['checks'])}), not an independent re-reading. No registered "
        f"cycle-1 or cycle-2 verdict is restated or altered.", "",
        f"**What was wrong.** Draft v3's abstract, contribution 4, 3.4, 6.1 and 9 concluded "
        f"that agreement carries information because each source gets one vote. Its quoted "
        f"AUROC ranges are CORRECT readings of the frozen `uncapped` arm; the error is that "
        f"the arm is capped and unsigned, because `cluster.align_anchored` collapses per "
        f"(agent, proposition) before `exp/e1.py:76-78` counts. The contrast varied polarity, "
        f"not capping. Separating them: uncapped signed BEATS capped on {n_beats} of "
        f"{len(PANELS)} panel-cycles and is {abs(worst):.4f} lower on the remaining one, so "
        f"the cap makes no measurable difference either way; no unsigned arm exceeds "
        f"{umax:.4f} anywhere.", "",
        f"**What was disclosed.** `single_best_calibration_selected` "
        f"(`prereg.yaml:166`, `plan.md:488`) was registered and never implemented in either "
        f"cycle, so no registered result distinguished cross-model agreement from one good "
        f"model. Post-hoc, the panel beats its calibration-selected best single source on "
        f"{len(gos)} of {len(PANELS)} panel-cycles ({min(pts):+.4f} to {max(pts):+.4f} nats) "
        f"and inconclusively on {', '.join(inc)}. 9 now closes there, per the recorded "
        f"decision on OQ1.", "",
        f"**Scope.** {n_marked} passages are delimited in `paper.md` by slice2 markers. "
        f"Everything outside them is asserted byte-identical to `{EVIDENCE_COMMIT}:paper.md` "
        f"by the slice gate, so the correction cannot have altered a section it does not "
        f"claim to touch.", "",
    ])


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
            print(f"STALE: no '{MARK}' entry matches the current paper and artifacts "
                  f"(expected {FP} {want})")
            return 1
        print(f"present and CURRENT: '{MARK}' ({FP} {want})")
        return 0
    if MARK in existing:
        want = fingerprint(root)
        if f"<!-- {FP}: {want} -->" in existing:
            print(f"{MARK} already present and current; not duplicating")
            return 0
        # A stale entry must be REPLACED, not left to wedge the gate: refusing to update
        # while --check reports STALE makes run_slice2.sh unpassable with no way forward.
        import re as _re
        blocks = _re.split(r"(?m)^(?=## )", existing)
        kept = [b for b in blocks if MARK not in b.split("\n")[0]]
        existing = "".join(kept).rstrip() + "\n"
        print(f"superseding a stale {MARK} entry")
    path.write_text(existing.rstrip() + "\n\n" + build(root) + "\n")
    if not path.read_text().startswith(existing.rstrip()):
        raise RuntimeError("DECISIONS.md was rewritten, not appended to")
    print(f"appended {MARK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
