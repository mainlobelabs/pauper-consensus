"""Item-level resampling. Every interval and null in this study is item-blocked.

Defect D5 is the reason. Propositions are nested within items, so resampling
propositions independently would pseudoreplicate: easy items produce both more
agreement and more correct propositions, and a proposition-level bootstrap turns
that item-difficulty confound into apparent proposition-level signal. Resampling
whole items keeps the nesting intact.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


def item_blocks(item_ids: list[str]) -> dict[str, np.ndarray]:
    idx: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(item_ids):
        idx[it].append(i)
    return {k: np.array(v) for k, v in idx.items()}


def item_bootstrap(
    item_ids: list[str], statistic, n_boot: int = 2000, seed: int = 20260807,
    alpha: float = 0.05,
) -> dict:
    """Percentile CI over items resampled with replacement.

    `statistic` receives the row indices of one resampled dataset and returns a
    float, or None when the resample is degenerate (e.g. one class absent).
    """
    blocks = item_blocks(item_ids)
    keys = list(blocks)
    rng = np.random.default_rng(seed)
    point = statistic(np.arange(len(item_ids)))
    draws = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        rows = np.concatenate([blocks[keys[p]] for p in pick])
        v = statistic(rows)
        if v is not None and np.isfinite(v):
            draws.append(v)
    if not draws:
        return {"point": point, "lo": None, "hi": None, "n_boot": 0}
    d = np.array(draws)
    return {
        "point": None if point is None else round(float(point), 5),
        "lo": round(float(np.quantile(d, alpha / 2)), 5),
        "hi": round(float(np.quantile(d, 1 - alpha / 2)), 5),
        "se": round(float(d.std(ddof=1)), 5),
        "n_boot": len(d),
    }


def within_item_permutation(
    item_ids: list[str], score: np.ndarray, y: np.ndarray, statistic,
    n_perm: int = 1000, seed: int = 20260807,
) -> dict:
    """Permute truth labels WITHIN each item, preserving each item's class balance.

    A global permutation would also destroy between-item difficulty structure
    and so would test a much weaker null: it would reject merely because some
    items are easier than others. Permuting within item asks the question that
    matters — does support predict truth beyond what item difficulty explains?
    """
    blocks = item_blocks(item_ids)
    rng = np.random.default_rng(seed)
    observed = statistic(score, y)
    if observed is None:
        return {"observed": None, "p": None, "n_perm": 0}
    null = []
    for _ in range(n_perm):
        yp = y.copy()
        for rows in blocks.values():
            yp[rows] = rng.permutation(yp[rows])
        v = statistic(score, yp)
        if v is not None:
            null.append(v)
    null = np.array(null)
    # +1 correction: a permutation p-value is never exactly zero
    p = (1 + (null >= observed).sum()) / (1 + len(null))
    return {
        "observed": round(float(observed), 5),
        "null_mean": round(float(null.mean()), 5),
        "null_sd": round(float(null.std(ddof=1)), 5),
        "p": round(float(p), 5),
        "n_perm": len(null),
    }


def paired_item_diff(item_ids: list[str], a: np.ndarray, b: np.ndarray,
                     n_boot: int = 2000, seed: int = 20260807) -> dict:
    """Bootstrap CI for a paired per-item difference (arm A minus arm B)."""
    blocks = item_blocks(item_ids)
    keys = list(blocks)
    per_item = np.array([float(a[blocks[k]].mean() - b[blocks[k]].mean())
                         for k in keys])
    rng = np.random.default_rng(seed)
    draws = np.array([
        per_item[rng.integers(0, len(keys), len(keys))].mean()
        for _ in range(n_boot)
    ])
    return {
        "point": round(float(per_item.mean()), 5),
        "lo": round(float(np.quantile(draws, 0.025)), 5),
        "hi": round(float(np.quantile(draws, 0.975)), 5),
        "sd_items": round(float(per_item.std(ddof=1)), 5),
        "n_items": len(keys),
    }


def decision(ci: dict, delta: float, higher_is_better: bool = True) -> str:
    """Protocol 1.1. Absence of evidence is not evidence of absence."""
    lo, hi, pt = ci.get("lo"), ci.get("hi"), ci.get("point")
    if lo is None or pt is None:
        return "inconclusive"
    if not higher_is_better:
        lo, hi, pt = -hi, -lo, -pt
    if lo > 0 and pt >= delta:
        return "go"
    if hi < delta:
        return "stop"
    return "inconclusive"


def error_correlation(correct: np.ndarray) -> dict:
    """Residual pairwise correlation of correctness indicators, and M_eff.

    M_eff = M / (1 + (M-1)*rho) is the Kish design effect (invariant I8). It is
    a dependence DIAGNOSTIC, not an accuracy theorem: it says how many
    independent votes the panel is worth, and it is capped at 1/rho however
    many models are added.
    """
    n, m = correct.shape
    if m < 2:
        return {"rho": None, "m_eff": float(m), "m": m}
    c = correct.astype(float)
    rhos = []
    for i in range(m):
        for j in range(i + 1, m):
            if c[:, i].std() < 1e-12 or c[:, j].std() < 1e-12:
                continue
            rhos.append(float(np.corrcoef(c[:, i], c[:, j])[0, 1]))
    if not rhos:
        return {"rho": None, "m_eff": float(m), "m": m}
    rho = float(np.mean(rhos))
    m_eff = m / (1 + (m - 1) * rho) if (1 + (m - 1) * rho) > 0 else float("inf")
    return {
        "rho": round(rho, 5),
        "rho_pairs": [round(r, 4) for r in rhos],
        "m_eff": round(m_eff, 4),
        "m": m,
        "cap_1_over_rho": round(1 / rho, 4) if rho > 0 else None,
    }


def double_fault(correct: np.ndarray) -> dict:
    """Rate at which two agents are wrong together, against the independent rate.

    The ratio is the direct read on the shared-error floor: independence
    predicts 1.0, and anything above it is dependence the panel cannot average
    away.
    """
    n, m = correct.shape
    obs, ind = [], []
    for i in range(m):
        for j in range(i + 1, m):
            wi, wj = ~correct[:, i], ~correct[:, j]
            obs.append(float((wi & wj).mean()))
            ind.append(float(wi.mean() * wj.mean()))
    o, e = float(np.mean(obs)), float(np.mean(ind))
    return {"observed": round(o, 5), "independent": round(e, 5),
            "ratio": round(o / e, 4) if e > 0 else None}
