"""Claim-instance-preserving alignment (D2).

`cluster.align_anchored` computes, for every (claim, target) pair in the top-k
retrieval set, a bidirectional NLI score — and then keeps only the per-(agent,
proposition) argmax. Everything else is discarded inside the function.

That discard is why the registered M6 ablation could never work.
`exp/e1.py:76-78` counts the SURVIVING observations and calls the result
"claim-instance counts", so `n_claims` is identically `n_emitting`: capped and
unsigned, bounded by the number of agents. The frozen `uncapped` arm therefore
compares signed support against an unsigned coverage count, which is a result
about POLARITY, not about capping.

`align_instances` runs the identical computation and additionally returns every
pair that passed the threshold, so the true claim-instance count exists.

CRITICAL — byte-identical measurement calls. `measure.embed` keys its cache on
a hash of the entire text list, so this function must issue exactly the calls
`align_anchored` issues, in exactly the same order, and differ ONLY in what it
retains afterwards. Both are looked up as module attributes (`measure.embed`,
not `from ... import embed`) so `wct3.strict` can wrap them. The bit-identity
test in `tests/test_wct3_align.py` asserts both properties directly.
"""
from __future__ import annotations

from wct import cluster
from wct import measure
from wct.schema import Claim, Item, Observation


def align_instances(item: Item, claims: list[Claim], k: int = 8):
    """`align_anchored`'s observations, plus every pre-collapse assignment.

    Returns (obs_list, instances, audit).

    `obs_list` is bit-identical to `cluster.align_anchored(item, claims, k)[0]`.
    `instances` is a list of dicts, one per (claim, target) pair scoring at or
    above `cluster.T_ALIGN`: {claim_uid, agent, pid, obs, score}. One claim can
    appear several times — it is scored against up to `k` targets and may pass
    against more than one — so `len(instances)` may EXCEED `len(claims)`. The
    only funnel invariant is `len(obs_list) <= len(instances)`.
    """
    props = cluster.canonical_propositions(item)
    if not claims or not props:
        return [], [], {"n_claims": len(claims), "n_props": len(props),
                        "n_pairs_scored": 0, "n_observations": 0,
                        "n_instances": 0, "same_agent_conflicts": 0,
                        "coverage": 0.0}

    twins = cluster.negative_twins(item)
    targets: list[tuple[int, str, str]] = []
    for pi, p in enumerate(props):
        targets.append((pi, "affirm", p.text))
        if p.pid in twins:
            targets.append((pi, "deny", twins[p.pid]))

    # identical call sequence to align_anchored, in identical order
    cv = measure.embed([c.text for c in claims])
    tv = measure.embed([t[2] for t in targets])
    top = measure.top_k_pairs(cv, tv, k=k)

    fwd_pairs, idx = [], []
    for ci, row in enumerate(top):
        for ti in row:
            fwd_pairs.append((claims[ci].text, targets[int(ti)][2]))
            idx.append((ci, int(ti)))
    fwd = measure.nli(fwd_pairs)
    rev = measure.nli([(b, a) for a, b in fwd_pairs])

    best: dict[tuple[str, str], tuple[float, str, str]] = {}
    instances: list[dict] = []
    conflicts = 0
    for n, (ci, ti) in enumerate(idx):
        bidir = float(min(fwd[n][0], rev[n][0]))
        if bidir < cluster.T_ALIGN:
            continue
        pi, obs, _ = targets[ti]
        c, p = claims[ci], props[pi]
        # THE correction: retained here, discarded by the frozen path
        instances.append({"claim_uid": c.uid, "agent": c.agent, "pid": p.pid,
                          "obs": obs, "score": round(bidir, 4)})
        key = (c.agent, p.pid)
        prev = best.get(key)
        if prev is None or bidir > prev[0]:
            if prev is not None and prev[1] != obs:
                conflicts += 1
            best[key] = (bidir, obs, c.uid)
        elif prev[1] != obs:
            conflicts += 1

    obs_list = [
        Observation(item_id=item.item_id, pid=pid, agent=agent, obs=o,
                    alignment_score=round(s, 4), source_claim=uid)
        for (agent, pid), (s, o, uid) in sorted(best.items())
    ]
    audit = {
        "n_claims": len(claims),
        "n_props": len(props),
        "n_pairs_scored": len(idx),
        "n_observations": len(obs_list),
        "n_instances": len(instances),
        "same_agent_conflicts": conflicts,
        "coverage": round(len(obs_list) / max(len(props) * cluster._n_agents(claims), 1), 4),
    }
    return obs_list, instances, audit


def instance_counts(instances: list[dict], pids: list[str]):
    """(unsigned, signed) uncapped claim-instance counts per proposition.

    The registered M6 ablation is the unsigned one: how much TEXT asserts a
    proposition, with no per-agent cap. The signed one exists so that capping
    and polarity can be varied independently instead of confounded — see the
    2x2 in `wct3.arms`.
    """
    import numpy as np
    pi = {p: i for i, p in enumerate(pids)}
    unsigned = np.zeros(len(pids))
    signed = np.zeros(len(pids))
    for inst in instances:
        j = pi.get(inst["pid"])
        if j is None:
            continue
        unsigned[j] += 1
        signed[j] += 1 if inst["obs"] == "affirm" else -1
    return unsigned, signed
