# Request: Build plan for the WCT spike experiment

## Thoughts / context

> Assess whats in this repo, and create a build plan to run an experiment, use scientific
> thinking here, this is a science experiment not production code, so be efficient but
> creative

Repo contains two documents and no code:
- `wave-convergence-thinking.md` — the original hand-drawn notes (wave-pool sketch, loss
  curve, amplitude table worked example).
- `plan.md` — a mature design-of-record: two separable claims (A: cross-architecture
  convergence is a quality signal; B: zero-inter-node-communication topology suits mixed
  local hardware), six-stage architecture, prior-art positioning, evaluation with a single
  go/no-go gate, known weaknesses, salvage value.

The deliverable for this run is a **build plan for the experiment**, not the experiment's
code. Emphasis on scientific validity (falsifiability, controls, statistical power) over
engineering polish.

## Acceptance criteria (proposed)

- [x] A1: Assessment of what exists, and what the environment can actually support.
- [x] A2: A build plan structured as a ladder of falsifiable experiments, each with a
      stated prediction and a **pre-registered kill threshold**, ordered by
      cost-to-information ratio.
- [x] A3: The plan identifies methodological defects in `plan.md`'s current evaluation
      design and states the correction.
- [x] A4: Negative controls / null models are specified, not just treatment arms.
- [x] A5: Resource plan is grounded in measured environment facts (models actually
      reachable, hardware actually present), not assumptions.
- [x] A6: Explicit scope discipline — what is deliberately NOT built in the spike.

## Constraints

- Science experiment, not production code. Efficiency over robustness.
- `plan.md` §10: two weeks, one gate, deliberate go/no-go. Do not let scope drift.

## Non-goals

- Writing the experiment's implementation code (this run produces the plan only).
- Claim B hardware/cluster work — gated behind Claim A per `plan.md` §6.3.

## Open questions

- OQ1: Is the two-week envelope in `plan.md` §10 wall-clock or working days?
- OQ2: Is OpenRouter free-tier inference acceptable for node generation (prompts are
  public benchmark items; no repo content egresses), or must nodes be local-only?
- OQ3: Is a published/external novelty claim in scope, or is this internal-only? Affects
  how much prior-art re-checking (`plan.md` §3) is warranted.
