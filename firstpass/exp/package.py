"""Assemble the minimum result package (protocol 7.3) and the artifact map.

Every number quoted in the paper must be readable out of one of these files, so
that a reader who would rather check the analysis than take it on trust can.
Negative and inconclusive results are included on exactly the same footing as
positive ones -- protocol 7.3 identifies a boundary-condition negative as
potentially the most useful outcome of the study.
"""
from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

import yaml

ARTIFACTS = {
    "out/e0_summary.json": "E0 2x2 factorial: per-cell accuracy, rho, M_eff, "
                           "double-fault, dose-response",
    "out/e1_summary.json": "E1 primary/co-primary/descriptive, nulls, EM "
                           "parameters, alignment audit",
    "out/dataset_manifest.json": "item ids, depth and answer histograms, "
                                 "conjunctive-rule counts",
    "out/generation_index.json": "every generation: item, agent, model, role, "
                                 "seed, cell, trace length, error",
    "out/m0_ceiling.txt": "M0 invariants I8-I14: design effect, oracle ceiling, "
                          "estimator comparison, power",
    "out/m0_simulate.txt": "M0 invariants I1-I5 against known ground truth, "
                           "plus the D9 paired heterogeneous-panel result",
    "prereg.yaml": "the pre-registration frozen at R0",
    "out/cache/": "immutable content-hashed generation, embedding and NLI "
                  "artifacts; all analysis re-runs over this at zero inference cost",
}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unavailable"


def main() -> int:
    out = Path("out")
    out.mkdir(exist_ok=True)
    prereg = yaml.safe_load(Path("prereg.yaml").read_text())

    pkg = {
        "reproduction": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "seeds": {
                "dataset_split": prereg["dataset"]["split_seed"],
                "decode": prereg["decode"]["seeds"],
                "bootstrap": 20260807,
            },
            "panels": prereg["panels"],
            "decode": prereg["decode"],
        },
        "artifact_map": ARTIFACTS,
        "results": {},
        "gates": {},
    }

    for name in ("e0_summary", "e1_summary",
                 "e0_summary_openrouter", "e1_summary_openrouter"):
        p = out / f"{name}.json"
        if p.exists():
            pkg["results"][name] = json.loads(p.read_text())

    for panel, key in (("local", "e1_summary"),
                       ("openrouter", "e1_summary_openrouter")):
        _gates_for(pkg, panel, pkg["results"].get(key, {}))

    pkg["panel_comparison"] = _compare_panels(pkg)
    pkg["failed_and_negative_results"] = _negatives(pkg)
    (out / "result_package.json").write_text(json.dumps(pkg, indent=2, sort_keys=True))

    print("RESULT PACKAGE")
    print(json.dumps(pkg["gates"], indent=2)[:1500])
    print("\npanel comparison:")
    print(json.dumps(pkg["panel_comparison"], indent=2))
    print("\nnegative / inconclusive:")
    for n in pkg["failed_and_negative_results"]:
        print(f"  - {n}")
    print("\nwrote out/result_package.json")
    return 0


def _gates_for(pkg: dict, panel: str, e1: dict) -> None:
    """Register every gate under its PANEL, so a flip between panels is visible."""
    for stratum, s in (e1.get("strata") or {}).items():
        tag = f"{panel}:E1[{stratum}]"
        if s.get("error"):
            pkg["gates"][tag] = {
                "panel": panel, "metric": "not evaluable", "decision": "undefined",
                "reason": s["error"], "prevalence": s.get("prevalence"),
            }
            continue
        for arm, r in (s.get("primary_delta_log_loss_vs_covariate") or {}).items():
            pkg["gates"][f"{tag}_primary_{arm}"] = {
                "panel": panel,
                "metric": "delta log-loss vs covariate baseline",
                "delta": r["delta"],
                "estimate": r["delta_log_loss"]["point"],
                "ci": [r["delta_log_loss"]["lo"], r["delta_log_loss"]["hi"]],
                "decision": r["decision"],
            }
        a = s.get("within_item_auroc") or {}
        if a:
            pkg["gates"][f"{tag}_within_item_auroc"] = {
                "panel": panel,
                "metric": "within-item AUROC, WCT-EM",
                "delta": a.get("delta"), "estimate": a.get("point"),
                "ci": [a.get("lo"), a.get("hi")], "decision": a.get("decision"),
                "degenerate_interval": a.get("lo") == a.get("hi"),
            }


def _compare_panels(pkg: dict) -> dict:
    """The registered primary, side by side. A flip here is the headline result."""
    out = {}
    for stratum in ("all_items", "negation_theories"):
        row = {}
        for panel in ("local", "openrouter"):
            g = pkg["gates"].get(f"{panel}:E1[{stratum}]_primary_WCT-EM")
            if g:
                row[panel] = {"estimate": g["estimate"], "ci": g["ci"],
                              "decision": g["decision"]}
        if len(row) == 2:
            row["verdict_flips"] = (row["local"]["decision"]
                                    != row["openrouter"]["decision"])
        out[stratum] = row
    return out


def _negatives(pkg: dict) -> list[str]:
    """Collect everything that did not go the study's way, explicitly."""
    neg = []
    for k, g in pkg["gates"].items():
        if g.get("decision") != "go":
            neg.append(f"{k}: {g.get('decision')} "
                       f"(estimate {g.get('estimate')}, delta {g.get('delta')})")
    e0 = pkg["results"].get("e0_summary", {})
    contrast = e0.get("registered_contrast_family_diversity", {})
    for role, c in contrast.items():
        red = c.get("rho_reduction")
        if red is not None and red <= 0:
            neg.append(
                f"E0 registered prediction FAILED for {role}: cross-family rho "
                f"{c['cross_family_rho']} is not below same-family rho "
                f"{c['same_family_rho']} (reduction {red})")
    if not Path("out/e1_summary_openrouter.json").exists():
        neg.append("OpenRouter panel NOT YET ANALYSED: the pre-registration "
                   "names it the PRIMARY panel and the local panel the "
                   "replication, so until it lands every result here rests on "
                   "one panel of three named models and supports no claim "
                   "about model families as a population (assumption M10)")
    return neg


if __name__ == "__main__":
    raise SystemExit(main())
