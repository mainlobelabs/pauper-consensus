"""M0 / part 2 — operator and panel mechanics.

Checks properties of the aggregation and propagation machinery that are decided
by algebra rather than by data, so they can be settled before any inference.

Invariants asserted here map to EXPERIMENT.md §3.0:
    I12  an even panel size decides a large fraction of binary propositions by tie
    I13  symmetric relation edges make diffusion recirculate a proposition's own
         evidence back to itself; a depth-restricted (nilpotent) W cannot
    I14  additive log-odds over correlated sources are overconfident, and the
         correction is a single monotone scalar fitted on calibration

Usage:  uv run --python 3.12 --with numpy --with scipy python m0/mechanics.py
"""
from math import comb, sqrt

import numpy as np
from scipy.stats import norm

RNG = np.random.default_rng(1)


# --------------------------------------------------------------------- I12
def tie_probability(m, p):
    """P(exact vote tie) for m independent sources of accuracy p on a binary claim."""
    if m % 2:
        return 0.0
    return comb(m, m // 2) * p ** (m // 2) * (1 - p) ** (m // 2)


def report_ties():
    print("=" * 74)
    print("I12  EXACT VOTE TIES ON BINARY PROPOSITIONS")
    print("=" * 74)
    print(f"{'M':>3} | " + "  ".join(f"p={p:<5}" for p in (0.6, 0.7, 0.8)))
    for m in (4, 5, 6, 7):
        row = "  ".join(f"{tie_probability(m, p):<7.3f}" for p in (0.6, 0.7, 0.8))
        print(f"{m:>3} | {row}")
    assert tie_probability(4, 0.7) > 0.25, "even panels tie often"
    assert tie_probability(5, 0.7) == 0.0
    print("\n  M=4 sends ~27% of propositions to a coin flip at p=0.70. Pin an ODD")
    print("  panel size in R0, or guarantee the score cannot produce exact ties.\n")


# --------------------------------------------------------------------- I13
def fixed_point(w, a0, alpha):
    """a* = (1-alpha)(I - alpha*P)^-1 a0 with absolute row normalisation."""
    p = w / np.maximum(np.abs(w).sum(1, keepdims=True), 1e-12)
    return (1 - alpha) * np.linalg.solve(np.eye(len(w)) - alpha * p, a0), p


def report_recirculation():
    print("=" * 74)
    print("I13  DIFFUSION SELF-ECHO:  a* = (1-a)(I - a*P)^-1 a0 = (1-a) sum a^t P^t")
    print("=" * 74)
    # two propositions that support each other -- NLI between near-equivalent
    # propositions is frequently close to symmetric, so this is the common case.
    w_sym = np.array([[0.0, 1.0], [1.0, 0.0]])
    # the same evidence, but restricted to depth-increasing edges only
    w_dag = np.array([[0.0, 0.0], [1.0, 0.0]])
    a0 = np.array([1.0, 0.1])  # one strong proposition, one weak
    print(f"{'alpha':>6} | {'symmetric a*':>22} {'depth-restricted a*':>22} {'self-echo share':>16}")
    for alpha in (0.3, 0.5, 0.8):
        sym, p_sym = fixed_point(w_sym, a0, alpha)
        dag, p_dag = fixed_point(w_dag, a0, alpha)
        echo = alpha ** 2 / (1 + alpha ** 2)
        assert np.allclose(np.diag(p_sym @ p_sym), 1.0), \
            "reciprocal edges return all second-order walk mass to its origin"
        assert np.allclose(np.linalg.matrix_power(p_dag, 2), 0.0), \
            "depth-restricted P must be nilpotent"
        print(f"{alpha:>6.1f} | {str(sym.round(4)):>22} {str(dag.round(4)):>22} {echo:>15.1%}")
    print("\n  diag(P^2) = 1 for a reciprocal pair: every unit of second-order walk")
    print("  mass returns to where it started. At alpha=0.8, 39% of accumulated")
    print("  amplitude is a proposition's own evidence echoing back.")
    print("  Restricting W to strictly depth-increasing edges makes P nilpotent:")
    print("  the Neumann series TERMINATES, inference is exact in D steps, there is")
    print("  no tolerance or iteration count, and self-echo is identically zero.\n")


# --------------------------------------------------------------------- I14
def report_calibration(k=4000, m=5, p=0.72):
    print("=" * 74)
    print("I14  CALIBRATION OF ADDITIVE LOG-ODDS UNDER CORRELATED SOURCES")
    print("=" * 74)

    def logloss(lo, t):
        q = np.clip(1 / (1 + np.exp(-np.clip(lo, -60, 60))), 1e-9, 1 - 1e-9)
        return float(-(t * np.log(q) + (1 - t) * np.log(1 - q)).mean())

    print(f"{'rho':>7} {'deff':>6} {'acc':>7} {'logloss naive':>14} "
          f"{'/deff':>9} {'best temp':>10} {'logloss@best':>13}")
    for r in (0.0, 0.25, 0.45):
        t = (RNG.random(k) < 0.5).astype(int)
        z = sqrt(r) * RNG.standard_normal((k, 1)) + sqrt(1 - r) * RNG.standard_normal((k, m))
        correct = z < norm.ppf(p)
        v = np.where(correct, np.where(t[:, None] == 1, 1, -1),
                     np.where(t[:, None] == 1, -1, 1))
        phi = np.corrcoef(v[:, 0], v[:, 1])[0, 1]
        lo = v.sum(1) * np.log(p / (1 - p))
        deff = 1 + (m - 1) * max(phi, 0.0)
        temps = np.linspace(0.5, 4.0, 200)
        losses = [logloss(lo / tt, t) for tt in temps]
        best = int(np.argmin(losses))
        acc = float(((lo > 0).astype(int) == t).mean())
        print(f"{phi:>7.3f} {deff:>6.2f} {acc:>7.3f} {logloss(lo, t):>14.4f} "
              f"{logloss(lo / deff, t):>9.4f} {temps[best]:>10.2f} {losses[best]:>13.4f}")
        # ranking is untouched by any positive scalar divisor
        assert np.array_equal(np.argsort(lo), np.argsort(lo / deff))
    print("\n  The analytic design-effect divisor helps at high rho but OVER-corrects")
    print("  at low rho. Fit ONE temperature on calibration instead. It is monotone,")
    print("  so ranking and selection are unchanged and the WCT-U supervision")
    print("  boundary in the ledger is not crossed.\n")


if __name__ == "__main__":
    report_ties()
    report_recirculation()
    report_calibration()
    print("all mechanics invariants passed")
