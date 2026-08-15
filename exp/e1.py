"""E1 — does unique-source support predict proposition correctness? (protocol 3.3)

This is the first direct test of the proposed claim-quality signal, and it is
the cheapest place where Claim A can die. Everything is item-blocked (defect
D5): propositions are nested within items, so a proposition-level bootstrap
would let item difficulty masquerade as proposition-level signal.

The registered primary is held-out delta log-loss for WCT-EM against a covariate
baseline that receives IDENTICAL calibration treatment. The covariate baseline
matters more than it looks: without it, "support predicts truth" cannot be
distinguished from "shallow propositions are both more agreed-upon and more
often true".

Usage:  .venv/bin/python -m exp.e1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from exp.common import PREREG, complete_items, load_dataset, load_generations
from wct import aggregate as agg
from wct import cluster, stats
from wct.extract import extract
from wct.schema import Item


# --------------------------------------------------------------- baseline
def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0,
                 iters: int = 400, lr: float = 0.1) -> np.ndarray:
    """Plain L2 logistic regression by gradient descent.

    Deliberately simple and fully in-repo: the baseline must be reproducible
    from the artifacts without pinning a modelling library's defaults.
    """
    Xb = np.hstack([np.ones((len(X), 1)), X])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = agg.sigmoid(Xb @ w)
        g = Xb.T @ (p - y) / len(y) + l2 * np.r_[0.0, w[1:]] / len(y)
        w -= lr * g
    return w


def predict_logistic(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    return agg.sigmoid(np.hstack([np.ones((len(X), 1)), X]) @ w)


# ------------------------------------------------------------- build data
def build_observations(items: list[Item], cell: dict, iids: list[str]):
    """Extract, align and assemble the per-proposition design matrix."""
    by_id = {i.item_id: i for i in items}
    agents = sorted({a for iid in iids for a in cell[iid]})
    rows, audits = [], []

    for iid in iids:
        item = by_id[iid]
        claims = []
        for a, g in sorted(cell[iid].items()):
            if g.trace.strip() and not g.error:
                claims.extend(extract(g, item))
        if not claims:
            continue
        obs, audit = cluster.align_anchored(item, claims, k=PREREG["measurement"]["nli"]["top_k"])
        audit.update(cluster.alignment_audit(item, claims, obs))
        audit["item_id"] = iid
        audits.append(audit)

        props = cluster.canonical_propositions(item)
        pids = [p.pid for p in props]
        V = agg.vote_matrix(obs, agents, pids)

        # claim-instance counts for the uncapped ablation (assumption M6)
        counts = np.zeros(len(pids))
        for o in obs:
            counts[pids.index(o.pid)] += 1

        for k, p in enumerate(props):
            if p.y is None:
                continue                      # Unknown: excluded from primary
            emitting = int((V[k] != agg.MISSING).sum())
            if emitting == 0:
                continue                      # nobody mentioned it: not rankable
            rows.append({
                "item_id": iid, "pid": p.pid, "y": p.y, "qdep": p.qdep,
                "votes": V[k].copy(), "n_emitting": emitting,
                "n_claims": counts[k], "text_len": len(p.text),
            })
    return rows, agents, audits


def to_arrays(rows, agents):
    y = np.array([r["y"] for r in rows])
    V = np.stack([r["votes"] for r in rows])
    iids = [r["item_id"] for r in rows]
    # covariates: depth, coverage, verbosity, length -- everything EXCEPT the
    # signed cross-agent support that WCT is being credited for
    X = np.array([[r["qdep"], r["n_emitting"], r["n_claims"], r["text_len"] / 50.0]
                  for r in rows], dtype=float)
    return y, V, iids, X


# ------------------------------------------------------------------ main
# ProofWriter theory families. In a *Noneg* theory nothing is stated with
# negation, so no positive proposition can ever be DISPROVED -- it is True or it
# is Unknown. Those items therefore contribute only y=1 propositions and cannot
# inform a truth-discrimination measurement at all. Splitting on this is a
# validity restriction, not a difficulty filter, and it is reported as a
# stratum rather than substituted for the frozen primary.
NEG_FAMILIES = ("RelNeg", "AttNeg")


def is_negation_theory(item_id: str) -> bool:
    return item_id.split("-")[0] in NEG_FAMILIES


def analyse(items, calib_ids, cell, iids, label: str) -> dict:
    rows, agents, audits = build_observations(items, cell, iids)
    if len(rows) < 50:
        return {"stratum": label, "n_props": len(rows),
                "error": "too few scored propositions"}
    y, V, riids, X = to_arrays(rows, agents)
    is_calib = np.array([i in calib_ids for i in riids])
    print(f"[{label}] propositions {len(y)} (calib {is_calib.sum()}, "
          f"test {(~is_calib).sum()}) items {len(set(riids))} "
          f"prevalence {y.mean():.4f}")
    if y[~is_calib].min() == y[~is_calib].max():
        return {"stratum": label, "n_props": int(len(y)),
                "n_items": len(set(riids)),
                "prevalence": round(float(y.mean()), 4),
                "error": "test split contains a single class; truth "
                         "discrimination is undefined here by construction"}

    out: dict = {"stratum": label, "n_props": int(len(y)),
                 "n_items": len(set(riids)), "agents": agents,
                 "prevalence": round(float(y.mean()), 4)}

    # ---------------- arms. Everything fitted on calib, applied to test.
    u = agg.wct_u(V)
    q_em, em_params = agg.wct_em(V)
    lo_em = agg.em_logodds(V, em_params)
    sup = agg.fit_supervised(V[is_calib], y[is_calib])
    lo_c = agg.em_logodds(V, sup)

    t_u = agg.fit_temperature(u[is_calib], y[is_calib])
    t_em = agg.fit_temperature(lo_em[is_calib], y[is_calib])
    t_c = agg.fit_temperature(lo_c[is_calib], y[is_calib])
    w = fit_logistic(X[is_calib], y[is_calib])

    preds = {
        "WCT-U": agg.sigmoid(u / t_u),
        "WCT-EM": agg.sigmoid(lo_em / t_em),
        "WCT-C": agg.sigmoid(lo_c / t_c),
        "covariate_baseline": predict_logistic(X, w),
        "uncapped": agg.sigmoid(
            np.array([r["n_claims"] for r in rows])
            / max(agg.fit_temperature(
                np.array([r["n_claims"] for r in rows])[is_calib], y[is_calib]), 1e-6)),
        "prevalence_only": np.full(len(y), float(y[is_calib].mean())),
    }
    out["temperatures"] = {"WCT-U": round(t_u, 3), "WCT-EM": round(t_em, 3),
                           "WCT-C": round(t_c, 3)}
    out["em_parameters"] = {
        "agents": agents,
        "sensitivity": [round(float(v), 4) for v in em_params.sens],
        "false_positive_rate": [round(float(v), 4) for v in em_params.fpr],
        "coverage_given_true": [round(float(v), 4) for v in em_params.cov1],
        "coverage_given_false": [round(float(v), 4) for v in em_params.cov0],
        "note": "estimated from the vote matrix alone; no truth labels consumed",
    }

    te = ~is_calib
    ti = [i for i, c in zip(riids, is_calib) if not c]
    out["arms"] = {}
    for name, p in preds.items():
        ll = agg.log_loss(p[te], y[te])
        au = agg.auroc(p[te], y[te])
        out["arms"][name] = {
            "test_log_loss": round(ll, 5),
            "test_auroc": None if au is None else round(au, 5),
            "test_accuracy": round(float(((p[te] > 0.5).astype(int) == y[te]).mean()), 5),
        }

    # ---------------- registered primary: delta log-loss vs covariate baseline
    base = preds["covariate_baseline"]
    prim = {}
    for name in ("WCT-EM", "WCT-U", "WCT-C"):
        p = preds[name]
        per_prop_base = _nll(base[te], y[te])
        per_prop_arm = _nll(p[te], y[te])
        d = stats.paired_item_diff(ti, per_prop_base, per_prop_arm)  # base - arm
        prim[name] = {
            "delta_log_loss": d,
            "delta": PREREG["E1"]["primary"]["delta"],
            "decision": stats.decision(d, PREREG["E1"]["primary"]["delta"]),
        }
    out["primary_delta_log_loss_vs_covariate"] = prim

    # ---------------- co-primary: precision@k
    k_rule = int(((V == agg.AFFIRM).sum(1) >= 2)[te].sum())
    out["co_primary_precision_at_k"] = {"k": k_rule}
    for name in ("WCT-EM", "WCT-U", "covariate_baseline"):
        p = preds[name][te]
        order = np.argsort(-p)[:max(k_rule, 1)]
        out["co_primary_precision_at_k"][name] = round(float(y[te][order].mean()), 5)

    # ---------------- descriptive: within-item AUROC, bootstrapped
    def within_item_auroc(rows_idx):
        vals = []
        sub_ids = np.array(ti)[rows_idx] if len(rows_idx) else []
        pe, ye = preds["WCT-EM"][te], y[te]
        for iid in set(sub_ids):
            m = sub_ids == iid
            a = agg.auroc(pe[rows_idx][m], ye[rows_idx][m])
            if a is not None:
                vals.append(a)
        return float(np.mean(vals)) if vals else None

    out["within_item_auroc"] = stats.item_bootstrap(ti, within_item_auroc, n_boot=1000)
    out["within_item_auroc"]["delta"] = PREREG["E1"]["descriptive"]["delta"]
    out["within_item_auroc"]["decision"] = stats.decision(
        out["within_item_auroc"], PREREG["E1"]["descriptive"]["delta"])

    # ---------------- null: permute truth WITHIN item
    out["permutation_null"] = stats.within_item_permutation(
        ti, preds["WCT-EM"][te], y[te],
        lambda s, yy: agg.auroc(s, yy),
        n_perm=PREREG["E1"]["nulls"]["within_item_truth_permutation"],
    )

    # ---------------- measurement audit (assumption M5)
    by_id = {i.item_id: i for i in items if i.item_id in set(iids)}
    probe_n = probe_hit = probe_wrong_prop = probe_wrong_pol = 0
    for iid in iids:
        pr = cluster.aligner_probe(by_id[iid], k=PREREG["measurement"]["nli"]["top_k"])
        if pr.get("n"):
            probe_n += pr["n"]
            probe_hit += round(pr["self_identification"] * pr["n"])
            probe_wrong_prop += pr["wrong_proposition"]
            probe_wrong_pol += pr["wrong_polarity"]

    rec = [a["recall"] for a in audits if a.get("recall") is not None]
    n_ref = int(sum(a.get("n_reference", 0) for a in audits))
    n_pred = int(sum(a["n_observations"] for a in audits))
    out["alignment_audit"] = {
        "aligner_self_identification": {
            "n_probes": probe_n,
            "accuracy": round(probe_hit / probe_n, 4) if probe_n else None,
            "wrong_proposition": probe_wrong_prop,
            "wrong_polarity": probe_wrong_pol,
            "note": "PRIMARY mapper diagnostic. Each canonical proposition's own "
                    "surface text and its negated form are fed back as pseudo-claims; "
                    "no model output, no reasoning and no truth label is involved, so "
                    "a failure here is unambiguously a measurement failure.",
        },
        "lexical_reference": {
            "n_reference": n_ref,
            "n_predicted": n_pred,
            "recall_mean": round(float(np.mean(rec)), 4) if rec else None,
            "note": "SECONDARY and deliberately partial. The lexical reference "
                    "fires only on near-verbatim non-conditional restatements, so it "
                    "covers a small fraction of observations. Recall against it is "
                    "meaningful; PRECISION against it is not reported, because an "
                    "aligner observation absent from a low-coverage reference is "
                    "unlabelled rather than wrong.",
        },
        "same_agent_conflicts": int(sum(a["same_agent_conflicts"] for a in audits)),
        "observations": n_pred,
        "claims": int(sum(a["n_claims"] for a in audits)),
        "note": "measures the MAPPER, not whether the agent was right (that is "
                "panel accuracy, in E0).",
    }

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='local', choices=['local', 'openrouter'])
    args = ap.parse_args()
    items, calib_ids, test_ids = load_dataset()
    gens, coverage = load_generations(items, calib_ids, backend=args.backend)
    cell = gens["cross_family_diverse_role"]
    iids = complete_items(cell, min_agents=2)
    print(f"coverage {coverage}; usable items {len(iids)}")

    neg = [i for i in iids if is_negation_theory(i)]
    noneg = [i for i in iids if not is_negation_theory(i)]

    strata = {
        # the frozen primary: every usable item, exactly as pre-registered
        "all_items": iids,
        # validity restriction: only theories in which a positive proposition
        # CAN be false. Reported alongside, never instead.
        "negation_theories": neg,
        # reported to make the point rather than to hide it: this stratum is
        # incapable of a negative and its AUROC is undefined by construction
        "noneg_theories": noneg,
    }
    out = {"coverage": coverage, "strata": {}}
    for label, subset in strata.items():
        if len(subset) < 5:
            continue
        out["strata"][label] = analyse(items, calib_ids, cell, subset, label)

    Path("out").mkdir(exist_ok=True)
    # panel-specific filename so a replication can never overwrite the primary
    suffix = "" if args.backend == "local" else "_openrouter"
    outfile = Path(f"out/e1_summary{suffix}.json")
    outfile.write_text(json.dumps(out, indent=2, sort_keys=True))
    for label, r in out["strata"].items():
        print(f"\n===== {label} =====")
        if r.get("error"):
            print(f"  n_props={r.get('n_props')} prevalence={r.get('prevalence')}")
            print(f"  {r['error']}")
            continue
        print(f"  n_props {r['n_props']}  items {r['n_items']}  "
              f"prevalence {r['prevalence']}")
        for arm, v in r["arms"].items():
            print(f"    {arm:<20} logloss {v['test_log_loss']:>8.4f}  "
                  f"auroc {str(v['test_auroc']):>8}  acc {v['test_accuracy']:.4f}")
        for arm, v in r["primary_delta_log_loss_vs_covariate"].items():
            d = v["delta_log_loss"]
            print(f"    PRIMARY {arm:<10} dLL {d['point']:+.4f} "
                  f"[{d['lo']:+.4f},{d['hi']:+.4f}] -> {v['decision'].upper()}")
        a = r["within_item_auroc"]
        print(f"    within-item AUROC {a['point']} [{a['lo']},{a['hi']}] "
              f"-> {a['decision'].upper()}")
        print(f"    permutation null p={r['permutation_null']['p']} "
              f"(observed {r['permutation_null']['observed']}, "
              f"null {r['permutation_null']['null_mean']})")
    print("\nwrote", outfile)
    return 0


def _nll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


if __name__ == "__main__":
    raise SystemExit(main())
