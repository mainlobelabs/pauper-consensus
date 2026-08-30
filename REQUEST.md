# Request: Slice 3 — five-family availability, measured before anything is registered

Workstream `20260828-181135-0d060fc4`, slice 3 of 4. Master: `MASTER_v3.md` §"Slice 3".
Prior slices: `e63f946` (corrected instrument), `87bfb7f` (paper corrections).

## Thoughts / context

> Do all three

Slice 4 registers a dose-response across panel sizes. The five-family target has now failed
TWICE on availability: cycle 1 found three families locally, not five (`GOTCHAS.md`,
2026-08-07: `deepseek-v4-flash` failed to load, and two ornith variants are ONE family, not
two); cycle 2 had to rebuild panel A mid-programme when two of its three models left the
catalogue. `paper.md` §8 records the target as never met. Registering M=5 without measuring
first risks freezing a design that cannot be run — which is the specific error this
programme exists to document.

Reframing that matters: the two cycle-2 panels already span SIX distinct families —
qwen, poolside (laguna), zhipu (GLM), nvidia (nemotron), openai (gpt-oss), google (gemma).
So the question is not "can five families be found" but "do the six already-pinned ones
still answer today, and does the answer leave five". One failure still leaves five; two
failures do not.

Known hazards, from `prereg_v2.yaml` and `GOTCHAS.md`:
- The `:1234` LM Studio catalogue LISTS `qwen3.8-27b` but 400s on completion. qwen serves
  on `:8083` under the stale launch alias `ornith35`. A model-list call would report it
  available when it is not, which is why E1 requires a real generation.
- Two variants of one family are not two independent sources.
- GLM-5.2 via Hoonify is PAID ($1.40/$4.40 per 1M). One trivial call per endpoint.

## Constraints

- **Real generation per candidate, not a catalogue lookup.** A listed model that fails to
  complete is the exact cycle-1 failure.
- **One trivial probe per endpoint.** No experimental item, no corpus content; the existing
  `exp/smoke_v2.py` throwaway theory is the shape to reuse.
- **One auxiliary, non-generation request per run is authorised**: `GET /api/v1/models`,
  to read paid rates live so a stale hard-coded rate cannot misstate spend. It is not
  billable and is declared in the artifact under `probe.auxiliary_requests`. Added here
  because the plan introduced it and this document, which governs scope, had not.
- **Third-party egress** is pre-approved for this project (`DECISIONS.md` 2026-07-27,
  OQ2 original) and is limited here to the smoke probes.
- **AMENDED 2026-08-30 (human instruction).** The paid OpenRouter tier is authorised
  and its harness binding is to be used (`harness.toml [providers.deepseek_paid]`,
  `kind = openrouter_paid`, on `OPENROUTER_API_KEY` — the account holding purchased
  credit). The scope therefore extends beyond the pinned six to their PAID-TIER TWINS,
  because `:free` is a tier suffix rather than part of the model: `openai/gpt-oss-20b`
  exists while `openai/gpt-oss-20b:free` returns 404 ("unavailable for free"), and the
  gemma and laguna `:free` tiers rate-limit. Twins are probed and reported SEPARATELY
  with `tier: paid`; they never count toward the pinned total.
- **No experimental generation, no cycle-3 corpus, no registration.** That is slice 4.
- The v2 tag stays byte-clean: no edit or addition under `exp/`, `wct/`, `m0/`.
- `out/v3/` and `out/e1*_summary*.json` remain byte-identical to `e63f946`.
- Findings are recorded whatever they are. If five families are not available, that is the
  result; the workstream does not stall and does not quietly register a design it cannot run.

## Non-goals

- Choosing cycle-3's panels, corpus, delta or predictions (slice 4).
- Any change to `paper.md`. Slice 2's corrections stand.
- Re-analysis of any kind; `out/v3/` is settled evidence.
- Hunting for NEW providers beyond the pinned six plus any already reachable locally. The
  question is whether the registrable set exists, not whether it can be maximised.

## Acceptance criteria

- E1: Every candidate endpoint smoke-tested by an attempted GENERATION that must return
  usable content, not a model-list or health call. Failures are recorded with their error.
- E2: Resolved serving identity recorded per model — the id requested, the id echoed, and
  for local models the loaded weights — so a substitution is detectable rather than assumed
  absent.
- E3: Distinct FAMILIES counted, not model ids, with the family attribution stated per model
  and two variants of one family counted once.
- E4: A written verdict on whether M=5 is registrable today, and which M=3 subsets the
  available set supports, with family disjointness stated.
- E5: If fewer than five families answer, the finding is reported plainly and slice 4 is
  told what IS available. No stall, no silent downgrade.
- E6: Cost bounded and reported: one probe per endpoint, with the paid endpoint's spend
  stated. No experimental generation.
- E7: One command runs the whole slice and exits non-zero on any failed assertion; the v2
  tag and the pinned evidence are asserted unchanged.
- E8: `DECISIONS.md` entry recording the measured availability and its consequence for
  slice 4, derived from the emitted artifact rather than written from expectation.

## Open questions

- OQ1: RESOLVED (human, 2026-08-30). M=5 is registrable ONLY WITH MARGIN — that is, only if
  MORE than five families answer, so one disappearance still leaves five. If exactly five
  answer, slice 4 registers M=3/M=4 as its primary with the fifth family as a DECLARED
  STRETCH ARM. Rationale: this programme has twice had models vanish mid-flight, and cycle 2
  had to rebuild a panel for exactly that reason. Registering M=5 on exactly five means one
  disappearance forces an unregistered substitution or an abandoned arm, which is what
  `prereg_v2.yaml`'s "exact pinned id or the panel is DROPPED" rule exists to prevent. A
  stretch arm degrades the design instead of breaking it, and the dose-response is still
  tested. Slice 3 must therefore report the family count AND the margin, not just whether
  five exist.
- OQ2: Probe the six already pinned. Additional local families may be probed at zero cost
  and reported as MARGIN CANDIDATES, clearly separated from the pinned set, since OQ1 makes
  margin the deciding quantity. They are not adopted here; slice 4 adjudicates.
