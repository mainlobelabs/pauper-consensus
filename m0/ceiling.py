"""M0 / part 1 — pre-inference ceiling analysis.

Run before spending any API quota. Establishes upper bounds on what any WCT
variant can achieve on a panel of M sources, and checks that the aggregation
estimators behave as the mathematics says they must.

Invariants asserted here map to EXPERIMENT.md §3.0:
    I8   effective panel size follows the Kish design effect and is capped at 1/rho
    I9   uniform-weight aggregation is NOT optimal on a heterogeneous panel
    I10  latent-truth EM matches uniform on homogeneous panels and beats it on
         heterogeneous ones, using no truth labels
    I11  oracle-of-panel selection bounds the achievable end-to-end effect

Usage:  uv run --python 3.12 --with numpy --with scipy python m0/ceiling.py
"""
from math import sqrt

import numpy as np
from scipy.stats import norm

RNG = np.random.default_rng(0)
M_PANEL = 4  # panel size used in the illustrative tables; R0 pins the real value


# --------------------------------------------------------------------- I8
def m_eff(m, rho):
    """Kish design effect. Effective independent votes in a panel of m sources."""
    return m / (1 + (m - 1) * rho)


def report_design_effect():
    print("=" * 74)
    print("I8  EFFECTIVE PANEL SIZE   M_eff = M / (1 + (M-1)*rho)")
    print("=" * 74)
    print(f"{'rho':>6} | {'M_eff(M=4)':>11} {'M_eff(M=5)':>11} {'M_eff(M=8)':>11} {'cap = 1/rho':>12}")
    for rho in [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7]:
        cap = (1 / rho) if rho > 0 else float("inf")
        print(f"{rho:>6.2f} | {m_eff(4, rho):>11.2f} {m_eff(5, rho):>11.2f} "
              f"{m_eff(8, rho):>11.2f} {cap:>12.2f}")
    # no amount of panel growth escapes the 1/rho cap
    for rho in [0.1, 0.3, 0.5]:
        assert m_eff(10_000, rho) <= 1 / rho + 1e-6
    print("\n  No panel size ever exceeds 1/rho effective votes. Measure rho in E0,")
    print("  then read the ceiling off this table BEFORE committing to a delta.\n")


# ------------------------------------------------------------- I11 + gain curve
def correlated_panel(n, m, p, r, rng):
    """Gaussian-copula correlated correctness indicators with marginal accuracy p."""
    z = sqrt(r) * rng.standard_normal((n, 1)) + sqrt(1 - r) * rng.standard_normal((n, m))
    return z < norm.ppf(p)


def report_gain_and_ceiling(n=400_000):
    print("=" * 74)
    print(f"I11 MAJORITY GAIN vs ORACLE CEILING (M={M_PANEL}, Gaussian copula, {n:,} sims)")
    print("=" * 74)
    print(f"{'p_single':>9} {'rho_phi':>9} {'majority':>9} {'gain':>8} "
          f"{'oracle':>9} {'headroom':>9}")
    for p in [0.60, 0.70, 0.80]:
        for r in [0.0, 0.2, 0.4]:
            correct = correlated_panel(n, M_PANEL, p, r, RNG)
            phi = np.corrcoef(correct[:, 0].astype(float),
                              correct[:, 1].astype(float))[0, 1]
            s = correct.sum(1)
            maj = (s > M_PANEL / 2) | ((s == M_PANEL / 2) & (RNG.random(n) < 0.5))
            oracle = s > 0  # any source correct => a perfect selector could find it
            assert oracle.mean() >= maj.mean() - 1e-9, "oracle must bound any selector"
            print(f"{p:>9.2f} {phi:>9.3f} {maj.mean():>9.3f} {maj.mean() - p:>+8.3f} "
                  f"{oracle.mean():>9.3f} {oracle.mean() - p:>+9.3f}")
    print("\n  'headroom' bounds E3's achievable effect. If the pilot's measured")
    print("  headroom is below delta, the end-to-end gate is unwinnable — stop there.\n")


# ---------------------------------------------------------------- I9 + I10
def dawid_skene(V, iters=200, tol=1e-9):
    """Binary Dawid-Skene EM. V[k,i] in {+1,-1,0}; 0 = source silent.

    Returns P(T_k = 1). Uses NO truth labels: truth is latent, per-source
    sensitivity/specificity are estimated from the vote matrix alone. Initialised
    at majority vote to resolve the label-flip non-identifiability.
    """
    _, _ = V.shape
    obs, aff = (V != 0), (V == 1)
    q = (aff.sum(1) + 0.5) / (obs.sum(1) + 1.0)
    prev = None
    for _ in range(iters):
        n1 = q @ obs + 1.0
        n0 = (1 - q) @ obs + 1.0
        sens = (q @ aff + 0.5) / n1
        spec = 1 - ((1 - q) @ aff + 0.5) / n0
        pi = np.clip(q.mean(), 1e-6, 1 - 1e-6)
        lo = (np.log(pi / (1 - pi))
              + aff @ np.log(sens / (1 - spec))
              + (obs & ~aff) @ np.log((1 - sens) / spec))
        q = 1 / (1 + np.exp(-np.clip(lo, -60, 60)))
        if prev is not None and np.abs(q - prev).max() < tol:
            break
        prev = q.copy()
    return q


def simulate_votes(k, ps, rng):
    t = (rng.random(k) < 0.5).astype(int)
    v = np.zeros((k, len(ps)), dtype=int)
    for i, p in enumerate(ps):
        right = rng.random(k) < p
        v[:, i] = np.where(right,
                           np.where(t == 1, 1, -1),
                           np.where(t == 1, -1, 1))
    return t, v


def report_estimators(k=1200, reps=30):
    print("=" * 74)
    print("I9/I10  UNIFORM (WCT-U) vs LATENT-TRUTH EM (WCT-EM) — neither uses labels")
    print("=" * 74)
    out = {}
    for spread, desc in [(0.0, "homogeneous   p=.70 for all sources"),
                         (0.225, "heterogeneous p in [.52,.93]")]:
        acc = {kk: [] for kk in ("best_single", "uniform", "ds_em", "oracle_wt")}
        for _ in range(reps):
            ps = np.clip(0.70 + spread * RNG.standard_normal(M_PANEL), 0.52, 0.93)
            t, v = simulate_votes(k, ps, RNG)
            acc["best_single"].append(ps.max())
            acc["uniform"].append((((v.sum(1) > 0).astype(int)) == t).mean())
            acc["ds_em"].append((((dawid_skene(v) > 0.5).astype(int)) == t).mean())
            w = np.log(ps / (1 - ps))  # true log-odds weights: bound for any weighting
            acc["oracle_wt"].append((((v @ w > 0).astype(int)) == t).mean())
        print(f"\n  {desc}")
        for name in ("best_single", "uniform", "ds_em", "oracle_wt"):
            arr = np.array(acc[name])
            print(f"    {name:>12}: {arr.mean():.4f}  (sd {arr.std():.4f})")
        out[desc[:3]] = {kk: float(np.mean(vv)) for kk, vv in acc.items()}

    hom, het = out["hom"], out["het"]
    # I9: uniform weighting is misspecified on a heterogeneous panel
    assert het["uniform"] < het["best_single"], \
        "expected uniform aggregation to lose to the best single source when sources differ"
    # I10: EM matches uniform when sources are equal, beats it when they are not
    assert abs(hom["ds_em"] - hom["uniform"]) < 0.01, \
        "EM should not cost anything on a homogeneous panel"
    assert het["ds_em"] > het["uniform"] + 0.01, \
        "EM should recover most of the oracle-weighting gap on a heterogeneous panel"
    recovered = ((het["ds_em"] - het["uniform"])
                 / max(het["oracle_wt"] - het["uniform"], 1e-9))
    print(f"\n  WCT-EM recovers {recovered:.0%} of the uniform -> oracle-weight gap,")
    print("  using no truth labels. A heterogeneous panel is exactly the regime the")
    print("  OpenRouter pool is in, so WCT-U alone would understate the method.\n")


# --------------------------------------------------------------------- power
def report_power():
    print("=" * 74)
    print("SAMPLE SIZES (paired, 80% power, alpha=.05 two-sided)")
    print("=" * 74)
    zt = norm.ppf(0.975) + norm.ppf(0.80)
    print("  continuous paired rubric / graded-preference difference:")
    for dz in [0.5, 0.4, 0.3, 0.25, 0.2]:
        print(f"    d_z={dz:<5} -> n = {int(np.ceil(zt ** 2 / dz ** 2)):>4} items")
    print("  binarised win/loss (sign test) vs the same effect kept graded:")
    print(f"    {'win rate':>9} {'d_z':>7} {'n graded':>9} {'n binary':>9} {'penalty':>8}")
    for pi in [0.70, 0.65, 0.60, 0.55]:
        dz = norm.ppf(pi)  # P(win) = Phi(d_z) for a normal paired difference
        n_graded = zt ** 2 / dz ** 2
        n_binary = zt ** 2 * pi * (1 - pi) / (pi - 0.5) ** 2
        print(f"    {pi:>9.2f} {dz:>7.3f} {int(np.ceil(n_graded)):>9} "
              f"{int(np.ceil(n_binary)):>9} {n_binary / n_graded:>7.2f}x")
        assert n_binary > n_graded, "binarising must cost items, never save them"
    print(f"    -> penalty converges to the sign-test ARE against the t-test on normal"
          f" data: pi/2 = {np.pi / 2:.2f}x")
    se = 0.15 / sqrt(40)
    print(f"  E1 within-item AUROC, 40 items, sd across items 0.15:")
    print(f"    se={se:.4f}, 95% half-width +/-{1.96 * se:.3f}"
          f" -> smallest detectable AUROC {0.5 + 1.96 * se:.3f}\n")


if __name__ == "__main__":
    report_design_effect()
    report_gain_and_ceiling()
    report_estimators()
    report_power()
    print("all ceiling invariants passed")
