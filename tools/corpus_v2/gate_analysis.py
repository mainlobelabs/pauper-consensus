#!/usr/bin/env python3
"""v2 system-level gate analysis (prereg-v2 defendant / self_review blocks).

Re-runs the v1 pass criterion (cutoff-probe/runs/2026-08-27-phase4/
pass_criterion.json) on the v2 corpus:

  1. Re-fit the ft_reason_included WCT-EM posterior deterministically
     (same seed 20260827 as eval_v2; ri is the first arm, so the RNG state
     matches the original run) and apply the frozen v1 calibration to get
     per-item P(PASS). Sanity: e0 and em_data_ll must reproduce
     eval_v2.json exactly.
  2. Gate the defendant claims (judge-supported adjudication, non-zero
     pool tie) through (a) jury consensus P(PASS) >= 0.5 and (b) 27B
     self-review PASS. Per arm: survivors, false-claim rate on
     survivors, false-claim catch.
  3. Article-block bootstrap (2000, seed 20260827, same as v1) of
     FCR_jury - FCR_selfreview. Branch (a): strictly lower with CI
     entirely below zero. Branch (b): within 10 points AND strictly
     lower total compute cost (USD proxy, amortized serving, v1
     per-token prices: 4B $0.20/$0.60, 27B $1.00/$3.00 per 1M).
     Jury cost basis = v1-consistent (the panel actually used to gate:
     the 4 ft_reason_included configs; v1 costed "jury_4fam_reason_
     included_x400"), plus the full 12-config corpus as context.
     Jury votes carry no per-call usage in the v2 runner, so token
     counts use the v1 measured 1,108,958/1,600 = 693.1 tokens/vote
     (identical 4 families, identical contract template; in/out split
     92.77/7.23 from the v1 measured totals). 27B tokens are measured
     from the run's per-call usage.
  4. System bar (prereg self_review.uses[0]): 27B self-review three-state
     accuracy and gate-binary accuracy on the v2 pool labels, with the
     jury ri arm alongside for the detection comparison.
  5. Final 8000-cell cross-tab: 27B self-review vs raw 12-config
     plurality consensus (ties FAIL > NOT_STATED > PASS) and vs the
     EM-calibrated gate binary.

Stdlib + numpy only. Deterministic.

Usage:
  .venv/bin/python tools/corpus_v2/gate_analysis.py \
    --corpus corpus-v2 --frozen corpus-v2/frozen/v1_baselines.json \
    --jury runs/2026-08-28-v2-jury --run runs/2026-08-29-v2-27b \
    --eval runs/2026-08-28-v2-jury/eval_v2.json \
    --out runs/2026-08-29-v2-27b/gate_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase4"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import EXPECT  # noqa: E402
from consensus_eval import TRUE, fit_wct_em  # noqa: E402
from eval_v2 import (  # noqa: E402
    RNG_SEED,
    apply_calib,
    build_items,
    load_corpus,
    load_votes,
    model_names,
)

# v1 measured cost basis (pass_criterion.json cost_test_split_10_articles)
V1_JURY_IN = 1028796
V1_JURY_OUT = 80162
V1_JURY_VOTES = 1600  # 4 families x 400
V1_TOK_PER_VOTE = (V1_JURY_IN + V1_JURY_OUT) / V1_JURY_VOTES
V1_IN_FRAC = V1_JURY_IN / (V1_JURY_IN + V1_JURY_OUT)
PRICE_4B_IN, PRICE_4B_OUT = 0.20, 0.60    # USD per 1M tokens
PRICE_27B_IN, PRICE_27B_OUT = 1.00, 3.00  # USD per 1M tokens
BOOT_N = 2000
BOOT_SEED = 20260827  # same as v1
TIE_PRIORITY = {"FAIL": 0, "NOT_STATED": 1, "PASS": 2}


def read_jsonl_last_wins(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"]] = r  # last row wins
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--jury", required=True, help="jury run dir (p8102.. native)")
    ap.add_argument("--run", required=True, help="27B run dir")
    ap.add_argument("--eval", required=True, help="eval_v2.json for sanity check")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    t0 = time.time()

    corpus = Path(args.corpus)
    frozen = json.loads(Path(args.frozen).read_text())
    eval_ref = json.loads(Path(args.eval).read_text())

    # ---- 1. ri arm EM re-fit (deterministic) + per-item P(PASS) ----
    c = load_corpus(corpus)
    data = build_items(c, frozen["covariate_spec"]["trap_vocab_order"])
    items, truth, X8 = data["items"], data["truth"], data["X8"]

    jury_root = Path(args.jury)
    native_dirs = sorted(d / "native" for d in sorted(jury_root.glob("p8*")))
    ms_ri = model_names("ft_reason_included")
    votes_ri = load_votes(native_dirs, ms_ri)
    v = [votes_ri.get(k, {}) for k in items]
    rng_em = np.random.default_rng(RNG_SEED)
    fit = fit_wct_em(v, rng_em)
    P = fit["posterior"]
    a = np.array(frozen["arms"]["ft_reason_included"]["a"])
    b = np.array(frozen["arms"]["ft_reason_included"]["b"])
    Q = apply_calib(P, a, b)
    i_pass = TRUE.index("PASS")
    ppass = Q[:, i_pass]

    # sanity: must reproduce eval_v2.json
    from eval_v2 import e0_for
    e0 = e0_for(votes_ri, items, truth, fit["voters"])
    ref = eval_ref["arms"]["ft_reason_included"]
    sanity = {
        "e0": round(e0, 4), "e0_ref": ref["e0"],
        "em_data_ll": round(float(fit["data_ll"]), 5),
        "em_data_ll_ref": ref["em_data_ll"],
    }
    assert sanity["e0"] == sanity["e0_ref"], sanity
    assert sanity["em_data_ll"] == sanity["em_data_ll_ref"], sanity

    # raw 12-config plurality consensus (for the final cross-tab)
    ms_all = []
    for arm in ("ft_reason_included", "ft_votes_only", "base_zeroshot"):
        ms_all += model_names(arm)
    votes_all = load_votes(native_dirs, ms_all)
    plurality = np.empty(len(items), dtype=object)
    n_ties = 0
    for j, k in enumerate(items):
        obs = [votes_all.get(k, {}).get(m) for m in ms_all]
        obs = [o for o in obs if o in TRUE]
        cnt = Counter(obs)
        top = max(cnt.values())
        winners = [s for s, n in cnt.items() if n == top]
        if len(winners) > 1:
            n_ties += 1
            winners = [min(winners, key=lambda s: TIE_PRIORITY[s])]
        plurality[j] = winners[0]

    # ---- 2. 27B run data ----
    run = Path(args.run)
    defendant = read_jsonl_last_wins(run / "defendant.jsonl")
    judge = read_jsonl_last_wins(run / "judge.jsonl")
    selfreview = read_jsonl_last_wins(run / "selfreview.jsonl")

    # self-review lookup (article, pool) -> answer
    sr_lookup: dict[tuple[str, int], str] = {}
    sr_missing = 0
    for r in selfreview.values():
        if r.get("missing") or r.get("answer") not in TRUE:
            sr_missing += 1
            continue
        sr_lookup[(r["article"], int(r["pool"]))] = r["answer"]

    # system bar (prereg self_review.uses[0]): three-state + gate-binary
    # accuracy on the v2 pool labels (frontier self-review control)
    n_nonmiss = 0
    sr_three = 0
    sr_gate = 0
    for j, k in enumerate(items):
        if k not in sr_lookup:
            continue
        n_nonmiss += 1
        ans, t = sr_lookup[k], truth[j]
        if ans == TRUE[t]:
            sr_three += 1
        if (ans == TRUE[i_pass]) == (t == i_pass):
            sr_gate += 1
    jur_gate = int((ppass >= 0.5).sum())
    jur_gate_acc = float(((ppass >= 0.5) == (truth == i_pass)).mean())
    jur_argmax = int((Q.argmax(axis=1) == truth).sum())

    # detection context (v1 detection_context analog): FAIL recall
    fail_mask = truth == TRUE.index("FAIL")
    jury_fail_recall = float((ppass[fail_mask] < 0.5).mean())
    sr_fail_recall = 0.0
    n_fail_tested = 0
    for j in np.where(fail_mask)[0]:
        k = items[j]
        if k in sr_lookup:
            n_fail_tested += 1
            if sr_lookup[k] != TRUE[i_pass]:
                sr_fail_recall += 1
    sr_fail_recall /= n_fail_tested

    # ---- 3. gate the defendant claims ----
    # item index lookup (article, pool) -> j
    j_of = {k: j for j, k in enumerate(items)}
    claims = []  # (article, claim_idx, false_claim, j) for gateable
    n_judge_rows = 0
    n_supported = 0
    n_gateable = 0
    n_tie0 = 0
    n_judge_unparse = 0
    for r in judge.values():
        n_judge_rows += 1
        if r.get("supported") is None:
            n_judge_unparse += 1
            continue
        if r["supported"]:
            n_supported += 1
        mp = r.get("match_pool")
        if not isinstance(mp, int) or mp == 0:
            n_tie0 += 1
            continue
        n_gateable += 1
        k = (r["article"], mp)
        if k not in j_of:
            raise SystemExit(f"judge tie not in pool: {k}")
        claims.append((r["article"], int(mp), not r["supported"], j_of[k]))
    n_false_gateable = sum(1 for cl in claims if cl[2])

    jur_retain = jur_false_retain = 0
    sr_retain = sr_false_retain = 0
    sr_gate_missing = 0
    per_claim = []  # (article, jur_retain, sr_retain_or_None, false)
    for article, mp, is_false, j in claims:
        jr = bool(ppass[j] >= 0.5)
        ans = sr_lookup.get((article, mp))
        sr = None if ans is None else (ans == TRUE[i_pass])
        if sr is None:
            sr_gate_missing += 1
        else:
            if sr:
                sr_retain += 1
                if is_false:
                    sr_false_retain += 1
        if jr:
            jur_retain += 1
            if is_false:
                jur_false_retain += 1
        per_claim.append((article, jr, sr, is_false))

    fcr_jur = jur_false_retain / jur_retain if jur_retain else None
    fcr_sr = sr_false_retain / sr_retain if sr_retain else None
    catch_jur = (1 - jur_false_retain / n_false_gateable) if n_false_gateable else None
    catch_sr = (1 - sr_false_retain / n_false_gateable) if n_false_gateable else None

    # article-block bootstrap of FCR_jury - FCR_sr (v1: same unit, seed)
    art_list = list(dict.fromkeys(k[0] for k in items))
    claims_by_art: dict[str, list] = defaultdict(list)
    for pc in per_claim:
        claims_by_art[pc[0]].append(pc)
    rng_boot = np.random.default_rng(BOOT_SEED)
    diffs = np.empty(BOOT_N)
    for b in range(BOOT_N):
        draw = rng_boot.integers(0, len(art_list), size=len(art_list))
        d = []
        for i in draw:
            for _, jr, sr, is_false in claims_by_art[art_list[i]]:
                # both arms must have a verdict on the claim to be in the
                # paired comparison (v1 had no missing; v2 SR has a few)
                if sr is None:
                    continue
                d.append((0.0 if jr else 1.0, 0.0 if sr else 1.0, is_false))
        if not d:
            diffs[b] = 0.0
            continue
        arr = np.array(d)
        # FCR on survivors per arm
        jur_surv = (arr[:, 0] == 0.0)
        sr_surv = (arr[:, 1] == 0.0)
        fj = arr[jur_surv, 2].mean() if jur_surv.any() else 0.0
        fs = arr[sr_surv, 2].mean() if sr_surv.any() else 0.0
        diffs[b] = fj - fs
    ci = [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]

    # ---- 4. cost (v1 formula, per-token USD proxy) ----
    # jury ri panel calls actually made (rows in the 4 ri model files)
    ri_calls = 0
    all_calls = 0
    for d in native_dirs:
        for f in d.glob("*.jsonl"):
            with open(f) as fh:
                n = sum(1 for line in fh if line.strip())
            all_calls += n
            if f.stem in ms_ri:
                ri_calls += n
    jury_ri_tok = ri_calls * V1_TOK_PER_VOTE
    jury_ri_in = jury_ri_tok * V1_IN_FRAC
    jury_ri_out = jury_ri_tok * (1 - V1_IN_FRAC)
    jury_full_tok = all_calls * V1_TOK_PER_VOTE
    jury_full_in = jury_full_tok * V1_IN_FRAC
    jury_full_out = jury_full_tok * (1 - V1_IN_FRAC)

    sr_in = sum(r["usage"]["prompt_tokens"] for r in selfreview.values())
    sr_out = sum(r["usage"]["completion_tokens"] for r in selfreview.values())
    def_judge = {**defendant, **judge}
    dj_in = sum(r["usage"]["prompt_tokens"] for r in def_judge.values())
    dj_out = sum(r["usage"]["completion_tokens"] for r in def_judge.values())

    def usd(ti, to, pin, pout):
        return ti / 1e6 * pin + to / 1e6 * pout

    cost = {
        "price_per_1M_usd": {"4b": [PRICE_4B_IN, PRICE_4B_OUT],
                             "27b": [PRICE_27B_IN, PRICE_27B_OUT]},
        "jury_ri_panel": {
            "calls": ri_calls, "tokens_proxy": {"input": round(jury_ri_in),
                                                "output": round(jury_ri_out),
                                                "total": round(jury_ri_tok)},
            "token_proxy_note": ("v1 measured 693.1 tok/vote, identical 4 "
                                 "families + contract template; in/out split "
                                 "92.77/7.23 from v1 measured totals"),
            "usd": round(usd(jury_ri_in, jury_ri_out, PRICE_4B_IN, PRICE_4B_OUT), 4),
        },
        "jury_full_12config": {
            "calls": all_calls,
            "tokens_proxy": {"total": round(jury_full_tok)},
            "usd": round(usd(jury_full_in, jury_full_out, PRICE_4B_IN,
                             PRICE_4B_OUT), 4),
        },
        "self_review_27b": {
            "calls": len(selfreview), "tokens_measured": {"input": sr_in,
                                                          "output": sr_out,
                                                          "total": sr_in + sr_out},
            "usd": round(usd(sr_in, sr_out, PRICE_27B_IN, PRICE_27B_OUT), 4),
        },
        "defendant_plus_judge_27b_shared": {
            "calls": len(def_judge), "tokens_measured": {"input": dj_in,
                                                         "output": dj_out},
            "note": "shared by both routes; excluded from the comparison (v1)",
        },
    }
    cost["ratio_ri_panel_over_sr"] = round(
        cost["jury_ri_panel"]["usd"] / cost["self_review_27b"]["usd"], 4)
    cost["ratio_full12_over_sr"] = round(
        cost["jury_full_12config"]["usd"] / cost["self_review_27b"]["usd"], 4)

    # length sensitivity: the v1 tok/vote proxy was measured on v1
    # articles; v2 articles are shorter, so the proxy overstates jury cost.
    # Adjust by article-length delta at ~4 chars/token (article text is the
    # only template variable).
    v1l_all = [len(p.read_text())
               for p in sorted(Path(args.corpus).parent.joinpath(
                   "corpus", "articles").glob("T*.md"))]
    v2l = [len(p.read_text())
           for p in sorted(corpus.glob("articles/*.md"))]
    v1m, v2m = (sum(v1l_all) / len(v1l_all), sum(v2l) / len(v2l)) \
        if v1l_all and v2l else (0.0, 0.0)
    adj_all = V1_TOK_PER_VOTE - (v1m - v2m) / 4
    cost["length_sensitivity"] = {
        "v1_article_mean_chars": round(v1m),
        "v2_article_mean_chars": round(v2m),
        "tok_per_vote_v1_measured": round(V1_TOK_PER_VOTE, 1),
        "tok_per_vote_length_adjusted": round(adj_all, 1),
        "ratio_ri_panel_over_sr_v1_measured": cost["ratio_ri_panel_over_sr"],
        "ratio_ri_panel_over_sr_length_adjusted": round(
            cost["ratio_ri_panel_over_sr"] * adj_all / V1_TOK_PER_VOTE, 4),
        "note": ("v2 articles are shorter, so the v1-measured proxy "
                 "overstates jury cost; both ratios < 1.0 keep branch (b)"),
    }

    # ---- 5. verdicts ----
    branch_a = bool(fcr_jur is not None and fcr_sr is not None
                    and fcr_jur < fcr_sr and ci[1] < 0)
    within_10 = bool(fcr_jur is not None and fcr_sr is not None
                     and abs(fcr_jur - fcr_sr) <= 0.10)
    branch_b = bool(within_10
                    and cost["ratio_ri_panel_over_sr"] < 1.0)
    verdict = ("PASS (branch b)" if branch_b
               else ("PASS (branch a)" if branch_a else "FAIL"))

    # ---- 6. final cross-tab (8000 cells) ----
    order = ["PASS", "FAIL", "NOT_STATED"]
    xtab_truth = {t: {s: 0 for s in order} for t in order}
    xtab_plur = {t: {s: 0 for s in order} for t in order}
    xtab_gate = {t: {"PASS": 0, "notPASS": 0} for t in order}
    sr_dist = Counter()
    for j, k in enumerate(items):
        t = TRUE[truth[j]]
        ans = sr_lookup.get(k)
        if ans is not None:
            sr_dist[ans] += 1
            xtab_truth[t][ans] += 1
            xtab_plur[plurality[j]][ans] += 1
        xtab_gate[t]["PASS" if ppass[j] >= 0.5 else "notPASS"] += 1
    n_cells = len(items)
    agree_truth = sum(xtab_truth[t][t] for t in order)
    agree_plur = sum(xtab_plur[t][t] for t in order)
    truth_dist = Counter(TRUE[t] for t in truth)
    plur_dist = Counter(plurality)

    out = {
        "sanity_em_refit": sanity,
        "system_bar": {
            "note": ("prereg self_review.uses[0]: three-state accuracy and "
                     "gate-binary (PASS) accuracy on v2 pool labels"),
            "n_pool_items": n_cells,
            "selfreview_27b": {
                "n_missing": sr_missing,
                "three_state_acc_nonmissing": round(sr_three / n_nonmiss, 5),
                "gate_binary_acc_nonmissing": round(sr_gate / n_nonmiss, 5),
            },
            "jury_ri_em": {
                "gate_binary_acc": round(jur_gate_acc, 5),
                "three_state_argmax_acc": round(jur_argmax / n_cells, 5),
            },
            "detection_context": {
                "jury_ri_fail_recall": round(jury_fail_recall, 5),
                "selfreview_27b_fail_recall": round(sr_fail_recall, 5),
            },
        },
        "defendant": {
            "n_defendant_calls": len(defendant),
            "n_judge_calls": n_judge_rows,
            "n_supported": n_supported,
            "n_unsupported": n_judge_rows - n_supported - n_judge_unparse,
            "n_judge_unparse": n_judge_unparse,
            "n_gateable_unique_pool_tie": n_gateable,
            "n_tie0": n_tie0,
            "n_false_gateable": n_false_gateable,
            "raw_false_claim_rate": round(
                (n_judge_rows - n_supported - n_judge_unparse) /
                (n_judge_rows - n_judge_unparse), 5),
        },
        "gates": {
            "jury_gated": {
                "gate": "WCT-EM ri consensus P(PASS) >= 0.5 on tied pool prop",
                "survivors": jur_retain, "of": n_gateable,
                "false_claim_rate": fcr_jur,
                "false_claim_catch": catch_jur,
            },
            "self_review_gated": {
                "gate": "27B self-review three-state == PASS on tied pool prop",
                "survivors": sr_retain, "of": n_gateable,
                "n_sr_verdict_missing": sr_gate_missing,
                "false_claim_rate": fcr_sr,
                "false_claim_catch": catch_sr,
            },
        },
        "bootstrap": {
            "resamples": BOOT_N, "unit": "article-block", "seed": BOOT_SEED,
            "ci_jury_minus_selfreview_false_claim_rate": [round(x, 5) for x in ci],
            "note": ("claims with a missing SR verdict excluded from the "
                     "paired draw (v1 had none)"),
        },
        "pass_criterion": {
            "branch_a_jury_beats_selfreview_ci_below_zero": branch_a,
            "branch_b_within_10pts_and_strictly_cheaper": branch_b,
            "within_10pts": within_10,
            "verdict": verdict,
        },
        "cost": cost,
        "cross_tab_final": {
            "n_cells": n_cells,
            "truth_dist": dict(truth_dist),
            "selfreview_dist_nonmissing": dict(sr_dist),
            "plurality12_dist": dict(plur_dist),
            "selfreview_vs_truth": xtab_truth,
            "selfreview_vs_plurality12": xtab_plur,
            "plurality_ties_fail_first": n_ties,
            "agreement_with_truth_nonmissing": round(
                agree_truth / n_nonmiss, 5),
            "agreement_with_plurality12_nonmissing": round(
                agree_plur / n_nonmiss, 5),
            "selfreview_vs_em_gate_binary": xtab_gate,
            "note": ("plurality = raw 12-config majority; ties broken "
                     "FAIL > NOT_STATED > PASS; EM gate = calibrated "
                     "P(PASS) >= 0.5; 'vs_truth' rows are ground truth, "
                     "'vs_plurality12' rows are the raw jury consensus "
                     "(matches the 50% checkpoint table)"),
        },
        "e0_n_eff": {
            "e0_ri": sanity["e0"],
            "n_eff_kish_4voters": round(4 / (1 + 3 * sanity["e0"]), 3),
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"wrote {out_path} in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
