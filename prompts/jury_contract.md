# Claim-verification prompt (the jury contract)

One call per claim. In: the article (evidence) plus one claim in question
form. Out: a single JSON object. Used by: the zero-shot jury baseline (P4),
the self-distillation targets (Phase 4), the frontier self-review control
(27B with the prompt), the losslessness check (Phase 4), and the registered
solver-as-proposer arm.

Drafted from the co-designer's quoted wording, kept verbatim: "Answer this
question only based on the information available on this article.
[question]". The link question from his thread was dropped per his
instruction. Final text freezes in `prereg.yaml`.

## Message layout

One call per claim. No system message. User message:

```
You are a careful fact-checker. A claim about the news article below is
stated in question form. Verify the claim against the article.

<article>
{article text, verbatim from corpus/articles/T##.md}
</article>

Answer this question only based on the information available on this
article.

{claim in question form, verbatim from corpus/pool/question_form/T##.md}
```

## Contract

1. The verdict rests solely on the article. No outside knowledge, no prior
   beliefs, no plausibility.
2. `PASS` if the article states the claim or directly entails it.
3. `FAIL` if the article states the opposite or gives a conflicting fact.
4. `NOT_STATED` if the article does not contain the information the
   question asks about.
5. Reply with a single JSON object and nothing else:

```
{"answer": "PASS" | "FAIL" | "NOT_STATED", "reason": "<one or two sentences grounding the verdict in the article>"}
```

The three-state answer field is deliberate: the explicit `NOT_STATED`
maps to the silence cell, which keeps the three-state estimator
(WCT-EM) alive.

## Call parameters

- Temperature 0, one call per claim (40 per article per proposer).
- Thinking off where the model exposes a toggle (Qwen3.5-4B:
  `chat_template_kwargs: {"enable_thinking": false}`); no toggle exists
  for the other four families.
- `max_tokens` 512 (the reason is free but expected to be one or two
  sentences).
- Reason field is free: the model's own grounding. Free thinking is what
  keeps the five families from making identical mistakes (RQ3).

## Output parsing

- Strict JSON parse of the whole completion (strip code fences if present;
  a single fenced object is accepted, free text around it is not).
- `answer` must be exactly `PASS`, `FAIL`, or `NOT_STATED` (case-
  insensitive). Anything else is a parse failure.
- Parse failures are logged as missing observations, never coerced. Parse
  rate is reported per proposer (target: 100 percent by construction).

## Mapping to corpus labels

- `PASS` = ENTAIL, `FAIL` = CONTRADICT, `NOT_STATED` = UNSPECIFIED.
- Gate binary: PASS vs not-PASS (ENTAIL vs not-ENTAIL).
- Correctness per claim: exact match against `corpus/labels/T##.json`.

## Question-form conversion rule (for `corpus/pool/question_form/`)

The pool is declarative; the contract takes question form. The question
form is a POLAR question that encodes the full claim, asserted value
included. The verdict is about the claim, so the claim must be in the
prompt: if the asserted value were deleted (a wh-question), the jury
could never answer FAIL for a wrong figure, and CONTRADICT would collapse
into ENTAIL. (Fixed 2026-08-26, before any rendering was frozen; the
earlier wh-form draft is superseded.)

Conversion is one mechanical rule, applied to all 1,200 propositions:

    "Is it true that {proposition text, verbatim, without trailing period}?"

No words are added, removed, or reworded beyond the prefix. The
proposition appears verbatim inside the question, so the question form
is auditable against the pool (and content-hashes are trivial). Negations
in the proposition are preserved as-is ("Is it true that Lala did not
make a direct landfall?").

Examples:

- "Lala's sustained winds on August 16 were 105 miles per hour." ->
  "Is it true that Lala's sustained winds on August 16 were 105 miles per hour?"
- "Lala did not make a direct landfall on the Island of Hawaiʻi." ->
  "Is it true that Lala did not make a direct landfall on the Island of Hawaiʻi?"
- "The five other senior executives all received 18-year sentences." ->
  "Is it true that the five other senior executives all received 18-year sentences?"

The seeded questions in `corpus/questions/T##.md` (wh-form, natural
answers) are the SOLVER baseline task, not the jury task. They stay as
is; the jury contract uses the polar forms only.

Renderings are frozen at the Phase 2 content hash.
