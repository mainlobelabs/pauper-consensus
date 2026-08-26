# wave-consensus

One line: a pre-registered experiment testing whether corpus-fine-tuned proposers that emit structured propositions, aggregated one-vote-per-source, predict proposition truth better than base rate, the single best proposer, and zero-shot panels.

## Commands

- format: `uv run ruff format .`
- lint: `uv run ruff check .`
- test: `uv run pytest`
- check (lint + format): `uv run ruff check . && uv run ruff format --check .`

## Ground rules for this repo

- This is a research project. The instrument matters more than the result.
- The registration (`prereg.yaml`) is frozen and git-tagged before any training or
  generation that it covers. Do not edit a frozen registration; cut `prereg_v2.yaml`.
- Every number in a report is read from committed artifacts under `out/`. Analysis
  re-runs run over the immutable content-hashed generation cache at zero inference cost.
- ARCHIVE ALL RUN LOGS AND ARTIFACTS (extremely critical, Andryo 2026-08-26): every run
  persists raw model outputs, server/download logs, stderr, and a run manifest
  (date, host, versions, model + weight sha256, commands, runner git hash) at run time.
  Never rely on console output; if it is not in a committed file it did not happen.
  See GOTCHAS.md 2026-08-26 (operations) for the exact convention and the helium run
  dir layout.
- Label analyses REGISTERED (frozen before the data they touch) or POST-HOC.
- Keep `DECISIONS.md` and `GOTCHAS.md` current. They are part of the record.

## Layout

- `src/wave_consensus/` package. `votes.py` is the one-vote-per-source primitive.
- `tests/` pytest.
- `SPEC.md` research spec. `PLAN.md` living plan (update at the end of each session).
