"""Derive the DECISIONS.md entry from the emitted artifacts (A10).

Every number is READ from out/v3/*.json rather than written from expectation,
so the entry cannot drift from what the run actually produced.
"""
from __future__ import annotations

import argparse
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

from exp3.reanalyse import PANELS
from wct3.observe import TOP_K

MARK = "V3 SLICE 1 OUTCOME"
FP = "artifacts-fingerprint"


def fingerprint(out_dir: Path) -> str:
    """Hash of every value the entry quotes, so --check detects a STALE entry
    rather than merely a missing one."""
    import hashlib
    data = {p: json.loads((out_dir / f"reanalysis_{p}.json").read_text()) for p in PANELS}
    quoted = []
    for p in PANELS:
        d = data[p]
        m = d["frozen_reproduction"]["map"]
        quoted.append((p, m, d["single_source"]["by_map"][m]["calibration_selected"],
                       d["panel_vs_single_best_calibration_selected"][m]["WCT-EM"]["decision"],
                       json.dumps(d["panel_vs_single_best_calibration_selected"][m]["WCT-EM"]["delta_log_loss"], sort_keys=True),
                       json.dumps({k: v["raw_auroc"] for k, v in d["m6_2x2"]["cells"].items()}, sort_keys=True),
                       json.dumps(d["alignment_audit"]["funnel"], sort_keys=True),
                       d["alignment_audit"]["aligner_self_identification"]["status"]))
    return hashlib.sha256(json.dumps(quoted, sort_keys=True).encode()).hexdigest()[:16]


def build(out_dir: Path) -> str:
    data = {p: json.loads((out_dir / f"reanalysis_{p}.json").read_text()) for p in PANELS}
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fp = fingerprint(out_dir)
    # the headline count is DERIVED; hard-coding "2 of 4" would survive a change
    # in the very result the entry exists to report
    n_inconc = sum(1 for p in PANELS
                   if data[p]["panel_vs_single_best_calibration_selected"][
                       data[p]["frozen_reproduction"]["map"]]["WCT-EM"]["decision"] != "go")
    L = [f"## {ts} - {MARK}: D1/D2/D3 corrected; the panel does not clearly beat its "
         f"best single source on {n_inconc} of {len(PANELS)} panel-cycles, and the "
         f"one-vote-per-source result is a POLARITY result, not a capping result.", "",
         f"<!-- {FP}: {fp} -->", ""]

    def _tot(p):
        ps = data[p]["frozen_reproduction_all_strata"]["per_stratum"]
        return sum(v["n_checks"] for v in ps.values()), sum(v["n_mismatched"] for v in ps.values())
    cover = ", ".join(f"{p} {_tot(p)[0] - _tot(p)[1]}/{_tot(p)[0]} across "
                      f"{len(data[p]['strata'])} strata ({', '.join(sorted(data[p]['strata']))})"
                      for p in PANELS)
    L.append("POST-HOC throughout. Nothing here restates a registered cycle-1 or cycle-2 "
             "verdict; every frozen quantity checked was reproduced EXACTLY, at the committed "
             "artifacts' own serialized precision, before any new number was read. Coverage: "
             + cover + ". SCOPE DISCLOSURE: cycle-1's `noneg_theories` stratum is excluded "
             "because its test split is single-class, so the frozen summary itself records an "
             "error there rather than results; there is nothing to reproduce. The v2 tag is "
             "untouched: the corrected instrument lives in wct3/ and exp3/.")
    L.append("")

    L.append("**D1 - the registered single-source arm, built at last.** "
             "`single_best_calibration_selected` (prereg.yaml:166, plan.md:488, simulated at "
             "m0/simulate.py:75) was never implemented by any analysis driver. Source chosen "
             "on CALIBRATION log-loss alone; the panel-minus-source contrast under each "
             "cycle's own registered calibration map:")
    L.append("")
    L.append("| panel | map | selected source | panel (WCT-EM) over that source | decision |")
    L.append("|---|---|---|---|---|")
    for p in PANELS:
        d = data[p]; m = d["frozen_reproduction"]["map"]
        v = d["panel_vs_single_best_calibration_selected"][m]["WCT-EM"]
        dl = v["delta_log_loss"]
        L.append(f"| {p} | {m} | {d['single_source']['by_map'][m]['calibration_selected']} | "
                 f"{dl['point']:+.4f} [{dl['lo']:+.4f}, {dl['hi']:+.4f}] | **{v['decision']}** |")
    L.append("")
    inconc = [p for p in PANELS
              if data[p]["panel_vs_single_best_calibration_selected"][
                  data[p]["frozen_reproduction"]["map"]]["WCT-EM"]["decision"] != "go"]
    L.append(f"On {len(inconc)} of {len(PANELS)} panel-cycles ({', '.join(inconc)}) the multi-model panel "
             f"is NOT shown to beat one model under the frozen decision rule. The registered "
             f"primary compares against an item-covariate baseline, so it establishes that "
             f"proposition-level vote scores carry signal; it does not establish that "
             f"CROSS-MODEL agreement is the mechanism. This is what cycle 3 registers.")
    L.append("")

    L.append("**D2 - the M6 ablation, corrected, refutes the claim it was cited for.** "
             "The frozen `uncapped` arm scores n_claims, which equals n_emitting identically "
             "because align_anchored collapses per (agent,pid) before exp/e1.py:76-78 counts. "
             "Varying capping and polarity separately (test AUROC):")
    L.append("")
    L.append("Raw (unmapped) test AUROC — the quantity the signal question asks. A fitted "
             "calibration map can take a negative slope on a signal-free arm and flip mapped "
             "AUROC about 0.5, so the mapped values are recorded in the artifacts under each "
             "cycle's own registered map and are not used here.")
    L.append("")
    L.append("| panel | capped+signed | capped+unsigned | uncapped+signed | uncapped+unsigned |")
    L.append("|---|---|---|---|---|")
    for p in PANELS:
        c = data[p]["m6_2x2"]["cells"]
        L.append(f"| {p} | {c['capped_signed']['raw_auroc']:.4f} | "
                 f"{c['capped_unsigned']['raw_auroc']:.4f} | "
                 f"{c['uncapped_signed']['raw_auroc']:.4f} | "
                 f"{c['uncapped_unsigned']['raw_auroc']:.4f} |")
    L.append("")
    cap_ok = [p for p in PANELS
              if data[p]["m6_2x2"]["cells"]["uncapped_signed"]["raw_auroc"]
              >= data[p]["m6_2x2"]["cells"]["capped_signed"]["raw_auroc"] - 0.01]
    unsigned_max = max(max(data[p]["m6_2x2"]["cells"][k]["raw_auroc"]
                           for k in ("capped_unsigned", "uncapped_unsigned"))
                       for p in PANELS)
    L.append(f"Removing the cap costs nothing (signed: uncapped matches or beats capped, "
             f"within 0.01, on {len(cap_ok)} of {len(PANELS)} panels). Removing the SIGN "
             f"destroys everything (no unsigned arm exceeds {unsigned_max:.4f} on any panel). "
             "paper.md 6.1 and contribution 4 — 'agreement carries information exactly when "
             "each source gets one vote; count text instead of sources and there is nothing "
             "there' — is therefore not supported by this instrument. The effect is polarity, "
             "not capping. This needs a paper correction (slice 2, B10), not a footnote.")
    L.append("")

    L.append("**D3 - the discarded audit, restored.** exp/e1_v2.py:189 binds the alignment "
             "audit and never uses it. Restored for all four panel-cycles:")
    L.append("")
    L.append("| panel | claims | instances | observations | same-agent conflicts | aligner probe |")
    L.append("|---|---|---|---|---|---|")
    for p in PANELS:
        a = data[p]["alignment_audit"]; f = a["funnel"]
        L.append(f"| {p} | {f['claims']} | {f['instances']} | {f['observations']} | "
                 f"{a['same_agent_conflicts']} | "
                 f"{a['aligner_self_identification']['status']} |")
    L.append("")
    L.append(f"The funnel is NOT monotone: alignment scores each claim against up to "
             f"top_k={TOP_K} targets, so one claim can pass against several. "
             f"observations <= instances is the invariant.")
    # derived, not asserted: the probe paragraph must follow the artifacts
    missing = [p for p in PANELS
               if data[p]["alignment_audit"]["aligner_self_identification"]["status"]
               != "computed"]
    if missing:
        L.append("")
        L.append(f"DISCLOSURE: the aligner self-identification probe is NOT COMPUTED for "
                 f"{', '.join(missing)}. Its NLI pairs are cached only for panels whose driver "
                 f"actually ran it, and exp/e1_v2.py never did — the omission being corrected. "
                 f"Computing them is local CPU NLI (no API, no quota) but is still new "
                 f"inference, which slice 1 forbids, so it is reported as absent rather than "
                 f"silently run.")
    else:
        probes = {p: data[p]["alignment_audit"]["aligner_self_identification"] for p in PANELS}
        acc = {p: probes[p]["accuracy"] for p in PANELS}
        wp = sum(probes[p]["wrong_polarity"] for p in PANELS)
        L.append("")
        L.append(f"The probe is computed on all four panel-cycles: self-identification "
                 f"{min(acc.values()):.4f}-{max(acc.values()):.4f}, and {wp} probe across "
                 f"{sum(probes[p]['n_probes'] for p in PANELS)} was scored with the wrong "
                 f"polarity. The cycle-2 corpus is therefore NOT measurably worse mapped than "
                 f"cycle 1's, so the depth-5 enrichment did not degrade the instrument.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="out/v3")
    ap.add_argument("--decisions", default="DECISIONS.md")
    ap.add_argument("--check", action="store_true",
                    help="verify the entry is present; do not write")
    ap.add_argument("--supersede", metavar="REASON",
                    help="append a NEW dated entry superseding the earlier one, "
                         "generated from the CURRENT artifacts. The project's "
                         "precedent (DECISIONS.md 2026-08-15) is a superseding "
                         "entry that leaves the original visible, not a rewrite.")
    args = ap.parse_args()
    path = Path(args.decisions)
    existing = path.read_text() if path.exists() else ""
    if args.check:
        if MARK not in existing:
            print(f"ABSENT: '{MARK}' in {path}")
            return 1
        want = fingerprint(Path(args.out_dir))
        if f"<!-- {FP}: {want} -->" not in existing:
            print(f"STALE: no {MARK} entry matches the current artifacts "
                  f"(expected {FP} {want}). Re-run with --supersede.")
            return 1
        print(f"present and CURRENT: '{MARK}' matches artifacts ({FP} {want})")
        return 0
    if args.supersede:
        body = build(Path(args.out_dir))
        head, _, rest = body.partition("\n")
        entry = (head.replace(MARK, f"{MARK} (SUPERSEDING)")
                 + f"\n\n**Supersedes the earlier {MARK} entry.** {args.supersede}\n"
                 + rest)
        _atomic_write(path, existing + ("\n" if existing and not existing.endswith("\n") else "")
                        + "\n" + entry + "\n")
        if not path.read_text().startswith(existing):
            raise RuntimeError(f"{path} was rewritten, not appended to")
        print(f"appended superseding {MARK} to {path}")
        return 0
    if MARK in existing:
        print(f"entry already present in {path}; not duplicating")
        return 0
    entry = build(Path(args.out_dir))
    _atomic_write(path, existing + ("\n" if existing and not existing.endswith("\n") else "")
                  + "\n" + entry + "\n")
    # append-only: the prior content must remain a strict prefix
    if not path.read_text().startswith(existing):
        raise RuntimeError(f"{path} was rewritten, not appended to; prior content is "
                           f"no longer a prefix. Restore from git before re-running.")
    print(f"appended {MARK} to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
