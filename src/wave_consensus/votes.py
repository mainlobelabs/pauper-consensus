"""Core voting primitive for wave-consensus.

The load-bearing invariant from the source paper: count *who* asserts a
proposition, never *how much text* asserts it. Each proposer (agent) gets at
most one observation per canonical proposition, regardless of how many times
the proposition appears in that proposer's trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Polarity(StrEnum):
    """Polarity of an asserted proposition.

    The source paper's alignment layer silently dropped every negative-
    polarity proposition (0 of 607 scored). Structured output makes polarity
    explicit so neither class can be dropped.
    """

    POS = "pos"
    NEG = "neg"


class Vote(StrEnum):
    AFFIRM = "affirm"
    DENY = "deny"


@dataclass(frozen=True)
class Observation:
    """A single (agent, proposition) observation.

    After the one-vote-per-source cap, at most one Observation exists per
    (agent, proposition_id) pair.
    """

    agent: str
    proposition_id: str
    polarity: Polarity
    vote: Vote


@dataclass
class VoteMatrix:
    """Proposition x agent vote table with silence as an explicit state.

    Silence is *not* a missing value: under truth-dependent coverage a
    proposer's silence carries information, so the absence of an Observation
    is itself a cell state, not a hole.
    """

    proposition_ids: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    # (proposition_id, agent) -> Observation
    _cells: dict[tuple[str, str], Observation] = field(default_factory=dict)

    def add(self, obs: Observation) -> None:
        if obs.proposition_id not in self.proposition_ids:
            self.proposition_ids.append(obs.proposition_id)
        if obs.agent not in self.agents:
            self.agents.append(obs.agent)
        # One vote per source: the first observation wins, repeats are dropped.
        self._cells.setdefault((obs.proposition_id, obs.agent), obs)

    def cell(self, proposition_id: str, agent: str) -> Observation | None:
        return self._cells.get((proposition_id, agent))

    def supports(self, proposition_id: str, vote: Vote) -> list[str]:
        """Distinct agents casting `vote` on the proposition (unique sources)."""
        return [
            agent
            for agent in self.agents
            if (obs := self.cell(proposition_id, agent)) is not None and obs.vote is vote
        ]

    def unique_source_support(self, proposition_id: str, vote: Vote) -> int:
        """Count of distinct agents for `vote`. This is the invariant metric."""
        return len(self.supports(proposition_id, vote))

    def instance_count(
        self, proposition_id: str, vote: Vote, instances: dict[tuple[str, str], int]
    ) -> int:
        """Claim-instance count (the ablation that destroys the signal).

        `instances` maps (proposition_id, agent) to how many times the agent's
        trace asserted the proposition. Summing these over agents is the
        verbosity-weighted count the paper shows collapses AUROC to a coin
        flip, so it is kept only as the comparison arm.
        """
        return sum(
            instances.get((proposition_id, agent), 0)
            for agent in self.agents
            if (obs := self.cell(proposition_id, agent)) is not None and obs.vote is vote
        )
