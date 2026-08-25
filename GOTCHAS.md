# GOTCHAS

Known environment constraints and traps. Newest first.

## 2026-08-25 (design)

- "Post-cutoff" is fuzzy, not a wall. Cutoff dates differ per family and drift
  with fine-tuning corpora. A topic that looks post-cutoff can be in one model's
  data. This is why the no-article contamination run is a Phase 2 gate, not an
  assumption: any seed question answered above chance without the article is
  flagged and re-selected or relabelled.
- Ground truth is single-labeler (the author). The CONTRADICT vs UNSPECIFIED
  boundary is a judgment call, and the whole negative class depends on it. The
  rubric must ship with worked examples of both sides, and the 10 percent
  re-check measures the wobble. This is disclosed in the report, not hidden.
- In-passing mentions are the UNSPECIFIED generator, which means the article's
  secondary facts must be real and checkable. A wrong secondary fact in the
  article silently relabels a batch of propositions. Verify each article's
  named real-world facts against the web before locking the corpus.

## 2026-08-25 (bootstrap)

- `uv init --bare` does not install the local package, so `tests/` import
  `wave_consensus` from `src/` via the `pythonpath = ["src"]` pytest option.
  If you move the package or add a build system, update that option.
- The bash tool resolves the working directory before running the command,
  so a `workdir` that does not exist yet errors before `mkdir` runs. Create the
  directory in a command that has no `workdir`, then use `workdir`.
- Python here is 3.14, so `StrEnum` (not `str, Enum`) is the clean base. Ruff
  rule UP042 enforces it.
