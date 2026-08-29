"""v2 consensus evaluation (2x2 prereg design).

Cells: {content-only bar, full bar} x {ft_reason_included, ft_votes_only},
plus base_zeroshot as a reference arm. The bars and the per-arm
calibration maps are FROZEN v1 artifacts (corpus-v2/frozen/
v1_baselines.json); the only things fitted on v2 data are the WCT-EM
posteriors (identical spec to v1) and their bootstrap re-fits.

Registered metrics (all 200 articles = test, per prereg-v2):
  primary:   calibrated WCT-EM vs frozen bar, delta log-loss per item,
             GO = delta >= 0.02 nats AND article-block bootstrap 95% CI
             excludes 0 (2000 resamples, EM re-fit per resample on votes
             alone, restarts=0, frozen bars).
  co-primary: within-article macro AUROC (P(PASS) score vs truth==PASS),
             calibrated EM vs bar, per cell.
  null:      within-article truth permutations (10000), fixed predictors,
             headline cell.
  e0:        pairwise proposition-level residual error correlation across
             the arm's four voters.
Predictions:
  P8: headline cell (content-only x reason_included) GO.
  P9: per fine-tuned arm, |full-bar delta v2 - full-bar delta v1| <= 0.05
      nats (continuity; v1 reference from the frozen verification block).

Vote rows: native/<model>.jsonl with variant "contract"; last row wins
per (model, article, item) on resume-appended retries. Item key is
"pool" (v2 runner) or "item" (v1 schema, for the v1-data smoke test).

Usage:
  .venv/bin/python tools/corpus_v2/eval_v2.py \
    --corpus corpus-v2 \
    --frozen corpus-v2/frozen/v1_baselines.json \
    --votes-spec '{"ft_reason_included": ["<run>/native"],
                   "ft_votes_only": ["<run>/native"],
                   "base_zeroshot": ["<run>/native"]}' \
    --out <run>/eval_v2.json \
    [--boot 2000] [--null 10000]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase4"))
from analyze import EXPECT  # noqa: E402
from consensus_eval import (  # noqa: E402
    FAMILIES,
    TRUE,
    auroc_macro,
    fit_wct_em,
    logloss,
    mlogit_predict,
)

RNG_SEED = 20260827
GO_THRESHOLD = 0.02
P9_TOL = 0.05

ARMS_FT = ("ft_reason_included", "ft_votes_only")
ALL_ARMS = ("ft_reason_included", "ft_votes_only", "base_zeroshot")
GO_CELLS = ("content_ft_reason_included", "content_ft_votes_only",
            "full_ft_reason_included", "full_ft_votes_only")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_votes(dirs: list[Path], models: list[str]) -> dict:
    """(tid, item) -> model -> observation in OBS. Last row wins."""
    votes: dict[tuple[str, int], dict[str, str]] = {}
    for m in models:
        for d in dirs:
            for r in read_jsonl(d / f"{m}.jsonl"):
                if r.get("variant") != "contract":
                    continue
                item = r.get("pool", r.get("item"))
                p = r.get("parsed") or {}
                ans = p.get("answer") if p else r.get("answer")
                obs = ans if ans in TRUE else "MISSING"
                votes.setdefault((r["article"], int(item)), {})[m] = obs
    return votes


def model_names(arm: str) -> list[str]:
    if arm == "ft_reason_included":
        return [f"{f}__reason_included" for f in FAMILIES]
    if arm == "ft_votes_only":
        return [f"{f}__votes_only" for f in FAMILIES]
    return list(FAMILIES)


def load_corpus(corpus: Path) -> dict:
    man = json.loads((corpus / "manifest.json").read_text())
    ids = [a["id"] for a in man["articles"]]
    labels, meta, articles = {}, {}, {}
    for tid in ids:
        labels[tid] = json.loads((corpus / "labels" / f"{tid}.json").read_text())
        articles[tid] = (corpus / "articles" / f"{tid}.md").read_text()
    meta = json.loads((corpus / "pool" / "metadata.json").read_text())
    return {"ids": ids, "labels": labels, "meta": meta, "articles": articles}


def build_items(c: dict, trap_order: list[str]) -> dict:
    """items: list of (tid, i); truth: (n,) idx; X8: (n, 8) features."""
    items, truth, X = [], [], []
    for tid in c["ids"]:
        art_len = len(c["articles"][tid])  # raw file text, as in v1
        for r in c["labels"][tid]:
            i = int(r["id"].rsplit("-", 1)[1])  # last segment = pool index (IDs: R02-001, V2-031-001)
            m = next(x for x in c["meta"][tid] if x["id"] == r["id"])
            f = [
                math.log1p(art_len),
                math.log1p(i - 1),
                math.log1p(len(r["proposition"])),
                0.0 if m["polarity"] == "affirmative" else 1.0,
            ]
            f += [1.0 if m["trap_type"] == t else 0.0 for t in trap_order]
            items.append((tid, i))
            truth.append(TRUE.index(EXPECT[r["label"]]))
            X.append(f)
    return {
        "items": items,
        "truth": np.array(truth),
        "X8": np.array(X, dtype=float),
    }


def apply_calib(P: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Frozen v1 3-class affine map: q = softmax_y(a_y * log p_y + b_y).

    Per-class elementwise transform of the log-posterior, then softmax
    across classes. Must match freeze_v1_fits.py exactly (same formula,
    same 1e-9 floor) so the frozen map applies identically to the one that
    produced the verified v1 numbers.
    """
    lp = np.log(np.clip(P, 1e-9, None))
    z = a * lp + b
    z = z - z.max(axis=1, keepdims=True)
    Q = np.exp(z)
    return Q / Q.sum(axis=1, keepdims=True)


def e0_for(votes_arm: dict, items: list, truth: np.ndarray, voters: list[str]) -> float:
    n = len(items)
    err = np.zeros((n, len(voters)))
    for vi, m in enumerate(voters):
        for j, k in enumerate(items):
            o = votes_arm.get(k, {}).get(m, "MISSING")
            err[j, vi] = 1.0 if o != TRUE[truth[j]] else 0.0
    res = err - err.mean(axis=0)
    pairs = []
    for a_i in range(len(voters)):
        for b_i in range(a_i + 1, len(voters)):
            ra, rb = res[:, a_i], res[:, b_i]
            if ra.std() > 0 and rb.std() > 0:
                pairs.append(float(np.corrcoef(ra, rb)[0, 1]))
    return float(np.mean(pairs)) if pairs else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--votes-spec", required=True,
                    help='JSON: arm -> list of native dirs, e.g. '
                         '\'{"ft_reason_included": ["runs/x/native"], ...}\'')
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--null", type=int, default=10000)
    ap.add_argument("--articles", default="",
                    help="comma list of article IDs to restrict to "
                         "(debugging / v1-data smoke test; default: all)")
    args = ap.parse_args()

    t0 = time.time()
    corpus = Path(args.corpus)
    frozen = json.loads(Path(args.frozen).read_text())
    spec = {k: [Path(d) for d in v]
            for k, v in json.loads(args.votes_spec).items()}

    c = load_corpus(corpus)
    if args.articles:
        keep = [t.strip() for t in args.articles.split(",") if t.strip()]
        known = set(c["ids"])
        unknown = [t for t in keep if t not in known]
        if unknown:
            raise SystemExit(f"unknown article ids: {unknown}")
        c["ids"] = [t for t in c["ids"] if t in set(keep)]
    data = build_items(c, frozen["covariate_spec"]["trap_vocab_order"])
    items, truth, X8 = data["items"], data["truth"], data["X8"]
    n_items = len(items)
    art_of_item = [k[0] for k in items]
    art_list = list(dict.fromkeys(art_of_item))
    items_by_art: dict[str, list[int]] = defaultdict(list)
    for j, a in enumerate(art_of_item):
        items_by_art[a].append(j)

    # Frozen bars (predictions fixed for the whole eval)
    P_content = mlogit_predict(np.array(frozen["covariate_content"]["W"]),
                               (np.array(frozen["covariate_content"]["norm_mu"]),
                                np.array(frozen["covariate_content"]["norm_sd"])),
                               X8[:, :4])
    P_full = mlogit_predict(np.array(frozen["covariate_full"]["W"]),
                            (np.array(frozen["covariate_full"]["norm_mu"]),
                             np.array(frozen["covariate_full"]["norm_sd"])),
                            X8)
    ll_content = -np.log(P_content[np.arange(n_items), truth] + 1e-12)
    ll_full = -np.log(P_full[np.arange(n_items), truth] + 1e-12)

    rng_em = np.random.default_rng(RNG_SEED)
    arms_out: dict[str, dict] = {}
    post_cal: dict[str, np.ndarray] = {}
    ll_q: dict[str, np.ndarray] = {}
    for arm in ALL_ARMS:
        ms = model_names(arm)
        votes_arm = load_votes(spec[arm], ms)
        v = [votes_arm.get(k, {}) for k in items]
        fit = fit_wct_em(v, rng_em)
        P = fit["posterior"]
        a = np.array(frozen["arms"][arm]["a"])
        b = np.array(frozen["arms"][arm]["b"])
        Q = apply_calib(P, a, b)
        post_cal[arm] = Q
        ll_q[arm] = -np.log(Q[np.arange(n_items), truth] + 1e-12)
        # per-model parse (missing) rates
        rates = {}
        for m in ms:
            obs = [votes_arm.get(k, {}).get(m, "MISSING") for k in items]
            rates[m] = round(sum(o == "MISSING" for o in obs) / n_items, 5)
        arms_out[arm] = {
            "em_data_ll": round(float(fit["data_ll"]), 5),
            "em_prior": {t: round(float(x), 4) for t, x in zip(TRUE, fit["pi"], strict=True)},
            "em_logloss_raw": round(logloss(P, truth), 5),
            "em_logloss_calibrated": round(logloss(Q, truth), 5),
            "missing_rate_per_model": rates,
            "e0": round(e0_for(votes_arm, items, truth, fit["voters"]), 4),
            "auc_em_cal": round(auroc_macro(Q[:, 0], (truth == 0).astype(int),
                                            art_of_item), 4),
        }

    # Cells: bar variant x arm
    ll_bar = {"content": ll_content, "full": ll_full}
    auc_bar = {
        "content": auroc_macro(P_content[:, 0], (truth == 0).astype(int), art_of_item),
        "full": auroc_macro(P_full[:, 0], (truth == 0).astype(int), art_of_item),
    }
    cells: dict[str, dict] = {}
    for bv in ("content", "full"):
        for arm in ALL_ARMS:
            delta = float(ll_bar[bv].mean() - ll_q[arm].mean())
            cells[f"{bv}_{arm}"] = {
                "bar_logloss": round(float(ll_bar[bv].mean()), 5),
                "em_cal_logloss": round(float(ll_q[arm].mean()), 5),
                "delta": round(delta, 5),
                "auc_em_cal": arms_out[arm]["auc_em_cal"],
                "auc_bar": round(auc_bar[bv], 4),
                "go": None,
            }

    # Bootstrap CIs for the four registered cells (EM re-fit per resample,
    # bars frozen). One EM re-fit per (arm, resample); both bar cells of
    # an arm share it.
    votes_by_item: dict[str, list[dict]] = {}
    for arm in ARMS_FT:
        va = load_votes(spec[arm], model_names(arm))
        votes_by_item[arm] = [va.get(k, {}) for k in items]
    calib_params = {
        arm: (np.array(frozen["arms"][arm]["a"]), np.array(frozen["arms"][arm]["b"]))
        for arm in ARMS_FT
    }
    rng_boot = np.random.default_rng(RNG_SEED + 1)
    n_art = len(art_list)
    boot_deltas: dict[str, np.ndarray] = {
        f"{bv}_{arm}": np.empty(args.boot) for bv in ("content", "full")
        for arm in ARMS_FT
    }
    for b in range(args.boot):
        if b % 100 == 0:
            print(f"bootstrap {b}/{args.boot} ({time.time() - t0:.0f}s)", flush=True)
        draw = rng_boot.integers(0, n_art, size=n_art)
        idx = np.concatenate([np.array(items_by_art[art_list[i]]) for i in draw])
        for arm in ARMS_FT:
            v = [votes_by_item[arm][j] for j in idx]
            fb = fit_wct_em(v, rng_boot, restarts=0)
            Qb = apply_calib(fb["posterior"], *calib_params[arm])
            tb = truth[idx]
            llq = float(-np.log(Qb[np.arange(len(idx)), tb] + 1e-12).mean())
            boot_deltas[f"content_{arm}"][b] = ll_content[idx].mean() - llq
            boot_deltas[f"full_{arm}"][b] = ll_full[idx].mean() - llq

    boot_ci: dict[str, list[float]] = {}
    for key in GO_CELLS:
        d = boot_deltas[key]
        lo, hi = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
        boot_ci[key] = [round(lo, 5), round(hi, 5)]
        cells[key]["go"] = bool(cells[key]["delta"] >= GO_THRESHOLD and lo > 0)

    # Null: headline cell only (content x ft_reason_included)
    rng_null = np.random.default_rng(RNG_SEED + 2)
    perm_deltas = np.empty(args.null)
    for p in range(args.null):
        if p % 1000 == 0:
            print(f"null {p}/{args.null} ({time.time() - t0:.0f}s)", flush=True)
        tp = np.empty_like(truth)
        for a in art_list:
            j = items_by_art[a]
            tp[j] = rng_null.permutation(truth[j])
        perm_deltas[p] = (ll_content - np.log(
            post_cal["ft_reason_included"][np.arange(n_items), tp] + 1e-12
        )).mean()
    null_ci = [float(np.percentile(perm_deltas, 2.5)),
               float(np.percentile(perm_deltas, 97.5))]
    headline = "content_ft_reason_included"
    p_value = float((perm_deltas >= cells[headline]["delta"]).mean())

    out = {
        "n_items": n_items,
        "n_articles": n_art,
        "spec": {
            "rng_em": RNG_SEED,
            "rng_boot": RNG_SEED + 1,
            "rng_null": RNG_SEED + 2,
            "boot": args.boot,
            "null": args.null,
            "go_threshold": GO_THRESHOLD,
            "em_spec": frozen["em_spec"],
            "calibration_spec": frozen["calibration_spec"],
            "frozen_file": str(args.frozen),
        },
        "arms": arms_out,
        "cells": cells,
        "headline": {
            "cell": headline,
            "delta": cells[headline]["delta"],
            "boot_ci95": boot_ci.get(headline),
            "null_perm_ci95": [round(x, 5) for x in null_ci],
            "null_p_value": round(p_value, 5),
            "P8": cells[headline]["go"],
        },
        "P9": {},
        "elapsed_s": round(time.time() - t0, 1),
    }
    for arm in ARMS_FT:
        v1_ref = frozen["arms"][arm]["verification_v1_test"]["delta_cal_vs_cov_full"]
        d2 = cells[f"full_{arm}"]["delta"]
        out["P9"][arm] = {
            "v2_full_delta": d2,
            "v1_full_delta": v1_ref,
            "within_0p05": bool(abs(d2 - v1_ref) <= P9_TOL),
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {out_path} in {time.time() - t0:.0f}s")
    for key in sorted(cells):
        c_ = cells[key]
        print(f"  {key}: delta {c_['delta']:+.5f} ci {boot_ci.get(key)} "
              f"GO={c_['go']}")
    print(f"  P8: {out['headline']['P8']}   P9: {out['P9']}")


if __name__ == "__main__":
    main()
