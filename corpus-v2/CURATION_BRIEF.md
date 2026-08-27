# Curation brief, v2 candidate selection

You are selecting candidate events for the wave-consensus v2 corpus. Each
candidate becomes one test article (~400-600 words) seeded with ~40 labelled
propositions, so the event must be self-contained and fact-dense.

## Input

Your month section of corpus-v2/shortlist.md (line range given in your task).
Each row: `- [score] **portal heading**: event text (source)`. The score is a
raw fact-density number, useful as a tie-breaker only, not a verdict.

## Pick criteria (all must hold)

1. Self-contained: a reader who knows nothing else can understand and verify
   the event from the article alone. No "as part of the ongoing war..."
   framing required.
2. Fact density: at least 3-4 independently verifiable sub-facts (names,
   numbers, dates, places, organisations, amounts, scores). Count them
   before picking.
3. Dated inside the window shown in your section.
4. Prefer events with a real-world verbatim article available (major-outlet
   coverage): disasters with tolls, elections with results, court verdicts,
   sports finals/records, business deals with amounts, science and health
   milestones, confirmations of deaths of public figures, firsts.

## Reject

- Ongoing-conflict status beats without new facts: "X says talks are
  progressing", "Y denies reports", "Z strikes W, N killed" where N and W
  carry no names or context. From the big ongoing wars (Iran war, Lebanon,
  Ukraine, Sudan, Gaza, Yemen, Red Sea), take AT MOST 20 percent of your
  month's picks, and only self-contained beats: a named ship sunk, a named
  person killed, a deal signed, a ceasefire declared with terms, an election.
- One-off thin beats: single death toll with no context, weather alerts,
  travel advisories, minor sports scores without a named tournament.
- Duplicate beats of the same story: if a story appears on 3+ days, pick at
  most 1-2 of its beats (the ones with the most facts), never 3+.
- Anything where the event text itself is ambiguous or contradicts itself
  without resolution.

## Domain balance (soft targets, over your whole pick set)

No single domain above ~25 percent of picks. Make sure your picks include a
mix of: disasters, politics/elections/law, business/economy, military (the
20 percent cap), science/tech, health/environment, sports, arts/film,
diplomacy with concrete facts. If your month is war-dominated (March, April),
be strict about the military cap.

## Output

Write your picks to corpus-v2/picks-<MONTH>.md (MONTH = 2026-02 etc.), one
line per candidate, format:

    DATE | PORTAL TOPIC | one-line summary with the key facts inline | DOMAIN

Target counts (primary picks, then a short "Reserve" section with the next
best 10 percent in case fact-check drops some):
- 2026-02 (window 02-15..02-28): 20 + 2 reserve
- 2026-03: 42 + 5
- 2026-04: 41 + 5
- 2026-05: 42 + 5
- 2026-06: 41 + 5
- 2026-07: 42 + 5
- 2026-08 (window 08-01..08-13 + 08-26..08-27): 22 + 3

Rules for the file:
- Keep DATE and PORTAL TOPIC exactly as in the shortlist (the TOPIC string
  identifies the event for downstream tooling).
- DOMAIN is one word: disaster, politics, business, military, science,
  health, sports, arts, economy, law, diplomacy, tech.
- In your final chat message return ONLY: pick count, reserve count, domain
  breakdown, 3 best picks with one line each, and any concerns (e.g. a month
  that did not reach target and why).
