"""POST-HOC calibration diagnostic for E1. NOT a replacement for the primary.

Read this first, because the whole point of this study is that post-hoc
analysis choices move results:

  The registered primary is, and remains, held-out delta log-loss for WCT-EM
  against the covariate baseline under a SINGLE FITTED TEMPERATURE, frozen at
  R0 with delta = 0.02. Its verdict stands: STOP on panel A, GO on panel B.
  Nothing in this file changes that, and nothing here may be reported as if it
  were the registered outcome.

What this file asks is a different and strictly diagnostic question: WHERE does
panel A's failure live? A held-out log-loss can fail for two unrelated reasons
-- the score may not rank truth (discrimination), or it may rank truth well
while emitting badly-scaled probabilities (calibration). The E1 arm table says
these are not the same story on panel A: WCT-EM reaches AUROC 0.891 there, far
above the covariate baseline's 0.598, while its log-loss is 0.385 against the
baseline's 0.210. High discrimination with bad log-loss is the signature of a
calibration failure.

The design isolates that cleanly. Every calibration map compared here is
MONOTONE in the underlying score, so AUROC, precision@k and the selector's
operating point are mathematically unchanged by construction -- the script
asserts this rather than assuming it. Only log-loss can move. Anything that
moves is therefore calibration and nothing else.

Three maps, each fitted on the CALIBRATION split alone and applied unchanged to
test, exactly as the registered pipeline does:

  temperature  sigmoid(s / t)          1 parameter   <- REGISTERED
  platt        sigmoid(a*s + b)        2 parameters
  isotonic     PAVA step function      nonparametric

The asymmetry that motivates the middle row: the covariate baseline is a
logistic regression, so it is fitted WITH an intercept and can match the base
rate. The WCT arms are calibrated by a temperature, which is a positive scalar
divisor and therefore has NO intercept -- at a test prevalence of 0.94 they are
structurally unable to shift toward the base rate however well they rank. The
registered primary compares the two anyway. Platt scaling gives the WCT arms
the same two parameters the baseline already had, which is the like-for-like
comparison the registered one is not.

Usage:  .venv/bin/python -m exp.recalib
Reads cache only. Zero inference cost, zero API calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from exp.common import PREREG, complete_items, load_dataset, load_generations
from exp.e1 import _nll, build_observations, fit_logistic, is_negation_theory, predict_logistic, to_arrays
from wct import aggregate as agg
from wct import stats

ARMS = ("WCT-EM", "WCT-U", "WCT-C")
MAPS = ("temperature", "platt", "isotonic")


# ------------------------------------------------------------ calibration maps
def fit_temperature_map(s: np.ndarray, y: np.ndarray):
    """REGISTERED: one positive scalar divisor. No intercept."""
    t = agg.fit_temperature(s, y)
    return lambda z: agg.sigmoid(z / t), {"t": round(float(t), 4)}


def fit_platt_map(s: np.ndarray, y: np.ndarray):
    """sigmoid(a*s + b). Monotone whenever a > 0, which is asserted downstream.

    Fitted by L-BFGS on the exact log-loss rather than by the gradient descent
    used for the covariate baseline: that baseline's fixed 400 steps at lr 0.1
    are adequate for its standardised covariates but would underfit raw EM
    log-odds, which run to +/-60 and would make the comparison a statement
    about the optimiser instead of about the parameterisation.
    """
    sd = float(s.std()) or 1.0
    z = s / sd                                   # scale only; a absorbs it back

    def nll(w):
        p = np.clip(agg.sigmoid(w[0] * z + w[1]), 1e-12, 1 - 1e-12)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())

    r = minimize(nll, np.array([1.0, 0.0]), method="L-BFGS-B")
    a, b = float(r.x[0]) / sd, float(r.x[1])
    return lambda q: agg.sigmoid(a * q + b), {"a": round(a, 6), "b": round(b, 4)}


def _pava(y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Pool adjacent violators. In-repo rather than sklearn, matching the
    baseline's rule that nothing rests on a library's defaults."""
    val, wt, cnt = list(y.astype(float)), list(w.astype(float)), [1] * len(y)
    i = 0
    while i < len(val) - 1:
        if val[i] <= val[i + 1] + 1e-12:
            i += 1
            continue
        tw = wt[i] + wt[i + 1]
        val[i] = (val[i] * wt[i] + val[i + 1] * wt[i + 1]) / tw
        wt[i], cnt[i] = tw, cnt[i] + cnt[i + 1]
        del val[i + 1], wt[i + 1], cnt[i + 1]
        if i > 0:
            i -= 1
    return np.repeat(np.array(val), np.array(cnt))


def fit_isotonic_map(s: np.ndarray, y: np.ndarray):
    """Nonparametric monotone fit, clipped away from 0/1.

    Clipping is not cosmetic: an unclipped isotonic block that is pure in one
    class emits probability exactly 0 or 1, and a single test point falling in
    it the wrong way returns infinite log-loss. The clip is set at the
    resolution one calibration point can support, 1/(2n).
    """
    order = np.argsort(s, kind="mergesort")
    xs, ys = s[order], y[order].astype(float)
    fit = _pava(ys, np.ones(len(ys)))
    eps = 1.0 / (2 * len(ys))
    fit = np.clip(fit, eps, 1 - eps)
    return lambda q: np.interp(q, xs, fit, left=fit[0], right=fit[-1]), {
        "n_blocks": int(len(np.unique(np.round(fit, 9)))), "clip": round(eps, 5)
    }


FITTERS = {"temperature": fit_temperature_map, "platt": fit_platt_map,
           "isotonic": fit_isotonic_map}


# ------------------------------------------------------------------- analysis
def analyse(items, calib_ids, cell, iids, label: str) -> dict:
    rows, agents, _ = build_observations(items, cell, iids)
    if len(rows) < 50:
        return {"stratum": label, "error": "too few scored propositions"}
    y, V, riids, X = to_arrays(rows, agents)
    is_calib = np.array([i in calib_ids for i in riids])
    te = ~is_calib
    if y[te].min() == y[te].max():
        return {"stratum": label, "n_props": int(len(y)),
                "prevalence": round(float(y.mean()), 4),
                "error": "test split contains a single class; undefined here"}
    ti = [i for i, c in zip(riids, is_calib) if not c]

    # raw scores, identical to the registered pipeline
    scores = {
        "WCT-U": agg.wct_u(V),
        "WCT-EM": agg.em_logodds(V, agg.wct_em(V)[1]),
        "WCT-C": agg.em_logodds(V, agg.fit_supervised(V[is_calib], y[is_calib])),
    }
    # the baseline is untouched: it already carries an intercept and is exactly
    # the arm the registered primary measures against
    base = predict_logistic(X, fit_logistic(X[is_calib], y[is_calib]))
    base_nll = _nll(base[te], y[te])

    out = {"stratum": label, "n_props": int(len(y)), "n_items": len(set(riids)),
           "n_test_props": int(te.sum()), "n_test_negatives": int((y[te] == 0).sum()),
           "prevalence_test": round(float(y[te].mean()), 4),
           "covariate_baseline": {
               "test_log_loss": round(agg.log_loss(base[te], y[te]), 5),
               "test_auroc": round(agg.auroc(base[te], y[te]), 5),
               "mean_predicted": round(float(base[te].mean()), 4),
           },
           "arms": {}}

    for arm, s in scores.items():
        au_raw = agg.auroc(s[te], y[te])          # unrounded: the assertion below
        rec: dict = {"auroc_raw_score": round(au_raw, 5), "maps": {}}
        for m in MAPS:
            f, params = FITTERS[m](s[is_calib], y[is_calib])
            p = f(s)
            ll = agg.log_loss(p[te], y[te])
            au = agg.auroc(p[te], y[te])
            d = stats.paired_item_diff(ti, base_nll, _nll(p[te], y[te]))
            rec["maps"][m] = {
                "params": params,
                "test_log_loss": round(ll, 5),
                "test_auroc": round(au, 5),
                "mean_predicted": round(float(p[te].mean()), 4),
                "calibration_in_the_large": round(float(p[te].mean() - y[te].mean()), 4),
                "delta_log_loss_vs_covariate": d,
                "decision": stats.decision(d, PREREG["E1"]["primary"]["delta"]),
                "registered": m == "temperature",
            }
            # The isolation argument requires the map to preserve ranking.
            #
            # temperature and platt are STRICTLY monotone (positive scale), so
            # they must not move AUROC at all; a drift here is a bug and stops
            # the run.
            #
            # isotonic is monotone but NOT strictly: PAVA pools adjacent points
            # into flat blocks, manufacturing ties the raw score did not have.
            # On a coarse score like WCT-U -- signed vote counts over a
            # 3-agent panel, so ~7 distinct values before pooling -- that can
            # merge genuinely separated groups and depress tie-averaged AUROC.
            # This is a real property of isotonic on discrete scores, not a
            # defect, but where it fires the log-loss change is no longer a
            # pure calibration effect. It is recorded and flagged rather than
            # tolerated silently, and such rows are excluded from the headline
            # calibration claim.
            drift = abs(au - au_raw)
            rec["maps"][m]["auroc_drift_vs_raw"] = round(drift, 6)
            rec["maps"][m]["rank_preserving"] = bool(drift < 1e-9)
            if m != "isotonic":
                assert drift < 1e-9, (
                    f"{arm}/{m} moved AUROC {au_raw} -> {au} (drift {drift}); a "
                    "strictly monotone map cannot do this and the isolation "
                    "argument fails")
        out["arms"][arm] = rec
    return out


def main() -> int:
    items, calib_ids, _ = load_dataset()
    out: dict = {
        "WARNING": "POST-HOC DIAGNOSTIC. The registered primary is the "
                   "'temperature' row and its verdict is unchanged. These "
                   "results explain that verdict; they do not restate it.",
        "delta_frozen_at_R0": PREREG["E1"]["primary"]["delta"],
        "panels": {},
    }
    for backend in ("local", "openrouter"):
        gens, coverage = load_generations(items, calib_ids, backend=backend)
        cell = gens["cross_family_diverse_role"]
        iids = complete_items(cell, min_agents=2)
        strata = {"all_items": iids,
                  "negation_theories": [i for i in iids if is_negation_theory(i)]}
        out["panels"][backend] = {"coverage": coverage, "strata": {}}
        for label, subset in strata.items():
            print(f"[{backend}/{label}] analysing {len(subset)} items ...")
            out["panels"][backend]["strata"][label] = analyse(
                items, calib_ids, cell, subset, label)

    Path("out").mkdir(exist_ok=True)
    Path("out/recalib_summary.json").write_text(json.dumps(out, indent=2, sort_keys=True))

    for backend, pv in out["panels"].items():
        for label, r in pv["strata"].items():
            if r.get("error"):
                continue
            print(f"\n===== {backend} / {label} =====")
            print(f"  test props {r['n_test_props']}  negatives {r['n_test_negatives']}"
                  f"  prevalence {r['prevalence_test']}")
            cb = r["covariate_baseline"]
            print(f"  covariate_baseline  logloss {cb['test_log_loss']:.4f}  "
                  f"auroc {cb['test_auroc']:.4f}  mean_pred {cb['mean_predicted']:.3f}")
            for arm, rec in r["arms"].items():
                print(f"  {arm}  (AUROC {rec['auroc_raw_score']:.4f}, "
                      f"identical under every map)")
                for m, v in rec["maps"].items():
                    d = v["delta_log_loss_vs_covariate"]
                    tag = " <-REGISTERED" if v["registered"] else ""
                    flag = "" if v["rank_preserving"] else f"  [rank drift {v['auroc_drift_vs_raw']:+.4f}]"
                    print(f"    {m:<12} logloss {v['test_log_loss']:>7.4f}  "
                          f"mean_pred {v['mean_predicted']:.3f}  "
                          f"dLL {d['point']:+.4f} [{d['lo']:+.4f},{d['hi']:+.4f}] "
                          f"-> {v['decision'].upper()}{tag}{flag}")
    print("\nwrote out/recalib_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
