"""Phase 2 registration freeze (task 10).

Computes the article-level 10/10/10 split (fixed seed), content-hashes every
frozen corpus file, fills corpus/manifest.json (split_role + sha256, version
bump), and writes prereg.yaml with the full registration (corpus hashes,
split, jury, verbatim prompts, arms, metrics, pass criterion, predictions,
training scheme, spend caps). Idempotent: re-running rewrites the same
deterministic artifacts.
"""

import hashlib
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus"
PROMPTS = REPO / "prompts"
SPLIT_SEED = 42
TAG = "prereg-waveconsensus-v1"
FROZEN = "2026-08-26"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def article_ids() -> list[str]:
    return sorted(p.stem for p in (CORPUS / "articles").glob("T*.md"))


def extract_template(md_path: Path) -> str:
    """Return the fenced user-message template block from a prompt file."""
    text = md_path.read_text()
    blocks = [b for b in text.split("```")[1::2]]
    for b in blocks:
        if "<article>" in b:
            return b.strip() + "\n"
    raise ValueError(f"no <article> template in {md_path}")


def main() -> None:
    arts = article_ids()
    assert len(arts) == 30, f"expected 30 articles, got {len(arts)}"

    rng = random.Random(SPLIT_SEED)
    shuffled = arts[:]
    rng.shuffle(shuffled)
    roles = (
        {a: "train" for a in shuffled[:10]}
        | {a: "calibration" for a in shuffled[10:20]}
        | {a: "test" for a in shuffled[20:]}
    )
    train = [a for a in shuffled[:10]]
    calib = [a for a in shuffled[10:20]]
    test = [a for a in shuffled[20:]]

    # Census: non-ENTAIL propositions on the test split.
    non_entail_test = 0
    for a in test:
        labels = json.loads((CORPUS / "labels" / f"{a}.json").read_text())
        non_entail_test += sum(1 for rec in labels if rec["label"] != "ENTAIL")
    census_pass = non_entail_test >= 60

    # Hash every frozen file.
    files = [
        CORPUS / "topics.md",
        CORPUS / "rubric.md",
        CORPUS / "pool" / "metadata.json",
        PROMPTS / "README.md",
        PROMPTS / "solver_baseline.md",
        PROMPTS / "jury_contract.md",
        PROMPTS / "covariates.md",
    ]
    for a in arts:
        files += [
            CORPUS / "articles" / f"{a}.md",
            CORPUS / "questions" / f"{a}.md",
            CORPUS / "pool" / f"{a}.md",
            CORPUS / "pool" / "question_form" / f"{a}.md",
            CORPUS / "labels" / f"{a}.json",
        ]
    hashes = {f.relative_to(REPO).as_posix(): sha256(f) for f in files}

    # Fill the manifest: split_role + per-article sha256, version bump.
    manifest_path = CORPUS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for art in manifest["articles"]:
        art["split_role"] = roles[art["id"]]
        art["sha256"] = hashes[f"corpus/articles/{art['id']}.md"]
    manifest["version"] = 2
    manifest["notes"] = manifest["notes"].replace(
        "label_counts filled in P1-6 (corpus/labels); split_role and sha256 filled at Phase 2.",
        "label_counts filled in P1-6 (corpus/labels); split_role and sha256"
        f" filled at Phase 2 (frozen {FROZEN}, tag {TAG}).",
    )
    manifest["frozen"] = {
        "date": FROZEN,
        "tag": TAG,
        "split_seed": SPLIT_SEED,
        "manifest_sha256_placeholder": True,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    manifest_hash = sha256(manifest_path)

    jury_contract = extract_template(PROMPTS / "jury_contract.md")
    solver_baseline = extract_template(PROMPTS / "solver_baseline.md")

    def yq(s: str) -> str:
        # Block scalar content must indent deeper than the 2-space key.
        return "    " + s.replace("\n", "\n    ")

    lines: list[str] = []
    ap = lines.append
    ap(f"# wave-consensus pre-registration (frozen {FROZEN}, tag {TAG})")
    ap("# Written before any fine-tuning or generation it covers. The")
    ap("# implementations ARE the registration: the committed corpus files,")
    ap("# prompts, and this artifact at git tag prereg-waveconsensus-v1.")
    ap(f"tag: {TAG}")
    ap(f"frozen: {FROZEN}")
    ap("authors:")
    ap("  - Andryo Marzuki (design, decisions, approvals)")
    ap("  - Jeremiah Mannings (co-designer)")
    ap("  - Frank (implementation, opencode agent)")
    ap("repo: github.com/marzukia/wave-consensus (private)")
    ap("spec: SPEC.md v0.14 (this file registers every quantity it defers)")
    ap("")
    ap("corpus:")
    ap("  articles: 30")
    ap("  propositions: 1200 (40 per article)")
    ap("  seed_questions: 600 (20 per article, solver baseline task only)")
    ap("  label_totals: {ENTAIL: 599, CONTRADICT: 310, UNSPECIFIED: 291}")
    ap("  labeler: single (Andryo Marzuki, disclosed)")
    ap("  recheck: 10 percent stratified blind recheck; 119/120 raw (99.2%),")
    ap("    120/120 after one original-label fix (T23-035). Self-consistency,")
    ap("    not inter-annotator agreement.")
    ap("  files:  # sha256 of every frozen corpus file")
    for path in sorted(hashes):
        ap(f"    {path}: {hashes[path]}")
    ap(f"  manifest_sha256: {manifest_hash}")
    ap("")
    ap("split:")
    ap("  algorithm: >-")
    ap("    ids = the 30 article ids sorted lexicographically;")
    ap("    python random.Random(42).shuffle(ids); the first 10 are train,")
    ap("    the next 10 calibration, the last 10 test. Article-level; no")
    ap("    proposition of a seen article appears in an unseen role.")
    ap(f"  seed: {SPLIT_SEED}")
    ap(f"  train: {json.dumps(train)}")
    ap(f"  calibration: {json.dumps(calib)}")
    ap(f"  test: {json.dumps(test)}")
    ap("  census:")
    ap(f"    non_entail_test: {non_entail_test}")
    ap("    threshold: 60")
    ap(f"    result: {'PASS' if census_pass else 'FAIL'}")
    ap("")
    ap("solver:")
    ap("  model: qwen3.8-27b (community merge, Gated DeltaNet hybrid)")
    ap("  host: marzuki-hydrogen, vLLM, port 8000")
    ap("  fine_tuned: false")
    ap("  temperature: 0")
    ap("  thinking: off (chat_template_kwargs enable_thinking false)")
    ap("")
    ap("jury:")
    ap("  rule: >-")
    ap("    Five base models from five distinct organizations, each below 4B,")
    ap("    documented training cutoff before 2026-08-14; where documentation")
    ap("    is absent, the frozen probe set (cutoff-probe/probes.md) is the")
    ap("    eligibility gate (blind to the 2026-08-14..2026-08-25 window).")
    ap("  members:")
    ap("    - model: meta-llama/Llama-3.2-1B-Instruct")
    ap("      org: Meta")
    ap("      params: 1.23B")
    ap("      cutoff: 2023-12 (model card)")
    ap("    - model: google/gemma-3-1b-it")
    ap("      org: Google")
    ap("      params: 1.0B")
    ap("      cutoff: 2024-08 (model card)")
    ap("    - model: microsoft/Phi-4-mini-instruct")
    ap("      org: Microsoft")
    ap("      params: 3.8B")
    ap("      cutoff: 2024-06 (model card)")
    ap("    - model: allenai/OLMoE-1B-7B-0125-Instruct")
    ap("      org: Allen AI")
    ap("      params: 1.3B active / 6.9B total (MoE)")
    ap("      cutoff: undocumented; probed, window-blind, eligible")
    ap("    - model: Qwen/Qwen3.5-4B")
    ap("      org: Alibaba")
    ap("      params: 4.66B (VLM, Gated DeltaNet hybrid)")
    ap("      cutoff: undocumented; probed, window-blind, eligible")
    ap("  same_family_arm: >-")
    ap("    Qwen3.5-4B shares the solver's family (Qwen3.8-27B). Registered")
    ap("    as a contrast arm for the family-blind-spot mechanism, not a")
    ap("    confound. The prereg report must show 5-juror consensus and")
    ap("    4-external leave-one-out side by side, plus arm-level per-class")
    ap("    analysis; the headline never depends on the arm.")
    ap("  fallbacks_4b:")
    ap("    - meta-llama/Llama-3.2-3B-Instruct (cutoff 2023-12)")
    ap("    - google/gemma-3-4b-it (cutoff 2024-08)")
    ap("  fallback_rule: >-")
    ap("    Primary below 75 percent on the calibration set is replaced by its")
    ap("    same-family 4B-class sibling; families without a 4B sibling (Phi,")
    ap("    OLMoE, Qwen) take a registered cross-family fill from the 4B-class")
    ap("    candidates. Declared here, applied family-by-family, labelled in")
    ap("    the report.")
    ap("")
    ap("prompts:  # verbatim frozen user-message templates (no system message)")
    ap("  jury_contract: |")
    ap(yq(jury_contract.rstrip("\n")))
    ap("  solver_baseline: |")
    ap(yq(solver_baseline.rstrip("\n")))
    ap("  parameters: {temperature: 0, max_tokens: 512, thinking: off}")
    ap("  question_form_rule: >-")
    ap('    "Is it true that {proposition text, verbatim, without trailing')
    ap('    period}?" applied to all 1200 pool propositions; negations')
    ap("    preserved as-is. Renderings in corpus/pool/question_form/,")
    ap("    content-hashed above.")
    ap("")
    ap("contract:")
    ap("  answers: [PASS, FAIL, NOT_STATED]")
    ap("  mapping: {PASS: ENTAIL, FAIL: CONTRADICT, NOT_STATED: UNSPECIFIED}")
    ap("  gate_binary: PASS vs not-PASS (ENTAIL vs non-ENTAIL)")
    ap("  calls: one call per claim (40 per article per proposer)")
    ap("  parse: strict JSON; failures are missing observations, never coerced;")
    ap("    parse rate reported per proposer")
    ap("")
    ap("arms:")
    ap("  primary: WCT-EM (three-state Dawid-Skene, unsupervised)")
    ap("  secondary: WCT-U (uniform signed support)")
    ap("  ablations:")
    ap("    - claim_instance_counting (verbosity-weighted; expected to fail)")
    ap("    - single_best_proposer_calibrated (oracle reference)")
    ap("  floor: base_rate")
    ap("")
    ap("baselines_in_order_of_stringency:")
    ap("  1: trivial base rate (floor)")
    ap("  2: single best proposer, calibrated (oracle reference)")
    ap("  3: zero-shot 1-4B jury native outputs on the same task (P4 arm)")
    ap("  4: frontier self-review (27B with the frozen jury contract on the")
    ap("     same claims; the null control the pass criterion compares against)")
    ap("  5: covariate logistic regression (the registered bar)")
    ap("  6: optional small supervised verifier trained on calibration labels")
    ap("")
    ap("covariate_baseline:")
    ap("  features: [article_length, pool_position, claim_length, polarity,")
    ap("             question_type]")
    ap("  fitted_on: calibration split only")
    ap("  note: model-free; the feature list is pinned here, not chosen after")
    ap("        seeing results")
    ap("")
    ap("metrics:")
    ap("  primary: >-")
    ap("    Held-out article-block delta log-loss, WCT-EM vs the covariate")
    ap("    baseline, delta threshold 0.02 nats, article-block bootstrap,")
    ap("    2000 resamples.")
    ap("  co_primary: within-article AUROC, WCT-EM vs ranked covariate baseline")
    ap("  null: within-article truth permutations, 10000 permutations")
    ap("  e0: pairwise proposition-level residual error correlation across")
    ap("      voters, reported as a number")
    ap("  calibration: Platt sigmoid(a*s+b), exact MLE on calibration split;")
    ap("                temperature kept as an ablation")
    ap("  solver_value: flag precision, flag recall, claim accuracy change")
    ap("                solver-alone vs solver-plus-jury (low-consensus claims")
    ap("                dropped); solver confidence = mean token probability")
    ap("                of the answer span")
    ap("  cost: per arm, total input/output tokens, GPU-seconds, USD, median")
    ap("        TTFT, minimum hardware at target concurrency")
    ap("  jury_size_sweep: gated false-claim rate at sizes 1/3/5; the 3-juror")
    ap("        arm is the three highest-calibration-accuracy families")
    ap("        (pre-specified); descriptive curve")
    ap("")
    ap("pass_criterion: >-")
    ap("    Across the test articles, the juror-gated system (defendant claims")
    ap("    gated by jury consensus, below-4B primary with the registered 4B")
    ap("    fallback where applied) PASSES if (a) it outperforms the frontier")
    ap("    self-review control on false-claim rate with the 95 percent")
    ap("    bootstrap CI of the difference entirely below zero, OR (b) it is")
    ap("    comparable within 10 percentage points of false-claim rate (point")
    ap("    estimate, bootstrap CI reported) at strictly lower total compute")
    ap("    cost (USD, amortized serving price). The cost ratio is a headline")
    ap("    number; the pass branch requires strictly lower cost, not a fixed")
    ap("    ratio.")
    ap("decision_rule: >-")
    ap("    GO requires the point estimate at or above delta AND the bootstrap")
    ap("    interval excluding zero. Point clears delta but the bound does")
    ap("    not: INCONCLUSIVE. Degenerate (zero-width) intervals are reported,")
    ap("    never silently interpreted.")
    ap("")
    ap("predictions:")
    ap("  P1: WCT-EM primary returns GO on the fine-tuned jury.")
    ap("  P2: Leave-one-proposer-out primary remains GO with each voter")
    ap("      removed in turn (including the solver-as-proposer, consensus")
    ap("      not oracle).")
    ap("  P3: Claim-instance counting AUROC below 0.65 on the test split")
    ap("      (one-vote-per-source invariant holds).")
    ap("  P4: Delta log-loss advantage over base rate on the fine-tuned jury")
    ap("      is at least as large as the zero-shot 4B jury's advantage on")
    ap("      the same articles.")
    ap("  P5: The jury consensus flags a strictly larger share of the solver's")
    ap("      non-ENTAIL claims than of its ENTAIL claims on test articles.")
    ap("      (power note) needs at least 100 pool-matched solver claims of")
    ap("      each class, else descriptive only.")
    ap("  P6: (co-designer's, verbatim intent) On test articles, over the")
    ap("      solver's pool-matched claims on UNSPECIFIED propositions,")
    ap("      (a) the solver bullshits a confident answer on at least 50")
    ap("      percent of them, and (b) the jury-consensus gate removes at")
    ap("      least half of those wrong answers (false-answer rate drops")
    ap("      from at least 50 percent to under 33 percent). (power note)")
    ap("      needs at least 30 such claims, else descriptive only.")
    ap("  P7: (a) The 5-juror consensus outperforms the single best juror on")
    ap("      false-claim rate (mechanism, same-family blind spots). (b) The")
    ap("      juror consensus's raw compute effort exceeds 50 percent of the")
    ap("      27B's while its false-claim rate is lower than the control's.")
    ap("      Raw compute effort = aggregate parameter scale x tokens.")
    ap("      (power note) needs complete token and parameter accounting for")
    ap("      every arm.")
    ap("")
    ap("training:")
    ap("  scheme: >-")
    ap("    Self-distillation. Before any fine-tuning, each base family runs")
    ap("    zero-shot on its own training slice under the jury contract and")
    ap("    its exact native output is captured. Target = {answer: PASS|FAIL")
    ap("    parsed from the native output, reason: native output verbatim}.")
    ap("    The LoRA learns only the wrapper (instruction style, JSON")
    ap("    contract, answer field); reasoning content stays native.")
    ap("  variants: [reason_included, votes_only]")
    ap("  adapters: 10 (2 variants x 5 families)")
    ap("  slices: >-")
    ap("    Disjoint 10-article training split per family, distinct seeds,")
    ap("    different recipe where possible, to keep error correlation low.")
    ap("  losslessness: >-")
    ap("    Per adapter, base and fine-tuned run on the 10 calibration")
    ap("    articles (untrained for every family): (a) exact-match agreement")
    ap("    of outputs, (b) PPL of the base native outputs under the")
    ap("    fine-tuned model as a ratio to the base self-PPL (1.0 lossless).")
    ap("    Descriptive, per family; divergent adapters are flagged")
    ap("    perturbed and their consensus share reported separately.")
    ap("")
    ap("contamination_check: >-")
    ap("    For every test article, each base juror answers the 20 seed")
    ap("    questions WITHOUT the article (parametric only) and WITH it,")
    ap("    before any fine-tuned output exists. Any question answered above")
    ap("    chance without the article is flagged parametric; flags are logged")
    ap("    before the fine-tuned test run is seen.")
    ap("")
    ap("spend_caps:  # hard cumulative per-model call caps, persisted across")
    ap("             # re-runs (runner maintains the counters)")
    ap("  qwen3_8_27b: 5000")
    ap("  each_juror_model: 5000")
    ap("")
    ap("discipline:")
    ap("  - Implementations are the registration. The committed files at the")
    ap("    tag are the record, not this prose.")
    ap("  - The decision-rule boundary clause (metrics.decision_rule) is the")
    ap("    C11 fix; it is explicit, not implied.")
    ap("  - Generation cache is content-hashed and immutable; analysis re-runs")
    ap("    at zero inference cost.")
    ap("  - DECISIONS.md and GOTCHAS.md are part of the record.")

    out = REPO / "prereg.yaml"
    out.write_text("\n".join(lines) + "\n")

    print(f"split seed {SPLIT_SEED}")
    print("train:", train)
    print("calib:", calib)
    print("test:", test)
    print(
        f"census non-ENTAIL test: {non_entail_test} (threshold 60, "
        f"{'PASS' if census_pass else 'FAIL'})"
    )
    print(f"manifest sha256: {manifest_hash}")
    print(f"wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
