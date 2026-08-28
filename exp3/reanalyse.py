"""Re-analyse all four panel-cycles under the corrected instrument. Cache-only.

POST-HOC throughout. This diagnoses cycles 1 and 2; it never restates their
registered verdicts, and it writes nowhere near their frozen summaries.

Zero inference is enforced, not asserted: `wct3.strict` is installed before any
analysis, so a cache miss in embed or NLI raises rather than computing. Run
with WCT_LOCAL_BASE pointed at an unroutable address as a second layer.

Usage:
  PYTHONPATH=. WCT_CACHE=out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 \
      .venv/bin/python -m exp3.reanalyse --panel all --out-dir out/v3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from wct3 import arms as v3arms
from wct3 import audit as v3audit
from wct3 import observe
from wct3 import strict

PANELS = ("c1_local", "c1_openrouter", "c2_panelA", "c2_panelB")


def _jsonable(o):
    """numpy scalars/arrays only. Anything else RAISES rather than being
    stringified, so a serialisation bug cannot reach an artifact as prose."""
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"unserialisable {type(o).__name__} in a result artifact: {o!r}")

# the committed frozen summary each panel must reproduce, and which calibration
# map that cycle actually registered (cycle 1: temperature, cycle 2: Platt)
# A8 covers every stratum the frozen instrument reports, not just all_items.
# cycle 1: negation_theories is a SUBSET of items (same per-item alignment, so
#          fully cached); noneg_theories is skipped because its test split is
#          single-class and the frozen summary itself records only an error there.
# cycle 2: all_items_S2 uses the registered S2 extractor. Its re-alignment is
#          cache-reachable because exp/e1_v2.py already ran it.
STRATA = {
    1: (("all_items", None, None),
        ("negation_theories", None, "negation")),
    2: (("all_items", None, None),
        ("all_items_S2", "s2", None)),
}

FROZEN = {
    "c1_local":       ("out/e1_summary.json", "temperature", 1),
    "c1_openrouter":  ("out/e1_summary_openrouter.json", "temperature", 1),
    "c2_panelA":      ("out/e1_v2_summary_panelA.json", "platt", 2),
    "c2_panelB":      ("out/e1_v2_summary_panelB.json", "platt", 2),
}


def load_panel(name: str):
    """Normalise both loader shapes to (items, calib_ids, cell)."""
    if name.startswith("c1_"):
        from exp.common import load_dataset, load_generations
        backend = name.split("_", 1)[1]
        items, calib_ids, _ = load_dataset()
        gens, _ = load_generations(items, calib_ids, backend=backend)
        return items, calib_ids, gens["cross_family_diverse_role"]
    from exp.run_generate_v2 import load_cell_v2
    from exp.v2_dataset import load_v2_items
    items, calib_ids, _ = load_v2_items()
    cell, _ = load_cell_v2(items, name.split("_", 1)[1])
    return items, calib_ids, cell


def _frozen_reproduction(name: str, res: dict, stratum: str = "all_items") -> dict:
    """Exact equality, at the committed artifacts' own serialized precision."""
    path, mapname, cycle = FROZEN[name]
    committed = json.loads(Path(path).read_text())["strata"][stratum]
    if cycle == 2:
        committed = committed["instrument_primary"]
        frozen_arms = committed["arms"]
        cov = {"covariate_frozen": committed["covariate_test_log_loss"]["gd"],
               "covariate_frozen_ml": committed["covariate_test_log_loss"]["ml"]}
        primaries = {a: committed["primary"][f"{a}_vs_covariate_gd"]["delta_log_loss"]
                     for a in ("WCT-U", "WCT-EM", "WCT-C")}
    else:
        frozen_arms = committed["arms"]
        cov = {"covariate_frozen": frozen_arms["covariate_baseline"]["test_log_loss"]}
        primaries = {a: committed["primary_delta_log_loss_vs_covariate"][a]["delta_log_loss"]
                     for a in ("WCT-U", "WCT-EM", "WCT-C")}

    checks = []

    def cmp(key, expected, got):
        checks.append({"key": key, "expected": expected, "got": got,
                       "match": expected == got})

    name_map = {"WCT-U": "WCT-U", "WCT-EM": "WCT-EM", "WCT-C": "WCT-C",
                "uncapped": "capped_unsigned", "prevalence_only": "prevalence_only"}
    for fname, ours in name_map.items():
        if fname not in frozen_arms:
            continue
        got = res["arms"][ours][mapname]
        for field in ("test_log_loss", "test_auroc", "test_accuracy"):
            if field in frozen_arms[fname]:
                cmp(f"arms.{fname}.{field}", frozen_arms[fname][field], got.get(field))
    for k, expected in cov.items():
        cmp(f"{k}.test_log_loss", expected, res["arms"][k][mapname]["test_log_loss"])
    for a, exp in primaries.items():
        got = res["primary_vs_covariate_frozen"][mapname][a]["delta_log_loss"]
        for field in ("point", "lo", "hi"):
            cmp(f"primary.{a}.{field}", round(exp[field], 5), round(got[field], 5))

    # A8 also covers the registered quantities beyond the arms and the primary
    cp = committed.get("co_primary_precision_at_k") or {}
    ours_cp = res["co_primary_precision_at_k"][mapname]
    for field in ("k", "WCT-EM", "WCT-U", "covariate_baseline"):
        if field in cp:
            cmp(f"co_primary.{field}", cp[field], ours_cp.get(field))
    wia = committed.get("within_item_auroc") or {}
    ours_w = res["within_item_auroc"][mapname]
    for field in ("point", "lo", "hi", "decision"):
        if field in wia:
            got = ours_w.get(field)
            cmp(f"within_item_auroc.{field}",
                round(wia[field], 5) if isinstance(wia[field], float) else wia[field],
                round(got, 5) if isinstance(got, float) else got)
    pn = committed.get("permutation_null") or {}
    ours_p = res["permutation_null"][mapname]
    for field in ("p", "observed", "null_mean", "null_sd", "n_perm"):
        if field in pn:
            got = ours_p.get(field)
            cmp(f"permutation_null.{field}",
                round(pn[field], 5) if isinstance(pn[field], float) else pn[field],
                round(got, 5) if isinstance(got, float) else got)
    # cycle-2's S1 block: same fields, same exactness
    if cycle == 2 and "S1_deny_filter" in (committed_src := json.loads(Path(path).read_text())["strata"][stratum]):
        cs1, os1 = committed_src["S1_deny_filter"], res.get("S1_deny_filter") or {}
        for arm, cv in (cs1.get("arms") or {}).items():
            ours = (os1.get("arms") or {}).get(
                {"uncapped": "capped_unsigned"}.get(arm, arm), {})
            got = ours.get(mapname, ours)
            for field in ("test_log_loss", "test_auroc"):
                if field in cv:
                    cmp(f"S1.arms.{arm}.{field}", cv[field], got.get(field))
        for key, cv in (cs1.get("primary") or {}).items():
            if not key.endswith("_vs_covariate_gd"):
                continue
            arm = key.split("_vs_")[0]
            mine = (os1.get("primary_vs_covariate_frozen") or {}).get(mapname, {}).get(arm)
            if mine:
                for f2 in ("point", "lo", "hi"):
                    cmp(f"S1.primary.{arm}.{f2}", round(cv["delta_log_loss"][f2], 5),
                        round(mine["delta_log_loss"][f2], 5))
        cmp("S1.audit.dropped", cs1.get("audit", {}).get("dropped"),
            (os1.get("audit") or {}).get("dropped"))

    # exact-ML primaries: cycle 2 registers them as a sensitivity row
    if cycle == 2:
        for a in primaries:
            src = committed["primary"].get(f"{a}_vs_covariate_ml")
            mine = res.get("primary_vs_covariate_ml", {}).get(mapname, {}).get(a)
            if src and mine:
                for f2 in ("point", "lo", "hi"):
                    cmp(f"primary_ml.{a}.{f2}", round(src["delta_log_loss"][f2], 5),
                        round(mine["delta_log_loss"][f2], 5))

    # co-primary bootstrap difference
    cpd = (committed.get("co_primary_precision_at_k") or {}).get("difference")
    if cpd:
        mine = (res["co_primary_precision_at_k"][mapname] or {}).get("difference") or {}
        for f2 in ("point", "lo", "hi"):
            cmp(f"co_primary.difference.{f2}", round(cpd[f2], 5),
                round(mine.get(f2, float('nan')), 5))

    # decisions, not just point estimates
    for a in primaries:
        src = (committed["primary"][f"{a}_vs_covariate_gd"] if cycle == 2
               else committed["primary_delta_log_loss_vs_covariate"][a])
        cmp(f"primary.{a}.decision", src["decision"],
            res["primary_vs_covariate_frozen"][mapname][a]["decision"])

    bad = [c for c in checks if not c["match"]]
    return {"map": mapname, "cycle": cycle, "source": path,
            "n_checks": len(checks), "n_mismatched": len(bad),
            "all_match": not bad, "mismatches": bad, "checks": checks}


def analyse_stratum(name, items, calib_ids, cell, iids, stratum, extractor, filt):
    from exp import e1
    if filt == "negation":
        iids = [i for i in iids if e1.is_negation_theory(i)]
    ext = None
    if extractor == "s2":
        from exp.e1_v2 import extract_s2
        ext = extract_s2
    rows, agents, audits = observe.build_rows(items, cell, iids, extractor=ext)
    y, V, riids, X = observe.to_arrays(rows, agents)
    is_calib = np.array([i in calib_ids for i in riids])
    te = ~is_calib
    u, s = observe.instance_arrays(rows)

    res = v3arms.analyse(rows, agents, y, V, riids, X, is_calib, u, s)
    if FROZEN[name][2] == 2:
        # cycle 2 registered S1 (drop deny votes self-contradicted by their own
        # trace) as an instrument variant and reports a full arm block for it,
        # so it is a frozen quantity like any other. The filter itself is the
        # FROZEN implementation, imported not reimplemented.
        from exp.e1_v2 import deny_filter
        by_id = {i.item_id: i for i in items}
        Vf, s1_audit = deny_filter(V, rows, agents, cell, by_id)
        res["S1_deny_filter"] = dict(
            v3arms.analyse(rows, agents, y, Vf, riids, X, is_calib, u, s),
            audit=s1_audit)
    res.update({
        "panel": name,
        "stratum": stratum,
        "agents": agents,
        "n_items": len(set(riids)),
        "n_props": len(rows),
        "prevalence": round(float(y.mean()), 4),
        "n_test_negatives": int((y[te] == 0).sum()),
        "alignment_audit": v3audit.panel_audit(items, iids, audits),
    })
    res["frozen_reproduction"] = _frozen_reproduction(name, res, stratum)
    return res


def analyse_panel(name: str) -> dict:
    items, calib_ids, cell = load_panel(name)
    from exp.common import complete_items
    iids = complete_items(cell, min_agents=2)
    cycle = FROZEN[name][2]
    strata = {}
    for stratum, extractor, filt in STRATA[cycle]:
        strata[stratum] = analyse_stratum(name, items, calib_ids, cell, iids,
                                          stratum, extractor, filt)
    out = dict(strata["all_items"])          # all_items stays at the top level
    out["strata"] = strata
    out["frozen_reproduction_all_strata"] = {
        "n_strata": len(strata),
        "all_match": all(s["frozen_reproduction"]["all_match"] for s in strata.values()),
        "per_stratum": {k: {"n_checks": s["frozen_reproduction"]["n_checks"],
                            "n_mismatched": s["frozen_reproduction"]["n_mismatched"]}
                        for k, s in strata.items()},
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="all", choices=("all",) + PANELS)
    ap.add_argument("--out-dir", default="out/v3")
    args = ap.parse_args()

    strict.install()          # zero inference, enforced before anything runs
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = PANELS if args.panel == "all" else (args.panel,)

    rc = 0
    for name in todo:
        res = analyse_panel(name)
        path = out_dir / f"reanalysis_{name}.json"
        path.write_text(json.dumps(res, indent=2, sort_keys=True, default=_jsonable))
        rep = res["frozen_reproduction_all_strata"]
        n_checks = sum(v["n_checks"] for v in rep["per_stratum"].values())
        n_bad = sum(v["n_mismatched"] for v in rep["per_stratum"].values())
        flag = "OK" if rep["all_match"] else f"MISMATCH x{n_bad}"
        ss = res["single_source"]["by_map"][FROZEN[name][1]]
        mapname = FROZEN[name][1]
        vs = res["panel_vs_single_best_calibration_selected"][mapname]["WCT-EM"]["delta_log_loss"]
        print(f"{name:16s} props={res['n_props']:4d} neg={res['n_test_negatives']:3d} "
              f"strata={rep['n_strata']} frozen={n_checks:2d} {flag:14s} "
              f"single={ss['calibration_selected']:10s} "
              f"panel-over-single={vs['point']:+.4f} [{vs['lo']:+.4f},{vs['hi']:+.4f}]")
        if not rep["all_match"]:
            rc = 1
            for sname, s in res["strata"].items():
                for m in s["frozen_reproduction"]["mismatches"][:4]:
                    print(f"    [{sname}] {m['key']}: expected {m['expected']} got {m['got']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
