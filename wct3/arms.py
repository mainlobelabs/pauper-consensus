"""Arms: the unbuilt single-source baseline (D1) and the capping x polarity 2x2 (D2).

Two corrections, both POST-HOC over frozen caches.

D1. `single_best_calibration_selected` is a REGISTERED arm — `prereg.yaml:166`,
`plan.md:488` baseline #1, simulated at `m0/simulate.py:75` — that no analysis
driver ever implemented, and `prereg_v2.yaml` dropped from its arm list without
comment. Without it, "the panel beats a covariate baseline" cannot be
distinguished from "one good model beats a covariate baseline", which is the
difference between the paper's claim and its evidence. The source is chosen on
CALIBRATION log-loss alone; `single_oracle` (chosen on test) is reported beside
it strictly as an upper bound, because quoting the oracle as if achievable is
the error `m0/ceiling.py:128-134` exists to prevent.

D2. The frozen `uncapped` arm scores `n_claims`, which equals `n_emitting`
identically (see `wct3.observe`): capped and unsigned. So the frozen comparison
against WCT-U varies capping AND polarity at once. The 2x2 varies them
separately:

                   signed                    unsigned
    capped      WCT-U (frozen)            the frozen "uncapped" arm
    uncapped    uncapped_signed           uncapped_unsigned (registered M6)
"""
from __future__ import annotations

import numpy as np

from exp import e1
from exp.recalib import fit_platt_map, fit_temperature_map
from wct import aggregate as agg
from wct import stats

FROZEN_DELTA = 0.02


def _both_maps(score, y, is_calib, allow_nonpositive=False):
    """Platt (cycle-2's registered map) and temperature (cycle-1's), both fitted
    on calibration only. Reporting both is what lets each cycle's frozen values
    reproduce under the map that cycle actually registered."""
    f_p, pp = fit_platt_map(score[is_calib], y[is_calib],
                            allow_nonpositive=allow_nonpositive)
    t = agg.fit_temperature(score[is_calib], y[is_calib])
    return {"platt": f_p(score), "temperature": agg.sigmoid(score / max(t, 1e-6)),
            "platt_params": pp, "temperature_t": round(float(t), 4)}


def _summarise(pred, y, te):
    au = agg.auroc(pred[te], y[te])
    return {"test_log_loss": round(agg.log_loss(pred[te], y[te]), 5),
            "test_auroc": None if au is None else round(au, 5),
            "test_accuracy": round(float(((pred[te] > 0.5).astype(int) == y[te]).mean()), 5)}


def analyse(rows, agents, y, V, iids, X, is_calib, inst_unsigned, inst_signed):
    """Every arm, both calibration maps, and the registered contrasts."""
    te = ~is_calib
    ti = [i for i, c in zip(iids, is_calib) if not c]
    out: dict = {"status": "POST-HOC", "seed": 20260807}

    # ---- score arms (frozen three, unchanged construction)
    scores = {
        "WCT-U": agg.wct_u(V),
        "WCT-EM": agg.em_logodds(V, agg.wct_em(V)[1]),
        "WCT-C": agg.em_logodds(V, agg.fit_supervised(V[is_calib], y[is_calib])),
    }
    # ---- the capping x polarity 2x2
    n_claims = np.array([r["n_claims"] for r in rows], dtype=float)
    m6 = {
        "capped_signed": scores["WCT-U"],          # == WCT-U, named for the 2x2
        "capped_unsigned": n_claims,               # what the frozen "uncapped" arm IS
        "uncapped_signed": inst_signed,
        "uncapped_unsigned": inst_unsigned,        # the registered M6 quantity
    }
    # ---- single-source arms (D1)
    per_agent = {}
    for j, a in enumerate(agents):
        per_agent[a] = agg.wct_u(V[:, [j]])

    maps: dict[str, dict] = {}
    for name, s in {**scores, **m6, **{f"single:{a}": v for a, v in per_agent.items()}}.items():
        maps[name] = _both_maps(s, y, is_calib, allow_nonpositive=True)

    # source selection: CALIBRATION log-loss only, no test information
    # Selection is PER MAP. The two cycles registered different calibration maps,
    # and the choice is not invariant across them: on cycle-1's local panel the
    # temperature map selects qwen (calib 0.38765) while Platt selects ornith
    # (0.20138). Selecting under one map and reporting the contrast under the
    # other silently mixes them, which is the defect this structure prevents.
    # Selection uses the UNROUNDED loss so rounding cannot flip a near-tie.
    sel_by_map, calib_ll_by_map, oracle_by_map = {}, {}, {}
    for m in ("platt", "temperature"):
        exact = {a: agg.log_loss(maps[f"single:{a}"][m][is_calib], y[is_calib])
                 for a in agents}
        sel_by_map[m] = min(exact, key=exact.get)
        calib_ll_by_map[m] = {a: round(v, 5) for a, v in exact.items()}
        test_ll = {a: agg.log_loss(maps[f"single:{a}"][m][te], y[te]) for a in agents}
        oracle_by_map[m] = min(test_ll, key=test_ll.get)

    # ---- covariate baselines: frozen (duplicated column), dedup, verbosity
    base = {}
    for variant, Xv in X.items():
        base[variant] = e1.predict_logistic(Xv, e1.fit_logistic(Xv[is_calib], y[is_calib]))
    base["frozen_ml"] = e1.predict_logistic(
        X["frozen"], _fit_ml(X["frozen"][is_calib], y[is_calib]))
    prevalence_only = np.full(len(y), float(y[is_calib].mean()))

    # ---- reporting
    arms: dict = {}
    for name in list(scores) + list(m6) + [f"single:{a}" for a in agents]:
        m = maps[name]
        arms[name] = {
            "platt": _summarise(m["platt"], y, te),
            "temperature": _summarise(m["temperature"], y, te),
            "platt_params": m["platt_params"], "temperature_t": m["temperature_t"],
        }
    arms["prevalence_only"] = {"platt": _summarise(prevalence_only, y, te),
                               "temperature": _summarise(prevalence_only, y, te)}
    for variant, p in base.items():
        arms[f"covariate_{variant}"] = {"platt": _summarise(p, y, te),
                                        "temperature": _summarise(p, y, te)}
    out["arms"] = arms

    out["single_source"] = {
        "note": "selected on CALIBRATION log-loss alone, SEPARATELY UNDER EACH MAP: "
                "the choice is not map-invariant (c1_local: temperature->qwen, "
                "Platt->ornith). `oracle_selected` is chosen on test and is an UPPER "
                "BOUND no unlabelled method can reach (m0/ceiling.py:128-134); it is "
                "never the baseline. Read the row for the map your cycle registered.",
        "by_map": {m: {"calibration_log_loss_per_agent": calib_ll_by_map[m],
                       "calibration_selected": sel_by_map[m],
                       "oracle_selected": oracle_by_map[m]}
                   for m in ("platt", "temperature")},
    }
    # Named arm rows the plan's REQUIRED_ARMS list calls for. covariate_baseline
    # is the registered name for the frozen covariate matrix; the two single-source
    # rows resolve, per map, to whichever agent that map selects — so a reader
    # never has to join metadata against a per-agent row to find them.
    for m in ("platt", "temperature"):
        arms.setdefault("covariate_baseline", {})[m] = arms["covariate_frozen"][m]
        arms.setdefault("single_best_calibration_selected", {})[m] = dict(
            arms[f"single:{sel_by_map[m]}"][m], agent=sel_by_map[m])
        arms.setdefault("single_oracle", {})[m] = dict(
            arms[f"single:{oracle_by_map[m]}"][m], agent=oracle_by_map[m],
            note="chosen on TEST; an upper bound no unlabelled method reaches")

    out["m6_2x2"] = {
        "note": "rows = capping, columns = polarity. paper.md 6.1 claims the ROW "
                "contrast (one vote per source) but the frozen arms only vary the "
                "COLUMN (signed vs unsigned), because n_claims == n_emitting.",
        "auroc_note": "raw_auroc is AUROC of the UNMAPPED score and is the quantity "
                      "the signal question asks. A fitted calibration map may take a "
                      "NEGATIVE slope on an arm carrying no signal (c1_local "
                      "capped_unsigned: Platt a=-0.0639), which reverses the ranking "
                      "and flips mapped AUROC about 0.5 -- a calibration artifact, "
                      "not a ranking fact. Mapped values are given under BOTH maps so "
                      "each cycle reads its own registered one.",
        "cells": {k: {"platt": arms[k]["platt"],
                      "temperature": arms[k]["temperature"],
                      "raw_auroc": (lambda a: None if a is None else round(a, 5))(
                          agg.auroc(m6[k][te], y[te])),
                      "platt_slope": arms[k]["platt_params"]["a"]}
                  for k in m6},
    }

    # ---- contrasts, frozen delta, frozen seed, item-block bootstrap
    def delta(a_pred, b_pred):
        d = stats.paired_item_diff(ti, e1._nll(a_pred[te], y[te]), e1._nll(b_pred[te], y[te]))
        return {"delta_log_loss": d, "delta": FROZEN_DELTA,
                "decision": stats.decision(d, FROZEN_DELTA)}

    # Contrasts are reported under BOTH calibration maps, because the two cycles
    # registered different ones: cycle 1 the intercept-less temperature, cycle 2
    # Platt. Comparing a cycle's frozen primary against the wrong map recovers
    # the missing-intercept effect (paper.md 4.1) instead of the frozen value.
    all_names = list(scores) + list(m6) + [f"single:{a}" for a in agents]
    vs_cov: dict = {"platt": {}, "temperature": {}}
    vs_cov_ml: dict = {"platt": {}, "temperature": {}}
    vs_single: dict = {"platt": {}, "temperature": {}}
    single_vs_cov: dict = {}
    for m in ("platt", "temperature"):
        sel_pred = maps[f"single:{sel_by_map[m]}"][m]     # the source THIS map selects
        for name in all_names:
            vs_cov[m][name] = delta(base["frozen"], maps[name][m])
            # cycle 2 registers an exact-ML refit as a sensitivity row beside the
            # GD fit; both are frozen quantities, so both must reproduce
            vs_cov_ml[m][name] = delta(base["frozen_ml"], maps[name][m])
        for name in scores:
            vs_single[m][name] = delta(sel_pred, maps[name][m])
        single_vs_cov[m] = delta(base["frozen"], sel_pred)
    out["primary_vs_covariate_frozen"] = vs_cov
    out["primary_vs_covariate_ml"] = vs_cov_ml
    out["panel_vs_single_best_calibration_selected"] = vs_single
    out["single_best_vs_covariate"] = single_vs_cov

    # sensitivity rows, explicitly labelled: the frozen baseline carries a
    # duplicated 'verbosity' column (it repeats coverage), so these two say what
    # the registered feature list actually described
    out["covariate_sensitivity"] = {
        "note": "SENSITIVITY. covariate_frozen is the registered matrix INCLUDING "
                "its duplicated column; dedup drops the duplicate; verbosity adds "
                "the per-item verbosity the registration named but the matrix "
                "never carried. Reported beside the frozen baseline, never instead.",
        "rows": {v: {"test_log_loss": arms[f"covariate_{v}"]["platt"]["test_log_loss"],
                     "test_auroc": arms[f"covariate_{v}"]["platt"]["test_auroc"],
                     "vs_frozen_baseline": {
                         m: delta(base["frozen"], base[v]) for m in ("platt",)}}
                 for v in ("dedup", "verbosity", "frozen_ml")},
    }
    # prevalence-only carries no calibration map (it IS a constant), but its
    # paired delta is still required alongside every other arm
    out["prevalence_only_vs_covariate"] = delta(base["frozen"], prevalence_only)

    # the remaining registered quantities, under BOTH maps so each cycle's
    # frozen values reproduce under the map that cycle registered
    out["co_primary_precision_at_k"] = {}
    out["within_item_auroc"] = {}
    out["permutation_null"] = {}
    for m in ("platt", "temperature"):
        pe = maps["WCT-EM"][m]
        pu = maps["WCT-U"][m]
        k_rule = int(((V == agg.AFFIRM).sum(1) >= 2)[te].sum())
        order = np.argsort(-pe[te])[:max(k_rule, 1)]
        order_u = np.argsort(-pu[te])[:max(k_rule, 1)]
        order_b = np.argsort(-base["frozen"][te])[:max(k_rule, 1)]
        affirm2 = ((V == agg.AFFIRM).sum(1) >= 2)[te]
        base_te = base["frozen"][te]

        def _prec_diff(rows_idx, _pe=pe):
            kk = int(affirm2[rows_idx].sum())
            if kk < 1:
                return None
            top = np.argsort(-_pe[te][rows_idx])[:kk]
            top_b = np.argsort(-base_te[rows_idx])[:kk]
            return float(y[te][rows_idx][top].mean() - y[te][rows_idx][top_b].mean())

        d_prec = stats.item_bootstrap(ti, _prec_diff, n_boot=2000)
        out["co_primary_precision_at_k"][m] = {
            "k": k_rule,
            "WCT-EM": round(float(y[te][order].mean()), 5),
            "WCT-U": round(float(y[te][order_u].mean()), 5),
            "covariate_baseline": round(float(y[te][order_b].mean()), 5),
            "difference": d_prec, "delta": 0.05,
            "decision": stats.decision(d_prec, 0.05),
        }

        def _wia(rows_idx, _pe=pe):
            vals, sub = [], np.array(ti)[rows_idx] if len(rows_idx) else []
            for iid in set(sub):
                a = agg.auroc(_pe[te][rows_idx][sub == iid], y[te][rows_idx][sub == iid])
                if a is not None:
                    vals.append(a)
            return float(np.mean(vals)) if vals else None

        wia = stats.item_bootstrap(ti, _wia, n_boot=1000)
        wia["decision"] = stats.decision(wia, 0.55)
        out["within_item_auroc"][m] = wia
        out["permutation_null"][m] = stats.within_item_permutation(
            ti, pe[te], y[te], lambda s_, yy: agg.auroc(s_, yy), n_perm=1000)
    return out


def _fit_ml(X, y, l2: float = 1.0):
    """cycle-2's registered exact-ML sensitivity fit (exp/e1_v2.fit_logistic_ml)."""
    from scipy.optimize import minimize
    Xb = np.hstack([np.ones((len(X), 1)), X])

    def nll(w):
        p = np.clip(agg.sigmoid(Xb @ w), 1e-12, 1 - 1e-12)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
                     + 0.5 * l2 * (w[1:] @ w[1:]))
    return minimize(nll, np.zeros(Xb.shape[1]), method="L-BFGS-B").x
