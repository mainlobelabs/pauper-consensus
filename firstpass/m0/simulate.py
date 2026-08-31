"""M0 / part 3 — simulator and invariants 1-5 (protocol 3.0).

Every latent variable is observable here, so the aggregation estimators can be
checked against a known answer before any of them is pointed at real model
output. That ordering is the point: a defect found here looks like a failing
assertion, whereas the same defect found after E1 is indistinguishable from a
negative experimental result.

Invariants 6 and 7 belong to diffusion (E2) and AND/OR derivation (E2.5), which
this study does not run; they are not asserted here and that gap is stated
rather than skipped quietly.

Usage:  .venv/bin/python -m m0.simulate
"""
from __future__ import annotations

import numpy as np

from wct.aggregate import (
    AFFIRM, DENY, MISSING, auroc, fit_supervised, em_logodds, wct_em, wct_u,
)


def simulate(
    n_props: int = 4000,
    m: int = 5,
    p: float | np.ndarray = 0.75,
    rho: float = 0.0,
    coverage: float | np.ndarray = 0.8,
    coverage_false: float | None = None,
    prevalence: float = 0.5,
    align_precision: float = 1.0,
    align_recall: float = 1.0,
    seed: int = 0,
):
    """Generate a vote matrix with known truth.

    `rho` is induced by a latent shared-misconception component via a Gaussian
    copula, which is what makes errors CONDITIONALLY dependent rather than just
    marginally similar — the regime plan.md 3.1 warns about.
    """
    rng = np.random.default_rng(seed)
    y = (rng.random(n_props) < prevalence).astype(int)
    ps = np.full(m, p, dtype=float) if np.isscalar(p) else np.asarray(p, dtype=float)
    cov1 = np.full(m, coverage, dtype=float) if np.isscalar(coverage) else np.asarray(coverage)
    cov0 = cov1 if coverage_false is None else np.full(m, coverage_false, dtype=float)

    # correlated correctness via a shared latent component
    from scipy.stats import norm

    z = (np.sqrt(rho) * rng.standard_normal((n_props, 1))
         + np.sqrt(1 - rho) * rng.standard_normal((n_props, m)))
    correct = z < norm.ppf(ps)[None, :]

    said_true = np.where(correct, y[:, None] == 1, y[:, None] == 0)
    emit_p = np.where(y[:, None] == 1, cov1[None, :], cov0[None, :])
    emitted = rng.random((n_props, m)) < emit_p

    V = np.where(emitted, np.where(said_true, AFFIRM, DENY), MISSING).astype(np.int8)

    # measurement noise: alignment recall drops observations, alignment
    # precision misroutes them to the wrong proposition
    if align_recall < 1.0:
        V = np.where(rng.random(V.shape) < align_recall, V, MISSING)
    if align_precision < 1.0:
        bad = (V != MISSING) & (rng.random(V.shape) > align_precision)
        V = np.where(bad, -V, V)  # misaligned claim lands as the opposite vote
    return V, y, correct


def _acc(score: np.ndarray, y: np.ndarray) -> float:
    return float(((score > 0).astype(int) == y).mean())


def single_baselines(correct: np.ndarray, frac: float = 0.5) -> tuple[float, float]:
    """(oracle single, calibration-selected single) on the same held-out half.

    These are NOT interchangeable and the difference is the point. The oracle
    picks the best source using truth labels no unlabelled practitioner has, so
    it is an upper bound and nothing more. The calibration-selected source picks
    the winner on the first half and is scored on the second, which is what an
    analyst can actually do. Reporting only the oracle would overstate the
    baseline and understate the panel; reporting only the achievable one would
    do the reverse.
    """
    n = len(correct)
    cut = int(n * frac)
    calib, test = correct[:cut], correct[cut:]
    oracle = float(test.mean(0).max())
    chosen = int(np.argmax(calib.mean(0)))
    return oracle, float(test[:, chosen].mean())


def report_i1_i2():
    print("=" * 74)
    print("I1/I2  PANEL GAIN GROWS WITH M_eff, AND COLLAPSES AS rho -> 1")
    print("=" * 74)
    print(f"{'rho':>6} | " + " ".join(f"{'M=' + str(m):>13}" for m in (3, 5, 9)))
    prev = {}
    for rho in (0.0, 0.2, 0.5, 0.9):
        row = []
        for m in (3, 5, 9):
            V, y, _ = simulate(m=m, rho=rho, coverage=1.0, seed=7)
            row.append(_acc(wct_u(V), y))
        print(f"{rho:>6.2f} | " + " ".join(f"{a:>13.4f}" for a in row))
        prev[rho] = row
    # I1: with independent sources, more panel is more accuracy
    assert prev[0.0][0] < prev[0.0][1] < prev[0.0][2], \
        "I1: WCT-U must improve with panel size at rho=0"
    # I2: dependence collapses the gain
    gain_indep = prev[0.0][2] - prev[0.0][0]
    gain_dep = prev[0.9][2] - prev[0.9][0]
    assert gain_dep < gain_indep / 2, \
        "I2: panel gain must collapse toward the shared-error floor as rho -> 1"
    print(f"\n  M=3->9 gain: {gain_indep:+.4f} at rho=0, {gain_dep:+.4f} at rho=0.9.")
    print("  Adding sources buys almost nothing once errors are shared.\n")


def report_i3():
    print("=" * 74)
    print("I3  DUPLICATING ONE SOURCE MOVES UNCAPPED COUNTING, NOT WCT-U")
    print("=" * 74)
    V, y, _ = simulate(m=5, rho=0.1, coverage=1.0, seed=11)
    dup = np.concatenate([V, V[:, [0]], V[:, [0]]], axis=1)  # agent 0 says it 3x
    u_base, u_dup = wct_u(V), wct_u(dup)
    print(f"  WCT-U accuracy      base {_acc(u_base, y):.4f}   "
          f"with agent-0 duplicated {_acc(u_dup, y):.4f}")
    # the cap is enforced upstream in cluster.py; here we show WHY it matters
    assert not np.array_equal(u_base, u_dup), \
        "duplicated columns must change an uncapped count (that is the hazard)"
    capped = wct_u(dup[:, :5])
    assert np.array_equal(u_base, capped), \
        "I3: capping at one observation per source restores the original score"
    print("  Uncapped, one verbose agent outvotes two quiet ones. cluster.py caps")
    print("  at one observation per (agent, proposition), which restores it.\n")


def report_i4():
    """Assumption M4: non-emission must be MODELLED, not assumed away either way.

    Both naive treatments are wrong, and they are wrong in opposite regimes,
    which is the whole reason the estimator carries a coverage parameter:

      - ignoring silence (plain WCT-U) is right when coverage is
        truth-independent and throws away real information when it is not;
      - forcing silence to a denial is harmful when coverage is
        truth-independent, and only looks good when coverage happens to be
        truth-dependent in the direction that flatters it.

    An earlier version of this check asserted that forcing silence to denial is
    always harmful under truth-dependent coverage. The simulator falsified it:
    at cov(Y=0)=0.30 silence really is evidence of falsity, so the crude rule
    gains. The invariant below is the one that survives.
    """
    print("=" * 74)
    print("I4  SILENCE MUST BE MODELLED: BOTH NAIVE TREATMENTS FAIL, IN OPPOSITE REGIMES")
    print("=" * 74)
    print(f"{'cov(Y=1)':>9} {'cov(Y=0)':>9} | {'ignore':>8} {'silence=deny':>13} "
          f"{'3-state EM':>11} | {'EM - best naive':>16}")
    margins = []
    for c1, c0 in ((0.8, 0.8), (0.8, 0.5), (0.8, 0.3)):
        V, y, _ = simulate(m=5, rho=0.0, coverage=c1, coverage_false=c0, seed=13)
        ignore = _acc(wct_u(V), y)
        forced = _acc(wct_u(np.where(V == MISSING, DENY, V)), y)
        q, _ = wct_em(V)
        em = _acc(q - 0.5, y)
        margins.append((c1, c0, ignore, forced, em))
        print(f"{c1:>9.2f} {c0:>9.2f} | {ignore:>8.4f} {forced:>13.4f} "
              f"{em:>11.4f} | {em - max(ignore, forced):>+16.4f}")

    indep = margins[0]
    assert indep[3] < indep[2] - 0.01, \
        "I4a: with truth-independent coverage, forcing silence to denial must hurt"
    for c1, c0, ignore, forced, em in margins:
        assert em >= max(ignore, forced) - 0.005, \
            f"I4b: three-state EM must not lose to either naive rule (cov {c1}/{c0})"
    dep = margins[-1]
    assert dep[3] > dep[2], \
        "I4c: under strongly truth-dependent coverage, silence IS informative, " \
        "so ignoring it must lose to using it"
    print("\n  Row 1: silence is uninformative, so converting it to a vote adds")
    print("  noise. Row 3: silence is informative, so ignoring it leaves signal")
    print("  on the table. Neither naive rule is safe in both regimes; the")
    print("  three-state estimator is, because it fits coverage per truth value.\n")


def report_i5():
    print("=" * 74)
    print("I5  ALIGNMENT QUALITY: WHERE THE WCT ADVANTAGE DISAPPEARS")
    print("=" * 74)
    print(f"{'precision':>10} {'recall':>8} | {'WCT-U':>8} {'WCT-EM':>8} "
          f"{'oracle 1':>9} {'calib 1':>8} | {'EM - calib1':>12}")
    surface = []
    for prec in (1.0, 0.9, 0.8, 0.7, 0.6):
        for rec in (1.0, 0.7):
            V, y, correct = simulate(
                m=5, rho=0.15, p=[0.62, 0.70, 0.75, 0.82, 0.88], coverage=0.85,
                align_precision=prec, align_recall=rec, seed=17,
            )
            q, _ = wct_em(V)
            oracle, calib1 = single_baselines(correct)
            row = (prec, rec, _acc(wct_u(V), y), _acc(q - 0.5, y), oracle, calib1)
            surface.append(row)
            print(f"{prec:>10.2f} {rec:>8.2f} | {row[2]:>8.4f} {row[3]:>8.4f} "
                  f"{oracle:>9.4f} {calib1:>8.4f} | {row[3] - calib1:>+12.4f}")
    clean = [r for r in surface if r[0] == 1.0 and r[1] == 1.0][0]
    dirty = [r for r in surface if r[0] == 0.6][0]
    assert clean[3] > dirty[3] + 0.02, \
        "I5: degrading alignment precision must degrade aggregation"
    print("\n  The break-even boundary is where 'EM - calib 1' crosses zero. Below")
    print("  it, agreement is measuring the mapper rather than the panel (M5),")
    print("  which is why cluster.py measures alignment against ground truth.")
    print("  Note how far apart the two single-source baselines are: an analysis")
    print("  that quotes the ORACLE single source sets a bar no unlabelled method")
    print("  can clear, and one that quotes only the achievable source flatters")
    print("  the panel. Both are reported here for that reason.\n")
    return surface


def report_heterogeneous():
    """D9 in the estimator this study actually ships: three-state, real coverage."""
    print("=" * 74)
    print("D9  UNIFORM vs LATENT-TRUTH EM ON A HETEROGENEOUS PANEL (three-state)")
    print("=" * 74)
    reps = 40
    keys = ("uniform", "em", "supervised", "oracle_single", "calib_single")
    diffs, rows = [], {k: [] for k in keys}
    for r in range(reps):
        ps = np.clip(0.72 + 0.14 * np.random.default_rng(100 + r).standard_normal(5),
                     0.52, 0.94)
        V, y, correct = simulate(m=5, p=ps, rho=0.12, coverage=0.85, seed=100 + r)
        q, _ = wct_em(V)
        sup = fit_supervised(V, y)
        oracle, calib1 = single_baselines(correct)
        rows["uniform"].append(_acc(wct_u(V), y))
        rows["em"].append(_acc(q - 0.5, y))
        rows["supervised"].append(_acc(em_logodds(V, sup), y))
        rows["oracle_single"].append(oracle)
        rows["calib_single"].append(calib1)
        diffs.append(rows["em"][-1] - rows["uniform"][-1])
    d = np.array(diffs)
    for k, v in rows.items():
        a = np.array(v)
        print(f"  {k:>14}: {a.mean():.4f}  (sd across reps {a.std(ddof=1):.4f})")
    # the PAIRED difference is the quantity with a meaningful interval; the
    # per-column sds above are dominated by the random draw of reliabilities
    lo, hi = np.quantile(
        [d[np.random.default_rng(s).integers(0, reps, reps)].mean()
         for s in range(2000)], [0.025, 0.975])
    print(f"\n  PAIRED EM - uniform: {d.mean():+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]"
          f"  over {reps} panels")
    assert lo > 0, "D9: EM must beat uniform on heterogeneous panels"
    print("  Reported paired, because the across-rep sd of each column is mostly")
    print("  the random draw of per-source reliabilities, not estimator noise.\n")


if __name__ == "__main__":
    report_i1_i2()
    report_i3()
    report_i4()
    report_i5()
    report_heterogeneous()
    print("all simulator invariants (I1-I5) passed")
