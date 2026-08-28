"""Row builder carrying the TRUE claim-instance counts (D2).

Mirrors `exp.e1.build_observations` exactly on every key that function
produces, and adds what the frozen path threw away:

  n_claims            the frozen field. Identically equal to n_emitting,
                      because align_anchored collapses per (agent, pid) before
                      exp/e1.py:76-78 counts. Kept for continuity and pinned by
                      a test so the defect stays visible.
  n_instances         uncapped, unsigned: how many claim instances assert or
                      deny the proposition. THIS is the registered M6 quantity.
  n_instances_signed  uncapped, signed: affirming instances minus denying ones.

Having both lets capping and polarity vary independently instead of being
confounded, which is what `wct3.arms` needs for the 2x2.

The loader is deliberately not this module's business: cycle 1 resolves cells
via `exp.common.load_generations` (per-CELL dicts) and cycle 2 via
`exp.run_generate_v2.load_cell_v2` (one cell). Both normalise to
`{item_id: {agent: Generation}}` at the driver boundary, so this function takes
that and knows about neither.
"""
from __future__ import annotations

import numpy as np

from exp.common import PREREG
from wct import aggregate as agg
from wct import cluster
from wct.extract import extract as _stock_extract
from wct3 import align as v3align

TOP_K = PREREG["measurement"]["nli"]["top_k"]


def build_rows(items, cell, iids, extractor=None):
    """Rows, agents, per-item audits. Superset of `e1.build_observations`."""
    extractor = extractor or _stock_extract
    by_id = {i.item_id: i for i in items}
    agents = sorted({a for iid in iids for a in cell[iid]})
    rows, audits = [], []

    for iid in iids:
        item = by_id[iid]
        claims, trace_lens = [], []
        for a, g in sorted(cell[iid].items()):
            if g.trace.strip() and not g.error:
                claims.extend(extractor(g, item))
                trace_lens.append(len(g.trace))
        if not claims:
            continue

        obs, instances, audit = v3align.align_instances(item, claims, k=TOP_K)
        audit.update(cluster.alignment_audit(item, claims, obs))
        audit["item_id"] = iid
        audits.append(audit)

        props = cluster.canonical_propositions(item)
        pids = [p.pid for p in props]
        V = agg.vote_matrix(obs, agents, pids)

        # frozen field, reproduced exactly: counts the COLLAPSED observations,
        # which is why it equals n_emitting on every row (D2)
        counts = np.zeros(len(pids))
        for o in obs:
            counts[pids.index(o.pid)] += 1
        # the corrected fields: counted over pre-collapse assignments
        inst_unsigned, inst_signed = v3align.instance_counts(instances, pids)

        # per-item verbosity, for the covariate baseline the registration named
        # but the frozen X never got (its 'verbosity' column duplicates coverage)
        item_claims = float(len(claims))
        item_trace = float(np.mean(trace_lens)) if trace_lens else 0.0

        for k, p in enumerate(props):
            if p.y is None:
                continue                      # Unknown: excluded from primary
            emitting = int((V[k] != agg.MISSING).sum())
            if emitting == 0:
                continue                      # nobody mentioned it: not rankable
            rows.append({
                "item_id": iid, "pid": p.pid, "y": p.y, "qdep": p.qdep,
                "votes": V[k].copy(), "n_emitting": emitting,
                "n_claims": counts[k], "text_len": len(p.text),
                "n_instances": float(inst_unsigned[k]),
                "n_instances_signed": float(inst_signed[k]),
                "item_claims": item_claims, "item_trace_len": item_trace,
            })
    return rows, agents, audits


def to_arrays(rows, agents):
    """`e1.to_arrays`' outputs plus the three covariate variants.

    Returns (y, V, item_ids, X) where X is a dict of variants:

      frozen     [qdep, n_emitting, n_claims, text_len/50] — exactly the
                 registered matrix, INCLUDING the duplicated column, so the
                 frozen baseline reproduces.
      dedup      the duplicate dropped.
      verbosity  dedup plus real per-item verbosity, which is what the
                 registration's feature list ("depth, coverage, verbosity,
                 length") actually described.
    """
    y = np.array([r["y"] for r in rows])
    V = np.stack([r["votes"] for r in rows])
    iids = [r["item_id"] for r in rows]
    qdep = np.array([r["qdep"] for r in rows], dtype=float)
    emit = np.array([r["n_emitting"] for r in rows], dtype=float)
    nclaims = np.array([r["n_claims"] for r in rows], dtype=float)
    tlen = np.array([r["text_len"] for r in rows], dtype=float) / 50.0
    vclaims = np.array([r["item_claims"] for r in rows], dtype=float) / 10.0
    vtrace = np.array([r["item_trace_len"] for r in rows], dtype=float) / 1000.0

    X = {
        "frozen": np.column_stack([qdep, emit, nclaims, tlen]),
        "dedup": np.column_stack([qdep, emit, tlen]),
        "verbosity": np.column_stack([qdep, emit, tlen, vclaims, vtrace]),
    }
    return y, V, iids, X


def instance_arrays(rows):
    """(uncapped unsigned, uncapped signed) score vectors for the M6 2x2."""
    return (np.array([r["n_instances"] for r in rows], dtype=float),
            np.array([r["n_instances_signed"] for r in rows], dtype=float))
