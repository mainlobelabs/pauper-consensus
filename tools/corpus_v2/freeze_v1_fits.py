"""Freeze the v1 baseline artifacts that the v2 eval consumes.

Registered in prereg-v2 (NOTES.md Phase 5: "Frozen from v1 (hashes into
prereg-v2): the 3 calibration maps (3-class affine, one per arm, fit on the
v1 calibration split), the v1 calibration split itself (used only for the
baseline fit), and the full 5-feature covariate fit.") plus the 4-feature
content-only covariate fit, which the v2 primary bar requires.

Everything here is a deterministic re-derivation from frozen v1 inputs
(corpus at tag prereg-waveconsensus-v1 + native vote JSONLs in
cutoff-probe/runs/2026-08-2{6,7}). No v2 data is touched.

The script self-verifies by reproducing the reported v1 test-split numbers
(consensus_eval.json + NOTES.md Phase 4):
  covariate (5-feature) test log-loss   0.27341
  raw EM test log-loss                  ri 0.52684 / vo 0.49212 / base 0.58423
  calibrated EM test log-loss (NOTES)   ri 0.2583  / vo 0.2543  / base 0.2777
If any check misses its target by more than 2e-4 the script exits non-zero.

Usage (repo .venv python, needs numpy + scipy):
  .venv/bin/python tools/corpus_v2/freeze_v1_fits.py
Output: corpus-v2/frozen/v1_baselines.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "phase4"))
import consensus_eval as ce  # noqa: E402

FT_DIR = REPO / "cutoff-probe/runs/2026-08-27-phase4/finetuned/native"
BASE_DIR = REPO / "cutoff-probe/runs/2026-08-26-phase3/native"
OUT = REPO / "corpus-v2/frozen/v1_baselines.json"

# Verification targets (v1 reported numbers, 4-decimal).
TARGETS = {
    "cov_full_ll": 0.27341,
    "raw_ll": {"ft_reason_included": 0.52684, "ft_votes_only": 0.49212, "base_zeroshot": 0.58423},
    "calib_ll": {"ft_reason_included": 0.2583, "ft_votes_only": 0.2543, "base_zeroshot": 0.2777},
}
TOL = 2e-4


def em_post(native_dir: Path, models: list[str], tids: set[str], rng: np.random.Generator):
    """WCT-EM posterior on one split, fresh rng stream (as in calib.py)."""
    votes = ce.load_votes(native_dir, models, tids)
    items = sorted(k for k in ce.truth_global if k[0] in tids)
    v = [votes.get(k, {}) for k in items]
    fit = ce.fit_wct_em(v, rng)
    return fit["posterior"], np.array([ce.truth_global[k] for k in items]), items


def calib_map_fit(lp_cal: np.ndarray, y_cal: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """3-class affine (Platt-like) on log-posteriors, Nelder-Mead.

    Exact settings of calib.py (the script that produced the v1 headline
    calibration numbers): p0=(1,1,1,0,0,0), maxiter=2000, xatol=1e-6,
    fatol=1e-8.
    """

    def nll(p):
        a, b = p[:3], p[3:]
        z = a * lp_cal + b
        z = z - z.max(1, keepdims=True)
        q = np.exp(z)
        q /= q.sum(1, keepdims=True)
        return -np.mean(np.log(q[np.arange(len(y_cal)), y_cal] + 1e-12))

    p0 = np.concatenate([[1.0, 1.0, 1.0], [0.0, 0.0, 0.0]])
    opts = {"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-8}
    res = minimize(nll, p0, method="Nelder-Mead", options=opts)
    return res.x[:3].copy(), res.x[3:].copy(), float(res.fun)


def apply_calib(lp: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    z = a * lp + b
    z = z - z.max(1, keepdims=True)
    q = np.exp(z)
    return q / q.sum(1, keepdims=True)


def main() -> None:
    splits = ce.article_ids_by_split()
    calib_ids, test_ids = set(splits["calibration"]), set(splits["test"])
    labels = ce.load_raw_labels()
    ce.truth_global = {
        (t, int(r["id"].split("-")[1])): ce.TRUE.index(ce.EXPECT[r["label"]])
        for t in (test_ids | calib_ids)
        for r in labels[t]
    }
    meta = json.loads((ce.CORPUS / "pool" / "metadata.json").read_text())
    articles = {t: (ce.CORPUS / "articles" / f"{t}.md").read_text() for t in test_ids | calib_ids}
    trap_vocab = sorted({r["trap_type"] for v in meta.values() for r in v})

    # ---- covariate fits (fitted on the v1 calibration split only) ----
    feats = ce.build_features(test_ids | calib_ids, labels, meta, articles)
    cal_items = sorted(k for k in ce.truth_global if k[0] in calib_ids)
    test_items = sorted(k for k in ce.truth_global if k[0] in test_ids)
    Xc = np.array([feats[k] for k in cal_items])
    yc = np.array([ce.truth_global[k] for k in cal_items])
    Xt = np.array([feats[k] for k in test_items])
    tt = np.array([ce.truth_global[k] for k in test_items])
    W_full, norm_full = ce.fit_mlogit(Xc, yc)
    W_content, norm_content = ce.fit_mlogit(Xc[:, :4], yc)

    P_cov_full = ce.mlogit_predict(W_full, norm_full, Xt)
    P_cov_content = ce.mlogit_predict(W_content, norm_content, Xt[:, :4])
    ll_cov_full = ce.logloss(P_cov_full, tt)
    ll_cov_content = ce.logloss(P_cov_content, tt)

    # ---- per-arm calibration maps + verification ----
    arms_spec = [
        ("ft_reason_included", [f"{f}__reason_included" for f in ce.FAMILIES], FT_DIR),
        ("ft_votes_only", [f"{f}__votes_only" for f in ce.FAMILIES], FT_DIR),
        ("base_zeroshot", list(ce.FAMILIES), BASE_DIR),
    ]
    arms_out = {}
    for arm, models, d in arms_spec:
        rng = np.random.default_rng(ce.RNG_SEED)
        post_cal, y_cal, _ = em_post(d, models, calib_ids, rng)
        a, b, calib_nll = calib_map_fit(np.log(np.clip(post_cal, 1e-9, None)), y_cal)
        rng = np.random.default_rng(ce.RNG_SEED)
        post_te, t_te, _ = em_post(d, models, test_ids, rng)
        ll_raw = ce.logloss(post_te, t_te)
        q_te = apply_calib(np.log(np.clip(post_te, 1e-9, None)), a, b)
        ll_cal = ce.logloss(q_te, t_te)
        pi = np.bincount(y_cal, minlength=3) / len(y_cal)
        arms_out[arm] = {
            "a": [float(x) for x in a],
            "b": [float(x) for x in b],
            "calib_fit_nll": calib_nll,
            "calib_label_mix": {t: float(x) for t, x in zip(ce.TRUE, pi, strict=True)},
            "verification_v1_test": {
                "raw_ll": round(float(ll_raw), 5),
                "calibrated_ll": round(float(ll_cal), 5),
                "delta_cal_vs_cov_full": round(float(ll_cov_full - ll_cal), 5),
            },
        }
        print(
            f"{arm}: a={np.round(a, 6).tolist()} b={np.round(b, 6).tolist()} | "
            f"cov_full {ll_cov_full:.5f} raw {ll_raw:.5f} calib {ll_cal:.5f}",
            flush=True,
        )

    # ---- self-verification against the reported v1 numbers ----
    checks = [("cov_full_ll", ll_cov_full, TARGETS["cov_full_ll"])]
    for arm in TARGETS["raw_ll"]:
        v1t = arms_out[arm]["verification_v1_test"]
        checks.append((f"raw_ll[{arm}]", v1t["raw_ll"], TARGETS["raw_ll"][arm]))
        checks.append((f"calib_ll[{arm}]", v1t["calibrated_ll"], TARGETS["calib_ll"][arm]))
    bad = [(n, got, want) for n, got, want in checks if abs(got - want) > TOL]
    for n, got, want in checks:
        status = "OK" if abs(got - want) <= TOL else "MISMATCH"
        print(f"  check {n:28s} got {got:.5f} target {want:.5f} {status}")
    if bad:
        for n, got, want in bad:
            print(f"MISMATCH {n}: got {got} want {want}", file=sys.stderr)
        sys.exit(1)

    out = {
        "description": (
            "Frozen v1 baseline artifacts for the wave-consensus v2 eval. "
            "Calibration maps: 3-class affine on WCT-EM log-posteriors, fit on the v1 "
            "calibration split (per arm). Covariate bars: multinomial logistic (L2, "
            "pure-numpy GD, seed 0, 3000 iters) fitted on the v1 calibration split. "
            "See tools/corpus_v2/freeze_v1_fits.py (committed at prereg-waveconsensus-v2) "
            "for the exact procedure and the self-verification against reported v1 numbers."
        ),
        "generated": "2026-08-28",
        "v1_inputs": {
            "corpus": "corpus/ (tag prereg-waveconsensus-v1, frozen 2026-08-26)",
            "native_votes": {
                "base": "cutoff-probe/runs/2026-08-26-phase3/native (commit 1273339 run tree)",
                "finetuned": "cutoff-probe/runs/2026-08-27-phase4/finetuned/native",
            },
        },
        "em_spec": {
            "estimator": "three-state MAP-EM Dawid-Skene (PASS/FAIL/NOT_STATED)",
            "observed": ce.OBS,
            "latent": ce.TRUE,
            "kappa_dirichlet": ce.KAPPA,
            "diag_prior": 0.8,
            "basins": "structured (all-sharp, per-voter-sharp) + 5 concentrated random restarts",
            "select": "highest data log-likelihood",
            "max_iter": 200,
            "convergence_tol": 1e-8,
            "rng_seed": ce.RNG_SEED,
        },
        "calibration_spec": {
            "method": "3-class affine (Platt-like) on log-posteriors; Nelder-Mead MLE",
            "p0": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0],
            "maxiter": 2000,
            "xatol": 1e-6,
            "fatol": 1e-8,
            "fit_split": "v1 calibration (10 articles, 400 items)",
        },
        "covariate_spec": {
            "model": (
                "multinomial logistic, 3 classes, L2 lam=1e-3, lr 0.1 "
                "halved at iter 500/1000/1500/2000/2500, seed 0, 3000 iters"
            ),
            "features_full": [
                "log1p(article_len)",
                "log1p(pool_position-1)",
                "log1p(claim_len)",
                "polarity (0 affirmative / 1 negative)",
                "one-hot trap_type (vocabulary order below)",
            ],
            "features_content": [
                "log1p(article_len)",
                "log1p(pool_position-1)",
                "log1p(claim_len)",
                "polarity",
            ],
            "trap_vocab_order": trap_vocab,
            "fit_split": "v1 calibration (10 articles, 400 items)",
            "n_fit_items": int(len(cal_items)),
        },
        "splits_v1": {k: v for k, v in sorted(splits.items())},
        "arms": arms_out,
        "covariate_full": {
            "W": W_full.tolist(),
            "norm_mu": list(norm_full[0]),
            "norm_sd": list(norm_full[1]),
        },
        "covariate_content": {
            "W": W_content.tolist(),
            "norm_mu": list(norm_content[0]),
            "norm_sd": list(norm_content[1]),
        },
        "verification_v1_test": {
            "n_items": int(len(test_items)),
            "cov_full_ll": round(float(ll_cov_full), 5),
            "cov_content_ll": round(float(ll_cov_content), 5),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    import hashlib

    h = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"wrote {OUT} sha256={h}")


if __name__ == "__main__":
    main()
