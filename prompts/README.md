# Frozen prompts (P1-9)

Drafted 2026-08-26 per PLAN task 9. Final text freezes in `prereg.yaml` at
Phase 2; changes after the freeze are a spec revision, not an edit.

- `solver_baseline.md` the 27B solver prompt, no contract. This is the
  without-prompt baseline control: the ordinary defendant answers.
- `jury_contract.md` the claim-verification prompt, the jury contract. One
  call per claim, out `{ answer: PASS|FAIL|NOT_STATED, reason }`. Used by
  the zero-shot jury (P4), the self-distillation targets (Phase 4), the
  frontier self-review control (27B with the same prompt), the losslessness
  check, and the registered solver-as-proposer arm.
- `covariates.md` the covariate feature list: what gets recorded per
  article, per claim, per juror x claim, per solver x question, per
  family.

Shared conventions:

- Article text is always the verbatim file content of
  `corpus/articles/T##.md` (title, byline, body), wrapped in `<article>`
  tags.
- System message: none (model default) for both prompts.
- Temperature 0 for all calls. Thinking off where the model exposes a
  thinking toggle (the 27B solver uses
  `chat_template_kwargs: {"enable_thinking": false}`, matching the
  deployed configuration).
- The 27B runs on the hydrogen endpoint (`http://100.95.144.25:8000/v1`,
  model `qwen3.8-27b`). Jury models run on marzuki-helium (oMLX).

## Open corpus item (before Phase 2)

The jury contract takes "the claim in question form". The 40-proposition
pool is declarative. Each proposition needs a frozen question-form
rendering (40 per article, 1,200 total), stored in
`corpus/pool/question_form/T##.md`, produced by the polar conversion rule
in `jury_contract.md` ("Is it true that {proposition}?", claim verbatim)
and content-hashed at the Phase 2 freeze. The seed mapping (which pool
propositions each seeded question targets, for solver scoring) is
formalized in `corpus/pool/metadata.json`. This pass is open; it is part
of the task 9 deliverable.
