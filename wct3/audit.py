"""Restore the alignment audit cycle 2 discarded (D3).

`cluster.alignment_audit` and `cluster.aligner_probe` are frozen and correct.
The cycle-2 driver simply never called them: `exp/e1_v2.py:189` binds `audits`
from `e1.build_observations` and never references it again, so neither cycle-2
summary carries any measurement-quality evidence at all.

That matters because the cycle-1 audit is HOW cycle 1's defect was found — the
claims -> observations funnel and the polarity restriction are both visible
there and nowhere else. The run that produced cycle 2's "go" has none of it.

This reproduces the cycle-1 block verbatim (same keys, same rounding, same
notes) and adds the claim-instance funnel that only `wct3.align` can produce.
"""
from __future__ import annotations

import numpy as np

from exp.common import PREREG
from wct import cluster

TOP_K = PREREG["measurement"]["nli"]["top_k"]

_SELF_ID_NOTE = (
    "PRIMARY mapper diagnostic. Each canonical proposition's own surface text "
    "and its negated form are fed back as pseudo-claims; no model output, no "
    "reasoning and no truth label is involved, so a failure here is "
    "unambiguously a measurement failure."
)
_LEX_NOTE = (
    "SECONDARY and deliberately partial. The lexical reference fires only on "
    "near-verbatim non-conditional restatements, so it covers a small fraction "
    "of observations. Recall against it is meaningful; PRECISION against it is "
    "not reported, because an aligner observation absent from a low-coverage "
    "reference is unlabelled rather than wrong."
)


def panel_audit(items, iids, audits) -> dict:
    """The frozen cycle-1 audit block, plus the claim-instance funnel.

    `audits` is the per-item list `wct3.observe.build_rows` returns, so the
    aligner probe is the only thing recomputed here.
    """
    by_id = {i.item_id: i for i in items if i.item_id in set(iids)}
    probe_n = probe_hit = probe_wrong_prop = probe_wrong_pol = 0
    probe_status, probe_reason = "computed", None
    for iid in iids:
        try:
            pr = cluster.aligner_probe(by_id[iid], k=TOP_K)
        except Exception as exc:                     # wct3.strict.CacheMiss
            # The probe feeds SYNTHETIC pseudo-claims through the aligner, so its
            # NLI pairs exist in the cache only for panels whose driver actually
            # ran it. exp/e1.py did (cycle 1); exp/e1_v2.py did not (D3 — it is
            # the very omission being corrected). Computing them now would be new
            # in-process NLI, which this slice's no-inference constraint forbids,
            # so the probe is reported as NOT COMPUTED rather than silently run.
            probe_status = "NOT COMPUTED"
            probe_reason = (f"{type(exc).__name__}: {exc}. The aligner probe was "
                            f"never run for this panel, so its NLI pairs are not "
                            f"cached. Computing them is local CPU NLI (no API, no "
                            f"quota) but is still new inference, which slice 1 "
                            f"forbids. Every other audit field below is computed "
                            f"from the existing cache and is unaffected.")
            break
        if pr.get("n"):
            probe_n += pr["n"]
            probe_hit += round(pr["self_identification"] * pr["n"])
            probe_wrong_prop += pr["wrong_proposition"]
            probe_wrong_pol += pr["wrong_polarity"]

    rec = [a["recall"] for a in audits if a.get("recall") is not None]
    n_ref = int(sum(a.get("n_reference", 0) for a in audits))
    n_pred = int(sum(a["n_observations"] for a in audits))
    n_claims = int(sum(a["n_claims"] for a in audits))
    n_inst = int(sum(a.get("n_instances", 0) for a in audits))

    return {
        "status": "POST-HOC",
        "aligner_self_identification": _probe_block(
            probe_status, probe_reason, probe_n, probe_hit,
            probe_wrong_prop, probe_wrong_pol),
        "lexical_reference": {
            "n_reference": n_ref,
            "n_predicted": n_pred,
            "recall_mean": round(float(np.mean(rec)), 4) if rec else None,
            "note": _LEX_NOTE,
        },
        "same_agent_conflicts": int(sum(a["same_agent_conflicts"] for a in audits)),
        "observations": n_pred,
        "claims": n_claims,
        "funnel": {
            "claims": n_claims,
            "instances": n_inst,
            "observations": n_pred,
            "note": "NOT monotone. Alignment scores each claim against up to "
                    f"top_k={TOP_K} targets, so one claim can pass against more "
                    "than one and instances may exceed claims. The invariant is "
                    "observations <= instances: observations are the "
                    "per-(agent, proposition) argmax subset of instances.",
        },
        "note": "measures the MAPPER, not whether the agent was right (that is "
                "panel accuracy, in E0).",
    }


def _probe_block(status, reason, n, hit, wrong_prop, wrong_pol) -> dict:
    """An incomplete probe reports NOTHING but its incompleteness.

    The loop stops at the first uncached item, so a partial run has counts for
    an arbitrary prefix of the panel. Publishing an accuracy over that prefix
    beside status="NOT COMPUTED" would read as a measurement; it is a fragment
    of one. The partial counts are kept under `partial` purely as disclosure.
    """
    if status == "computed":
        return {"status": status, "n_probes": n,
                "accuracy": round(hit / n, 4) if n else None,
                "wrong_proposition": wrong_prop, "wrong_polarity": wrong_pol,
                "note": _SELF_ID_NOTE}
    return {"status": status, "reason": reason,
            "n_probes": None, "accuracy": None,
            "wrong_proposition": None, "wrong_polarity": None,
            "partial": {"note": "counts from the item prefix processed before the "
                                "first cache miss; NOT a panel measurement",
                        "n_probes": n,
                        "accuracy": round(hit / n, 4) if n else None,
                        "wrong_proposition": wrong_prop,
                        "wrong_polarity": wrong_pol},
            "note": _SELF_ID_NOTE}
