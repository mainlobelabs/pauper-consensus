"""Shared cached-artifact schema (DECISIONS.md, slice 1).

SCHEMA_VERSION is part of every cache key, so changing a dataclass here
invalidates prior artifacts rather than silently reinterpreting them. The
simulator and the real pipeline both emit these types, which is what lets the
E0-E2.5 analysis code be shared (protocol 3.0, REQUEST.md A8).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = "1"

Verdict = Literal["True", "False", "Unknown"]
Obs = Literal["affirm", "deny", "missing"]


@dataclass(frozen=True)
class Proposition:
    """A canonical proposition with ground-truth entailment status under OWA.

    `answer` is the label ProofWriter derives from the theory's closure, so it
    is truth by construction rather than by annotation (assumption M1).
    """

    pid: str
    text: str
    representation: str
    answer: Verdict
    qdep: int
    proof: str
    qlen: str = ""

    @property
    def y(self) -> int | None:
        """Binary truth for the mechanism experiment; None where undecidable."""
        return {"True": 1, "False": 0}.get(self.answer)


@dataclass(frozen=True)
class Item:
    """One reasoning item: a theory, a target question, and its proposition space."""

    item_id: str
    theory: str
    question: str
    answer: Verdict
    qdep: int
    stratum: str
    propositions: tuple[Proposition, ...]
    n_conjunctive_rules: int = 0
    rules: tuple[str, ...] = ()

    def decidable(self) -> tuple[Proposition, ...]:
        return tuple(p for p in self.propositions if p.y is not None)


@dataclass
class Generation:
    """One model's response to one item. Immutable once cached."""

    item_id: str
    agent: str
    model: str
    role: str
    content: str
    reasoning: str
    seed: int
    temperature: float
    resolved_model: str = ""
    provider: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    latency_s: float = 0.0
    attempt: int = 1
    error: str = ""

    @property
    def trace(self) -> str:
        """The rationale. Reasoning models split it out of `content`."""
        if self.reasoning and self.content:
            return f"{self.reasoning}\n\n{self.content}"
        return self.reasoning or self.content


@dataclass
class Claim:
    """One extracted claim instance (plan.md 4.2)."""

    uid: str
    item_id: str
    agent: str
    text: str
    polarity: int = 1
    depends_on: tuple[str, ...] = ()
    confidence: float | None = None
    source_span: str = ""
    terminal_for: str = ""


@dataclass
class Observation:
    """One agent's single observation of one canonical proposition.

    Capped at one per (agent, proposition) by construction: assumption M6.
    """

    item_id: str
    pid: str
    agent: str
    obs: Obs
    alignment_score: float = 0.0
    source_claim: str = ""


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses/tuples so artifacts are plain JSON."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj
