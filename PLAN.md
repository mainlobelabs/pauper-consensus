# Plan — Slice 1: Scaffold and M0 mathematical gate

Run `20260727-201557-5e045099` · STANDARD · workstream `20260727-201552-894582b7` slice 1/7
Request: `REQUEST.md` · Specification: `EXPERIMENT.md` §2, §3.0 · Design of record: `plan.md`

---

## 1. The one design decision that shapes this slice

Protocol §3.0 says M0 "verifies the implementation and identifies which empirical
quantities must be measured." Verifying an implementation requires the implementation to
exist. But protocol §2's module table assigns `aggregate.py` to E1, `diffuse.py` to E2, and
`derive.py` to E2.5 — slices 4, 5 and 6. Invariants 1–3 need the estimators, invariant 6
needs propagation, and invariant 7 needs AND/OR selection. So either M0 tests throwaway
reference implementations that later slices replace, or slice 1 builds the real ones.

**Decision: slice 1 builds the real analysis-side modules.** They are inference-free by
construction, so they can be written and fully verified against simulated ground truth
before a single API call. Later slices then add only what genuinely needs model output —
`nodes.py`, `extract.py`, `cluster.py`, `measure.py` — plus the experiment drivers.

This is the protocol's own "separate expensive immutable inference from free repeatable
analysis" principle (§2) applied to build order rather than runtime. It front-loads all
mathematics into the one slice that has ground truth available, and it means a defect in
the estimators surfaces against a known answer rather than against real model output where
it would be indistinguishable from a negative result.

It also enlarges slice 1 beyond a literal reading of the master's slice boundary. That was
recorded rather than silently absorbed, and taken to the plan gate.

**Ratified at the step-4 human gate** (see `DECISIONS.md`): build the real modules; slice 1
owns `wct/schema.py`; `m0.gate` and `m0.sweep` stay separate with a `--full` staleness
check. Slices 4–6 are correspondingly reduced to the inference-dependent modules
(`nodes.py`, `extract.py`, `cluster.py`, `measure.py`) plus their experiment drivers, and
`MASTER.md` is updated to match so the workstream and the plan do not diverge.

## 2. Layout

```
pyproject.toml              deps pinned, uv.lock committed          A1
prereg.yaml                 protocol §3.1(4) fields, delta unset    A2
wct/
  schema.py                 shared artifact schema  <-- OQ4         A4, A8
  cache.py                  write-once content-hashed store         A3
  simulate.py               generative simulator                    A4
  aggregate.py              WCT-U, WCT-EM, WCT-C, temperature       A9
  diffuse.py                depth-restricted + ablations            A9
  derive.py                 AND/OR selection, linear-path diag      A9
m0/
  ceiling.py                EXISTS — I8–I11                         A6
  mechanics.py              EXISTS — I12–I14                        A6
  invariants.py             protocol §3.0 invariants 1–7            A5
  sweep.py                  failure surface, break-even boundary    A7, A8
  gate.py                   one command, non-zero on failure        A10
tests/test_m0.py            pytest wrapper over both invariant sets A5, A6
```

`wct/schema.py` is the interface every later slice consumes. OQ4 asks whether slice 1
should own it; the plan assumes yes, because the simulator cannot emit a matching schema
without defining one.

## 3. Approach, in dependency order

**Step 1 — scaffold (A1, A2).** `uv venv --python 3.12`; numpy, scipy, networkx, pytest,
pyyaml now; httpx, transformers, torch (CPU) declared but unused this slice. Commit
`uv.lock`. `prereg.yaml` carries every §3.1(4) field with `delta: null` and a comment
naming it an R0 blocker, so slice 2 cannot start inference against unset thresholds.

*On the no-network constraint.* `REQUEST.md` bans **inference** calls — OpenRouter, the
local generation endpoint, the embedding endpoint. Package installation from PyPI is
expected and permitted; the two are different networks in every sense that matters here.
Concretely: `uv sync` resolves from PyPI, `uv.lock` is committed so the resolution is
reproducible, and `torch` is installed CPU-only via `--torch-backend=cpu` (~200 MB, no
CUDA wheels). If PyPI is unreachable, that is an A1 failure to report, not a constraint
violation to work around. The gate itself (`m0.gate`) makes no network call of any kind,
and that is asserted by test, not by convention — see §4.1.

**Step 2 — schema and cache (A3, A8).** Define the artifact records once: trace, claim,
proposition cluster, relation, derivation. Cache is write-once, content-addressed, keyed
per protocol §2 on (item, resolved model/provider metadata, prompt template, decode params,
requested seed); analysis-side changes never invalidate it. Unit-tested with synthetic
records — no inference exists yet. Rejecting a rewrite of an existing key is a test case,
not a convention.

**Step 3 — simulator (A4).** Latent binary truth with configurable prevalence; `M` sources
with sensitivity, false-positive rate, and truth-dependent coverage; conditionally
independent errors plus a latent shared-misconception component controlling residual
correlation and same-wrong convergence; claim duplication and variable decomposition
granularity; alignment confusion with configurable precision/recall; acyclic AND/OR
derivations with configurable missing-premise and invalid-inference rates. Emits
`wct/schema.py` records. Fixed seeds, seed recorded per row.

**Step 4 — estimators and operators (A9).** `aggregate.py`: WCT-U capped unique-source
signed score; WCT-EM three-state Dawid–Skene with truth latent, initialised at majority
vote; WCT-C with oracle and estimated parameters; one monotone temperature. `diffuse.py`:
depth-restricted nilpotent operator as default with a runtime nilpotency assertion, plus
row-normalised diffusion and loopy BP as registered ablations. `derive.py`: bipartite
AND/OR DAG, exact max-closure via min-cut with AO* over OR nodes, MDL complexity prior,
and the linear-path diagnostic.

**Step 5 — invariants 1–7 (A5, A6).** One test module; `m0/gate.py` runs it together with
`ceiling.py` and `mechanics.py` and exits non-zero on any failure (A10).

**Step 6 — sweep (A7, A8).** Grid over mean reliability, residual correlation `rho`,
shared-wrong rate, union coverage, alignment precision/recall, dependency precision/recall,
and panel size `M`. Emits the failure surface and the break-even boundary against
single-source and voting baselines. Specified operationally in §4.2.

## 4. Invariant → test mapping

| # | Invariant (protocol §3.0) | Verified by |
| --- | --- | --- |
| 1 | `p>0.5`, coverage adequate, alignment correct, `rho=0` → unique-source aggregation improves with effective panel size | `simulate` + `aggregate.wct_u` |
| 2 | `rho→1` → panel gain collapses to the shared-error floor | sweep over `rho` |
| 3 | duplicating one source's wording changes uncapped counting but not WCT-U/WCT-EM/WCT-C | duplication generator + capping |
| 4 | treating missing as denial is detectably biased when coverage is truth-dependent | three-state vs two-state estimator |
| 5 | mapping errors degrade aggregation; the precision/recall region where any WCT advantage vanishes is exposed | alignment-confusion sweep |
| 6 | row-normalised diffusion converges for `alpha<1`; convergence alone does not improve truth recovery | `diffuse` + truth-recovery delta |
| 7 | a linear path can accept an inference missing a conjunctive premise; the AND/OR selector cannot | `derive` vs linear-path diagnostic |
| 8–14 | already implemented and passing | `m0/ceiling.py`, `m0/mechanics.py` |

Invariants 4 and 7 are the two most likely to fail first: both encode a *distinction* the
implementation must preserve, and both are easy to satisfy vacuously if the generator never
produces the discriminating case. Each test therefore has a **guard** assertion that the
discriminating case occurred, checked before the outcome assertion.

### 4.1 Commands, thresholds, tolerances

Everything below is deterministic: seeds fixed in `prereg.yaml`, `K = 4000` propositions,
20 reps per cell unless stated.

| Command | Purpose | Budget |
| --- | --- | --- |
| `uv run python -m m0.gate` | invariants 1–14, exits non-zero on any failure | < 90 s |
| `uv run pytest -q` | same assertions under pytest, plus cache/schema unit tests | < 120 s |
| `uv run python -m m0.sweep --out artifacts/m0/` | A7/A8 failure surface and break-even | minutes; see §4.2 |

| # | Guard (must hold, else the test is vacuous) | Assertion | Tolerance |
| --- | --- | --- | --- |
| 1 | `rho ≈ 0` (measured \|phi\| ≤ 0.02), alignment F1 = 1.0, coverage ≥ 0.95 | `acc(M=9) - acc(M=3) ≥ 0.05`; each step in `M ∈ {3,5,7,9}` ≥ `-0.01` | MC noise ±0.01 |
| 2 | measured phi ≥ 0.85 at the `rho→1` end | `gain(rho=0.9) ≤ 0.25 × gain(rho=0.0)` | ±0.02 |
| 3 | uncapped count actually shifts: `\|acc_unc(dup) - acc_unc(nodup)\| ≥ 0.02` | `\|acc(dup) - acc(nodup)\| ≤ 0.005` for WCT-U, WCT-EM, WCT-C | ±0.005 |
| 4 | coverage differs by truth class: `\|cov(T=1) - cov(T=0)\| ≥ 0.15` | three-state estimator beats missing-as-denial by ≥ 0.02 accuracy | ±0.01 |
| 5 | alignment F1 spans `[0.5, 1.0]` in the grid | degradation monotone in F1; a break-even vs best-single exists in range, or is explicitly reported absent | ±0.01 |
| 6 | `alpha ∈ {0.3, 0.5, 0.8, 0.95}` all reach `‖a_{t+1} - a_t‖∞ < 1e-9` within 500 iters | at `rho = 0`: `\|AUROC(diffused) - AUROC(direct)\| ≤ 0.01` — converging is not helping | ±0.01 |
| 7 | the top-scoring linear path routes through an inference node with a missing conjunctive premise | AND/OR selection has premise-set recall `= 1.0` on every selected inference | exact |

Invariant 6's second clause is the one that matters and it is deliberately an *upper*
bound: protocol §3.0(6) says convergence alone must not improve truth recovery, so a
diffusion that appears to help at `rho = 0` indicates a leak, not a win.

`m0.gate` writes `artifacts/m0/gate_report.json` recording every guard value, assertion
value, margin, and the seed — so a pass that only just cleared a threshold is visible
rather than reported as a flat green.

**No-network assertion.** `tests/test_m0.py` monkeypatches `socket.socket` to raise for the
duration of the gate. A network call anywhere in the M0 path is a test failure, which makes
the constraint mechanical rather than a matter of discipline.

### 4.2 Sweep specification (A7, A8)

- **Command:** `uv run python -m m0.sweep --out artifacts/m0/ [--quick]`. `--quick` runs a
  declared canary subgrid used for reproducibility checking.
- **Grid:** the seven axes named in A7, values declared in `prereg.yaml` under `m0.grid`.
- **Outputs:**
  - `artifacts/m0/failure_surface.csv` — one row per grid cell × method, columns:
    grid axes, method, accuracy, AUROC, log-loss, `M_eff`, n_reps, seed.
  - `artifacts/m0/breakeven.json` — per method, the boundary where it overtakes both
    single-best and uncapped voting, or `null` with a reason if none exists in range.
  - `artifacts/m0/sweep_meta.json` — grid hash, prereg hash, package versions, wall time.
- **Pass/fail:** the sweep is *descriptive*, not a correctness gate. It passes when it
  completes over the full declared grid with no cell erroring, every method has a
  break-even entry (a value or an explicit `null` + reason), and `--quick` reproduces
  bit-identical numbers across two runs. A missing boundary is a scientific result, not a
  failure; a *silently* missing boundary is a failure.
- **Relationship to `m0.gate`:** the sweep is **not** in the gate's fast path — it is
  minutes to the gate's seconds, and coupling them would discourage running the gate. But
  `m0.gate --full` asserts the sweep artifacts exist and that `sweep_meta.grid_hash`
  matches the current `prereg.yaml`, so stale artifacts cannot masquerade as current. This
  split is question 3 at the gate.

## 5. Rollback

Cheap by construction: this slice mutates no external state. No API calls, no database, no
deployed surface; every artifact is either a file in the working tree or under gitignored
`artifacts/`.

| Scenario | Reversal |
| --- | --- |
| Whole slice abandoned | `git reset --hard c82d045` (the pre-freeze baseline) and delete `artifacts/`. Returns the repo to docs + `m0/ceiling.py` + `m0/mechanics.py`. |
| §1 scope decision reversed at the gate | Delete `wct/aggregate.py`, `wct/diffuse.py`, `wct/derive.py` and their tests; mark invariants 1–3, 6, 7 deferred to slices 4/5/6 in `prereg.yaml`. The three modules are self-contained files with no callers outside `m0/`, so this is a deletion, not an unpick. |
| Schema churn breaks a later slice | `wct/schema.py` carries `SCHEMA_VERSION`, included in the cache key. A later slice pins the version it was built against; mismatched artifacts are rejected loudly rather than silently reinterpreted. |
| Simulator found to be tuned to pass | Generator parameters live in `prereg.yaml` and are committed *before* the invariant tests are written; `git log prereg.yaml` shows any later movement, and each is a recorded deviation. |

All slice-1 work lands on `main` as local commits only. Push is human-only, so nothing
leaves the machine and no reversal needs to be coordinated with a remote.

## 6. Risks

| Risk | Handling |
| --- | --- |
| Scope creep from §1's decision — slice 1 absorbs three later modules | Bounded to analysis-side, inference-free code. `nodes/extract/cluster/measure` stay out. Plan gate accepts or rejects explicitly. |
| Vacuous invariants that pass without exercising the case | Each test asserts the discriminating condition occurred first |
| Simulator tuned until invariants pass | Generator parameters are declared in `prereg.yaml` before the invariants are written; changing them to make a test pass is a recorded deviation |
| Schema churn breaking later slices | `wct/schema.py` versioned; cache key includes schema version |
| AO\* exponential blowup on dense OR nodes | Report the two-stage max-closure relaxation gap; cap search and log the cap rather than truncating silently |
| M0 passing is mistaken for evidence about real models | Protocol §6.13 already registers this; `gate.py` prints the disclaimer on success |

## 7. Acceptance criteria

From `REQUEST.md`, with how each is discharged and how it is verified.

- A1: `uv` venv pinned to Python 3.12 with protocol §2 dependencies installed and locked. → §3 step 1; verified by `uv.lock` committed and `uv run python -V` reporting 3.12.
- A2: `prereg.yaml` skeleton carrying every field protocol §3.1(4) lists, `delta` unset and marked as blocking R0. → §3 step 1; verified by a test asserting every required key is present and every `delta` is `null`.
- A3: Cache layer per protocol §2 layout, write-once, content-hashed, keyed on (item, resolved model/provider metadata, prompt template, decode params, requested seed). → §3 step 2; verified by unit tests including a rewrite-rejection case.
- A4: `simulate.py` generates latent truth, sources with sensitivity/FPR/truth-dependent coverage, shared-misconception component, duplication, decomposition granularity, alignment confusion, and AND/OR derivations with configurable defect rates. → §3 step 3; verified by invariants 1–7 exercising every generator knob.
- A5: Protocol §3.0 invariants 1–7 implemented as tests and passing. → §3 step 5; verified by `m0.gate` and `pytest`, with the guard assertions in §4.1.
- A6: Existing invariants I8–I14 run in the same invocation and still pass. → §3 step 5; verified by `m0.gate` invoking `ceiling.py` and `mechanics.py`.
- A7: Sweep over mean reliability, residual correlation, shared-wrong rate, union coverage, alignment precision/recall, dependency precision/recall, panel size `M`. → §3 step 6; specified in §4.2; verified by `failure_surface.csv` covering the full declared grid with no erroring cell.
- A8: Failure-surface output plus break-even boundary where each WCT variant overtakes single-source and voting baselines. → §4.2; verified by `breakeven.json` carrying a value or an explicit `null` + reason for every method.
- A9: Comparison across single-best, uncapped counting, WCT-U, WCT-EM, oracle WCT-C, estimated WCT-C, diffusion, linear-path diagnostic, and dependency-closed AND/OR selection. → §3 step 4 builds them; §4.2 compares them; verified by every method appearing in `failure_surface.csv`.
- A10: One command runs the whole M0 gate and exits non-zero if any invariant fails. → `uv run python -m m0.gate`; verified by a test that forces an invariant failure and asserts a non-zero exit.

Schema ownership (REQUEST.md OQ4) and the §1 scope decision are resolved in `DECISIONS.md`.

## 8. Definition of done

`python -m m0.gate` exits 0 with invariants 1–14 passing; `pytest` green; `uv.lock`
committed; `prereg.yaml` present with `delta` unset and flagged; sweep artifacts written;
no network call anywhere in the slice; the §1 scope decision either ratified or reversed at
the plan gate.

## 9. Open questions

**Resolved at the step-4 gate** and recorded in `DECISIONS.md`: the §1 scope decision, OQ4
(slice 1 owns `wct/schema.py`), and the gate/sweep split. Nothing now blocks build.

**Still open, and deliberately not blocking this slice.** OQ1–OQ3 from `REQUEST.md` are
slice-2+ blockers, carried here so they are not rediscovered at R0:

- OQ1 — who sets the `delta` values R0 blocks on, and does slice 2 stop and wait?
- OQ2 — does a failed experimental gate abandon the workstream or park it for a human
  go/no-go?
- OQ3 — dataset sourcing for E1 (checkable multi-step items) and E3 (open-ended items with
  criterion rubrics): existing benchmark, hand-authored, or both?

OQ3 is the one with the longest lead time and it gates both slice 2's manifest freeze and
slice 4's labelling. It should be answered during slice 1's build rather than discovered at
R0.
