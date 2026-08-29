# Pauper Consensus

A pre-registered research experiment. We test a sharpened form of cross-model
proposition-level consensus: instead of running generic models and aligning their
free text, we fine-tune several small proposers on a corpus so each emits a set of
structured atomic propositions, then aggregate **one vote per source** and measure
whether the resulting support predicts proposition truth.

It is an independent replication-and-refinement of Mannings & Marzuki,
*The Flip Was in the Instrument: Two Pre-Registered Cycles of Cross-Model
Proposition Aggregation* (2026). The source paper's instrument failed at the
free-text-to-proposition boundary (its NLI alignment layer scored 0 of 607
negative-polarity propositions). Pauper Consensus removes that boundary by making
propositions structured, and re-runs the frozen gate.

## Install

```bash
uv sync
```

## Run

```bash
uv run pytest
```

## Test

Same command. One passing test suite ships in the bootstrap; it covers the
one-vote-per-source cap, silence-as-a-state, and negative-polarity handling.

## Docs

- `SPEC.md` the research spec (question, design, gate, predictions, deliverables).
- `PLAN.md` the living plan (phases, current state, next step).
- `AGENTS.md` exact commands and ground rules.
