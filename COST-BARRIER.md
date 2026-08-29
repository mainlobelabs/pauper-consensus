# Cost / barrier-to-entry comparison (AUD)

v2 wave-consensus: single 27B frontier-adjacent model vs 12-config jury of 3–4B
models. Purpose: quantify the "low barrier to entry" claim for the paper.

All prices AUD. Hardware prices: owner-reported for the two cards actually
used in the experiment (RTX A$9,100, Mac Studio A$6,300); 2080 Ti from the
AU used market (A$500–800 typical, eBay AU up to A$1,200; AU market review
Feb 2026). FX: 1 USD = 1.3958 AUD (2026-08-28 close) for reference only.

## Hardware rows

| Route | Silicon | VRAM | Year/gen | Price (AUD) | TDP |
|---|---|---|---|---|---|
| 27B single model | RTX PRO 5000 Blackwell (48GB GDDR7) | 48 GB | 2025, Blackwell | **$9,100** (owner-reported; US street $5.2k–9k) | 300 W |
| Jury (as run) | Mac Studio M3 Ultra, 96 GB unified | 96 GB | 2025, consumer | **$6,300** (owner-reported) | ~280 W sustained |
| Jury (Turing tier) | 2× RTX 2080 Ti 11 GB (used, AU market) | 22 GB + offload | 2018, Turing | **$1,200** (2 × ~$600) | 2× 250 W |

## Measured throughput (this experiment)

| Route | Workload | Time | Rate |
|---|---|---|---|
| Jury (Mac) | 96,000 votes, 12 configs × 8,000, 3–4B models, llama.cpp, 6-way parallel | 13.2 h (2026-08-28 11:24 → 08-29 00:37, helium) | **7,262 votes/h** |
| 27B (hydrogen) | 8,800 calls planned (200 defendant + 600 judge + 8,000 self-review), vLLM FP8, MTP spec decode, **1 of 3 slots** | in progress at 1.09 calls/s | **~3,900 calls/h** (conservative; slot was shared) |

Tokens per call ≈ 662 (27B run, measured from API usage), ≈ 700 (jury votes).
So in tokens/h: jury ≈ 1.4 k tok/s vs 27B ≈ 0.7 k tok/s on shared slot.

**The 3–4B jury already out-throughputs the 27B per wall-clock hour** on
consumer silicon, despite the 27B having a 48 GB GDDR7 part and FP8/MTP.

## Cost model (assumptions stated)

- Amortization: straight-line over 3 years (8,760 h), zero residual.
- Electricity: A$0.30/kWh residential (Melbourne), sustained TDP.
- $/h = amortization + power.

| Route | Amort $/h | Power $/h | Total $/h |
|---|---|---|---|
| 27B (RTX PRO 5000) | 9100/8760 = 1.04 | 0.300×0.30 = 0.09 | **1.13** |
| Jury (Mac Studio) | 6300/8760 = 0.72 | 0.280×0.30 = 0.08 | **0.80** |
| Jury (2× 2080 Ti) | 1200/8760 = 0.14 | 0.500×0.30 = 0.15 | **0.29** |

## Per 10k verifications

| Route | Hours for 10k | AUD per 10k |
|---|---|---|
| 27B (RTX PRO 5000) | 10000/3900 = 2.6 h | **$2.90** |
| Jury (Mac Studio) | 10000/7262 = 1.4 h | **$1.10** |
| Jury (2× 2080 Ti, est) | 10000/5000 = 2.0 h | **$0.58** (est) |

Full 96k-vote jury: **~$11 on the Mac, ~$5.5 on 2 used Turings** (est) vs
**~$28 for the same 96k verifications on the 27B** — before counting that
the Mac/Turings are already owned or buyable for ≤$1,200.

Turing throughput is an **estimate, not a measurement**: 4B Q4_K_M ≈ 2.4 GB,
decode is bandwidth-bound (~616 GB/s GDDR6), 5–6 parallel streams per card in
llama.cpp server; assume ~2,500 votes/h per card. Flag for a 1-day
bench if the claim needs a measured number.

## The barrier claim (defensible wording)

- Memory is the real barrier: the 27B needs **48 GB GDDR7** — only
  Blackwell-gen workstation/datacenter parts (US street $5.2k+, A$9k local),
  released 2025.
- The entire 12-config jury (12 × ~2.4 GB Q4) needs **~29 GB** — fits on
  **two used 2018 Turing cards (~$1,200)** with light CPU offload, or
  three clean (~$1,800). That silicon has a decade of accumulated
  availability and is what most GPU owners already have in a drawer.
- Phrasing: "consumer / widely-owned / second-hand silicon", not "old" as a
  quality claim. The 2080 Ti is old; the Mac Studio is not — both are
  *accessible* tier.
- Headline: *jury quality with 3–4B voters, runnable on ~$1,200 of used 2018
  GPUs that most labs already own, vs a $9,100 48 GB part for the
  single-model baseline — at 7.6× lower capital and ~5× lower running cost
  per 10k verifications.*

## Caveats

- Quality head-to-head (jury vs 27B) is still landing (self-review 8,000
  calls in flight as of writing); the barrier numbers hold regardless, but
  the "neutral or better" quality premise needs the final eval.
- Mac row is a *system* price (CPU+GPU+RAM+SSD); the jury only uses the
  unified memory, so the effective silicon cost is a slice of that.
- 27B row: our slot was shared (max-num-seqs 3, we held 1); solo throughput
  is higher, which makes the 27B look better on $/10k — the table is
  conservative for the 27B.
- llama.cpp vs vLLM runtime maturity differences are not separated out.
