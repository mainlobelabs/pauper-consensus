# Session handoff — 2026-08-31

State after the GPU/instrument work and slice 4 (cycle-3 registration).

## Where things stand

**Slice 4 is NOT conformant yet.** Three acceptance criteria are outstanding,
and they are a chain rather than three separate jobs:

| id | state | why |
|----|-------|-----|
| B4 | **unmet** | no observed echo for the 5 OpenRouter members + the declared fallback; needs `OPENROUTER_API_KEY`. The local qwen member now verifies FULLY (both `model_path` and `n_params`). |
| B9 | **unmet** | the tag cannot be created while B4 is unmet — the gate refuses |
| B11 | **regenerates** | the DECISIONS entry is rendered from the registration; it goes stale whenever the registration changes and is rewritten by the next gate run |

Everything else is built, gated and committed, and the cross-model spec review
has been through four rounds. Do not read "gate passed" as "slice done": the
gate exits **2** precisely to say "every assertion met EXCEPT B4".

    ./run_slice4.sh            -> exit 2  (every assertion met EXCEPT B4)
    ./run_slice4.sh --smoke    -> needs OPENROUTER_API_KEY; closes B4
    ./run_slice4.sh --tag      -> refuses while B4 is unmet

Exit codes are the pass signal: `0` everything met, `2` only B4 outstanding,
`1` a real assertion failed.

## What you need to do

1. **Export `OPENROUTER_API_KEY`** (it is not in my environment, any dotenv, or
   any profile I could read — it was exported in your interactive shell when
   slice 3 ran).
2. `./run_slice4.sh --smoke` — probes the six panel endpoints + the qwen
   fallback, ONE call each at 64 max_tokens (cents). This writes the observed
   echoes that B4 requires.
3. Re-run `./run_slice4.sh`. If it exits 0, `./run_slice4.sh --tag` creates
   `prereg-v3-2026-08-30`, annotated with the registration and evidence
   fingerprints.
4. **Push** — 9 local commits (this session's 7 plus 2 earlier), and pushing is human-only:  `git push origin e1-results-and-paper`

## Commits this session

    76d2c49  GPU NLI in fp32, and the fp16 instrument finding that forced it
    db17a28  Slice 4: cycle-3 registration on 9,805 items, delta=0.0448
    cea4035  Slice 4 spec round 1: close 7 of 8 blockers
    ad64dcf  Slice 4 spec round 2: close 7 more blockers
    911ef0b  Slice 4 spec round 3: contingency pricing, full-progression adjudication
    653e276  Slice 4 spec round 4: n_params pin closed from the GGUF; caps clamped

## The two findings that matter most

**The NLI instrument was never fp32.** The checkpoint config declares
`dtype=float16` and transformers honours it on CPU too, so cycles 1-2 were
measured in fp16 — which is DEVICE DEPENDENT (4.4e-03 CPU-vs-GPU, with argmax
flips). fp32 is device independent (7.8e-06, none) and on CPU is also 2.7x
faster, so the frozen path took the slowest, least accurate and least
reproducible option. Cycle 3 registers fp32/GPU; the driver fails closed rather
than falling back. Throughput 43 -> 2,500 pairs/sec, so a full pass is ~1.4 h
instead of ~80 h. Cycles 1-2's published results are UNAFFECTED: re-aligning
panel A under fp32 reproduced all 1,565 observations exactly.

Do NOT mix precisions in one analysis. The smallest observed alignment margin
is 0.0021, exactly 1x the fp16->fp32 perturbation. Cycle 3 uses a separate
`WCT_CACHE` root; the gate pins the frozen cache at 1826 entries.

**delta = 0.0448, from the CONCLUSIVE cycles only.** c2_panelB's margin is
+0.0329 with a CI spanning zero, so it is excluded rather than allowed to lower
the floor. The cycle-2 artifacts carry both the base instrument and the
registered S1_deny_self_contradiction variant; the base is primary and the node
is now PINNED in code. REQUEST.md decides it — "three of four panel-cycles, and
inconclusively on the fourth" is true only under the base reading. The variant
is reported as declared sensitivity.

## Registration summary

| | |
|---|---|
| corpus | 9,805 items, sha `63ca8131…e504a1`, cycle 2's 150 a complete subset |
| delta | 0.0448 nats (min conclusive margin, argmin c1_local) |
| power | primary needs 101-248 items; dose floor 0.0071 nats at n=9,805 |
| panels | 6 families, M=3 ⊂ M=4 ⊂ M=5, rank 6 (laguna) declared margin |
| instrument | fp32 / cuda, fail-closed, separate cache root |
| cost | 58,830 calls authorised, worst case $90.29 under a $121 cap |

## Environment

- `.venv` — frozen, torch 2.13.0+cpu. Reproduces cycles 1-2. **Do not change.**
- `.venv-cuda` — torch 2.13.0 + CUDA 13, both GPUs. New cycles only.
- llama-server is back up on :8083 at tensor-split **70,30** — the best of your
  sweep (1389 MiB free, 80.06 t/s). Note the sweep never reached its 2000 MiB
  target; the answer lies beyond the swept range (72,28 / 75,25).
- LM Studio on :1234 serves the nomic embedder AND qwen3.8-27b.

## Known gaps, stated plainly

- **B4 unmet.** Five remote endpoints and the fallback have no observed echo.
- **B9 unmet.** No tag exists, so cycle 3 may not generate.
- **B11 is fingerprint-bound.** It reports STALE whenever the registration is rebuilt;
  running the gate rewrites it. That is by design, not a defect.
- **Spec conformance is not yet clean.** Five review rounds have run; each found real
  defects and each was addressed. The last verdict still lists B4/B9 (the credential
  chain) plus items fixed after it was issued. Expect the next round to find more — treat a
  `conforms: true` verdict, not my summary, as the completion signal.
- **n_params: CLOSED.** `/props` does not expose it, but the loaded weights file does:
  the GGUF header of the `model_path` that `/props` reports carries
  `general.size_label = 27B`, matching the registered pin. Both halves of qwen's
  identity now verify, and a mismatch fails the check.
- **The registration is not tagged**, so cycle 3 may not generate. The driver
  refuses any non-dry run without the tag resolving to the tested tree.
- **`paper.md` is untouched.** The fp16 disclosure is durable in DECISIONS.md and
  GOTCHAS.md; publishing it needs a separately authorised paper slice, since
  "any change to paper.md" is an explicit non-goal of this slice.
