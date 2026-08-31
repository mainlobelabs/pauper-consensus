"""E1_v2 analysis: registered primary, secondaries S1/S2, depth descriptives.

Committed BEFORE any v2 generation; these implementations ARE the registration
of every formula prereg_v2.yaml names (`analysis_code_freeze`). Structure and
discipline follow exp/e1.py; the registered differences:

  - Calibration map: Platt sigmoid(a*s+b) fitted on calib by exact ML
    (exp/recalib.py fit_platt_map, the frozen implementation). Temperature is
    reported as an ablation for v1 continuity, never as the primary.
  - Baseline sensitivity: the covariate baseline is reported under BOTH the
    v1-style GD fit (primary verdict) and an exact-ML refit (registered
    sensitivity row).
  - S1 deny self-contradiction filter and S2 step-exemption extractor are
    registered instrument variants, analysed with the identical primary
    formula, reported alongside and never substituted for the primary.
  - Registered descriptives: vote correctness / unanimity by qdep 0-5.

Usage:  .venv/bin/python -m exp.e1_v2 [--panel panelA|panelB] [--skip-s2]
S2 requires re-alignment of admitted segments: local embedding + CPU NLI, zero
API quota, and per GOTCHAS it must only run after ALL generation is complete.
--skip-s2 exists so the rest of the analysis can run before that pass.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from exp import e1
from exp.recalib import fit_platt_map, fit_temperature_map
from exp.v2_dataset import PREREG_V2, load_v2_items
from wct import aggregate as agg
from wct import cluster, stats
from wct.extract import (_DERIVE_CUE, _NOISE, _SPLIT, _clean, _is_claimlike,
                         extract, vocabulary_of)
from wct.schema import Claim


# ---------------------------------------------------------- S2 extractor
def extract_s2(gen, item):
    """extract.py behaviour PLUS the registered 'step '-prefix exemption.

    A segment is additionally admitted iff (a) the ONLY reason the stock
    filter rejects it is a _NOISE prefix, (b) that prefix is 'step ', and
    (c) the segment carries a _DERIVE_CUE match. Sampled precision of this
    class on v1 was 20/20 (battery T2); a blanket _NOISE relaxation sampled
    at 50% noise, which is why only 'step ' is exempted.
    """
    base = extract(gen, item)
    if not gen.trace.strip():
        return base
    ents, preds = vocabulary_of(item)
    seen = {c.text.lower() for c in base}
    out = list(base)
    for i, raw in enumerate(_SPLIT.split(gen.trace)):
        s = _clean(raw)
        low = s.lower()
        if not s or low in seen or _is_claimlike(s, ents, preds):
            continue
        if not low.startswith("step "):
            continue
        if not _DERIVE_CUE.search(low):
            continue
        # strip the step prefix and re-test: the exemption admits the segment
        # only if the prefix was the sole objection. The original segment must
        # also satisfy the stock length band, so the exemption cannot admit a
        # segment the registered class ('rejected SOLELY by the prefix')
        # excludes for being too long or too short.
        if not (8 <= len(s) <= 220):
            continue
        stripped = re.sub(r"^step\s*\d*\s*[:\.\)]?\s*", "", s, flags=re.I)
        if not _is_claimlike(stripped, ents, preds):
            continue
        if stripped.lower() in seen:      # dedup on the ADMITTED text too
            continue
        seen.add(low)
        seen.add(stripped.lower())
        out.append(Claim(
            uid=f"{item.item_id}::{gen.agent}::s2_{len(out)}",
            item_id=item.item_id, agent=gen.agent, text=stripped,
            polarity=-1 if e1_negated(stripped) else 1,
            source_span=f"seg{i}",
        ))
    return out


def e1_negated(s: str) -> bool:
    from wct.extract import _negated
    return _negated(s)


# ------------------------------------------------------------- S1 filter
_NEG_TOKENS = re.compile(r"\b(not|isn't|is not|does not|doesn't|cannot|can't|no)\b", re.I)


def _positive_surfaces(prop) -> list[str]:
    """Normalised positive surface forms to search for.

    Two forms, both registered: the representation-derived 'subj verb obj'
    token sequence, and (for positive-polarity propositions) the proposition's
    own surface text — the form the path-battery T8 measurement matched on, so
    the registered filter stays anchored to the measurement that motivated it.
    """
    out = []
    parts = re.findall(r'"([^"]*)"', prop.representation)
    if len(parts) >= 3:
        out.append(re.sub(r"[^a-z ]", "", f"{parts[0]} {parts[1]} {parts[2]}".lower()).strip())
    if len(parts) >= 4 and parts[3] == "+":
        out.append(re.sub(r"[^a-z ]", "", prop.text.lower()).strip())
    return [s for s in out if s]


def deny_filter(V: np.ndarray, rows: list[dict], agents: list[str],
                cell: dict, by_id: dict) -> tuple[np.ndarray, dict]:
    """S1: drop deny votes self-contradicted by their own trace.

    A deny at V[k, j] is set to MISSING when agent j's trace for that item
    contains, in some segment, one of the proposition's positive surface forms
    (token-boundary padded) with no negation token in that segment and no
    conditional framing — a segment beginning 'if ' restates a rule rather
    than asserting its consequent, so it never counts as an affirmation.
    Measured on v1 (battery T8): deny precision 0.153 when self-contradicted
    vs 0.798 when not.
    """
    V2 = V.copy()
    audit = {"denies": 0, "dropped": 0}
    seg_cache: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for k, r in enumerate(rows):
        prop = next(p for p in by_id[r["item_id"]].propositions
                    if p.pid == r["pid"])
        surfaces = _positive_surfaces(prop)
        if not surfaces:
            continue
        for j, a in enumerate(agents):
            if V[k, j] != agg.DENY:
                continue
            audit["denies"] += 1
            gen = cell.get(r["item_id"], {}).get(a)
            if gen is None:
                continue
            ck = (r["item_id"], a)
            if ck not in seg_cache:
                seg_cache[ck] = [
                    (s, re.sub(r"[^a-z ]", "", _clean(s).lower()))
                    for s in _SPLIT.split(gen.trace)
                ]
            hit = False
            for seg, norm in seg_cache[ck]:
                if norm.startswith("if "):
                    continue
                padded = f" {norm} "
                if any(f" {pos} " in padded for pos in surfaces) \
                        and not _NEG_TOKENS.search(seg):
                    hit = True
                    break
            if hit:
                V2[k, j] = agg.MISSING
                audit["dropped"] += 1
    return V2, audit


# ---------------------------------------------------------------- fitting
def fit_logistic_ml(X: np.ndarray, y: np.ndarray, l2: float = 1.0) -> np.ndarray:
    """Registered sensitivity row: the same penalised objective as e1.fit_logistic
    but solved to convergence by L-BFGS instead of 400 fixed GD steps."""
    Xb = np.hstack([np.ones((len(X), 1)), X])

    def nll(w):
        p = np.clip(agg.sigmoid(Xb @ w), 1e-12, 1 - 1e-12)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
                     + 0.5 * l2 * (w[1:] @ w[1:]))

    return minimize(nll, np.zeros(Xb.shape[1]), method="L-BFGS-B").x


# ---------------------------------------------------------------- analysis
def analyse(items, calib_ids, cell, iids, label: str, extractor) -> dict:
    by_id = {i.item_id: i for i in items}
    # e1.build_observations resolves `extract` in ITS OWN module namespace
    # (e1.py does `from wct.extract import extract`), so the variant must be
    # bound there — patching wct.extract.extract would silently do nothing.
    stock = e1.extract
    e1.extract = extractor             # registered variant or stock
    try:
        rows, agents, audits = e1.build_observations(items, cell, iids)
    finally:
        e1.extract = stock
    if len(rows) < 50:
        return {"stratum": label, "n_props": len(rows), "error": "too few propositions"}
    y, V, riids, X = e1.to_arrays(rows, agents)
    is_calib = np.array([i in calib_ids for i in riids])
    te = ~is_calib
    ti = [i for i, c in zip(riids, is_calib) if not c]
    if y[te].min() == y[te].max():
        return {"stratum": label, "error": "single-class test split"}

    out: dict = {"stratum": label, "n_props": int(len(y)),
                 "n_items": len(set(riids)), "agents": agents,
                 "prevalence": round(float(y.mean()), 4),
                 "n_test_negatives": int((y[te] == 0).sum())}

    def run_arms(Vm, tag: str) -> dict:
        u = agg.wct_u(Vm)
        lo_em = agg.em_logodds(Vm, agg.wct_em(Vm)[1])
        lo_c = agg.em_logodds(Vm, agg.fit_supervised(Vm[is_calib], y[is_calib]))
        w_gd = e1.fit_logistic(X[is_calib], y[is_calib])
        base_gd = e1.predict_logistic(X, w_gd)
        base_ml = e1.predict_logistic(X, fit_logistic_ml(X[is_calib], y[is_calib]))
        scores = {"WCT-EM": lo_em, "WCT-U": u, "WCT-C": lo_c}
        res: dict = {"arms": {}, "primary": {}}
        for name, s in scores.items():
            f_p, pp = fit_platt_map(s[is_calib], y[is_calib])
            f_t, tp = fit_temperature_map(s[is_calib], y[is_calib])
            p = f_p(s)
            res["arms"][name] = {
                "platt_params": pp, "temperature_ablation_t": tp["t"],
                "test_log_loss": round(agg.log_loss(p[te], y[te]), 5),
                "test_log_loss_temperature": round(agg.log_loss(f_t(s)[te], y[te]), 5),
                "test_auroc": round(agg.auroc(p[te], y[te]), 5),
            }
            for bname, base in (("vs_covariate_gd", base_gd), ("vs_covariate_ml", base_ml)):
                d = stats.paired_item_diff(ti, e1._nll(base[te], y[te]),
                                           e1._nll(p[te], y[te]))
                res["primary"][f"{name}_{bname}"] = {
                    "delta_log_loss": d, "delta": 0.02,
                    "decision": stats.decision(d, 0.02),
                }
        res["covariate_test_log_loss"] = {
            "gd": round(agg.log_loss(base_gd[te], y[te]), 5),
            "ml": round(agg.log_loss(base_ml[te], y[te]), 5)}
        # reference arms: prevalence-only carries no calibration map (it IS a
        # constant); the uncapped M6 ablation gets the identical Platt
        # treatment as every score arm
        n_claims = np.array([r["n_claims"] for r in rows], dtype=float)
        f_unc, _ = fit_platt_map(n_claims[is_calib], y[is_calib], allow_nonpositive=True)
        p_unc = f_unc(n_claims)
        p_prev = np.full(len(y), float(y[is_calib].mean()))
        for nm, p in (("prevalence_only", p_prev), ("uncapped", p_unc)):
            au = agg.auroc(p[te], y[te])
            res["arms"][nm] = {
                "test_log_loss": round(agg.log_loss(p[te], y[te]), 5),
                "test_auroc": None if au is None else round(au, 5)}

        # co-primary, registered adjudication: WCT-EM precision@k MINUS the
        # covariate baseline's at the same k; k and both precisions recomputed
        # inside every item-block resample; three-way decision at delta 0.05
        lo_full = agg.em_logodds(Vm, agg.wct_em(Vm)[1])
        f_p, _ = fit_platt_map(lo_full[is_calib], y[is_calib])
        pe = f_p(lo_full)[te]
        base_te = base_gd[te]
        affirm2 = ((Vm == agg.AFFIRM).sum(1) >= 2)[te]

        def prec_diff(rows_idx):
            kk = int(affirm2[rows_idx].sum())
            if kk < 1:
                return None
            top = np.argsort(-pe[rows_idx])[:kk]
            top_b = np.argsort(-base_te[rows_idx])[:kk]
            return float(y[te][rows_idx][top].mean() - y[te][rows_idx][top_b].mean())

        d_prec = stats.item_bootstrap(ti, prec_diff, n_boot=2000)
        k = int(affirm2.sum())
        order = np.argsort(-pe)[:max(k, 1)]
        order_b = np.argsort(-base_te)[:max(k, 1)]
        res["co_primary_precision_at_k"] = {
            "k": k,
            "WCT-EM": round(float(y[te][order].mean()), 5),
            "covariate_baseline": round(float(y[te][order_b].mean()), 5),
            "difference": d_prec, "delta": 0.05,
            "decision": stats.decision(d_prec, 0.05),
        }
        # registered descriptive: within-item AUROC, v1 construction, 1000 boots
        def within_item_auroc(rows_idx):
            vals = []
            sub_ids = np.array(ti)[rows_idx] if len(rows_idx) else []
            for iid in set(sub_ids):
                m = sub_ids == iid
                a = agg.auroc(pe[rows_idx][m], y[te][rows_idx][m])
                if a is not None:
                    vals.append(a)
            return float(np.mean(vals)) if vals else None

        wia = stats.item_bootstrap(ti, within_item_auroc, n_boot=1000)
        wia["delta"] = 0.55
        wia["decision"] = stats.decision(wia, 0.55)
        res["within_item_auroc"] = wia
        # null
        res["permutation_null"] = stats.within_item_permutation(
            ti, pe, y[te], lambda s_, yy: agg.auroc(s_, yy), n_perm=1000)
        return res

    out["instrument_primary"] = run_arms(V, "primary")
    Vf, s1_audit = deny_filter(V, rows, agents, cell, by_id)
    out["S1_deny_filter"] = {"audit": s1_audit, **run_arms(Vf, "S1")}

    # registered descriptives: depth curves
    qdep = np.array([r["qdep"] for r in rows])
    desc = {}
    for q in sorted(set(qdep.tolist())):
        m = qdep == q
        Vq, yq = V[m], y[m]
        emitted = Vq != agg.MISSING
        correct = ((Vq == agg.AFFIRM) == (yq[:, None] == 1)) & emitted
        n_votes = int(emitted.sum())
        unan = (emitted.sum(1) == len(agents)) & (
            (Vq == Vq[:, :1]) | ~emitted).all(1)
        desc[str(q)] = {
            "n_props": int(m.sum()),
            "vote_correctness": round(float(correct.sum() / max(n_votes, 1)), 4),
            "unanimity_rate": round(float(unan.mean()), 4) if m.sum() else None,
            "unanimous_correct": round(float(
                (correct[unan].sum() / max(emitted[unan].sum(), 1))), 4) if unan.any() else None,
        }
    # pooled qdep>=4 unanimity figure: the quantity registered prediction P2
    # adjudicates against (only depth-5 items populate these bins)
    m4 = qdep >= 4
    if m4.any():
        Vq, yq = V[m4], y[m4]
        emitted = Vq != agg.MISSING
        unan = (emitted.sum(1) == len(agents)) & ((Vq == Vq[:, :1]) | ~emitted).all(1)
        correct = ((Vq == agg.AFFIRM) == (yq[:, None] == 1)) & emitted
        desc["pooled_qdep_ge4"] = {
            "n_props": int(m4.sum()),
            "unanimous_correct": round(float(
                correct[unan].sum() / max(emitted[unan].sum(), 1)), 4) if unan.any() else None,
        }
    out["depth_descriptives"] = desc
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="panelB", choices=["panelA", "panelB"])
    ap.add_argument("--skip-s2", action="store_true",
                    help="run everything except the S2 re-alignment pass")
    args = ap.parse_args()
    items, calib_ids, _ = load_v2_items()
    # v2 panels are mixed-backend, so the loader is run_generate_v2's, not
    # exp.common's (which reads the v1 prereg panels)
    from exp.run_generate_v2 import load_cell_v2
    cell, coverage = load_cell_v2(items, args.panel)
    from exp.common import complete_items
    iids = complete_items(cell, min_agents=2)
    print(f"coverage {coverage}; usable items {len(iids)}")

    out = {"coverage": coverage, "strata": {
        "all_items": analyse(items, calib_ids, cell, iids, "all_items", extract)}}
    if not args.skip_s2:
        out["strata"]["all_items_S2"] = analyse(
            items, calib_ids, cell, iids, "all_items_S2", extract_s2)

    Path("out").mkdir(exist_ok=True)
    outfile = Path(f"out/e1_v2_summary_{args.panel}.json")
    outfile.write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    print("wrote", outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
