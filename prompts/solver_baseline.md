# Solver baseline prompt (no contract)

The without-prompt baseline control. The solver (qwen3.8-27b) answers each
article's 20 questions in natural prose. No verification contract, no JSON,
no PASS/FAIL vocabulary. The solver's claims are matched to pool
propositions by the author's seed mapping; unmatched claims are logged, not
scored.

## Message layout

One call per article. No system message. User message:

```
Below is a news article, followed by 20 questions about it.

<article>
{article text, verbatim from corpus/articles/T##.md}
</article>

Answer each question in order.

1. {question 1, verbatim from corpus/questions/T##.md}
2. {question 2}
...
20. {question 20}
```

## Call parameters

- Endpoint: hydrogen, model `qwen3.8-27b`.
- Temperature 0.
- Thinking off: `chat_template_kwargs: {"enable_thinking": false}`
  (identical to the deployed configuration; the only difference between the
  with-prompt control and this baseline is the prompt).
- One call per article (30 calls).

## Claim extraction and scoring

- Each numbered answer is one solver claim (600 claims total).
- Seed mapping: each question's expected answer maps to its seeded pool
  propositions (the P1-4/P1-5 seed notes, formalized in
  `corpus/pool/question_form/T##.md`). Matched claims are scored against
  `corpus/labels/T##.json` (gate binary: ENTAIL vs not-ENTAIL; full label
  where available).
- Unmatched claims (the solver asserts something no pool proposition
  covers) are logged in the results file, never scored.
- This same article plus its 20 questions goes to the with-prompt control
  (frontier self-review) in the form: the 27B verifies each of its own 40
  pool claims with `jury_contract.md`, one call per claim.
