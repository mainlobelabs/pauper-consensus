"""Gate the four re-analysis artifacts. Fails closed, names the offending value.

Two jobs:
  1. structural — every artifact carries the panel identity, a complete audit,
     a funnel obeying the invariants that actually hold, every required arm,
     POST-HOC labelling and a recorded seed;
  2. fidelity — every UNTOUCHED frozen quantity reproduces EXACTLY at the
     committed artifacts' own serialized precision. Not a tolerance: the
     bootstraps are seeded (`wct/stats.py`, default_rng(20260807)) and the
     summaries store rounded values, so exact equality is achievable. A
     mismatch is a finding to report, never something to widen a bound around.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from exp3.reanalyse import FROZEN, PANELS
from wct3.observe import TOP_K

# an observation is one (agent, proposition) cell; the x3 is slack for the
# three-state vote, so this is a sanity ceiling, not a tight bound
OBS_CEILING_SLACK = 3

REQUIRED_ARMS = ("WCT-U", "WCT-EM", "WCT-C", "prevalence_only",
                 "capped_signed", "capped_unsigned",
                 "uncapped_signed", "uncapped_unsigned",
                 "covariate_baseline", "covariate_frozen",
                 "covariate_dedup", "covariate_verbosity",
                 "single_best_calibration_selected", "single_oracle")

# every stratum the frozen instrument reports and that is reproducible cache-only
REQUIRED_STRATA = {1: {"all_items", "negation_theories"},
                   2: {"all_items", "all_items_S2"}}


def _independent_frozen_check(d: dict, fails: list, name: str) -> None:
    """Open the committed summaries HERE and compare.

    The point is independence: `frozen_reproduction.all_match` is written by
    exp3.reanalyse, the same code whose output is under test, so trusting it
    makes the gate circular. This re-derives the comparison from the committed
    artifact and the emitted one, sharing no code with the producer.
    """
    path, mapname, cycle = FROZEN[name]
    committed_all = json.loads(Path(path).read_text())["strata"]
    n = 0
    for stratum, s in (d.get("strata") or {}).items():
        c = committed_all.get(stratum)
        if not c:
            fails.append(f"{name}/{stratum}: no committed stratum to compare against")
            continue
        cc = c["instrument_primary"] if cycle == 2 else c
        # registered panel identity, from the committed summary. The agent list
        # lives at STRATUM level in both cycles, so it must be read from `c`, not
        # from `cc` -- guarding on `cc is c` made this dead for cycle 2.
        if c.get("agents") and d.get("agents") != c["agents"]:
            fails.append(f"{name}/{stratum}: agents {d.get('agents')} != registered {c['agents']}")
        ours = s.get("arms") or {}
        alias = {"uncapped": "capped_unsigned", "covariate_baseline": "covariate_frozen"}
        for arm, cv in (cc.get("arms") or {}).items():
            mine = ours.get(alias.get(arm, arm))
            if mine is None:
                fails.append(f"{name}/{stratum}: no emitted arm for frozen '{arm}'")
                continue
            got = mine[mapname] if mapname in mine else mine
            for field in ("test_log_loss", "test_auroc", "test_accuracy"):
                if field in cv:
                    n += 1
                    if cv[field] != got.get(field):
                        fails.append(f"{name}/{stratum}: arms.{arm}.{field} "
                                     f"committed {cv[field]} != emitted {got.get(field)}")
        prim = (cc.get("primary") if cycle == 2
                else cc.get("primary_delta_log_loss_vs_covariate")) or {}
        for key, cv in prim.items():
            arm = key.split("_vs_")[0] if cycle == 2 else key
            if cycle == 2 and not key.endswith("_vs_covariate_gd"):
                continue
            mine = (s.get("primary_vs_covariate_frozen") or {}).get(mapname, {}).get(arm)
            if mine is None:
                fails.append(f"{name}/{stratum}: no emitted primary for '{key}'")
                continue
            for field in ("point", "lo", "hi"):
                n += 1
                if round(cv["delta_log_loss"][field], 5) != round(mine["delta_log_loss"][field], 5):
                    fails.append(f"{name}/{stratum}: primary.{arm}.{field} committed "
                                 f"{cv['delta_log_loss'][field]} != emitted "
                                 f"{mine['delta_log_loss'][field]}")
            n += 1
            if cv["decision"] != mine["decision"]:
                fails.append(f"{name}/{stratum}: primary.{arm}.decision committed "
                             f"{cv['decision']} != emitted {mine['decision']}")
        # the registered quantities beyond arms and primaries
        cp = cc.get("co_primary_precision_at_k") or {}
        mine_cp = (s.get("co_primary_precision_at_k") or {}).get(mapname) or {}
        for field in ("k", "WCT-EM", "WCT-U", "covariate_baseline"):
            if field in cp:
                n += 1
                if cp[field] != mine_cp.get(field):
                    fails.append(f"{name}/{stratum}: co_primary.{field} committed "
                                 f"{cp[field]} != emitted {mine_cp.get(field)}")
        if cp.get("difference"):
            for f2 in ("point", "lo", "hi"):
                n += 1
                got = (mine_cp.get("difference") or {}).get(f2)
                if got is None or round(cp["difference"][f2], 5) != round(got, 5):
                    fails.append(f"{name}/{stratum}: co_primary.difference.{f2} committed "
                                 f"{cp['difference'][f2]} != emitted {got}")
        wia = cc.get("within_item_auroc") or {}
        mine_w = (s.get("within_item_auroc") or {}).get(mapname) or {}
        for field in ("point", "lo", "hi", "decision"):
            if field in wia:
                n += 1
                a, b = wia[field], mine_w.get(field)
                if (round(a, 5) if isinstance(a, float) else a) != (
                        round(b, 5) if isinstance(b, float) else b):
                    fails.append(f"{name}/{stratum}: within_item_auroc.{field} "
                                 f"committed {a} != emitted {b}")
        pn = cc.get("permutation_null") or {}
        mine_p = (s.get("permutation_null") or {}).get(mapname) or {}
        for field in ("p", "observed", "null_mean", "null_sd", "n_perm"):
            if field in pn:
                n += 1
                a, b = pn[field], mine_p.get(field)
                if (round(a, 5) if isinstance(a, float) else a) != (
                        round(b, 5) if isinstance(b, float) else b):
                    fails.append(f"{name}/{stratum}: permutation_null.{field} "
                                 f"committed {a} != emitted {b}")
        # cycle-2's registered exact-ML primaries are a frozen sensitivity row
        for key, cv in (cc.get("primary") or {}).items():
            if not key.endswith("_vs_covariate_ml"):
                continue
            arm = key.split("_vs_")[0]
            mine = (s.get("primary_vs_covariate_ml") or {}).get(mapname, {}).get(arm)
            if mine is None:
                fails.append(f"{name}/{stratum}: no emitted exact-ML primary for '{key}'")
                continue
            for f2 in ("point", "lo", "hi"):
                n += 1
                if round(cv["delta_log_loss"][f2], 5) != round(mine["delta_log_loss"][f2], 5):
                    fails.append(f"{name}/{stratum}: primary_ml.{arm}.{f2} committed "
                                 f"{cv['delta_log_loss'][f2]} != emitted "
                                 f"{mine['delta_log_loss'][f2]}")
        # cycle-2's registered S1 instrument variant is a frozen block too
        cs1 = c.get("S1_deny_filter") or {}
        if cs1:
            os1 = s.get("S1_deny_filter") or {}
            if not os1:
                fails.append(f"{name}/{stratum}: frozen S1_deny_filter block not reproduced")
            for arm, cv in (cs1.get("arms") or {}).items():
                ours = (os1.get("arms") or {}).get(
                    {"uncapped": "capped_unsigned"}.get(arm, arm), {})
                got = ours.get(mapname, ours)
                for field in ("test_log_loss", "test_auroc"):
                    if field in cv:
                        n += 1
                        if cv[field] != got.get(field):
                            fails.append(f"{name}/{stratum}: S1.arms.{arm}.{field} "
                                         f"committed {cv[field]} != emitted {got.get(field)}")
            for key, cv in (cs1.get("primary") or {}).items():
                if not key.endswith("_vs_covariate_gd"):
                    continue
                arm = key.split("_vs_")[0]
                mine = ((os1.get("primary_vs_covariate_frozen") or {})
                        .get(mapname, {}).get(arm))
                if mine is None:
                    fails.append(f"{name}/{stratum}: no emitted S1 primary for '{key}'")
                    continue
                for f2 in ("point", "lo", "hi"):
                    n += 1
                    if round(cv["delta_log_loss"][f2], 5) != round(mine["delta_log_loss"][f2], 5):
                        fails.append(f"{name}/{stratum}: S1.primary.{arm}.{f2} committed "
                                     f"{cv['delta_log_loss'][f2]} != emitted "
                                     f"{mine['delta_log_loss'][f2]}")
            n += 1
            if cs1.get("audit", {}).get("dropped") != (os1.get("audit") or {}).get("dropped"):
                fails.append(f"{name}/{stratum}: S1.audit.dropped committed "
                             f"{cs1.get('audit', {}).get('dropped')} != emitted "
                             f"{(os1.get('audit') or {}).get('dropped')}")
    # Per-cycle floors. Cycle 1's frozen summaries carry no S1_deny_filter block
    # and no co-primary bootstrap difference (both are cycle-2 registrations), so
    # a single constant would either be vacuous for cycle 2 or unmeetable for
    # cycle 1. These are tripwires against the comparison silently shrinking.
    floor = {1: 80, 2: 120}[cycle]
    if n < floor:
        fails.append(f"{name}: independent check covered only {n} fields "
                     f"(cycle-{cycle} floor is {floor})")


def check(path: Path) -> list[str]:
    fails: list[str] = []

    def need(cond, msg):
        if not cond:
            fails.append(f"{path.name}: {msg}")

    if not path.exists():
        return [f"{path.name}: MISSING"]
    d = json.loads(path.read_text())

    expected_panel = path.stem.replace("reanalysis_", "")
    need(d.get("panel") == expected_panel,
         f"artifact declares panel {d.get('panel')!r} but is named for {expected_panel!r}")
    # the agent list is checked against the REGISTERED one in the independent pass
    need(d.get("status") == "POST-HOC", "top-level status is not POST-HOC")
    need(d.get("seed") == 20260807, f"seed not recorded as 20260807: {d.get('seed')}")
    need(isinstance(d.get("n_test_negatives"), int), "n_test_negatives absent")

    a = d.get("alignment_audit") or {}
    need(a.get("status") == "POST-HOC", "alignment audit not labelled POST-HOC")
    for k in ("aligner_self_identification", "lexical_reference",
              "same_agent_conflicts", "claims", "observations", "funnel"):
        need(k in a, f"alignment audit missing {k}")
    si = a.get("aligner_self_identification") or {}
    # A6 requires a COMPLETE audit on every panel of both cycles. Under the
    # 2026-08-28 amendment the cycle-2 probe is computable, so NOT COMPUTED is
    # no longer an acceptable terminal state — it fails the gate.
    need(si.get("status") == "computed",
         f"aligner probe not computed (status={si.get('status')}); run "
         f"exp3.probe_backfill --confirm under the recorded amendment")
    need(isinstance(si.get("accuracy"), float) and si.get("n_probes"),
         "aligner probe reports no accuracy or probe count")

    f = a.get("funnel") or {}
    if f:
        n_ag = len(d.get("agents") or [])
        need(f["observations"] <= f["instances"],
             f"funnel: observations {f['observations']} > instances {f['instances']}")
        need(f["instances"] <= f["claims"] * TOP_K,
             f"funnel: instances {f['instances']} > claims*top_k {f['claims'] * TOP_K}")
        need(f["observations"] <= d["n_props"] * n_ag,
             f"funnel: observations {f['observations']} exceed the "
             f"(proposition x agent) cell ceiling {d['n_props'] * n_ag}")

    arms = d.get("arms") or {}
    for name in REQUIRED_ARMS:
        need(name in arms, f"required arm missing: {name}")
    sroot = d.get("single_source") or {}
    need(set(sroot.get("by_map", {})) == {"platt", "temperature"},
         "single_source must select under BOTH maps: the choice is not map-invariant")
    ss = (sroot.get("by_map") or {}).get(FROZEN[d["panel"]][1], {})
    need("calibration_selected" in ss, "single_best_calibration_selected absent (D1)")
    need("oracle_selected" in ss, "single_oracle absent")
    if ss.get("calibration_selected"):
        ll = ss["calibration_log_loss_per_agent"]
        # reported values are rounded, so a tie is legitimate; the invariant is
        # that nothing beats the selection, not that it is uniquely minimal
        need(ll[ss["calibration_selected"]] <= min(ll.values()) + 1e-9,
             "selected source does not minimise CALIBRATION loss — test leakage?")
        need(f"single:{ss['calibration_selected']}" in arms,
             "selected source has no arm")
    need(bool(d.get("panel_vs_single_best_calibration_selected")),
         "panel-vs-single-source contrast absent")
    need(bool(d.get("covariate_sensitivity", {}).get("rows")),
         "covariate sensitivity rows absent or unlabelled")
    need(bool(d.get("prevalence_only_vs_covariate")), "prevalence_only paired delta absent")
    for k in ("co_primary_precision_at_k", "within_item_auroc", "permutation_null"):
        need(bool(d.get(k)), f"registered quantity absent: {k}")
    cells = d.get("m6_2x2", {}).get("cells", {})
    need(set(cells) == {"capped_signed", "capped_unsigned",
                        "uncapped_signed", "uncapped_unsigned"}, "M6 2x2 incomplete")
    for k, c in cells.items():
        need("raw_auroc" in c and "platt" in c and "temperature" in c,
             f"M6 cell {k} must carry raw_auroc and BOTH mapped variants: a fitted "
             f"negative slope flips mapped AUROC about 0.5 on a signal-free arm")

    cycle = FROZEN[d["panel"]][2]
    strata = d.get("strata") or {}
    need(set(strata) == REQUIRED_STRATA[cycle],
         f"strata coverage is {set(strata)}, required {REQUIRED_STRATA[cycle]} "
         f"(A8 covers every stratum the frozen instrument reports)")
    allrep = d.get("frozen_reproduction_all_strata") or {}
    need(allrep.get("all_match") is True,
         f"not every stratum reproduced: {allrep.get('per_stratum')}")
    for sname, s in strata.items():
        sr = s.get("frozen_reproduction") or {}
        need(sr.get("n_mismatched") == 0, f"stratum {sname}: {sr.get('n_mismatched')} mismatches")
        need(sr.get("n_checks", 0) >= 25, f"stratum {sname}: only {sr.get('n_checks')} checks")

    _independent_frozen_check(d, fails, d.get("panel"))

    rep = d.get("frozen_reproduction") or {}
    need(rep.get("source") == FROZEN[d["panel"]][0], "frozen source mismatch")
    need(rep.get("all_match") is True, "frozen_reproduction did not self-report all_match")
    need(rep.get("n_mismatched") == 0, f"frozen mismatches: {rep.get('n_mismatched')}")
    need(rep.get("n_checks", 0) >= 30,
         f"too few frozen checks: {rep.get('n_checks')}")
    if not rep.get("all_match"):
        for m in rep.get("mismatches", []):
            fails.append(f"{path.name}: FROZEN MISMATCH {m['key']}: "
                         f"expected {m['expected']} got {m['got']}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="out/v3")
    args = ap.parse_args()
    fails: list[str] = []
    for name in PANELS:
        fails += check(Path(args.out_dir) / f"reanalysis_{name}.json")
    if fails:
        print(f"VALIDATION FAILED ({len(fails)}):", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"validation OK: {len(PANELS)} artifacts, structure + frozen fidelity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
