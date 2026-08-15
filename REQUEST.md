# Request: Slice 1 — Scaffold and M0 mathematical gate

Workstream `20260727-201552-894582b7`, slice 1 of 7. Master: `MASTER.md`.
Specification: `EXPERIMENT.md` §2 (harness architecture) and §3.0 (M0).

## Thoughts / context

> build it

Build the experiment specified in `EXPERIMENT.md` against `plan.md`. Science experiment,
not production code: efficiency and falsifiability over robustness.

This slice is the repo scaffold plus the mathematical gate that must pass **before any API
call is made**. M0 makes every latent variable observable and tests whether the
implementation behaves correctly under its own stated assumptions. Protocol §3.0: "Do not
spend API calls until all invariants pass."

Stage zero already holds: git is initialised with a pre-freeze baseline commit, and M0
invariants I8–I14 are implemented and passing in `m0/ceiling.py` and `m0/mechanics.py`.
This slice adds the simulator and invariants 1–7 around them.

## Constraints

- `EXPERIMENT.md` is the specification; where this document disagrees, the protocol wins.
- Python venv pinned to 3.12 via `uv`; 3.14 is the system default and lacks torch wheels.
- No GPU. **No model or inference API calls anywhere in this slice** — no OpenRouter, no
  local generation endpoint, no embedding endpoint. Package installation from PyPI is
  expected and permitted; "no network" means no inference, not no packaging.
- `Date.now()`-style nondeterminism is banned in simulation code paths: fixed seeds, and
  the seed recorded in every result row.
- Simulator output schema must match the real cached-artifact schema so E1–E2.5 analysis
  code is shared rather than reimplemented.

## Non-goals

- Any node generation, extraction, clustering, NLI measurement, or judging.
- Claim B work of any kind.
- Everything in protocol §5 "Deliberately not built".

## Acceptance criteria

- A1: `uv` venv pinned to Python 3.12 with protocol §2 dependencies installed and locked.
- A2: `prereg.yaml` skeleton carrying every field protocol §3.1(4) lists, with `delta` values explicitly unset and marked as blocking R0.
- A3: Cache layer implementing the protocol §2 artifact layout, write-once and content-hashed, keyed on (item, resolved model/provider metadata, prompt template, decode params, requested seed).
- A4: `simulate.py` generates latent proposition truth, sources with configurable sensitivity/FPR/truth-dependent coverage, a latent shared-misconception component, claim duplication, variable decomposition granularity, alignment confusion, and acyclic AND/OR derivations with configurable missing-premise and invalid-inference rates.
- A5: Protocol §3.0 invariants 1–7 implemented as tests and passing.
- A6: Existing invariants I8–I14 run in the same test invocation and still pass.
- A7: Sweep over mean reliability, residual correlation, shared-wrong rate, union coverage, alignment precision/recall, dependency precision/recall, and panel size M.
- A8: Failure-surface output plus the break-even boundary where each WCT variant overtakes the single-source and voting baselines.
- A9: Comparison across single-best source, uncapped claim counting, WCT-U, WCT-EM, oracle-parameter WCT-C, estimated WCT-C, diffusion, linear-path diagnostic, and dependency-closed AND/OR selection.
- A10: One command runs the whole M0 gate and exits non-zero if any invariant fails.

## Open questions

- OQ1: R0 (slice 2) blocks on `delta` values, which cannot be set until datasets and rubric scales are frozen. Who sets them, and does slice 2 stop and wait for that decision?
- OQ2: Slices 3–7 are conditional on empirical results. Should a failed experimental gate abandon the workstream outright, or park it for a human go/no-go?
- OQ3: Dataset sourcing is unspecified. E1 needs checkable multi-step items; E3 needs open-ended items with criterion-level rubrics. Existing benchmark, hand-authored, or both?
- OQ4: Protocol §3.0 requires the simulator to emit "a schema matching the real cached artifacts", but that schema is not itself specified anywhere. This slice must define it, which makes slice 1 the de facto owner of an interface every later slice depends on. Confirm that is intended.
