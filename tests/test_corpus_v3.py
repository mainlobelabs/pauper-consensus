"""exp3.corpus_v3 pins the registered corpus and names the quantities it returns (B5)."""
from __future__ import annotations

import pytest

from exp3 import corpus_v3 as C


@pytest.fixture(scope="module")
def items():
    return C.load_corpus()


def test_corpus_size_and_hash_match_the_registration(items):
    assert len(items) == C.EXPECTED_N_ITEMS == 9805
    assert C.corpus_sha256(items) == C.EXPECTED_SHA256


def test_no_item_id_collisions(items):
    ids = [it.item_id for it in items]
    assert len(set(ids)) == len(ids) == 9805


def test_collision_is_raised_not_silently_absorbed(monkeypatch):
    """A duplicate id must fail loudly: it would make the corpus smaller than claimed."""
    real = C.data.load_items
    def dup(*a, **k):
        out = real(*a, **k)
        return out + out[:1] if out else out
    monkeypatch.setattr(C.data, "load_items", dup)
    with pytest.raises(C.CorpusError, match="colliding item_id"):
        C.load_corpus()


def test_cycle2_items_are_a_complete_subset(items):
    assert C.cycle2_is_subset(items) is True


def test_missing_cycle2_item_is_raised(items, monkeypatch):
    from exp import v2_dataset
    monkeypatch.setattr(C, "load_corpus", lambda: items[:10])
    monkeypatch.setattr(v2_dataset, "load_v2_items", lambda: ([items[0]], None, None))
    assert C.cycle2_is_subset(items[:10]) is True   # sanity: present case passes
    bad = [it for it in items[:10]]
    class Fake:
        item_id = "definitely-not-in-corpus"
    monkeypatch.setattr(v2_dataset, "load_v2_items", lambda: ([Fake()], None, None))
    with pytest.raises(C.CorpusError, match="absent from the cycle-3 corpus"):
        C.cycle2_is_subset(bad)


def test_b5_uses_positive_polarity_negatives_not_the_item_target_rate(items):
    """The distinction the plan review caught: these are different quantities."""
    counts = C.decidable_counts(items)
    assert counts["decidable"] == 91052
    assert counts["positive_polarity_negatives"] == 45526
    # the ITEM-target false rate is a different number and must not be used for B5
    item_false = sum(1 for it in items if str(it.answer).lower().startswith("f"))
    assert item_false != counts["positive_polarity_negatives"]


def test_projection_is_labelled_not_a_gate():
    p = C.projected_scored_negatives(9805, 5)
    assert p.is_gate is False
    assert p.assumptions, "a projection without stated assumptions is not a projection"
    assert p.n_scored_positive_polarity_negatives == round(C.SCORED_NEG_PER_ITEM_AGENT * 9805 * 5)
    # scales with panel size
    assert (C.projected_scored_negatives(9805, 3).n_scored_positive_polarity_negatives
            < p.n_scored_positive_polarity_negatives)


def test_source_parquet_hashes_cover_all_six_inputs():
    h = C.source_parquet_sha256()
    assert len(h) == 6
    assert all(len(v) == 64 for v in h.values())


def test_verify_returns_every_registered_figure():
    v = C.verify()
    assert v["n_items"] == 9805
    assert v["sha256"] == C.EXPECTED_SHA256
    assert v["cycle2_subset"] is True
    assert v["positive_polarity_negatives"] == 45526
    assert len(v["source_parquet_sha256"]) == 6


def test_verify_raises_on_a_wrong_registered_hash(monkeypatch):
    monkeypatch.setattr(C, "EXPECTED_SHA256", "0" * 64)
    with pytest.raises(C.CorpusError, match="sha256"):
        C.verify()


def test_module_writes_no_artifact_of_its_own():
    """Building cycle-3 corpus artifacts is a non-goal; this module returns values.

    (wct.data.download may fetch a missing parquet INPUT -- that is the data
    layer's job and predates this slice. What is forbidden here is corpus_v3
    emitting a derived artifact that the registration should be embedding.)
    """
    import inspect, pathlib
    src = inspect.getsource(C)
    for forbidden in ('open(', 'write_text', 'json.dump', 'to_json', 'savez', 'mkdir'):
        assert forbidden not in src, f"corpus_v3 appears to write: {forbidden!r}"

    out = pathlib.Path("out")
    before = {p: p.stat().st_mtime for p in out.rglob("*") if p.is_file()} if out.exists() else {}
    C.verify()
    after = {p: p.stat().st_mtime for p in out.rglob("*") if p.is_file()} if out.exists() else {}
    assert before == after, "verify() touched out/"
