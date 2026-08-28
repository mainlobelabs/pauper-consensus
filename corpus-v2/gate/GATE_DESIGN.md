# Per-topic contamination gate, corpus v2

Registered 2026-08-28 (tag prereg-waveconsensus-v2) BEFORE any gate probe
result is seen. Implements the Phase 5 design rule: "any topic where a panel
model shows knowledge is dropped" (NOTES.md).

## Purpose

Batch-4 cutoff probes verified the window 2026-02-15..08-27 blind for the 27B
solver only. The panel base models (4B/1B class) were never checked against
this specific window, and two panel members (OLMoE-1B-7B, Qwen3.5-4B) have no
documented cutoff. This gate checks each of the 251 primary topics individually.
Fine-tuned adapters inherit base-model knowledge, so only base models are probed.

## Panel (7 base models, helium, omlx instances 8102-8107)

llama-3.2-1b-instruct, llama-3.2-3b-instruct, gemma-3-1b-it, gemma-3-4b-it,
phi-4-mini-instruct, olmoe-0125-instruct, qwen35-4b.
Weights in /Volumes/nvme0/models (base dirs + fused ft dirs present for the
jury phase).

## Probes

- 5 probes per topic x 251 topics = 1,255 probes, authored from the
  fact-checked [V]/[V*] annotations in corpus-v2/topics.md. Answer key = the
  verified fact; aliases cover reported variants (e.g. disputed tolls).
- Each probe targets ONE specific value: multi-digit number, proper noun, or
  exact date. Small single-digit integers are used only when they are the
  distinctive fact (e.g. final toll 9).
- Files: corpus-v2/gate/probes-2026-MM.jsonl per month batch (+ probes-reserve.jsonl),
  one JSON object per probe:
  {"topic_id","probe_id" (P1..P5),"q","key","aliases":[...],"kind"
  (number|name|date|place)}. gate_run.py accepts multiple --probes files.
- Global canaries, run for every model in the run:
  - GC1 must KNOW: "Who won the 2022 FIFA World Cup?" -> Argentina.
    A model that fails GC1 is FLAGGED (broken instance/template); its results
    are recorded but do not trigger topic drops.
  - GC2 must NOT KNOW: the V2-001 P1 probe (in-window specific fact). A model
    that answers GC2 CORRECT is FLAGGED the same way.
- Probe authoring constraint: questions must not contain the answer value.

## Call parameters (identical to cutoff-probe/probe_jury.py convention)

temp 0, max_tokens 64, chat_template_kwargs.enable_thinking=false (ignored by
servers without it), one question per call, 3 retries on transport error,
300s timeout.

## Scoring (per model, per probe)

- CORRECT: response contains the key or an alias (case-insensitive; numeric
  keys match the number with or without commas/suffixes).
- WRONG: a specific answer that does not match.
- UNKNOWN: refusal, "in the future", "not in my training data", no specific
  answer.
- Automatic scoring by gate_run.py, then reviewed; review overrides (with
  reason) archived in gate_review.jsonl and take precedence.

## Drop rule (pre-registered)

- topic-model KNEW = >=1 probe CORRECT (after review), and the model is not
  flagged by canaries.
- TOPIC DROPPED = KNEW by >=1 panel model.
- Survivors proceed to article writing. If survivors < 160 (hard minimum),
  the 30 reserves are gated the same way and added; if still < 160, scope
  decision with the co-designer (no post-hoc relaxation of the drop rule).

## Cost

251 x 5 x 7 = 8,785 topic calls + 2 canaries x 7 = 8,799 total. Each call
<1k tokens. Across 6 omlx instances, max-concurrent-requests 8 per instance.

## Archive (CRITICAL house rule: archive at run time)

corpus-v2/gate/runs/2026-08-28/:
- gate_results.jsonl: one line per (model, topic, probe) with full response
  text, score, instance, timestamp.
- gate_review.jsonl: review overrides.
- gate_summary.json: per-topic per-model CORRECT counts + DROPPED verdicts.
- manifest.json: git hash, model list, instances, call parameters, start/end.
