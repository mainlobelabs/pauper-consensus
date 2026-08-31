"""Proposition alignment: claim instances -> canonical propositions.

Two modes, and the difference between them is itself a result.

`anchored` aligns claims to the theory's canonical proposition set. That set is
derivable from the theory's facts and rules WITHOUT knowing any truth value, so
using it consumes no labels and stays on the WCT-U side of the supervision
ledger. It isolates the aggregation question from the alignment question.

`free` discovers propositions by clustering claims across agents, which is what
WCT must do on any dataset without a canonical set. Scoring `free` against
`anchored` measures assumption M5 directly — whether agreement is measuring
reasoning or measuring the mapper.

Propositions are canonicalised to POSITIVE polarity. ProofWriter emits every
statement in both forms ("X sees Y" / "X does not see Y"); treating them as two
propositions would let one agent's single belief vote twice, once affirming and
once denying, which is exactly the double-counting plan.md 3.1 forbids.
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np

from .schema import Claim, Item, Observation, Proposition

# Frozen on calibration at R0; sensitivity analysis varies them over stored
# raw probabilities without re-running NLI.
T_ALIGN = 0.60      # bidirectional entailment for "same proposition"
T_DENY = 0.60       # contradiction for "denies the proposition"


def _is_negative_form(rep: str) -> bool:
    return rep.rstrip(")").rstrip().endswith('"-"')


def canonical_propositions(item: Item) -> list[Proposition]:
    """The positive-polarity proposition set, one per underlying statement."""
    out, seen = [], set()
    for p in item.propositions:
        if _is_negative_form(p.representation) or p.representation in seen:
            continue
        seen.add(p.representation)
        out.append(p)
    return out


def negative_twins(item: Item) -> dict[str, str]:
    """canonical pid -> the surface text of its negated form.

    ProofWriter states every proposition in both polarities, so the negated
    surface form is available rather than synthesised. Having it is what lets
    polarity be read off WHICH form a claim matches, instead of being inferred
    from an NLI contradiction against some other proposition.
    """
    pos = {}
    for p in item.propositions:
        if not _is_negative_form(p.representation):
            pos[p.representation.replace('"+"', '"-"')] = p.pid
    twins = {}
    for p in item.propositions:
        if _is_negative_form(p.representation) and p.representation in pos:
            twins[pos[p.representation]] = p.text
    return twins


def align_anchored(
    item: Item, claims: list[Claim], k: int = 8
) -> tuple[list[Observation], dict]:
    """One observation per (agent, canonical proposition). Assumption M6.

    Polarity is read from WHICH polarity form of the proposition a claim
    matches, not from an NLI contradiction against the positive form.

    That distinction is load-bearing on this dataset and it was got wrong first
    time. ProofWriter propositions are permutations of a tiny closed vocabulary,
    so two DIFFERENT propositions over the same entities are usually scored as a
    contradiction: "the mouse sees the bald eagle" against "the bald eagle sees
    the mouse" returns contradiction at 0.996. Reading that as a denial makes
    every agent deny almost every proposition it did not mention, which is not
    evidence about the proposition at all. Matching against both surface forms
    keeps NLI doing alignment only, which is the one job plan.md 3.1 gives it.

    Where an agent's own claims disagree about the same proposition the
    highest-scoring observation wins and the conflict is counted, because
    dropping such conflicts silently would understate single-agent noise.
    """
    from . import measure

    props = canonical_propositions(item)
    if not claims or not props:
        return [], {"n_claims": len(claims), "n_props": len(props),
                    "n_pairs_scored": 0, "n_observations": 0,
                    "same_agent_conflicts": 0, "coverage": 0.0}

    twins = negative_twins(item)
    # each proposition contributes two alignment targets: its positive surface
    # form (match => affirm) and its negative surface form (match => deny)
    targets: list[tuple[int, str, str]] = []
    for pi, p in enumerate(props):
        targets.append((pi, "affirm", p.text))
        if p.pid in twins:
            targets.append((pi, "deny", twins[p.pid]))

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
    conflicts = 0
    for n, (ci, ti) in enumerate(idx):
        bidir = float(min(fwd[n][0], rev[n][0]))
        if bidir < T_ALIGN:
            continue
        pi, obs, _ = targets[ti]
        c, p = claims[ci], props[pi]
        key = (c.agent, p.pid)
        prev = best.get(key)
        if prev is None or bidir > prev[0]:
            if prev is not None and prev[1] != obs:
                conflicts += 1
            best[key] = (bidir, obs, c.uid)
        elif prev[1] != obs:
            conflicts += 1
    probs = idx

    obs_list = [
        Observation(item_id=item.item_id, pid=pid, agent=agent, obs=o,
                    alignment_score=round(s, 4), source_claim=uid)
        for (agent, pid), (s, o, uid) in sorted(best.items())
    ]
    audit = {
        "n_claims": len(claims),
        "n_props": len(props),
        "n_pairs_scored": len(probs),
        "n_observations": len(obs_list),
        "same_agent_conflicts": conflicts,
        "coverage": round(len(obs_list) / max(len(props) * _n_agents(claims), 1), 4),
    }
    return obs_list, audit


_NEG_RE = re.compile(r"\b(not|isn't|is not|does not|doesn't|cannot|can't)\b", re.I)


def _negates_prop(claim_text: str, prop_text: str) -> bool:
    """True when the claim negates a proposition stated positively."""
    return bool(_NEG_RE.search(claim_text)) and not _NEG_RE.search(prop_text)


def _n_agents(claims: list[Claim]) -> int:
    return len({c.agent for c in claims}) or 1


def align_free(
    item: Item, claims: list[Claim], k: int = 8, t: float = T_ALIGN
) -> tuple[list[list[int]], dict]:
    """Discover propositions by clustering claims on bidirectional entailment.

    Greedy transitive-closure clustering with an explicit transitivity audit:
    entailment is not an equivalence relation, so merging on it necessarily
    creates violations. Counting them is the honest alternative to pretending
    the relation is transitive.
    """
    from . import measure

    if not claims:
        return [], {"clusters": 0, "transitivity_violations": 0}
    v = measure.embed([c.text for c in claims])
    n = len(claims)
    kk = min(k + 1, n)
    top = np.argpartition(-(v @ v.T), kk - 1, axis=1)[:, :kk]

    pairs, idx = [], []
    for i, row in enumerate(top):
        for j in row:
            if int(j) <= i:
                continue
            pairs.append((claims[i].text, claims[int(j)].text))
            idx.append((i, int(j)))
    if not pairs:
        return [[i] for i in range(n)], {"clusters": n, "transitivity_violations": 0}
    fwd = measure.nli(pairs)
    rev = measure.nli([(b, a) for a, b in pairs])
    link = {ij: float(min(fwd[m][0], rev[m][0])) for m, ij in enumerate(idx)}

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    merged = [ij for ij, s in link.items() if s >= t]
    for i, j in merged:
        parent[find(i)] = find(j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    clusters = sorted(groups.values(), key=lambda g: g[0])

    # transitivity audit: i~j and j~l merged, but i,l scored and below threshold
    linked = set(merged) | {(j, i) for i, j in merged}
    violations = 0
    for i, j in link:
        if find(i) == find(j) and (i, j) not in linked and link[(i, j)] < t:
            violations += 1
    return clusters, {
        "clusters": len(clusters),
        "transitivity_violations": violations,
        "n_pairs_scored": len(link),
    }


_STOP = frozenset(
    "the a an is are does do it that then we can will to of and so therefore".split()
)


def _norm(s: str) -> frozenset[str]:
    """Content-word bag, with negation stripped so polarity is handled separately."""
    s = _NEG_RE.sub(" ", s.lower())
    return frozenset(re.sub(r"[^a-z ]+", " ", s).split()) - _STOP


_CONDITIONAL = re.compile(r"\b(if|then|whenever|rule|suppose|assume)\b", re.I)


def reference_alignment(item: Item, claims: list[Claim]) -> dict[str, str]:
    """High-precision claim->proposition reference by lexical match.

    ProofWriter statements are templated and models restate them near-verbatim,
    so a tight lexical match is right when it fires. Low recall is fine: this is
    the yardstick, not the instrument.

    Two restrictions earn their place, both found by inspecting what a looser
    rule did on the pilot item. Conditionals are excluded, because "if something
    sees the mouse then it is cold" is a restatement of a RULE and contains the
    proposition "the mouse is cold" without asserting it. And the claim may
    carry at most a couple of tokens beyond the proposition, because a bare
    superset test lets any long sentence swallow a short proposition.
    """
    props = canonical_propositions(item)
    ptoks = {p.pid: _norm(p.text) for p in props}
    ref: dict[str, str] = {}
    for c in claims:
        if _CONDITIONAL.search(c.text):
            continue
        ctoks = _norm(c.text)
        hits = [pid for pid, t in ptoks.items()
                if t and t <= ctoks and len(ctoks - t) <= 2]
        if len(hits) == 1:  # unambiguous match only
            ref[c.uid] = hits[0]
    return ref


def reference_observations(item: Item, claims: list[Claim]) -> set[tuple[str, str, str]]:
    """(agent, pid, affirm|deny) implied by the lexical reference alignment."""
    ref = reference_alignment(item, claims)
    by_uid = {c.uid: c for c in claims}
    props = {p.pid: p.text for p in canonical_propositions(item)}
    out = set()
    for uid, pid in ref.items():
        c = by_uid[uid]
        obs = "deny" if _negates_prop(c.text, props[pid]) else "affirm"
        out.add((c.agent, pid, obs))
    return out


def alignment_audit(item: Item, claims: list[Claim], obs: list[Observation]) -> dict:
    """Precision/recall of the NLI aligner against the lexical reference.

    Compared at the OBSERVATION level -- (agent, proposition, polarity) -- not
    per claim instance. A per-claim comparison would score the one-vote-per-
    agent cap as recall failure: the reference maps many restatements of the
    same fact to one proposition, and the pipeline is supposed to collapse them
    (assumption M6). Scoring the collapsed output is scoring what is actually
    used downstream.

    This measures the MAPPER. It is deliberately not the same quantity as
    whether the agent's assertion was true: an agent affirming a false
    proposition is a wrong agent, not a wrong alignment, and scoring the two
    together would let panel error masquerade as measurement error (M5).
    """
    ref = reference_observations(item, claims)
    got = {(o.agent, o.pid, o.obs) for o in obs}
    if not ref:
        return {"n_reference": 0, "precision": None, "recall": None,
                "n_predicted": len(got)}
    tp = len(ref & got)
    return {
        "n_reference": len(ref),
        "n_predicted": len(got),
        "precision": round(tp / len(got), 4) if got else None,
        "recall": round(tp / len(ref), 4),
        "tp": tp, "fp": len(got - ref), "fn": len(ref - got),
    }


def aligner_probe(item: Item, k: int = 8) -> dict:
    """Self-identification test for the aligner. No agent involved at all.

    Feed each canonical proposition's own surface text back in as a pseudo-claim
    and check it aligns to itself as an affirm; feed its negated form and check
    it aligns to the same proposition as a deny. This isolates the MAPPER
    completely -- there is no model output, no reasoning and no truth label in
    the loop -- so a failure here is unambiguously a measurement failure.

    It is not a trivial test on this dataset. The proposition space is a closed
    vocabulary of permutations over a handful of entities and relations, so the
    aligner has to separate "the mouse sees the bald eagle" from "the bald eagle
    sees the mouse", which a bag-of-words instrument cannot do and which NLI
    scores as a confident contradiction rather than as neutral.
    """
    props = canonical_propositions(item)
    twins = negative_twins(item)
    if not props:
        return {"n": 0}

    # each probe is its own agent, otherwise the one-vote-per-agent cap would
    # collapse all the probes into a single observation
    probes: list[Claim] = []
    expect: dict[str, tuple[str, str]] = {}
    for i, p in enumerate(props):
        uid = f"probe::pos::{i}"
        probes.append(Claim(uid=uid, item_id=item.item_id, agent=uid, text=p.text))
        expect[uid] = (p.pid, "affirm")
        if p.pid in twins:
            uid = f"probe::neg::{i}"
            probes.append(Claim(uid=uid, item_id=item.item_id, agent=uid,
                                text=twins[p.pid], polarity=-1))
            expect[uid] = (p.pid, "deny")

    obs, _ = align_anchored(item, probes, k=k)
    got = {o.source_claim: (o.pid, o.obs) for o in obs}

    hit = sum(1 for uid, exp in expect.items() if got.get(uid) == exp)
    wrong_prop = sum(1 for uid, exp in expect.items()
                     if uid in got and got[uid][0] != exp[0])
    wrong_pol = sum(1 for uid, exp in expect.items()
                    if uid in got and got[uid][0] == exp[0] and got[uid][1] != exp[1])
    return {
        "n": len(expect),
        "self_identification": round(hit / len(expect), 4),
        "wrong_proposition": wrong_prop,
        "wrong_polarity": wrong_pol,
        "unmatched": len(expect) - len(got.keys() & expect.keys()),
    }


def panel_accuracy(item: Item, obs: list[Observation]) -> dict:
    """Per-agent proposition-level sensitivity and false-positive rate.

    Distinct from alignment_audit: this is how often each AGENT is right about
    a proposition, which is what feeds WCT-C's reliability parameters and E0's
    error-correlation estimates.
    """
    truth = {p.pid: p.y for p in canonical_propositions(item)}
    per: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    )
    for o in obs:
        y = truth.get(o.pid)
        if y is None:
            continue
        said = 1 if o.obs == "affirm" else 0
        cell = ("tp" if said else "fn") if y == 1 else ("fp" if said else "tn")
        per[o.agent][cell] += 1
    return {k: dict(v) for k, v in per.items()}
