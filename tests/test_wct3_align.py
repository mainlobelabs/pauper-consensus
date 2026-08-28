"""wct3.align reproduces the frozen aligner exactly, and retains more (D2)."""
from __future__ import annotations

import numpy as np
import pytest

from exp import e1
from exp.common import complete_items
from exp.run_generate_v2 import load_cell_v2
from exp.v2_dataset import load_v2_items
from wct import cluster, measure
from wct.extract import extract
from wct3 import align as v3align
from wct3 import strict

N_ITEMS = 6          # enough to exercise conflicts and multi-target passes


@pytest.fixture(scope="module")
def cases():
    items, _, _ = load_v2_items()
    cell, _ = load_cell_v2(items, "panelA")
    iids = complete_items(cell, min_agents=2)[:N_ITEMS]
    by_id = {i.item_id: i for i in items}
    out = []
    for iid in iids:
        item = by_id[iid]
        claims = []
        for a, g in sorted(cell[iid].items()):
            if g.trace.strip() and not g.error:
                claims.extend(extract(g, item))
        if claims:
            out.append((item, claims))
    assert out, "no usable items — is out/cache/generation populated?"
    return out


def _record_calls(monkeypatch):
    """Capture every measurement call, then delegate to the real (cached) one."""
    calls = []
    real_embed, real_nli = measure.embed, measure.nli

    def rec_embed(texts, batch=64):
        calls.append(("embed", list(texts)))
        return real_embed(texts, batch)

    def rec_nli(pairs, model_id=measure.NLI_MODEL, batch=64):
        calls.append(("nli", [tuple(p) for p in pairs]))
        return real_nli(pairs, model_id, batch)

    monkeypatch.setattr(measure, "embed", rec_embed)
    monkeypatch.setattr(measure, "nli", rec_nli)
    return calls


def test_observations_are_bit_identical(cases):
    for item, claims in cases:
        frozen, _ = cluster.align_anchored(item, claims, k=8)
        got, _, _ = v3align.align_instances(item, claims, k=8)
        assert len(got) == len(frozen), item.item_id
        for a, b in zip(got, frozen):
            assert (a.item_id, a.pid, a.agent, a.obs, a.alignment_score,
                    a.source_claim) == (b.item_id, b.pid, b.agent, b.obs,
                                        b.alignment_score, b.source_claim)


def test_audit_matches_frozen_on_shared_keys(cases):
    for item, claims in cases:
        _, frozen_audit = cluster.align_anchored(item, claims, k=8)
        _, _, audit = v3align.align_instances(item, claims, k=8)
        for k in frozen_audit:
            assert audit[k] == frozen_audit[k], (item.item_id, k)


def test_measurement_calls_are_byte_identical(cases, monkeypatch):
    """The cache is keyed on whole-list hashes, so identical calls are the
    difference between a cache hit and silently re-embedding 2 GB."""
    item, claims = cases[0]
    frozen_calls = _record_calls(monkeypatch)
    cluster.align_anchored(item, claims, k=8)
    frozen = list(frozen_calls)
    frozen_calls.clear()
    v3align.align_instances(item, claims, k=8)
    assert list(frozen_calls) == frozen


def test_instances_are_retained_and_may_exceed_claims(cases):
    """The whole point of D2: the pre-collapse assignments survive."""
    saw_multi = False
    for item, claims in cases:
        obs, instances, audit = v3align.align_instances(item, claims, k=8)
        assert len(obs) <= len(instances), item.item_id      # the only invariant
        assert audit["n_instances"] == len(instances)
        per_claim = {}
        for inst in instances:
            per_claim[inst["claim_uid"]] = per_claim.get(inst["claim_uid"], 0) + 1
        if any(v > 1 for v in per_claim.values()):
            saw_multi = True
    assert saw_multi, ("no claim passed against >1 target across the sample; the "
                       "non-monotone funnel claim needs a witness")


def test_frozen_n_claims_is_really_n_emitting(cases):
    """Pin the defect itself, so it stays documented by the suite (D2)."""
    items, _, _ = load_v2_items()
    cell, _ = load_cell_v2(items, "panelA")
    iids = complete_items(cell, min_agents=2)[:N_ITEMS]
    rows, _, _ = e1.build_observations(items, cell, iids)
    nc = np.array([r["n_claims"] for r in rows])
    ne = np.array([r["n_emitting"] for r in rows])
    assert (nc == ne).all(), "defect D2 no longer reproduces — check exp/e1.py:76-78"


def test_strict_mode_raises_on_a_cache_miss():
    strict.install()
    try:
        with pytest.raises(strict.CacheMiss):
            measure.embed(["a string no run has ever embedded — wct3 strict probe"])
        with pytest.raises(strict.CacheMiss):
            measure.nli([("wct3 strict probe premise", "wct3 strict probe hypothesis")])
        assert measure.embed([]).shape == (0, 768)     # empty stays a fast path
    finally:
        strict.uninstall()
    assert not strict.installed()
