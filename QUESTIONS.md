# Questions

The spec review budget is spent (3/3 round(s) used). A human decision is required.

## ⚠ The previous findings are STALE — they are NOT blocking you

The diff has MOVED since the last review (`975cf89b3c6b` → `89f8245fdfd2`).
GPT has **not** reviewed the current code. The findings below describe an EARLIER diff and
**may already be fixed** — they are shown for context only and are deliberately NOT listed as
blocking items.

What you almost certainly want:

```bash
relay.py grant-rounds --n 2 --reason "converging; needs another review round"
relay.py spec          # re-review the CURRENT diff
```

The commit remains blocked, but by the correct reason — `commit-ready` reports the GPT verdict
as STALE (bound to an earlier diff), not by the fixed findings below.

### What the last review said (about OLDER code — may be fixed)

- [blocker] expected 'B4: Pin an observed expected echo for every panel member, verify the declared qwen fallback, and verify local qwen by both model_path and n_params.'; actual 'out/slice4/smoke/smoke.json has no successful echo for glm, nemotron, gptoss, gemma, laguna, or qwen_or. Local qwen reports n_params=null. prereg_v3.yaml therefore uses requested-id defaults for the remote members, and exp3.smoke_v3.tag_ready() reports the registration incomplete.' -> Run successful bounded probes for every registered endpoint and fallback, persist their observed identities, and obtain an independently verifiable n_params measurement for local qwen before rebuilding the registration.
- [blocker] expected 'B2: Use the stated slice-1 variance basis and register the approximately 0.0101-nat detectable M=3-to-M=5 increment at n=9,805.'; actual 'prereg_v3.yaml registers 0.0071 nats using only SDs from conclusive base-instrument cycles (0.1606–0.2514). REQUEST.md OQ1 and PLAN.md instead specify approximately 0.0101 and a variance range extending to about 0.313.' -> Recompute power using the variance basis required by REQUEST/PLAN, or obtain an explicit request amendment before freezing a different basis and detectable floor.
- [blocker] expected 'B1/B6 and T5: Implement the registered primary using delta=0.0448, a frozen calibration map, and the fixed M-member panels.'; actual 'exp3.run_cycle3 delegates primary decisions to wct3.arms, where FROZEN_DELTA is hard-coded to 0.02; the registered 0.0448 is only copied into provenance. The driver also hard-codes platt without an explicit primary-map field and analyses items with min_agents=2, so an M=5 result can be based on fewer than five sources.' -> Read the primary delta and calibration map from prereg_v3.yaml, adjudicate P1 against 0.0448, and require the registered fixed membership or a preregistered missing-data rule.
- [blocker] expected 'B6/T5: Compute the dose-response with the registered paired item-block bootstrap over per-item M=5 minus M=3 margins.'; actual 'per_item_margin returns proposition-level losses with repeated item IDs. dose_response then maps each ID to its last proposition while retaining repeated IDs, effectively weighting by proposition count and discarding other propositions rather than averaging within each item.' -> Aggregate proposition losses within each item first, pair one margin per shared item, then bootstrap those item-level increments; add a multi-proposition regression test.
- [blocker] expected "B3/T5: Execute the registered sixth-family promotion and qwen fallback when their triggers fire, including checking qwen's loaded weights."; actual 'run_cycle3.py only appends a fallback/promotion event and mutates a local members list. It never generates the replacement member, does not add replacement generations to cell, and later filters analysis using the original registered member sets. It also performs no runtime model_path/n_params check for qwen.' -> Perform identity preflight, execute the registered replacement as a complete model-major pass, update each affected nested panel deterministically, and preserve/report pre-promotion data as registered.
- [blocker] expected 'B7: Count every endpoint attempt against persistent call and dollar caps, with retry, fallback, and promotion volume included in per-panel caps.'; actual 'generate_member charges once before nodes.Client.generate, but Client._call performs its own retries and repeated 429 attempts, so actual requests are not fully charged. Per-panel caps cover only base-panel retry allowance and exclude the priced promotion/fallback passes; the M=5 USD cap is $22.38 although the qwen fallback alone is priced at $53.71.' -> Centralize retry accounting at the HTTP-attempt boundary and derive enforceable per-panel caps that include every permitted contingency while remaining within the authorized total.
- [blocker] expected 'B10: The one-command gate exits non-zero whenever any assertion is unmet, with its exit code as the sole pass signal.'; actual "run_slice4.sh --allow-incomplete-smoke exits successfully and prints 'GATE PASSED with B4 UNMET'. The gate's happy-path test invokes this bypass." -> Remove the passing bypass from the production gate, or make any incomplete-smoke execution return non-zero and keep test-only bypassing outside the pass-signalling command.
- [major] expected 'B1: Freeze one unambiguous role-prompt schedule before generation.'; actual 'prereg_v3.yaml describes a Latin square over forward/backward/skeptic, but role_set and run_cycle3.py rotate forward/backward/skeptic/neutral. The registered schedule and implementation therefore disagree.' -> Choose one role set, emit it consistently in the schedule and role_set fields, and test exact assignments across items and members.
- [missing/blocker] B9: Annotated tag prereg-v3-2026-08-30 resolving to the tested registration tree, created before any cycle-3 generation. (No matching tag exists, so the protocol remains a draft and B8 correctly prevents non-dry generation.)

### Decide

- [ ] Grant more review rounds (`relay.py grant-rounds --n N --reason ...`), or accept the
      change as-is, or re-scope REQUEST/PLAN.

Run: `20260830-221830-30689369`
