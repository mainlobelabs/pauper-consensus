"""Stratum-1 dataset: ProofWriter OWA with proof trees intact.

GOTCHAS.md records why this source and not PrOntoQA: 95.5% of items here carry
at least one conjunctive rule, so protocol invariant 7 (a linear path can accept
an inference missing a co-premise; the AND/OR selector cannot) is actually
exercised, and E2.5 gets real multi-premise dependency ground truth.

The property that makes this dataset load-bearing for E1 is that every candidate
proposition already has a truth value derived from the theory's closure. Nothing
is hand-annotated, so assumption M1 holds by construction and the measurement
audit can be scored against a known answer rather than against adjudication.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from .schema import Item, Proposition

HF_REPO = "hitachi-nlp/proofwriter_processed_OWA"
DATA_DIR = Path("data")
# depth-3 gives QDep 0-6 with proof lengths 1-9: enough depth variation for the
# complexity prior to have something to bite on, without depth-5's long tail.
DEFAULT_CONFIG = "depth-3"


def download(config: str = DEFAULT_CONFIG, split: str = "test") -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / f"proofwriter_{config}_{split}.parquet"
    if dest.exists():
        return dest
    url = (
        f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/"
        f"{config}/{split}-00000-of-00001.parquet"
    )
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def _n_premises(representation: str) -> int:
    """Count antecedent literals in a ProofWriter rule representation.

    Format: ((("x" "is" "kind" "+") ("x" "sees" "y" "+")) -> ("x" "is" "cold" "+"))
    Two or more antecedent literals means the rule is conjunctive.
    """
    head = representation.split(") ->")[0]
    return len(re.findall(r'\("[^"]*"\s+"', head))


def load_items(
    config: str = DEFAULT_CONFIG,
    split: str = "test",
    limit: int | None = None,
    min_qdep: int = 2,
    require_conjunctive: bool = True,
    seed: int = 20260807,
) -> list[Item]:
    """Build items whose target question needs a multi-step, ideally conjunctive proof.

    Only questions with a True/False answer become targets. Unknown questions are
    kept in the proposition space but never used as the item's own question,
    because 'the theory does not decide this' is a different task from the
    multi-step derivation the panel is being asked to perform.
    """
    import pandas as pd

    df = pd.read_parquet(download(config, split))
    rng = __import__("random").Random(seed)
    items: list[Item] = []

    for _, row in df.iterrows():
        rules = row["rules"] or {}
        rule_texts, n_conj = [], 0
        for _, v in sorted(rules.items()):
            if v is None:
                continue
            rule_texts.append(v["text"])
            if _n_premises(v["representation"]) >= 2:
                n_conj += 1
        if require_conjunctive and n_conj == 0:
            continue

        questions = row["questions"] or {}
        props: list[Proposition] = []
        for qk, q in sorted(questions.items()):
            if q is None:
                continue
            props.append(
                Proposition(
                    pid=f"{row['id']}::{qk}",
                    text=q["question"],
                    representation=q["representation"],
                    answer=q["answer"],
                    qdep=int(q["QDep"] or 0),
                    proof=str(q.get("proofs", "")),
                    qlen=str(q.get("QLen", "")),
                )
            )
        # the item's own question must require real derivation, not fact lookup
        targets = [p for p in props if p.y is not None and p.qdep >= min_qdep]
        if not targets:
            continue
        target = rng.choice(targets)

        items.append(
            Item(
                item_id=f"{row['id']}::{target.pid.split('::')[1]}",
                theory=row["theory"],
                question=target.text,
                answer=target.answer,
                qdep=target.qdep,
                stratum="formal",
                propositions=tuple(props),
                n_conjunctive_rules=n_conj,
                rules=tuple(rule_texts),
            )
        )
        if limit and len(items) >= limit:
            break
    return items


def split_items(
    items: list[Item], calib_frac: float = 0.5, seed: int = 20260807
) -> tuple[list[Item], list[Item]]:
    """Item-level calibration/test split.

    Every threshold, temperature and matching rule is fitted on `calib` and
    applied unchanged to `test`. The split is at the ITEM level because claims
    are nested within items (defect D5): splitting on claims would leak an
    item's difficulty across the boundary.
    """
    shuffled = sorted(items, key=lambda i: i.item_id)
    __import__("random").Random(seed).shuffle(shuffled)
    cut = int(len(shuffled) * calib_frac)
    return shuffled[:cut], shuffled[cut:]


def save_manifest(items: list[Item], path: str = "out/dataset_manifest.json") -> None:
    """R0 A4: the dataset manifest is committed before any generation runs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "source": HF_REPO,
                "config": DEFAULT_CONFIG,
                "n_items": len(items),
                "n_propositions": sum(len(i.propositions) for i in items),
                "n_decidable": sum(len(i.decidable()) for i in items),
                "qdep_hist": _hist(i.qdep for i in items),
                "answer_hist": _hist(i.answer for i in items),
                "conjunctive_rules_per_item": _hist(i.n_conjunctive_rules for i in items),
                "item_ids": [i.item_id for i in items],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _hist(vals) -> dict:
    out: dict = {}
    for v in vals:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))
