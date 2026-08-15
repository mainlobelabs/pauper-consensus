"""One common extractor, applied identically to every trace (protocol 4.2).

Using a single fixed extractor for all agents isolates the generation hypothesis
from model-specific self-extraction: if each model extracted its own claims, a
model that writes tidy bullet points would score as a better *reasoner* purely
because it is a better *formatter*.

The extractor is deterministic and consumes no inference. It is a measurement
instrument, so its errors are measured (cluster.py audits alignment against the
theory's canonical proposition set) rather than assumed away.
"""
from __future__ import annotations

import re

from .schema import Claim, Generation, Item

# Sentence-ish segmentation that survives markdown bullets and numbered steps.
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RULE_REF = re.compile(r"\brule\s*(\d+)\b", re.I)
_STEP_REF = re.compile(r"\bstep\s*(\d+)\b", re.I)

# Fragments that mark a sentence as procedural narration rather than a claim
# about the theory. Kept deliberately short: over-filtering here would silently
# drop real claims and inflate apparent precision.
_NOISE = (
    "let me", "let's", "i need to", "i should", "first,", "okay", "wait",
    "so the answer", "the statement is", "answer:", "in summary", "therefore, the",
    "we need to", "looking at", "the question asks", "let us", "i'll", "i will",
    "now,", "next,", "finally,", "step ", "conclusion",
)

_DERIVE_CUE = re.compile(
    r"\b(derive|deduce|conclude|infer|follows|licenses|gives us|tells us|"
    r"we (?:can |now )?(?:get|have|know)|applying|apply|satisfies|holds)\b",
    re.I,
)


def _clean(s: str) -> str:
    s = _BOLD.sub(r"\1", s)
    s = re.sub(r"^[\s\-\*\d\.\)\:]+", "", s)      # bullets, numbering
    s = re.sub(r"\s+", " ", s).strip(" .;:,")
    return s


def _is_claimlike(s: str, entities: set[str], predicates: set[str]) -> bool:
    """A claim about the microworld names an entity AND says something of it.

    Requiring both is what separates a claim from narration. Traces are full of
    sentences that mention the entities while asserting nothing about them --
    "the user wants me to determine if the statement about the bald eagle is
    true" -- and an entity-only filter admits all of them. On a closed
    vocabulary the predicate requirement is cheap and it removed the bulk of the
    extraction noise in the pilot.
    """
    low = s.lower()
    if len(s) < 8 or len(s) > 220:
        return False
    if any(low.startswith(n) for n in _NOISE):
        return False
    if any(m in low for m in _META):
        return False
    return (any(e in low for e in entities)
            and any(re.search(rf"\b{re.escape(p)}\b", low) for p in predicates))


# first-person / task-framing narration, which mentions entities but asserts
# nothing about the microworld
_META = (
    "the user", "the question", "the statement is", "i need", "my task",
    "the task", "let me", "input:", "target statement", "the answer",
    "output", "step-by-step", "structure of", "we are asked", "asks whether",
)


def vocabulary_of(item: Item) -> tuple[set[str], set[str]]:
    """(entities, predicates) from canonical representations.

    Representations are ("subject" "verb" "object" "+/-"), so the subject and a
    concrete object are entities, and the verb plus any attribute are predicates.
    """
    ents: set[str] = set()
    preds: set[str] = set()
    for p in item.propositions:
        parts = re.findall(r'"([^"]*)"', p.representation)
        if len(parts) >= 3:
            ents.add(parts[0].lower())
            preds.add(parts[1].lower())
            preds.add(parts[2].lower())
    ents = {e for e in ents if e and e != "something"}
    # an object that is itself an entity is both; keep it in entities too
    preds = {p for p in preds if p and p != "something"}
    return ents, preds | {"is", "are"}


def entities_of(item: Item) -> set[str]:
    return vocabulary_of(item)[0]


def extract(gen: Generation, item: Item) -> list[Claim]:
    """Claim instances from one trace, in emission order.

    `depends_on` is populated from explicit in-text back-references (rule N,
    step N). Depth is NOT taken from the model's own numbering: defect D7 —
    model-reported depth penalises extraction granularity rather than
    overthinking, so depth is recomputed centrally from the DAG downstream.
    """
    if not gen.trace.strip():
        return []
    ents, preds = vocabulary_of(item)
    claims: list[Claim] = []
    seen: set[str] = set()

    for i, raw in enumerate(_SPLIT.split(gen.trace)):
        s = _clean(raw)
        if not _is_claimlike(s, ents, preds):
            continue
        key = s.lower()
        if key in seen:          # same agent restating the same sentence
            continue
        seen.add(key)
        deps = tuple(
            f"rule{m}" for m in _RULE_REF.findall(s)
        ) + tuple(f"step{m}" for m in _STEP_REF.findall(s))
        claims.append(
            Claim(
                uid=f"{item.item_id}::{gen.agent}::c{len(claims)}",
                item_id=item.item_id,
                agent=gen.agent,
                text=s,
                polarity=-1 if _negated(s) else 1,
                depends_on=deps,
                source_span=f"seg{i}",
                terminal_for=item.question if _terminal(s, item) else "",
            )
        )
    return claims


_NEG = re.compile(r"\b(not|isn't|is not|does not|doesn't|cannot|can't|no longer)\b", re.I)


def _negated(s: str) -> bool:
    return bool(_NEG.search(s))


def _terminal(s: str, item: Item) -> bool:
    q = item.question.lower().rstrip(".")
    return q[:24] in s.lower()


def answer_of(gen: Generation) -> str | None:
    """The model's final verdict, from the registered ANSWER: line."""
    m = re.findall(r"ANSWER\s*:\s*(True|False)", gen.trace, re.I)
    if m:
        return m[-1].capitalize()
    # registered fallback: a lone trailing verdict word
    tail = gen.trace.strip()[-200:].lower()
    for w in ("true", "false"):
        if re.search(rf"\b{w}\b\s*\.?\s*$", tail):
            return w.capitalize()
    return None


def has_conjunctive_step(gen: Generation) -> bool:
    """Whether the trace ever cites two premises for one inference.

    This is the behavioural counterpart of protocol invariant 7 and is reported
    per agent: a panel that never states co-premises cannot supply the complete
    premise sets E2.5 needs.
    """
    for seg in _SPLIT.split(gen.trace):
        low = seg.lower()
        if _DERIVE_CUE.search(low) and re.search(r"\band\b", low):
            return True
    return False
