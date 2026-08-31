"""Render the slice-4 outcome entry FROM the registration, fingerprinted. (B11)

Two failure modes this is written against, both observed in this programme:

  * A hand-written outcome drifts from the artifacts it claims to summarise. So the entry
    is RENDERED from prereg_v3.yaml and never typed.
  * Slice 2's decider refused to update when its heading already existed, so a stale entry
    survived and the gate reported STALE forever with no way to converge. This one
    SUPERSEDES an existing entry atomically instead of refusing.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

MARK = "V3 SLICE 4 OUTCOME"
FP_LABEL = "registration-fingerprint"
DECISIONS = Path("DECISIONS.md")
PREREG = Path("prereg_v3.yaml")


def _atomic_write(path: Path, text: str) -> None:
    d = path.parent
    fd, tmp = tempfile.mkstemp(dir=d, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def fingerprint(prereg: Path = PREREG) -> str:
    """Fingerprint of the SOURCE registration, so a stale entry is detectable."""
    return hashlib.sha256(prereg.read_bytes()).hexdigest()[:16]


def build(prereg: Path = PREREG) -> str:
    """Render the entry ENTIRELY from prereg_v3.yaml.

    Every material value below is read from an explicit registration field. Hard-coding
    them here -- as an earlier version did for the cycle-2 item count, the +0.220/+0.272
    margins, the fp16/fp32 divergence and the retry allowance -- lets the entry disagree
    with the registration while still passing its own self-check, because the check
    compares against this same renderer.
    """
    reg = yaml.safe_load(prereg.read_text())
    fp = fingerprint(prereg)
    ds, delta, power = reg["dataset"], reg["delta"], reg["power"]
    dr = power["dose_response_increment"]
    panels, cost, ins = reg["panels"], reg["cost"], reg["instrument"]
    dd = ins["measured_device_dependence"]
    proj = ds["projected_scored_positive_polarity_negatives"]
    members = ", ".join(f"{m['rank']}:{m['agent']}({m['tier']})" for m in panels["members"])
    caps = cost["hard_cap"]
    auth = cost["authorised_volume"]
    excluded = ", ".join(delta["excluded_inconclusive"]) or "none"

    return "\n".join([
        f"## {MARK}: cycle 3 registered at delta={delta['value']} nats on {ds['n_items']} "
        f"items, {'/'.join(sorted(panels['nested_subsets']))} nested, "
        f"{ins['precision']}/{ins['device']} instrument.",
        "",
        f"- {FP_LABEL}: `{fp}`",
        f"- Registration: `{prereg}` (tag `{reg['tag']}`)",
        "",
        f"**Corpus.** {ds['n_items']} items, SHA-256 `{ds['sha256'][:16]}...`, "
        f"{ds['decidable']:,} decidable propositions of which "
        f"{ds['positive_polarity_negatives']:,} are positive-polarity negatives. "
        f"{ds['comparability']} Projected SCORED positive-polarity negatives at M=5: "
        f"{proj['M=5']:,} — a projection, is_gate={proj['is_gate']}.",
        "",
        f"**Delta.** {delta['value']} {delta['units']}, from: {delta['formula']} "
        f"Argmin {delta['argmin']}; {delta['n_conclusive']} of {delta['n_panel_cycles']} "
        f"panel-cycles conclusive, excluding {excluded}. "
        f"immutable_after_results={delta['immutable_after_results']}.",
        "",
        f"**Power.** The primary needs "
        f"{power['primary']['M=5']['required_n_at_sd_max']} items at the worst observed "
        f"per-item SD ({power['sd_items_observed']['max']}) and has {ds['n_items']}. The "
        f"binding arm is the dose-response increment, detectable to "
        f"{dr['detectable_at_registered_n']} nats at this n. {dr['note']}",
        "",
        f"**Panels.** {len(panels['members'])} families, fixed ordering ({members}). "
        f"{panels['nested_property']}. Rank "
        f"{panels['declared_margin']['rank']} ({panels['declared_margin']['agent']}) is the "
        f"declared margin; qwen carries a declared fallback to "
        f"{panels['declared_fallback']['model']}. Ordering rule: {panels['ordering_rule']}.",
        "",
        f"**Instrument.** {ins['precision']} on {ins['device']}. "
        f"{ins['change_from_cycles_1_2']} Measured over {dd['n_pairs']} pairs: "
        f"fp16 across devices {dd['cpu_fp16_vs_gpu_fp16']['max_abs']} max with "
        f"{dd['cpu_fp16_vs_gpu_fp16']['argmax_flips']} argmax flip(s); fp32 across devices "
        f"{dd['cpu_fp32_vs_gpu_fp32']['max_abs']} with "
        f"{dd['cpu_fp32_vs_gpu_fp32']['argmax_flips']}. {ins['fail_closed'].capitalize()}.",
        "",
        f"**Cost.** Authorised volume {auth['calls']:,} calls, cap "
        f"${caps['run_total_usd']} (source: {auth['usd_authorisation_source']}); "
        f"rate-derived worst case ${auth['usd_estimated_worst_case']} including the "
        f"{cost['retry_allowance']:.0%} retry allowance and both registered contingencies "
        f"({', '.join(cost['contingencies'])}). {caps['persistence']}",
        "",
    ])


def _find_entry(text: str) -> tuple[int, int] | None:
    """Span of an existing MARK section, up to the next H2 or EOF."""
    m = re.search(rf"^## {re.escape(MARK)}.*?$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", text[m.end():], re.M)
    return (m.start(), m.end() + nxt.start()) if nxt else (m.start(), len(text))


def apply(prereg: Path = PREREG, decisions: Path = DECISIONS) -> str:
    """Write or SUPERSEDE the entry atomically. Never refuses because one exists."""
    entry = build(prereg)
    text = decisions.read_text()
    span = _find_entry(text)
    if span:
        text = text[:span[0]] + entry + text[span[1]:]
        action = "superseded"
    else:
        text = text.rstrip("\n") + "\n\n" + entry
        action = "created"
    _atomic_write(decisions, text)
    return action


def check(prereg: Path = PREREG, decisions: Path = DECISIONS) -> tuple[bool, str]:
    """True only if an entry exists AND its fingerprint matches the current registration."""
    text = decisions.read_text()
    span = _find_entry(text)
    if not span:
        return False, f"no '{MARK}' entry in {decisions}"
    body = text[span[0]:span[1]]
    want = fingerprint(prereg)
    m = re.search(rf"{re.escape(FP_LABEL)}: `([0-9a-f]+)`", body)
    if not m:
        return False, f"entry carries no {FP_LABEL}"
    if m.group(1) != want:
        return False, (f"STALE: entry {FP_LABEL} {m.group(1)} != current registration "
                       f"{want}; re-run to supersede it")
    if body.strip() != build(prereg).strip():
        return False, "STALE: entry text differs from what the registration renders"
    return True, f"current ({FP_LABEL} {want})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--prereg", default=str(PREREG))
    a = ap.parse_args()
    ok, msg = check(Path(a.prereg))
    if a.check:
        print(msg)
        return 0 if ok else 1
    action = apply(Path(a.prereg))
    print(f"{action}: {check(Path(a.prereg))[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
