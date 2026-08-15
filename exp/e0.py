"""E0 — model-family x role-prompt calibration (protocol 3.2).

The 2x2 factorial exists because defect D4 is otherwise unfixable: giving nodes
different expert instructions in order to engineer divergence confounds
model-family diversity with role-prompt diversity, and a same-architecture
ablation alone cannot separate them.

E0 makes no continuation claim. It measures rho, M_eff, double-fault rate and
consensus accuracy per cell, and it checks the registered directional
prediction that cross-family panels carry lower residual error correlation than
same-family ones. If they do not, premise (a) of Claim A has failed at its
cheapest possible test.

Usage:  .venv/bin/python -m exp.e0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from exp.common import CELLS, PREREG, complete_items, load_dataset, load_generations
from wct import stats
from wct.extract import answer_of, has_conjunctive_step


def cell_table(cell_name: str, cell: dict, items_by_id: dict) -> dict:
    """Per-cell accuracy, dependence and consensus, on items all agents answered."""
    iids = complete_items(cell, min_agents=2)
    agents = sorted({a for iid in iids for a in cell[iid]})
    rows, keep = [], []
    for iid in iids:
        truth = items_by_id[iid].answer
        got = {}
        for a in agents:
            g = cell[iid].get(a)
            got[a] = answer_of(g) if g else None
        if any(v is None for v in got.values()):
            continue          # registered exclusion: unparseable verdict
        keep.append(iid)
        rows.append([1 if got[a] == truth else 0 for a in agents])
    if not rows:
        return {"cell": cell_name, "n_items": 0}

    correct = np.array(rows, dtype=bool)
    n, m = correct.shape
    per_agent = {a: round(float(correct[:, i].mean()), 4) for i, a in enumerate(agents)}

    # majority vote with an explicit tie policy; M=3 is odd so ties cannot occur
    votes = correct.sum(1)
    consensus = float((votes > m / 2).mean())

    # same-wrong convergence: all agents wrong AND agreeing on the same verdict
    same_wrong = 0
    for r, iid in enumerate(keep):
        if correct[r].any():
            continue
        verdicts = {answer_of(cell[iid][a]) for a in agents}
        same_wrong += int(len(verdicts) == 1)

    dep = stats.error_correlation(correct)
    df = stats.double_fault(correct)
    disagree = float(np.mean([
        (correct[:, i] != correct[:, j]).mean()
        for i in range(m) for j in range(i + 1, m)
    ])) if m > 1 else 0.0

    ci = stats.item_bootstrap(
        keep, lambda rows_: float((correct[rows_].sum(1) > m / 2).mean())
    )
    conj = {
        a: round(float(np.mean([
            has_conjunctive_step(cell[iid][a]) for iid in keep if a in cell[iid]
        ])), 4) for a in agents
    }
    return {
        "cell": cell_name,
        "n_items": n,
        "agents": agents,
        "per_agent_accuracy": per_agent,
        "mean_single_accuracy": round(float(correct.mean()), 4),
        "best_agent_accuracy": round(float(max(per_agent.values())), 4),
        "consensus_accuracy": round(consensus, 4),
        "consensus_ci": ci,
        "gain_over_mean_single": round(consensus - float(correct.mean()), 4),
        "gain_over_best_agent": round(consensus - max(per_agent.values()), 4),
        "pairwise_disagreement": round(disagree, 4),
        "double_fault": df,
        "dependence": dep,
        "same_wrong_convergence": round(same_wrong / max(n, 1), 4),
        "states_conjunctive_step": conj,
        "item_ids": keep,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='local', choices=['local', 'openrouter'])
    args = ap.parse_args()
    items, calib, test = load_dataset()
    by_id = {i.item_id: i for i in items}
    gens, coverage = load_generations(items, calib, backend=args.backend)
    print(f"generation coverage: {coverage}")

    results = {"coverage": coverage, "cells": {}}
    for c in CELLS:
        r = cell_table(c, gens[c], by_id)
        results["cells"][c] = r
        if r["n_items"]:
            print(f"\n{c}: n={r['n_items']}")
            print(f"  per-agent {r['per_agent_accuracy']}")
            print(f"  consensus {r['consensus_accuracy']:.4f}  "
                  f"(mean single {r['mean_single_accuracy']:.4f}, "
                  f"best {r['best_agent_accuracy']:.4f})")
            print(f"  rho {r['dependence']['rho']}  M_eff {r['dependence']['m_eff']}"
                  f"  double-fault ratio {r['double_fault']['ratio']}")

    # ---- registered contrast: does cross-family lower dependence? ----
    def rho_of(c):
        return results["cells"][c].get("dependence", {}).get("rho")

    contrasts = {}
    for role in ("same_role", "diverse_role"):
        cf, sf = f"cross_family_{role}", f"same_family_{role}"
        a, b = rho_of(cf), rho_of(sf)
        contrasts[role] = {
            "cross_family_rho": a, "same_family_rho": b,
            "rho_reduction": None if (a is None or b is None) else round(b - a, 5),
            "cross_family_m_eff": results["cells"][cf].get("dependence", {}).get("m_eff"),
            "same_family_m_eff": results["cells"][sf].get("dependence", {}).get("m_eff"),
        }
    results["registered_contrast_family_diversity"] = contrasts

    # ---- dose-response: consensus gain against measured M_eff ----
    pts = [(results["cells"][c]["dependence"]["m_eff"],
            results["cells"][c]["gain_over_mean_single"], c)
           for c in CELLS if results["cells"][c].get("n_items")
           and results["cells"][c]["dependence"]["m_eff"] is not None]
    results["dose_response"] = {
        "points": [{"m_eff": round(m, 4), "gain": g, "cell": c} for m, g, c in pts],
        "slope": (round(float(np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)[0]), 5)
                  if len(pts) >= 2 else None),
        "note": "gain regressed on MEASURED M_eff; compare against the M0 curve "
                "in m0/simulate.py report_i1_i2, which is the same quantity "
                "under known ground truth.",
    }

    Path("out").mkdir(exist_ok=True)
    # panel-specific filename so a replication can never overwrite the primary
    suffix = "" if args.backend == "local" else "_openrouter"
    outfile = Path(f"out/e0_summary{suffix}.json")
    outfile.write_text(json.dumps(results, indent=2, sort_keys=True))
    print("\nwrote", outfile)
    print("registered contrast:", json.dumps(contrasts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
