"""Unique-source proposition aggregation: WCT-U, WCT-EM, WCT-C.

The supervision ledger is the thing to keep straight here, because the whole
"unsupervised" claim rests on it:

  WCT-U   uniform signed support. No labels. A RANK score, not a probability.
  WCT-EM  three-state Dawid-Skene. Truth is latent; per-agent sensitivity,
          false-positive rate and truth-dependent coverage are estimated from
          the vote matrix ALONE. Consumes no truth labels, so it sits on the
          WCT-U side of the ledger (D9), and it is the primary unsupervised arm
          because uniform weighting is misspecified on a heterogeneous panel.
  WCT-C   the same observation model with parameters fitted on labelled
          CALIBRATION items only, then applied unchanged to test.

Three states matter. Absence is never silently converted into a negative vote
(assumption M4): coverage is modelled per truth value, so if a model stays quiet
more often about false propositions, silence is informative and the estimator
uses it. If coverage is truth-independent the coverage terms cancel and silence
contributes exactly zero, which is the behaviour plan.md 3.1 requires.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AFFIRM, DENY, MISSING = 1, -1, 0
EPS = 1e-9


def vote_matrix(observations, agents: list[str], pids: list[str]) -> np.ndarray:
    """V[z, m] in {+1, -1, 0}. One entry per (proposition, agent): assumption M6."""
    ai = {a: i for i, a in enumerate(agents)}
    pi = {p: i for i, p in enumerate(pids)}
    V = np.zeros((len(pids), len(agents)), dtype=np.int8)
    for o in observations:
        if o.pid in pi and o.agent in ai:
            V[pi[o.pid], ai[o.agent]] = AFFIRM if o.obs == "affirm" else DENY
    return V


# ------------------------------------------------------------------ WCT-U
def wct_u(V: np.ndarray, normalise: bool = False) -> np.ndarray:
    """Signed unique-source support. Missing contributes zero."""
    score = (V == AFFIRM).sum(1).astype(float) - (V == DENY).sum(1)
    if normalise:
        emitting = np.maximum((V != MISSING).sum(1), 1)
        score = score / emitting
    return score


def uncapped(claim_counts: np.ndarray) -> np.ndarray:
    """Ablation: count claim INSTANCES, not sources.

    Registered to test assumption M6 — whether verbosity was manufacturing
    consensus. It is not a WCT arm.
    """
    return claim_counts.astype(float)


# ----------------------------------------------------------------- WCT-EM
@dataclass
class DSParams:
    pi: float
    sens: np.ndarray      # P(affirm | Y=1, emitted)
    fpr: np.ndarray       # P(affirm | Y=0, emitted)
    cov1: np.ndarray      # P(emit | Y=1)
    cov0: np.ndarray      # P(emit | Y=0)


def _loglik_terms(V: np.ndarray, p: DSParams):
    """Per-proposition log-likelihood under Y=1 and Y=0."""
    aff, den, mis = (V == AFFIRM), (V == DENY), (V == MISSING)
    l1 = (aff @ np.log(p.cov1 * p.sens + EPS)
          + den @ np.log(p.cov1 * (1 - p.sens) + EPS)
          + mis @ np.log(1 - p.cov1 + EPS))
    l0 = (aff @ np.log(p.cov0 * p.fpr + EPS)
          + den @ np.log(p.cov0 * (1 - p.fpr) + EPS)
          + mis @ np.log(1 - p.cov0 + EPS))
    return l1, l0


def wct_em(
    V: np.ndarray, iters: int = 300, tol: float = 1e-9, alpha: float = 0.5
) -> tuple[np.ndarray, DSParams]:
    """Three-state Dawid-Skene. Returns P(Y=1 | votes) and fitted parameters.

    Initialised at majority vote, which resolves the label-swapping
    non-identifiability: agreement alone cannot distinguish a unanimously
    correct panel from a unanimously wrong one without an anchor, and
    'the average source is better than random' (assumption M2) is that anchor.
    """
    n, m = V.shape
    aff, den, mis = (V == AFFIRM), (V == DENY), (V == MISSING)
    emitted = ~mis

    q = (aff.sum(1) + alpha) / (emitted.sum(1) + 2 * alpha)
    q = np.clip(q, 1e-4, 1 - 1e-4)
    params = None
    prev = None

    for _ in range(iters):
        # M-step (alpha-smoothed so a silent or unanimous agent cannot make a
        # parameter degenerate and freeze the E-step)
        n1 = q @ emitted + 2 * alpha
        n0 = (1 - q) @ emitted + 2 * alpha
        sens = (q @ aff + alpha) / n1
        fpr = ((1 - q) @ aff + alpha) / n0
        cov1 = (q @ emitted + alpha) / (q.sum() + 2 * alpha)
        cov0 = ((1 - q) @ emitted + alpha) / ((1 - q).sum() + 2 * alpha)
        pi = float(np.clip(q.mean(), 1e-4, 1 - 1e-4))
        params = DSParams(pi, np.clip(sens, 1e-4, 1 - 1e-4),
                          np.clip(fpr, 1e-4, 1 - 1e-4),
                          np.clip(cov1, 1e-4, 1 - 1e-4),
                          np.clip(cov0, 1e-4, 1 - 1e-4))
        # E-step
        l1, l0 = _loglik_terms(V, params)
        lo = np.log(pi / (1 - pi)) + l1 - l0
        q = 1 / (1 + np.exp(-np.clip(lo, -60, 60)))
        if prev is not None and np.abs(q - prev).max() < tol:
            break
        prev = q.copy()
    return q, params


def em_logodds(V: np.ndarray, p: DSParams) -> np.ndarray:
    l1, l0 = _loglik_terms(V, p)
    return np.log(p.pi / (1 - p.pi)) + l1 - l0


# ------------------------------------------------------------------ WCT-C
def fit_supervised(V: np.ndarray, y: np.ndarray, alpha: float = 0.5) -> DSParams:
    """Fit the observation model on LABELLED calibration propositions only."""
    aff, emitted = (V == AFFIRM), (V != MISSING)
    y1, y0 = (y == 1), (y == 0)
    sens = (aff[y1].sum(0) + alpha) / (emitted[y1].sum(0) + 2 * alpha)
    fpr = (aff[y0].sum(0) + alpha) / (emitted[y0].sum(0) + 2 * alpha)
    cov1 = (emitted[y1].sum(0) + alpha) / (max(y1.sum(), 1) + 2 * alpha)
    cov0 = (emitted[y0].sum(0) + alpha) / (max(y0.sum(), 1) + 2 * alpha)
    pi = float(np.clip(y.mean(), 1e-4, 1 - 1e-4))
    return DSParams(pi, np.clip(sens, 1e-4, 1 - 1e-4), np.clip(fpr, 1e-4, 1 - 1e-4),
                    np.clip(cov1, 1e-4, 1 - 1e-4), np.clip(cov0, 1e-4, 1 - 1e-4))


# ------------------------------------------------------- calibration (I14)
def fit_temperature(scores: np.ndarray, y: np.ndarray,
                    grid: np.ndarray | None = None) -> float:
    """One monotone scalar, fitted on calibration (invariant I14).

    Additive log-odds over correlated sources are overconfident, and the
    analytic design-effect divisor over-corrects at low rho. A single fitted
    temperature dominates both. Being a positive scalar divisor it is strictly
    monotone, so ranking and selection are unchanged and the WCT-U supervision
    boundary is not crossed by applying it.
    """
    if grid is None:
        grid = np.linspace(0.25, 6.0, 240)
    best, best_loss = 1.0, np.inf
    for t in grid:
        loss = log_loss(sigmoid(scores / t), y)
        if loss < best_loss:
            best, best_loss = float(t), loss
    return best


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -60, 60)))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def auroc(score: np.ndarray, y: np.ndarray) -> float | None:
    """Rank AUROC with tie correction. None where one class is absent."""
    pos, neg = (y == 1).sum(), (y == 0).sum()
    if pos == 0 or neg == 0:
        return None
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    s = score[order]
    i = 0                                   # average ranks within tie groups
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + j + 2) / 2
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))
