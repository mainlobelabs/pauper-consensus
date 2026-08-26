"""Phase 4 consensus evaluation (prereg arms, metrics, predictions).

Registered arms:
  - WCT-EM (three-state Dawid-Skene, unsupervised) on the fine-tuned
    jury, two variant arms (reason_included, votes_only), 4 families.
  - WCT-EM on the zero-shot 4B base jury (P4 contrast arm).
  - Covariate baseline: multinomial logistic on [article_length,
    pool_position, claim_length, polarity, question_type], fitted on
    the calibration split only (prereg covariate_baseline).
  - Base rate (calibration label mix), the floor.

Registered metrics (test articles):
  - primary: article-block delta log-loss WCT-EM vs covariate baseline,
    threshold 0.02 nats, article-block bootstrap (2000 resamples, EM
    refit per resample on votes alone).
  - co-primary: within-article AUROC, WCT-EM vs covariate baseline.
  - null: within-article truth permutations (10000), fixed predictors.
  - e0: pairwise proposition-level residual error correlation across
    voters.
Predictions:
  - P4: fine-tuned delta >= zero-shot 4B delta on the same articles.
  - P5: consensus flags a larger share of non-ENTAIL solver claims than
    ENTAIL ones (pool-matched via seeded_by).
  - P6: on UNSPECIFIED pool-matched claims, (a) >= 50% confident
    bullshits, (b) jury gate removes a reported share.

Usage (on helium):
  python3.11 tools/phase4/consensus_eval.py \
    --ft-native /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native \
    --base-native /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/native \
    --solver <phase3>/solver-baseline/qwen3.8-27b.jsonl \
    --out /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/consensus_eval.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))
from analyze import CORPUS, EXPECT, article_ids_by_split  # noqa: E402

FAMILIES = [
    "llama-3.2-3b-instruct",
    "gemma-3-4b-it",
    "phi-4-mini-instruct",
    "qwen35-4b",
]
OBS = ["PASS", "FAIL", "NOT_STATED", "MISSING"]  # observed outcomes
TRUE = ["PASS", "FAIL", "NOT_STATED"]  # latent truth
RNG_SEED = 20260827
KAPPA = 5.0  # Dirichlet concentration for the MAP-EM voter prior


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_votes(native_dir: Path, models: list[str], tids: set[str]) -> dict:
    """(tid, item) -> model -> observation in OBS."""
    votes: dict[tuple[str, int], dict[str, str]] = {}
    for m in models:
        for r in read_jsonl(native_dir / f"{m}.jsonl"):
            if r["article"] not in tids or r["variant"] != "contract":
                continue
            p = r.get("parsed")
            obs = p["answer"] if p and p.get("answer") in TRUE else "MISSING"
            votes.setdefault((r["article"], int(r["item"])), {})[m] = obs
    return votes


# ---------------------------------------------------------------- WCT-EM


def _ds_data_ll(Y: np.ndarray, Z: np.ndarray, pi: np.ndarray) -> float:
    """Vectorized sum of item log-likelihoods log sum_y pi_y * prod_v Z[v,y,o_iv]."""
    n_items, n_t = Y.shape[0], 3
    term = np.tile(np.log(pi + 1e-12), (n_items, 1))
    for v in range(Y.shape[1]):
        for y in range(n_t):
            term[:, y] += np.log(Z[v, y] + 1e-12)[Y[:, v]]
    m = term.max(axis=1)
    term -= m[:, None]
    return float(np.sum(np.log(np.sum(np.exp(term), axis=1)) + m))


def fit_wct_em(votes: list[dict[str, str]], rng: np.random.Generator, restarts: int = 5) -> dict:
    """Unsupervised three-state Dawid-Skene EM with structured restarts.

    votes: list of {voter: observation}, observation in OBS.
    Explores the all-voters-sharp basin, one single-voter-sharp basin per
    voter, and `restarts` concentrated random basins, and returns the
    posterior probabilities (n_items, 3) over TRUE from the basin with the
    highest data log-likelihood.
    """
    voters = sorted({v for d in votes for v in d})
    n_items, n_v, n_t, n_o = len(votes), len(voters), len(TRUE), len(OBS)
    obs_idx = {o: i for i, o in enumerate(OBS)}
    mat = np.array([[d.get(v, "MISSING") for v in voters] for d in votes])
    Y = np.array([[obs_idx[o] for o in row] for row in mat])

    # MAP-EM: Dirichlet prior on each voter row. MLE-EM overfits voter
    # confidence in small samples (an overconfident matrix can raise the
    # data likelihood while hurting the posterior); a prior mean of
    # "80 percent diagonal, rest spread" with concentration KAPPA is the
    # standard shrinkage fix. Still fully unsupervised (no labels used).
    prior_mean = np.full((n_t, n_o), 0.2 / (n_o - 1))
    for y in range(n_t):
        prior_mean[y, y] = 0.8
    A = KAPPA * prior_mean  # Dirichlet alpha, (n_t, n_o)

    def log_posterior(pi, Z) -> np.ndarray:
        # log P(y_i) + sum_v log Z[v, y, obs_iv], per candidate truth y
        lp = np.tile(np.log(pi), (n_items, 1))
        for v in range(n_v):
            for y in range(n_t):
                lp[:, y] += np.log(Z[v, y] + 1e-12)[Y[:, v]]
        lp -= lp.max(axis=1, keepdims=True)
        p = np.exp(lp)
        return p / p.sum(axis=1, keepdims=True)

    def one_run(pi, Z) -> tuple:
        P = log_posterior(pi, Z)
        for _ in range(200):
            Pprev = P
            # M-step (MAP with Dirichlet(A) prior per voter row)
            R = P.sum(axis=0)
            pi = R / R.sum()
            Znew = np.zeros((n_v, n_t, n_o))
            for v in range(n_v):
                for o in range(n_o):
                    mask = Y[:, v] == o
                    Znew[v, :, o] = P[mask, :].sum(axis=0) + A[:, o]
            Znew /= Znew.sum(axis=2, keepdims=True)
            P = log_posterior(pi, Znew)
            if np.abs((P - Pprev).sum()).max() < 1e-8:
                break
        ll = _ds_data_ll(Y, Znew, pi)
        return ll, pi, Znew, P

    # Structured basins: uniform Z is a DS-EM fixed point (uniform
    # posterior forever), and flat Dirichlet inits land in its basin, so
    # restarts must be off-uniform. Basins: all voters sharp, each single
    # voter sharp, plus `restarts` concentrated random inits.
    best = None
    pi0 = np.full(n_t, 1.0 / n_t)
    inits: list[tuple[np.ndarray, np.ndarray]] = []
    for sharp in [None] + list(range(n_v)):
        # non-sharp voters flat (uniform), sharp voters diagonal-heavy
        Z_k = np.full((n_v, n_t, n_o), 1.0 / n_o)
        for v in range(n_v):
            if sharp is None or v == sharp:
                Z_k[v] = 0.05
                for y in range(n_t):
                    Z_k[v, y, y] = 0.8
                Z_k[v] /= Z_k[v].sum(axis=1, keepdims=True)
        inits.append((pi0, Z_k))
    for _ in range(restarts):
        Z_k = np.array([rng.dirichlet(np.full(n_o, 2.0)) for _ in range(n_v * n_t)]).reshape(
            n_v, n_t, n_o
        )
        inits.append((rng.dirichlet(np.ones(n_t) * 4), Z_k))
    for pi_k, Z_k in inits:
        ll, pi, Z, P = one_run(pi_k, Z_k)
        if best is None or ll > best[0]:
            best = (ll, pi, Z, P)
    ll, pi, Z, P = best
    return {"posterior": P, "pi": pi, "Z": Z, "voters": voters, "n_items": n_items, "data_ll": ll}


def logloss(post: np.ndarray, truth_idx: np.ndarray) -> float:
    return float(-np.mean(np.log(post[np.arange(len(truth_idx)), truth_idx] + 1e-12)))


def auroc_macro(scores: np.ndarray, truth_pass: np.ndarray, article: list[str]) -> float:
    """Within-article AUROC of score vs truth==PASS, macro over articles."""
    by_art: dict[str, tuple[list[float], list[int]]] = defaultdict(lambda: ([], []))
    for s, t, a in zip(scores, truth_pass, article, strict=True):
        by_art[a][0].append(float(s))
        by_art[a][1].append(int(t))
    aucs = []
    for _a, (s, t) in by_art.items():
        if len(set(t)) < 2:
            continue
        aucs.append(_auroc(np.array(s), np.array(t)))
    return float(np.mean(aucs)) if aucs else float("nan")


def _auroc(score: np.ndarray, label: np.ndarray) -> float:
    order = np.argsort(-score)
    ranks = np.empty(len(order), dtype=float)
    # average ranks for ties
    s_sorted = score[order]
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        avg = (i + j + 2) / 2  # 1-based average rank
        ranks[order[i : j + 1]] = avg
        i = j + 1
    n_pos = label.sum()
    n_neg = len(label) - n_pos
    sum_ranks_pos = ranks[label == 1].sum()
    # ranks are 1 = highest score, so invert the Mann-Whitney statistic
    return float(1.0 - (sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


# ----------------------------------------------------- covariate baseline


def load_raw_labels() -> dict[str, list[dict]]:
    """tid -> list of {id, proposition, label, ...} (raw corpus label files)."""
    out: dict[str, list[dict]] = {}
    for f in sorted(CORPUS.glob("labels/T*.json")):
        out[f.stem] = json.loads(f.read_text())
    return out


def build_features(tids: set[str], labels: dict, meta: dict, articles: dict) -> dict:
    """(tid, item) -> feature vector. labels = load_raw_labels()."""
    feats: dict[tuple[str, int], np.ndarray] = {}
    trap_vocab = sorted({r["trap_type"] for v in meta.values() for r in v})
    for tid in tids:
        art_len = len(articles[tid])
        for r in labels[tid]:
            i = int(r["id"].split("-")[1])
            m = next(x for x in meta[tid] if x["id"] == r["id"])
            f = [
                math.log1p(art_len),
                math.log1p(i - 1),
                math.log1p(len(r["proposition"])),
                0.0 if m["polarity"] == "affirmative" else 1.0,
            ]
            f += [1.0 if m["trap_type"] == t else 0.0 for t in trap_vocab]
            feats[(tid, i)] = np.array(f)
    return feats


def fit_mlogit(X: np.ndarray, y: np.ndarray, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Multinomial logistic, 3 classes, L2, pure-numpy GD."""
    rng = np.random.default_rng(seed)
    n, d = X.shape
    mu = X.mean(axis=0)
    sd = X.std(axis=0) + 1e-9
    Xs = (X - mu) / sd
    W = rng.normal(0, 0.01, size=(d + 1, 3))
    lr, lam, iters = 0.1, 1e-3, 3000
    Xb = np.hstack([Xs, np.ones((n, 1))])
    for it in range(iters):
        z = Xb @ W  # (n, 3)
        z -= z.max(axis=1, keepdims=True)
        P = np.exp(z)
        P /= P.sum(axis=1, keepdims=True)
        grad = Xb.T @ (P - np.eye(3)[y]) / n + lam * W
        grad[-1] -= lam * W[-1]  # no penalty on bias
        W -= lr * grad
        if it % 500 == 0 and it:
            lr *= 0.5
    return W, (mu, sd)


def mlogit_predict(W: np.ndarray, norm: tuple, X: np.ndarray) -> np.ndarray:
    mu, sd = norm
    Xb = np.hstack(((X - mu) / sd, np.ones((len(X), 1))))
    z = Xb @ W
    z -= z.max(axis=1, keepdims=True)
    P = np.exp(z)
    return P / P.sum(axis=1, keepdims=True)


# ------------------------------------------------------------- solver side


SOLVER_ANS = re.compile(r"^\s*(\d{1,2})[.)]\s*(.+)$", re.M)


def parse_solver_answers(raw: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in SOLVER_ANS.finditer(raw):
        n = int(m.group(1))
        if 1 <= n <= 20:
            out[n] = m.group(2).strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ft-native", required=True)
    ap.add_argument("--base-native", required=True)
    ap.add_argument("--solver", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = np.random.default_rng(RNG_SEED)
    splits = article_ids_by_split()
    test_ids, calib_ids = set(splits["test"]), set(splits["calibration"])
    labels = load_raw_labels()
    meta = json.loads((CORPUS / "pool" / "metadata.json").read_text())
    articles = {t: (CORPUS / "articles" / f"{t}.md").read_text() for t in test_ids | calib_ids}

    truth = {
        (tid, int(r["id"].split("-")[1])): TRUE.index(EXPECT[r["label"]])
        for tid in test_ids | calib_ids
        for r in labels[tid]
    }

    ft_dir, base_dir = Path(args.ft_native), Path(args.base_native)
    arms = {
        "ft_reason_included": [f"{f}__reason_included" for f in FAMILIES],
        "ft_votes_only": [f"{f}__votes_only" for f in FAMILIES],
        "base_zeroshot": list(FAMILIES),
    }
    votes_test = {
        a: load_votes(ft_dir if a != "base_zeroshot" else base_dir, ms, test_ids)
        for a, ms in arms.items()
    }

    items = sorted(k for k in truth if k[0] in test_ids)
    item_tid = [k[0] for k in items]
    truth_idx = np.array([truth[k] for k in items])
    feats = build_features(test_ids | calib_ids, labels, meta, articles)
    calib_items = sorted(k for k in truth if k[0] in calib_ids)
    X_cal = np.array([feats[k] for k in calib_items])
    y_cal = np.array([truth[k] for k in calib_items])
    X_test = np.array([feats[k] for k in items])
    W, norm = fit_mlogit(X_cal, y_cal)
    P_cov = mlogit_predict(W, norm, X_test)
    base_mix = np.bincount(y_cal, minlength=3) / len(y_cal)

    out = {"arms": {}, "n_test_items": len(items)}
    post_cache: dict[str, np.ndarray] = {}
    for arm in arms:
        v = [votes_test[arm].get(k, {}) for k in items]
        fit = fit_wct_em(v, rng)
        post = fit["posterior"]
        post_cache[arm] = post
        ll_em = logloss(post, truth_idx)
        ll_cov = logloss(P_cov, truth_idx)
        ll_base = float(-np.mean(np.log(base_mix[truth_idx] + 1e-12)))
        auc_em = auroc_macro(post[:, 0], (truth_idx == 0).astype(int), item_tid)
        auc_cov = auroc_macro(P_cov[:, 0], (truth_idx == 0).astype(int), item_tid)
        delta = ll_cov - ll_em

        # article-block bootstrap (2000): resample articles, refit EM on
        # votes alone, covariate predictions fixed (fitted on calibration)
        art_list = sorted(set(item_tid))
        items_by_art: dict[str, list[int]] = defaultdict(list)
        for j, a in enumerate(item_tid):
            items_by_art[a].append(j)
        n_art = len(art_list)
        deltas = np.empty(2000)
        for b in range(2000):
            idx = [
                j
                for a in (art_list[ai] for ai in rng.integers(0, n_art, size=n_art))
                for j in items_by_art[a]
            ]
            fb = fit_wct_em([v[j] for j in idx], rng, restarts=0)
            tb = truth_idx[idx]
            deltas[b] = logloss(P_cov[idx], tb) - logloss(fb["posterior"], tb)
        boot_ci = (
            float(np.percentile(deltas, 2.5)),
            float(np.percentile(deltas, 97.5)),
        )

        # null: 10000 within-article truth permutations, fixed predictors
        perm_deltas = np.empty(10000)
        art_item_idx = {a: items_by_art[a] for a in art_list}
        for p in range(10000):
            tp = np.empty_like(truth_idx)
            for a in art_list:
                j = art_item_idx[a]
                tp[j] = rng.permutation(truth_idx[j])
            perm_deltas[p] = logloss(P_cov, tp) - logloss(post, tp)
        null_ci = (
            float(np.percentile(perm_deltas, 2.5)),
            float(np.percentile(perm_deltas, 97.5)),
        )

        # e0: pairwise residual error correlation across voters
        voters = fit["voters"]
        err = np.zeros((len(items), len(voters)))
        for vi, m in enumerate(voters):
            for j, k in enumerate(items):
                o = votes_test[arm].get(k, {}).get(m, "MISSING")
                err[j, vi] = 1.0 if (o != TRUE[truth_idx[j]]) else 0.0
        res = err - err.mean(axis=0)
        pairs = []
        for a_i in range(len(voters)):
            for b_i in range(a_i + 1, len(voters)):
                ra, rb = res[:, a_i], res[:, b_i]
                if ra.std() > 0 and rb.std() > 0:
                    pairs.append(float(np.corrcoef(ra, rb)[0, 1]))
        e0 = float(np.mean(pairs)) if pairs else float("nan")

        out["arms"][arm] = {
            "em_logloss": round(ll_em, 5),
            "cov_logloss": round(ll_cov, 5),
            "base_rate_logloss": round(ll_base, 5),
            "delta_vs_cov": round(delta, 5),
            "delta_boot_ci95": [round(x, 5) for x in boot_ci],
            "delta_passes_0.02": delta >= 0.02 and boot_ci[0] > 0,
            "auc_em": round(auc_em, 4),
            "auc_cov": round(auc_cov, 4),
            "null_perm_delta_ci95": [round(x, 5) for x in null_ci],
            "e0": round(e0, 4),
            "em_prior": {t: round(float(x), 4) for t, x in zip(TRUE, fit["pi"], strict=True)},
        }
        print(
            f"{arm}: ll em {ll_em:.4f} cov {ll_cov:.4f} base {ll_base:.4f} "
            f"delta {delta:.4f} ci {boot_ci} auc em/cov {auc_em:.3f}/{auc_cov:.3f} e0 {e0:.3f}",
            flush=True,
        )

    # P4: fine-tuned delta vs zero-shot delta
    p4 = {
        arm: out["arms"][arm]["delta_vs_cov"]
        for arm in ("ft_reason_included", "ft_votes_only", "base_zeroshot")
    }
    p4["fine_tuned_beats_zeroshot"] = (
        min(p4["ft_reason_included"], p4["ft_votes_only"]) >= p4["base_zeroshot"]
    )
    out["P4"] = p4

    # P5 / P6: solver pool-matched claims (seeded_by maps question ->
    # proposition(s) seeded into it)
    solver_recs = {r["article"]: r["raw"] for r in read_jsonl(Path(args.solver))}
    q2props: dict[str, dict[int, list[str]]] = {tid: defaultdict(list) for tid in test_ids}
    for tid in test_ids:
        for r in meta[tid]:
            for q in r["seeded_by"]:
                q2props[tid][q].append(r["id"])
    item_pos = {k: j for j, k in enumerate(items)}
    claims = []
    for tid in sorted(test_ids):
        ans = parse_solver_answers(solver_recs.get(tid, ""))
        for q, text in sorted(ans.items()):
            for pid in q2props[tid].get(q, []):
                i = int(pid.split("-")[1])
                k = (tid, i)
                lab = EXPECT[next(r["label"] for r in labels[tid] if r["id"] == pid)]
                row = {
                    "article": tid,
                    "proposition": pid,
                    "truth": lab,
                    "solver_answer": text[:200],
                    "confident": _confident(text),
                }
                jj = item_pos[k]
                for arm in ("ft_reason_included", "ft_votes_only", "base_zeroshot"):
                    row[f"gate_{arm}"] = "PASS" if post_cache[arm][jj, 0] >= 0.5 else "not_PASS"
                claims.append(row)
    out["solver_pool_matched"] = _p5_p6(claims)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}")


def _confident(text: str) -> bool:
    low = text.lower()
    words = ("not stated", "unspecified", "unclear", "unknown", "no mention", "cannot", "can't")
    refuse = any(w in low for w in words)
    return not refuse and len(text) > 0


def _p5_p6(claims: list[dict]) -> dict:
    def shares(arm: str) -> dict:
        ent = [c for c in claims if c["truth"] == "PASS"]
        non = [c for c in claims if c["truth"] != "PASS"]

        def flag(c: dict) -> bool:
            return c[f"gate_{arm}"] == "not_PASS"

        return {
            "n_entail": len(ent),
            "n_non_entail": len(non),
            "flag_share_entail": round(sum(map(flag, ent)) / len(ent), 4) if ent else None,
            "flag_share_non_entail": round(sum(map(flag, non)) / len(non), 4) if non else None,
        }

    p6 = {}
    for arm in ("ft_reason_included", "ft_votes_only", "base_zeroshot"):
        uns = [c for c in claims if c["truth"] == "NOT_STATED"]
        p6[arm] = {
            "n": len(uns),
            "confident_share": round(sum(c["confident"] for c in uns) / len(uns), 4)
            if uns
            else None,
            "gate_removal_share": round(
                sum(c[f"gate_{arm}"] == "not_PASS" for c in uns) / len(uns), 4
            )
            if uns
            else None,
        }
    return {
        "n_claims": len(claims),
        "P5": {
            arm: shares(arm) for arm in ("ft_reason_included", "ft_votes_only", "base_zeroshot")
        },
        "P6": p6,
    }


if __name__ == "__main__":
    main()
