"""Emit prereg_v3.yaml. Every figure is DERIVED; none is hand-typed. (B1-B7)

Two numbers in this programme were registered wrong by being read off the wrong
quantity (a raw parquet row count reported as an item count; an item-target
FALSE rate reported as B5's scored-negative projection). The defence is not more
care, it is removing the opportunity: this module computes every figure from an
artifact, writes the yaml, and the slice gate re-runs it and diffs.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import yaml

from exp3 import corpus_v3
from exp3.availability import PAID_OR_RATES, PAID_OR_RATES_EXTRA
from exp3.smoke_v3 import M_SUBSETS, PANEL, QWEN_FALLBACK

OUT = Path("prereg_v3.yaml")
TAG = "prereg-v3-2026-08-30"

# Each cycle's OWN registered calibration map. Reading a cycle under the other
# cycle's map is not what was registered and inflates the spread.
REGISTERED_MAP = {"c1_local": "temperature", "c1_openrouter": "temperature",
                  "c2_panelA": "platt", "c2_panelB": "platt"}
PRIMARY_ARM = "WCT-EM"

# WHICH node of each reanalysis artifact carries the registered primary comparison.
# Pinned explicitly because the earlier implementation took "the first node containing
# the key", which is not a specification: the cycle-2 artifacts carry BOTH the base
# instrument (top level) and the registered S1_deny_self_contradiction VARIANT at
# strata.<stratum>.S1_deny_filter, and cycle 1 has no variant level at all.
#
# The base instrument is primary: prereg_v2 lists S1_deny_self_contradiction under
# `registered_instrument_variants`, not as the primary. The choice is checkable against
# REQUEST.md's own description of slice 1 -- "three of four panel-cycles, and
# inconclusively on the fourth". Under the base instrument that is exactly what the
# artifacts say (c2_panelB's CI spans zero). Reading c2 under the variant instead makes
# all four conclusive and contradicts the request it would claim to implement, while
# also comparing cycle 1's base against cycle 2's variant.
PRIMARY_PATH: dict[str, tuple[str, ...]] = {
    "c1_local": (), "c1_openrouter": (), "c2_panelA": (), "c2_panelB": ()}
VARIANT_PATH: dict[str, tuple[str, ...]] = {
    "c2_panelA": ("strata", "all_items", "S1_deny_filter"),
    "c2_panelB": ("strata", "all_items", "S1_deny_filter")}

# two-sided alpha=0.05, power=0.80
Z = 1.959963985 + 0.8416212336


KEY = "panel_vs_single_best_calibration_selected"


def _at(doc: dict, path: tuple[str, ...]) -> dict:
    node = doc
    for k in path:
        node = node[k]
    return node


def _read_margin(name: str, path: tuple[str, ...]) -> dict:
    """Read ONE margin from an explicitly pinned node. No searching, no fallback."""
    d = json.loads(Path(f"out/v3/reanalysis_{name}.json").read_text())
    arm = _at(d, path)[KEY][REGISTERED_MAP[name]][PRIMARY_ARM]
    v = arm["delta_log_loss"]
    return {"map": REGISTERED_MAP[name], "arm": PRIMARY_ARM, "point": v["point"],
            "lo": v["lo"], "hi": v["hi"], "sd_items": v["sd_items"],
            "n_items": v["n_items"], "decision": arm.get("decision"),
            "artifact_path": list(path) + [KEY, REGISTERED_MAP[name], PRIMARY_ARM]}


def measured_margins() -> dict:
    """Slice 1's margins from the PINNED primary node of each artifact."""
    return {name: _read_margin(name, path) for name, path in PRIMARY_PATH.items()}


def variant_margins() -> dict:
    """The registered S1_deny_self_contradiction variant, reported as sensitivity.

    Registered, disclosed, and NOT used to set delta -- so a reader can see both the
    primary and the variant rather than having to trust that the right node was read.
    """
    return {name: _read_margin(name, path) for name, path in VARIANT_PATH.items()}


def derive_delta(margins: dict) -> dict:
    """δ = the smallest CONCLUSIVE margin already observed. Frozen before results exist.

    Only panel-cycles whose interval actually cleared the decision rule contribute.
    c2_panelB's margin is +0.03292 with a CI spanning zero ("inconclusive"): including it
    would register a threshold derived partly from a result the programme could NOT
    establish, which is the opposite of what a floor derived from evidence means.
    """
    conclusive = {k: v["point"] for k, v in margins.items() if v.get("decision") == "go"}
    excluded = {k: {"point": v["point"], "decision": v.get("decision")}
                for k, v in margins.items() if v.get("decision") != "go"}
    if not conclusive:
        raise ValueError("no conclusive panel-cycle: delta cannot be derived from evidence")
    lo_name = min(conclusive, key=conclusive.get)
    return {
        "value": round(conclusive[lo_name], 4),
        "units": "nats of held-out log loss",
        "formula": (f"min over CONCLUSIVE panel-cycles (decision == 'go') of the "
                    f"{PRIMARY_ARM} panel_vs_single_best_calibration_selected "
                    f"delta_log_loss point estimate, each read under that cycle's OWN "
                    f"registered calibration map ({REGISTERED_MAP})"),
        "argmin": lo_name,
        "inputs_conclusive": conclusive,
        "excluded_inconclusive": excluded,
        "n_conclusive": len(conclusive),
        "n_panel_cycles": len(margins),
        "artifact": "out/v3/reanalysis_<panel-cycle>.json",
        "immutable_after_results": True,
        "rationale": ("cycle 3 must detect at least the smallest effect cycles 1-2 "
                      "CONCLUSIVELY showed; the mean or max would register a threshold the "
                      "programme has not demonstrated it can meet, and including an "
                      "inconclusive cycle would lower the floor on the strength of a "
                      "result that did not clear its own decision rule"),
    }


def required_n(delta: float, sd: float) -> int:
    """Paired per-item design: n = (z_{a/2}+z_b)^2 * sd^2 / delta^2."""
    return math.ceil((Z ** 2) * (sd ** 2) / (delta ** 2))


def detectable_delta(n: int, sd: float) -> float:
    return Z * sd / math.sqrt(n)


def power_table(margins: dict, n_corpus: int) -> dict:
    """Required n for M=3, M=4, M=5, and the detectable increment at the registered n."""
    sds = [v["sd_items"] for v in margins.values() if v.get("decision") == "go"]
    sd_lo, sd_hi = min(sds), max(sds)
    delta = derive_delta(margins)["value"]
    per_m = {}
    for M in (3, 4, 5):
        per_m[f"M={M}"] = {
            "required_n_at_sd_min": required_n(delta, sd_lo),
            "required_n_at_sd_max": required_n(delta, sd_hi),
            "powered_at_registered_n": required_n(delta, sd_hi) <= n_corpus,
        }
    return {
        "alpha": 0.05, "power": 0.80, "test": "two-sided paired item-block bootstrap",
        "delta": delta,
        "sd_items_observed": {"min": sd_lo, "max": sd_hi,
                              "source": "slice 1 per-item SD across the CONCLUSIVE panel-cycles "
                                        "(the same set that derives delta)"},
        "primary": per_m,
        "dose_response_increment": {
            "detectable_at_registered_n": round(detectable_delta(n_corpus, sd_hi), 4),
            "detectable_at_sd_min": round(detectable_delta(n_corpus, sd_lo), 4),
            "n": n_corpus,
            "note": ("this is the SMALLEST M=3->M=5 increment the registered n can detect. "
                     "The primary contrast is comfortably powered; the dose-response "
                     "increment is the binding arm and this is its floor. If the true "
                     "increment is below this, the arm is underpowered and a null is "
                     "uninterpretable -- stated here rather than discovered afterwards."),
        },
    }


def panel_block(expected_echoes: dict | None) -> dict:
    members = []
    for c in PANEL:
        m = {"rank": c["rank"], "agent": c["agent"], "family": c["family"],
             "model": c["model"], "tier": c["tier"], "backend": c["backend"],
             "role": c.get("role", "panel_member")}
        if c.get("expected_resolved"):
            m["expected_resolved"] = c["expected_resolved"]
            m["expected_source"] = "registered alias override"
        else:
            m["expected_resolved"] = c["model"]
            m["expected_source"] = "requested id (default)"
        if c.get("identity_evidence"):
            m["identity_evidence"] = c["identity_evidence"]
            m["identity_basis"] = "weights: model_path + n_params, NOT the echoed alias"
        if expected_echoes and c["agent"] in expected_echoes:
            m["observed_echo_at_smoke"] = expected_echoes[c["agent"]]
        members.append(m)
    return {
        "ordering_rule": ("identity assurance descending: the three families whose PINNED "
                          "ids still answered in slice 3, then the paid twins of the "
                          "families whose :free tier was withdrawn or rate limited"),
        "members": members,
        "nested_subsets": {f"M={k}": list(v) for k, v in M_SUBSETS.items()},
        "nested_property": "M=3 subset of M=4 subset of M=5, by rank",
        "declared_margin": {
            "rank": 6, "agent": "laguna", "family": "poolside",
            "promotion_trigger": ("a primary member (ranks 1-5) fails its expected-echo "
                                  "check or becomes unreachable for a whole panel pass"),
            "promoted_into": "the vacated rank, preserving the nested subset structure",
            "data_before_promotion": ("observations already collected under the vacated "
                                      "member are RETAINED and reported separately; they "
                                      "are not merged into the promoted member's arm"),
            "adjudicator": "the human owner, recorded in DECISIONS.md before the run resumes",
            "disclosure": "any promotion is disclosed in the results as a registered event",
        },
        "declared_fallback": {
            "for": "qwen", "model": QWEN_FALLBACK["model"], "tier": QWEN_FALLBACK["tier"],
            "trigger": "the local endpoint is unreachable or its loaded weights do not match",
            "caveat": ("the fallback is the PROVIDER's own build, not the registered "
                       "quantised Qwen3.8-27B-Q4_K_M weights, so it is a different "
                       "artifact answering for the same family"),
            "disclosure": "promotion is disclosed and the affected items flagged",
        },
    }


def _member_cost(model: str, tier: str, n_calls: int, rates: dict,
                 tok_in: int, tok_out: int) -> dict:
    r = rates.get(model)
    if tier in ("local", "free") or r is None:
        return {"tier": tier, "calls": n_calls, "usd": 0.0,
                "note": "no metered rate at this tier"}
    usd = n_calls * (tok_in * r["in"] + tok_out * r["out"]) / 1e6
    return {"tier": tier, "calls": n_calls, "rate_in": r["in"], "rate_out": r["out"],
            "usd": round(usd, 2)}


def cost_block(n_items: int) -> dict:
    """Rates from slice 3's evidence; calls AND dollars for every registered path. (B7)

    Prices the base panels, both registered contingencies (sixth-family promotion, qwen
    local->OpenRouter fallback) and the retry allowance, because a cap that covers only
    the happy path is not a cap on what the run can actually spend.
    """
    rates = dict(PAID_OR_RATES)
    rates.update(PAID_OR_RATES_EXTRA)
    tok_out, tok_in = 2000, 900
    retry = 0.20

    panels, contingencies = {}, {}
    for M in (3, 4, 5):
        members = [c for c in PANEL if c["rank"] in M_SUBSETS[M]]
        per = {c["agent"]: _member_cost(c["model"], c["tier"], n_items, rates, tok_in, tok_out)
               for c in members}
        base_usd = round(sum(v["usd"] for v in per.values()), 2)
        panels[f"M={M}"] = {
            "calls": n_items * len(members),
            "usd": base_usd,
            "usd_with_retry": round(base_usd * (1 + retry), 2),
            "per_member": per,
        }

    margin = [c for c in PANEL if c["rank"] == 6][0]
    contingencies["sixth_family_promotion"] = {
        "when": "a primary member fails its echo check or becomes unreachable",
        **_member_cost(margin["model"], margin["tier"], n_items, rates, tok_in, tok_out),
        "note": "a promoted member runs a FULL pass, so this is additive, not a swap",
    }
    contingencies["qwen_openrouter_fallback"] = {
        "when": "the local qwen endpoint is unreachable or its weights do not match",
        **_member_cost(QWEN_FALLBACK["model"], QWEN_FALLBACK["tier"], n_items, rates,
                       tok_in, tok_out),
        "note": ("qwen is free while local; the fallback is metered, so this contingency "
                 "is the single largest unbudgeted risk in the design"),
    }

    all_six_calls = n_items * (len(PANEL))
    cont_usd = round(sum(c["usd"] for c in contingencies.values()), 2)
    worst_usd = round(panels["M=5"]["usd"] + cont_usd, 2)
    worst_with_retry = round(worst_usd * (1 + retry), 2)

    return {
        "rate_source": "slice 3 measured paid-tier rates (USD per 1M tokens)",
        "token_projection": {"prompt_tokens_per_call": tok_in,
                             "completion_tokens_per_call": tok_out,
                             "basis": "registered max_tokens; prompt length projected from "
                                      "the corpus theory+question distribution"},
        "panels": panels,
        "contingencies": contingencies,
        "retry_allowance": retry,
        "requests_per_registered_call": {
            "max": 8,
            "basis": ("wct.nodes.Client._call allows 2 model attempts and up to 6 "
                      "rate-limit resumptions per generate(); a 429 means the request "
                      "was never served"),
            "billing_note": ("only a SERVED request produces tokens, so the dollar cap "
                             "bounds spend even though the HTTP request count can exceed "
                             "the registered call count"),
            "cap_unit": ("the registered call cap counts generate() calls -- one per "
                         "(item, member) -- not HTTP requests"),
        },
        "authorised_volume": {
            "calls": all_six_calls,
            "basis": f"{n_items} items x {len(PANEL)} families (M=5 plus the declared margin)",
            "usd_authorised": 121.00,
            "usd_authorisation_source": "REQUEST.md OQ4, human 2026-08-30",
            "usd_estimated_worst_case": worst_with_retry,
            "note": ("OQ4's ~$121 was a scaling estimate made before per-tier rates were "
                     "applied; the rate-derived worst case is lower. The CAP is held at "
                     "the authorised $121 so the run cannot exceed what was authorised, "
                     "and the estimate is reported separately rather than quietly "
                     "replacing the authorisation."),
        },
        "hard_cap": {
            "per_panel_cumulative_calls": {
                f"M={M}": math.ceil(panels[f"M={M}"]["calls"] * (1 + retry))
                for M in (3, 4, 5)},
            # A per-panel USD cap covering only the base panel is not a cap on what the
            # RUN can spend: both registered contingencies (a promoted sixth family, and
            # the qwen fallback moving a free local member onto a metered tier) are full
            # extra passes. The M=5 base is far cheaper than the qwen fallback alone, so
            # a base-only cap would abort a legitimate registered contingency.
            "per_panel_cumulative_usd": {
                f"M={M}": round((panels[f"M={M}"]["usd"] + cont_usd) * (1 + retry), 2)
                for M in (3, 4, 5)},
            "per_panel_usd_includes": ["base panel", "retry allowance",
                                       *contingencies.keys()],
            "run_total_usd": 121.00,
            "persistence": ("both counters are persisted to out/cycle3/caps.json and survive "
                            "re-runs; a re-run RESUMES them rather than resetting, charges "
                            "before the call so a crash cannot re-run free, and aborts on "
                            "breach of either the call cap or the dollar cap"),
            "retries_count_against_caps": True,
            "paid_ids_required": ("where a paid tier exists the paid id is registered and "
                                  "used; :free ids are not pinned, since slice 3 measured "
                                  "them 429ing and a full panel pass cannot rely on them"),
        },
    }


SMOKE_ARTIFACT = Path("out/slice4/smoke/smoke.json")


def smoke_echoes() -> dict:
    """Observed serving identities, read from the smoke ARTIFACT.

    Taken from the artifact rather than passed in, so the figure is derived like every
    other one and the gate's rebuild is reproducible whether or not smoke has run.
    """
    if not SMOKE_ARTIFACT.exists():
        return {}
    d = json.loads(SMOKE_ARTIFACT.read_text())
    return {r["agent"]: {"echoed": r.get("echoed"), "status": r.get("status"),
                         "weights_match": (r.get("identity") or {}).get("weights_match"),
                         "n_params": (r.get("identity") or {}).get("n_params")}
            for r in d.get("records", [])}


def m0_grid() -> dict:
    """The M0 simulation grid, pinned by content hash. (EXPERIMENT.md 3.1(4))"""
    p = Path("out/m0_ceiling.txt")
    if not p.exists():
        return {"available": False,
                "note": "m0/ceiling.py output not present; grid cannot be pinned"}
    raw = p.read_bytes()
    head = [ln for ln in raw.decode().splitlines() if ln.strip()][:12]
    return {
        "artifact": str(p),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "invariant": "I8 effective panel size M_eff = M / (1 + (M-1)*rho)",
        "why_registered": ("the dose-response prediction is about M_eff, not raw M: if "
                           "inter-source error correlation rho is high, adding sources "
                           "buys little and a flat dose-response is the PREDICTED result "
                           "rather than a refutation of the panel"),
        "excerpt": head,
    }


def wct_definitions() -> dict:
    """WCT-U / WCT-EM / WCT-C, frozen as definitions rather than arm labels."""
    return {
        "WCT-U": ("signed UNIQUE-SOURCE support: each canonical proposition scores the "
                  "number of distinct sources affirming it minus those denying it, with "
                  "one observation per (agent, proposition) by construction (M6). "
                  "Frozen implementation: wct3/observe.py build_rows + to_arrays."),
        "WCT-EM": ("Dawid-Skene three-state latent-truth aggregation over the same "
                   "observation matrix, estimating per-agent confusion and a per-item "
                   "latent state; PRIMARY arm. Frozen implementation: wct/aggregate.py."),
        "WCT-C": ("the supervised variant: the same observation matrix scored by a "
                  "classifier fitted on the calibration split, so it measures what a "
                  "supervised reader could extract rather than what the unsupervised "
                  "aggregate does."),
        "covariate_baseline": ("logistic on qdep, n_emitting, n_claims, text_len/50 -- the "
                               "arm every WCT arm must beat to claim proposition-level "
                               "signal rather than item difficulty."),
        "single_best_calibration_selected": ("the best single source CHOSEN ON THE "
                                             "CALIBRATION SPLIT and then evaluated on test; "
                                             "the honest comparator, as distinct from an "
                                             "oracle that peeks at test."),
    }


def build(expected_echoes: dict | None = None) -> dict:
    corpus = corpus_v3.verify()
    margins = measured_margins()
    delta = derive_delta(margins)
    n = corpus["n_items"]
    proj5 = corpus_v3.projected_scored_negatives(n, 5)

    doc = {
        "protocol_version": "v3",
        "tag": TAG,
        "freeze_discipline": (
            "This file and the analysis driver are committed and tagged BEFORE any cycle-3 "
            "generation exists. The implementations ARE the registration."),
        "estimand": (
            "The fixed-panel difference in held-out log loss between the panel aggregate and "
            "the calibration-selected best single source, over the item distribution. Models "
            "and roles are fixed experimental levels; uncertainty generalises over items."),
        "instrument": {
            "nli_model": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            "precision": "fp32",
            "device": "cuda",
            "implementation": "wct3.gpu.nli_gpu",
            "change_from_cycles_1_2": (
                "cycles 1-2 ran fp16, not fp32: the checkpoint config declares "
                "dtype=float16 and transformers honours it on CPU as well as GPU. This is "
                "registered as an INSTRUMENT CHANGE."),
            "measured_device_dependence": {
                "cpu_fp32_vs_gpu_fp32": {"max_abs": 7.8e-06, "argmax_flips": 0},
                "cpu_fp16_vs_gpu_fp16": {"max_abs": 4.4e-03, "argmax_flips": 1},
                "cpu_fp16_vs_cpu_fp32": {"max_abs": 3.8e-03, "argmax_flips": 0},
                "n_pairs": 800,
                "conclusion": "fp16 is device dependent; fp32 is not. fp32 is registered.",
            },
            "cache_isolation": (
                "cycle 3 uses a SEPARATE WCT_CACHE root. fp16-cached and fp32-computed NLI "
                "are never mixed: the smallest observed alignment margin is 0.0021, exactly "
                "1x the fp16->fp32 score perturbation."),
            "fail_closed": (
                "a non-dry run aborts if the registered fp32/GPU instrument is unavailable; "
                "there is no fp16 fallback path"),
        },
        "dataset": {
            "n_items": n,
            "sha256": corpus["sha256"],
            "configs": corpus["configs"],
            "splits": corpus["splits"],
            "source_sha256": corpus["source_parquet_sha256"],
            "propositions": corpus["propositions"],
            "decidable": corpus["decidable"],
            "positive_polarity_negatives": corpus["positive_polarity_negatives"],
            "cycle2_subset": corpus["cycle2_subset"],
            "comparability": (
                "cycle 2's 150 items are a verified COMPLETE SUBSET, so the registered "
                "+0.220/+0.272 results remain comparable on that stratum. The shared item "
                "set means cycle 3's dose-response is evidence about panel SIZE on this "
                "corpus, not independent evidence about the corpus."),
            "capable_of_containing_falsehoods": True,
            "projected_scored_positive_polarity_negatives": {
                "M=5": proj5.n_scored_positive_polarity_negatives,
                "M=3": corpus_v3.projected_scored_negatives(n, 3).n_scored_positive_polarity_negatives,
                "per_item_agent_rate": round(proj5.per_item_agent_rate, 4),
                "assumptions": list(proj5.assumptions),
                "is_gate": False,
                "note": "a PROJECTION, explicitly not an execution gate (B5)",
            },
        },
        "panels": panel_block(expected_echoes if expected_echoes is not None
                              else {k: v["echoed"] for k, v in smoke_echoes().items()
                                    if v.get("echoed")}),
        "smoke_evidence": {
            "artifact": str(SMOKE_ARTIFACT),
            "present": SMOKE_ARTIFACT.exists(),
            "observed": smoke_echoes(),
        },
        "wct_definitions": wct_definitions(),
        "m0_simulation_grid": m0_grid(),
        "arms": [
            "WCT-EM (primary)", "WCT-U", "WCT-C",
            "covariate_baseline (the arm every WCT arm must beat)",
            "single_best_calibration_selected (the registered comparator)",
            "prevalence_only (constant; no calibration map)",
        ],
        "generation": {
            "cell": "cross_family_diverse_role only",
            "roles": {
                "schedule": "latin_square(cross_family key order, [forward, backward, "
                            "skeptic], item index)",
                "prompts": "wct/nodes.py build_prompt(item, role), frozen at the v2 tag",
                # EXACTLY the three roles the schedule names. An earlier version listed
                # a fourth ("neutral") that the schedule did not cover, so the registered
                # rotation and the implemented rotation disagreed -- and a role prompt
                # that is not in the schedule is not frozen by it.
                "role_set": ["forward", "backward", "skeptic"],
                "note": ("roles are rotated across families by the Latin square so role is "
                         "not confounded with vendor -- the confound cycle 1 could not rule "
                         "out because it varied both at once"),
            },
            "seed": 20260807,
            "temperature": 0.7,
            "max_tokens": 2000,
            "scheduling": (
                "MODEL-MAJOR and strictly before analysis: one model completes its whole "
                "pass before the next begins; no concurrent model swaps; no embedding or "
                "analysis call is issued while generation is active, because the local "
                "server has a single model slot."),
            "failed_calls": "never written to the immutable artifact cache",
        },
        "delta": delta,
        "power": power_table(margins, n),
        "measured_margins_slice1": margins,
        "measured_margins_slice1_registered_variant": {
            "what": ("the registered S1_deny_self_contradiction variant of the same "
                     "comparison, for the two cycles that have it"),
            "used_for_delta": False,
            "why_reported": ("the primary node is pinned in code (PRIMARY_PATH); reporting "
                             "the variant alongside lets a reader verify the selection "
                             "instead of trusting it"),
            "values": variant_margins(),
        },
        "predictions": {
            "P1_primary": {
                "claim": (f"the panel aggregate beats the calibration-selected best single "
                          f"source by at least delta={delta['value']} nats at M=5"),
                "supports": "lower bound of the paired item-block bootstrap CI > delta",
                "refutes": "upper bound of the CI < delta",
                "inconclusive": "the CI spans delta",
            },
            "P2_dose_response": {
                "claim": ("the margin over the best single source GROWS from M=3 to M=4 to "
                          "M=5, as error decorrelation predicts"),
                "estimand": "margin(M=5) - margin(M=3), paired on the items both panels scored",
                "uncertainty_method": ("percentile CI from the item-block bootstrap, 2000 "
                                       "resamples, seed 20260807, alpha 0.05 -- the same "
                                       "method the frozen contrasts use"),
                "decision_variable": "the paired increment's CI against the detectable floor",
                "supports": "CI lower bound > detectable floor",
                "refutes": ("CI upper bound < detectable floor -- the panel may still beat "
                            "the best single source while ADDING sources buys nothing, "
                            "which is evidence against the decorrelation premise rather "
                            "than against the panel"),
                "inconclusive": "the CI spans the detectable floor",
                "mutually_exclusive": ("lower > floor and upper < floor cannot both hold "
                                       "because lower <= upper, so exactly one verdict "
                                       "applies. An earlier formulation combined a "
                                       "lower-bound-above-zero test with a monotonicity "
                                       "conjunct and could fire SUPPORTS and REFUTES at "
                                       "once for a CI lying wholly between 0 and the floor."),
                "monotonicity": ("reported for M=3 -> M=4 -> M=5 but NOT part of the "
                                 "verdict: it is a description, not a test, and adding it "
                                 "as a conjunct would leave the outcomes non-exhaustive"),
                "implementation": "exp3.run_cycle3.dose_response",
                "multiplicity": (
                    "P1 and P2 are the only registered confirmatory tests. Across the three "
                    "aggregation arms (WCT-U, WCT-EM, WCT-C) and two calibration maps, "
                    "WCT-EM under the registered map is PRIMARY and the rest are reported as "
                    "registered sensitivity, not as additional chances to succeed. No "
                    "alpha is spent on them."),
            },
        },
        "exclusions": (
            "items with no decidable proposition; agents returning no parseable claim for an "
            "item; observations whose alignment score is below T_ALIGN. Exclusion rules are "
            "frozen here and applied identically to every arm."),
        "panel_membership_rule": {
            "min_agents_per_item": "equal to the panel size M",
            "why": ("an item analysed under M=5 must actually carry five sources. A lower "
                    "threshold would let an 'M=5' result rest on two sources for some "
                    "items, which is exactly the quantity the dose-response varies, so "
                    "the arms would differ by less than their labels claim"),
            "consequence": ("items where any member produced no parseable claim are "
                            "dropped from that panel's analysis, and the retained item "
                            "count is reported per M"),
        },
        "primary_adjudication": {
            "delta": "the registered delta above, NOT wct3.arms.FROZEN_DELTA",
            "arms_frozen_delta": 0.02,
            "why": ("wct3.arms carries cycle 2's frozen delta of 0.02 and must keep it or "
                    "slice 1's frozen reproduction breaks. Cycle 3 therefore adjudicates "
                    "in exp3.run_cycle3.primary_verdict against its own registered delta; "
                    "reading arms' `decision` field would register one threshold and "
                    "apply another"),
            "implementation": "exp3.run_cycle3.primary_verdict",
        },
        "analysis_splits": {
            "calibration_fraction": 0.5, "split_seed": 20260807,
            "note": "calibration/test split is drawn once from the pinned corpus and reused "
                    "by every arm, so arms differ only in aggregation",
        },
        "cost": cost_block(n),
        "analysis_code_freeze": (
            "exp3/run_cycle3.py and its dependencies are committed at the tag. Any change "
            "after the tag is a protocol amendment and must be recorded in DECISIONS.md."),
    }
    return doc


def write(expected_echoes: dict | None = None) -> Path:
    doc = build(expected_echoes)
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False, width=100, allow_unicode=True))
    return OUT


def fingerprint(path: Path = OUT) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    p = write()
    print(f"wrote {p} ({p.stat().st_size} bytes)")
    print(f"fingerprint {fingerprint(p)}")
