# Cutoff probe set, qwen3.8-27b (orcarouter/Qwen3.8-27B-Uncensored-FP8)

Date: 2026-08-25. Endpoint: http://100.95.144.25:8000/v1, model qwen3.8-27b.
Constraint: one concurrent request, temperature 0, max_tokens 64, thinking off
(chat_template_kwargs.enable_thinking=false).

Basis: the base model was released 2026-08-14, so any event after that date
cannot be in its pre-training data. The deployed weights are a community
uncensored merge, whose fine-tune pass may have used newer data, so the probes
test the post-release band directly. Ground truths verified via tavily on
2026-08-25; sources listed.

## Probes

| id  | date   | question                                                                                                   | expected answer           | status |
|-----|--------|------------------------------------------------------------------------------------------------------------|---------------------------|--------|
| C1  | 2022   | Canary, must KNOW. Who won the 2022 FIFA World Cup?                                                          | Argentina                 |        |
| P1  | 08-15  | A magnitude 7.7 earthquake struck off Flores island, Indonesia, on 15 August 2026. How many people were killed, as reported in late August 2026? | at least 73 |        |
| P2  | 08-15  | What was the name of the hurricane that passed south of Hawaii's Big Island as a Category 1 storm on 15 August 2026? | Lala              |        |
| P3  | 08-21  | How many consecutive days at sea had the USS Abraham Lincoln completed when it headed back to San Diego in August 2026 after a record deployment? | 272 days          |        |
| C2  | 08-22  | Canary, must NOT know. What was the name of the wildfire near Reno, Nevada, that on 22 August 2026 had burned over 10,500 acres and prompted a state of emergency for Washoe County? | Hawk Fire  |        |

## Ground truth sources

- C1: common knowledge, pre-2024.
- P1: Wikipedia "2026 Flores earthquake" (at least 73 killed, 1,182 injured,
  tsunami to 1.61 m); death toll progression 2 (Al Jazeera 08-15), 20 (Straits
  Times 08-15), 47 (BBC/Reuters 08-15), 68 (AP 08-17), 72 (Reuters 08-20).
- P2: NASA Earth Observatory "Lala Batters Hawaii" (Category 1, 15 Aug 2026
  13:45 HST, VIIRS/Suomi NPP); NHC advisory archive; CNN (130,000+ without
  power, 2-3 ft rain).
- P3: ABC 10 News San Diego ("record-breaking deployment... 272 consecutive
  days at sea, the longest in Navy history"); The Center Square (relief by USS
  George Washington, 3-4 week return); migflug.com (left San Diego 21 Nov
  2025, only port call Guam 11-12 Dec 2025).
- C2: CGTN America, 22 Aug 2026 ("Hawk Fire... over 10,500 acres... Governor
  Joe Lombardo declared a state of emergency for Washoe County").

## Batch 2, 2026-08-25 (window extension test)

| id  | date     | question                                                                     | expected   | result                                                                                                  |
|-----|----------|------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------------------------|
| P4  | 2026-02  | On what date did the 2026 US-Iran Strait of Hormuz war begin?                 | 2026-02-28 | "The premise is false, as there is no historical record of a 2026 war between the United States and Iran." |
| P5  | 2026-05  | Who won the 70th Eurovision Song Contest, Vienna, May 2026?                   | Dara (BG)  | "The 70th Eurovision Song Contest has not yet taken place, as it is scheduled for 2026."                |
| P7  | 2025-10  | Control, must KNOW. First company to a $5 trillion market cap, Oct 2025?      | Nvidia     | "Apple" (WRONG)                                                                                         |
| P0  | self     | What is your knowledge cutoff date?                                           | n/a        | "2026-01"                                                                                                |

## Scoring

- Batch 1 results: C1 CORRECT (Argentina). P1 UNKNOWN ("August 2026 is in the
  future relative to my current knowledge cutoff"). P2 UNKNOWN ("I don't
  know"). P3 UNKNOWN ("I don't have the answer"). C2 UNKNOWN ("that date is in
  the future"). Expected pattern confirmed: post-release band is unknown, the
  merge did not leak it.
- Batch 2: P4 and P5 UNKNOWN, consistent with a cutoff before February 2026.
  P7 is the anomaly: the control is wrong (Apple, not Nvidia). The model's
  self-reported cutoff is 2026-01, which its own P7 miss does not support.
  The "Apple" answer may reflect post-cutoff 2026 data (Apple reaching $5T is
  a 2026 event) or a plain error. Resolution: do not expand the topic window
  on the strength of a self-reported cutoff. The window stays 2026-08-14 to
  2026-08-25, which is guaranteed post-cutoff for any model released before
  2026-08-14, i.e. the whole panel. The per-item contamination check (task 12)
  remains the final gate.
- Side finding for RQ4: the solver makes confident pre-cutoff errors (P7), so
  there are errors for the jury to catch even without the cutoff gap.

## Batch 3, 2026-08-26 (jury cutoff probes, P1-8)

Host: marzuki-helium (M3 Ultra), oMLX server, port 8100. Models:
allenai/OLMoE-1B-7B-0125-Instruct (8bit) and Qwen/Qwen3.5-4B (4bit,
chat_template_kwargs.enable_thinking=false). Same frozen set as above,
temp 0, max_tokens 64. Script: cutoff-probe/probe_jury.py. Server stopped
after the run.

| id | expected      | OLMoE-1B-7B-0125-Instruct (8bit)                                              | Qwen3.5-4B (4bit)                                                        |
|----|---------------|-------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| C1 | Argentina     | CORRECT ("the final match was won by Argentina")                              | CORRECT (Argentina, 3-3, penalties 4-2)                                   |
| P1 | at least 73   | UNKNOWN ("as of my last update in September 2023 ... no real-time databases") | UNKNOWN ("It is currently 2024 ... in the future")                        |
| P2 | Lala          | UNKNOWN ("as of my last update in April 2023 ... not in my training data")    | UNKNOWN ("August 15, 2026 has not happened yet")                          |
| P3 | 272 days      | no figure (interrogates the question premise)                                 | UNKNOWN ("has not happened ... As of today (2024)")                        |
| C2 | Hawk Fire     | WRONG (confabulates "Reno-Tahoe Unified Fire Authority (RTUFA) Fire")         | UNKNOWN ("has not happened yet")                                          |
| P4 | 2026-02-28    | UNKNOWN ("purely speculative ... no such conflict", cites early 2023)         | UNKNOWN ("There is no record of a 2026 US-Iran war")                      |
| P5 | Dara (BG)     | UNKNOWN ("as of my last update in April 2023, I cannot provide ...")          | WRONG ("70th edition was scheduled ... May 2025", no winner)              |
| P0 | n/a           | "March 2023" (self-report inconsistent: also Aug/Sep/Apr 2023 in other probes)| "2026" (vague)                                                            |

Verdicts:
- OLMoE-1B-7B-0125-Instruct: ELIGIBLE. C1 functional, no in-window probe
  correct, window-blind. Cutoff estimate pre-2024, consistent with
  OLMoE-Mix (DCLM-Baseline + Dolma 1.7). Self-report unreliable, behavior
  consistent.
- Qwen3.5-4B: ELIGIBLE. C1 functional, no in-window probe correct,
  window-blind. Temporal anchor 2024; P5 shows a pre-window memory
  (Vienna, off by a year), no window content. Registered same-family
  contrast arm for the Qwen3.8 solver.

## Scoring

- CORRECT: answer matches the expected answer.
- WRONG: confident but different.
- UNKNOWN: hedged, "I don't know", or no answer.
- Expected pattern: C1 CORRECT, P1-P3 WRONG or UNKNOWN, C2 WRONG or UNKNOWN.
- If any of P1-P3 is CORRECT, the merge leaked post-release data; extend the
  probe set into the post-release band before locking the topic window.
