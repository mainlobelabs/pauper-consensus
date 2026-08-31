"""Cycle 3's corpus: build it, verify it, and pin it. (B5)

This module returns VALUES for the registration to embed; it writes no artifact
of its own, because "building cycle 3's corpus artifacts" is a non-goal of this
slice. Everything here is derived from the parquet inputs and re-derivable by
the gate, so no figure in prereg_v3.yaml is ever hand-typed.

Two counts in this programme have already been misstated by being read off the
wrong quantity:

  * "2,353 items" was the raw parquet ROW count; the filtered set was 2,277.
  * a "50% FALSE" figure was the ITEM TARGET answer rate, which is not what B5
    asks for. B5 asks for scored POSITIVE-POLARITY NEGATIVES. Canonical
    propositions are all positive-polarity by construction (wct/cluster.py:15 --
    polarity is read from WHICH surface form a claim matches, not from the
    proposition), so the population is decidable propositions whose ground-truth
    answer is false, and the projection is how many of those actually get scored.

Both classes of error are why every function here names the quantity it returns.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from wct import data
from wct.schema import Item

CONFIGS = ("depth-3", "depth-5")
SPLITS = ("test", "dev", "train")

# Pinned by the human decision of 2026-08-30. The gate re-derives and compares.
EXPECTED_N_ITEMS = 9805
EXPECTED_SHA256 = "63ca8131b43b5c81681deed8bc705c6c2f6f1c56fdac929d9b1efb7584e504a1"

# Measured on cycle 2 panel A (150 items, 3 agents): of 608 distinct propositions
# that received an observation, 123 were negatives -> 0.2733 scored negatives per
# (item, agent). Used ONLY for the B5 projection, which is not a gate.
SCORED_NEG_PER_ITEM_AGENT = 123 / (150 * 3)


class CorpusError(RuntimeError):
    """The corpus does not match what was registered."""


@dataclass(frozen=True)
class Projection:
    """A projection, explicitly NOT an execution gate (B5)."""

    n_scored_positive_polarity_negatives: int
    per_item_agent_rate: float
    assumptions: tuple[str, ...]
    is_gate: bool = False


def load_corpus() -> list[Item]:
    """The registered 9,805 items, in a deterministic order.

    Raises CorpusError on any item_id collision: two configs contributing the
    same id would silently make the corpus smaller than it claims to be, which
    is exactly the class of error this module exists to prevent.
    """
    items: list[Item] = []
    for config in CONFIGS:
        for split in SPLITS:
            items.extend(data.load_items(config=config, split=split))
    items.sort(key=lambda it: it.item_id)

    seen: dict[str, int] = {}
    for it in items:
        seen[it.item_id] = seen.get(it.item_id, 0) + 1
    dupes = sorted(k for k, v in seen.items() if v > 1)
    if dupes:
        raise CorpusError(
            f"{len(dupes)} colliding item_id(s) across {CONFIGS}x{SPLITS}; "
            f"first: {dupes[:5]}"
        )
    return items


def corpus_sha256(items: list[Item] | None = None) -> str:
    """Content hash of the pinned corpus, over id/question/answer/theory."""
    items = load_corpus() if items is None else items
    h = hashlib.sha256()
    for it in items:
        h.update(f"{it.item_id}\x01{it.question}\x01{it.answer}\x01{it.theory}\x00".encode())
    return h.hexdigest()


def source_parquet_sha256() -> dict[str, str]:
    """SHA-256 of each source parquet, so the inputs are pinned, not just the derived set."""
    out = {}
    for config in CONFIGS:
        for split in SPLITS:
            p = Path("data") / f"proofwriter_{config}_{split}.parquet"
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def decidable_counts(items: list[Item] | None = None) -> dict[str, int]:
    """Population counts. `negatives` are the POSITIVE-POLARITY negatives of B5."""
    items = load_corpus() if items is None else items
    n_props = n_dec = n_neg = 0
    for it in items:
        n_props += len(it.propositions)
        for p in it.decidable():
            n_dec += 1
            if str(p.answer).lower().startswith("f"):
                n_neg += 1
    return {
        "propositions": n_props,
        "decidable": n_dec,
        "positive_polarity_negatives": n_neg,
        "positive_polarity_positives": n_dec - n_neg,
    }


def projected_scored_negatives(n_items: int, m_agents: int) -> Projection:
    """B5's projected count of SCORED positive-polarity negatives.

    Not the population count and not the item-target FALSE rate: the number of
    negatives expected to actually receive an observation, projected from cycle
    2's measured alignment yield.
    """
    return Projection(
        n_scored_positive_polarity_negatives=round(
            SCORED_NEG_PER_ITEM_AGENT * n_items * m_agents),
        per_item_agent_rate=SCORED_NEG_PER_ITEM_AGENT,
        assumptions=(
            "cycle-2 panelA alignment yield (123 scored negatives over 150 items x 3 agents) "
            "generalises to this corpus and to the cycle-3 panel",
            "depth-3 items are the new majority and may align differently from the depth-5 "
            "items the rate was measured on",
            "only 20.2% of scored propositions were negatives although 50.0% of decidable "
            "propositions are, so models restate truths more readily than falsehoods; the "
            "projection inherits that asymmetry",
        ),
        is_gate=False,
    )


def cycle2_is_subset(items: list[Item] | None = None) -> bool:
    """Cycle 2's 150 items must remain inside the corpus, or comparability is lost."""
    from exp.v2_dataset import load_v2_items

    items = load_corpus() if items is None else items
    ids = {it.item_id for it in items}
    v2, _, _ = load_v2_items()
    missing = [it.item_id for it in v2 if it.item_id not in ids]
    if missing:
        raise CorpusError(
            f"{len(missing)} of {len(v2)} cycle-2 items are absent from the cycle-3 corpus; "
            f"comparability with the registered +0.220/+0.272 results would be lost. "
            f"first: {missing[:5]}"
        )
    return True


def verify() -> dict:
    """Re-derive every registered corpus figure. Raises on any mismatch."""
    items = load_corpus()
    if len(items) != EXPECTED_N_ITEMS:
        raise CorpusError(f"corpus has {len(items)} items, registered {EXPECTED_N_ITEMS}")
    sha = corpus_sha256(items)
    if sha != EXPECTED_SHA256:
        raise CorpusError(f"corpus sha256 {sha} != registered {EXPECTED_SHA256}")
    cycle2_is_subset(items)
    counts = decidable_counts(items)
    return {
        "n_items": len(items),
        "sha256": sha,
        "configs": list(CONFIGS),
        "splits": list(SPLITS),
        "source_parquet_sha256": source_parquet_sha256(),
        **counts,
        "cycle2_subset": True,
    }
