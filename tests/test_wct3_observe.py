"""wct3.observe reproduces e1.build_observations and adds the real counts."""
from __future__ import annotations

import numpy as np
import pytest

from exp import e1
from exp.common import complete_items
from exp.run_generate_v2 import load_cell_v2
from exp.v2_dataset import load_v2_items
from wct3 import observe

N_ITEMS = 8


@pytest.fixture(scope="module")
def built():
    items, calib, _ = load_v2_items()
    cell, _ = load_cell_v2(items, "panelA")
    iids = complete_items(cell, min_agents=2)[:N_ITEMS]
    frozen_rows, frozen_agents, _ = e1.build_observations(items, cell, iids)
    rows, agents, audits = observe.build_rows(items, cell, iids)
    return frozen_rows, frozen_agents, rows, agents, audits


def test_rows_match_frozen_on_every_frozen_key(built):
    frozen_rows, frozen_agents, rows, agents, _ = built
    assert agents == frozen_agents
    assert len(rows) == len(frozen_rows)
    for a, b in zip(rows, frozen_rows):
        for k in b:
            if k == "votes":
                assert np.array_equal(a[k], b[k])
            else:
                assert a[k] == b[k], k


def test_frozen_n_claims_equals_n_emitting(built):
    """D2 pinned: the frozen 'claim-instance' field is a capped agent count."""
    _, _, rows, agents, _ = built
    nc = np.array([r["n_claims"] for r in rows])
    ne = np.array([r["n_emitting"] for r in rows])
    assert (nc == ne).all()
    assert nc.max() <= len(agents)


def test_true_instance_counts_are_not_the_frozen_ones(built):
    """The corrected count is uncapped, so it must break the agent ceiling."""
    _, _, rows, agents, _ = built
    ni = np.array([r["n_instances"] for r in rows])
    ne = np.array([r["n_emitting"] for r in rows])
    assert (ni >= ne).all(), "an instance count below the capped count is impossible"
    assert ni.max() > len(agents), (
        "no proposition drew more claim instances than there are agents; the "
        "uncapped arm would be indistinguishable from the capped one")


def test_signed_instances_bounded_by_unsigned(built):
    _, _, rows, _, _ = built
    u, s = observe.instance_arrays(rows)
    assert (np.abs(s) <= u).all()


def test_covariate_variants(built):
    _, _, rows, agents, _ = built
    y, V, iids, X = observe.to_arrays(rows, agents)
    frozen = X["frozen"]
    # the registered matrix carries 'verbosity' as a duplicate of 'coverage'
    assert np.array_equal(frozen[:, 1], frozen[:, 2])
    assert X["dedup"].shape[1] == 3
    assert X["verbosity"].shape[1] == 5
    # and the frozen matrix is byte-identical to e1.to_arrays'
    fy, fV, fiids, fX = e1.to_arrays(rows, agents)
    assert np.array_equal(frozen, fX)
    assert np.array_equal(y, fy) and np.array_equal(V, fV) and iids == fiids


def test_audits_carry_the_funnel(built):
    _, _, _, _, audits = built
    assert audits
    for a in audits:
        assert a["n_observations"] <= a["n_instances"]
        assert "self_identification" not in a or a["n_claims"] > 0
