# Label rubric, wave-consensus corpus

Frozen at Phase 2 with the rest of the corpus. Every proposition in the pool
is labelled by this rubric. The labeler is the author (single labeler,
disclosed); a 10 percent sample is re-checked from scratch against this file
and the agreement rate is logged (task 8).

## 1. The three labels

Each proposition is a single self-contained declarative sentence about one
claim. It is labelled relative to exactly one article (its parent article).

- **ENTAIL**: the article states the claim, or restates it with identical
  meaning (paraphrase, equivalent number, equivalent date form). The label
  is earned by the text, not by the labeler's prior knowledge.
- **CONTRADICT**: the article states a fact that the claim is incompatible
  with. Incompatible means they cannot both be true for the same subject and
  time: a different number for the same quantity, a different date for the
  same event, a different role for the same person, an explicit negation of
  the claim, or the opposite polarity of a stated fact.
- **UNSPECIFIED**: the article does not state the claim and does not state
  the opposite either. The article is silent on the point. The claim may be
  true or false in the real world; that does not matter. Silence is the
  label.

The binary gate target is ENTAIL vs non-ENTAIL. A correct verdict passes
exactly the ENTAIL propositions. UNSPECIFIED is the hallucination class: a
verifier that passes an UNSPECIFIED proposition has certified a claim the
article does not support, which is the failure mode this experiment measures.

## 2. Core rules

R1. Article is the oracle. Label from the parent article's text only. The
labeler knows the real-world facts (they were verified to build the article),
but prior knowledge never grants ENTAIL and never converts UNSPECIFIED into
CONTRADICT. If the article does not say it, it is not CONTRADICT.

R2. Direct statement. ENTAIL requires the claim to be stated or an immediate
restatement of a stated fact. A claim that needs external knowledge, a second
hop of inference, or a comparison the article never makes is UNSPECIFIED,
even if every step is reasonable.

R3. One claim per proposition. Compound claims are split before labelling.
A proposition that binds two facts ("X happened and Y is true") is a drafting
error, not a label choice.

R4. Same subject and time. Contradiction requires the same subject (same
person, object, quantity) and a compatible time reference. A claim about a
different time than the stated one is CONTRADICT only if the article pins the
time explicitly.

R5. Latest stated figure wins. When an article reports an evolving quantity
(death toll, acreage, outage counts), the last figure stated is the current
state. A claim is judged against the latest figure unless the claim
explicitly references the earlier moment.

R6. Both polarities in every class. The pool must contain positive claims and
negative claims in each of the three classes. A negated claim is labelled by
the same procedure: does the article state the negated fact (ENTAIL), state
its opposite (CONTRADICT), or say nothing (UNSPECIFIED)?

R7. Every label records its evidence. ENTAIL and CONTRADICT labels record the
exact span of article text that earns the label. UNSPECIFIED labels record a
one-line reason for the silence (which point the article does not address).

## 3. Number and quantity rules

N1. Exact numbers. The article states 73 killed.
- "73 people were killed" is ENTAIL.
- "72 people were killed" is CONTRADICT (different number, same quantity).
- "More than 100 people were killed" is CONTRADICT.
- "At least 70 people were killed" is ENTAIL (compatible with the stated
  number, no new information).

N2. Lower bounds and ranges. The article states "at least 47 killed".
- "46 people were killed" is CONTRADICT (violates the bound).
- "47 people were killed" (pinned exact) is UNSPECIFIED: the article states a
  floor, not an exact count, so the exact value is not stated.
- "At least 50 people were killed" is UNSPECIFIED if the article never raises
  the floor to 50, even though the final toll later exceeded it in the real
  world (R1).

N3. Approximators. The article states "about 20 billion dollars".
- "The tariffs cover roughly 20 billion dollars of goods" is ENTAIL.
- "The tariffs cover exactly 20.0 billion dollars" is UNSPECIFIED (the
  approximator is dropped, a precision the article does not state).
- "The tariffs cover 25 billion dollars" is CONTRADICT only if the article
  states a different precise or approximate figure that 25 is incompatible
  with; with "about 20" it is CONTRADICT.

N4. Percentages and fractions follow the same rules as N1 to N3.

## 4. Time rules

T1. "The collapse happened on Tuesday, 18 August 2026" (stated).
- "The collapse happened on 18 August" is ENTAIL.
- "The collapse happened on Wednesday" is CONTRADICT.
- "The collapse happened in 2026" is ENTAIL (restatement).
- "The collapse happened last year" is CONTRADICT.

T2. If the article gives no time for an event, any time claim about it is
UNSPECIFIED. "The fire started in the morning" when the article says nothing
about the time of ignition is UNSPECIFIED.

## 5. Identity and role rules

I1. "Michele Sensi-Contugi, Ecuador's director of national intelligence, was
among those killed" (stated).
- "Ecuador's intelligence chief died in the crash" is ENTAIL.
- "Ecuador's foreign minister died in the crash" is CONTRADICT (different
  role for the same identified person).
- "An Ecuadorian journalist died in the crash" is UNSPECIFIED if the article
  names no journalist (the article identifies a different Ecuadorian; it does
  not say no other Ecuadorian died).

I2. If the article states a set ("all seven people on board were killed"),
claims about membership in the set are judged against the named members. A
claim naming an unmentioned person is UNSPECIFIED, not CONTRADICT.

## 6. Negation rules

G1. The article states "the mine was closed on 22 August".
- "The government closed the mine on 22 August" is ENTAIL.
- "The government did not close the mine" is CONTRADICT (opposite polarity of
  a stated fact).
- "The mine was not state-owned" is UNSPECIFIED (ownership is never stated;
  closure says nothing about ownership).

G2. "The robot's 9.39 second time broke Usain Bolt's 9.58 second record"
(stated).
- "The robot did not beat Bolt's record" is CONTRADICT.
- "No robot had run a 100m under 9.5 seconds before the games" is
UNSPECIFIED (the article states no prior time, so the prior state is not
stated).

## 7. Worked boundary cases (the CONTRADICT vs UNSPECIFIED line)

B1. Identity of a stated death. The article says "one person was killed by
the storm, a woman found dead in Naalehu". It does not give her age.
- "A woman was killed by the storm" is ENTAIL.
- "A 90-year-old woman was killed by the storm" is UNSPECIFIED: the article
  states one death and identifies the victim as a woman, but never states an
  age. The claim adds an un stated attribute. It is not CONTRADICT because
  the article does not say "a younger woman" or any other age.
- "A 90-year-old woman survived the storm" is CONTRADICT only if the article
  had identified the victim's age; with no age stated, it is UNSPECIFIED.
This is the canonical case: a stated category plus an unstated attribute is
UNSPECIFIED; a stated category plus a conflicting attribute is CONTRADICT.

B2. Consequence the article never draws. The article says the mine "was
about 50 kilometres from the town of Baboua, near the border of Cameroon".
- "The mine was in the Central African Republic" is ENTAIL (the article
  states the village and prefecture in western CAR).
- "The miners were mostly nationals of the Central African Republic" is
UNSPECIFIED: the article says miners were from CAR and Cameroon and names
3 to 5 Cameroonian victims, but never states the split.
- "The mine was in Cameroon" is CONTRADICT (stated location is CAR).

B3. Two reporting figures. The article carries both "the mines minister said
49 people died" and "local officials said more than 100 people were killed"
(same quantity, two attributed figures, the higher stated later).
- "The mines minister put the death toll at 49" is ENTAIL (names the source
  the article attributes the figure to).
- "Local officials said more than 100 people were killed" is ENTAIL.
- "The death toll was 49" is CONTRADICT: the claim pins the quantity to the
  lower figure, and the article states a higher figure for the same quantity
  (N1, R5: latest stated figure wins).
- "The death toll was disputed" is UNSPECIFIED: the article shows two
  attributed figures but never states that they are disputed or in conflict.
Rule B3: a claim that names the source a figure is attributed to is judged
against that attribution; a sourceless claim is judged against the latest
stated figure for the same quantity.

B4. Scope of a stated restriction. The article states "from 3 September the
canal will allow 34 ships a day, down from 36".
- "The canal cut daily transits to 34 starting in September" is ENTAIL.
- "The canal cut daily transits to 34 starting 1 September" is CONTRADICT
  (stated date is 3 September).
- "The canal cut daily transits to 30 starting in September" is CONTRADICT.
- "The canal cut daily transits for container ships" is UNSPECIFIED (the
  article never restricts the measure to any ship class).

B5. Causation the article does not state. The article states the fire began
near Hawk Meadow Trail and was "human-caused".
- "The fire was human-caused" is ENTAIL.
- "The fire started from a power line" is UNSPECIFIED: human-caused is
  stated, the specific mechanism is not.
- "The fire started naturally from lightning" is CONTRADICT (incompatible
  with the stated cause).

B6. Stated set plus absent member. The article names the victims of the
crash: pilot Josh Outram, four Americans, an Ecuadorian official and his
wife. It names no other nationalities.
- "Four Americans were among those killed" is ENTAIL.
- "A Canadian was among those killed" is UNSPECIFIED (no nationality stated;
  the named set does not rule out an unnamed member being Canadian because
  the article gives the complete count of seven and names seven people, so
  any additional named nationality would exceed the count and be
  CONTRADICT. Label: UNSPECIFIED for the attribute, CONTRADICT for the count.
  A single proposition must pick one: "A Canadian was among the seven killed"
  is CONTRADICT, because seven are named and none is Canadian.)
Rule B6: when the article states the full count and names every member, a
claim adding an un named member to the set is CONTRADICT; when the article
states a partial count, it is UNSPECIFIED.

## 8. Label record format

Each label is stored as:

```
{
  "id": "T25-017",
  "proposition": "The mines minister put the death toll at 49.",
  "label": "ENTAIL",
  "evidence": "The mines minister said 49 people had died there.",
  "silence_reason": null
}
```

For UNSPECIFIED, `evidence` is null and `silence_reason` names the point the
article does not address (for example "article states no victim ages").

## 9. Disagreement resolution

If a proposition looks labelable two ways, the order of preference is:
(1) split the proposition into two and label each; (2) if it cannot be
split, apply R2 (direct statement) and default to UNSPECIFIED. CONTRADICT
always requires a quotable span; if the labeler cannot quote the conflicting
sentence, the label is not CONTRADICT.
