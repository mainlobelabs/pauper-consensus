"""Assert every figure quoted in paper.md's corrected passages against the evidence.

Slice 2's corrections restate three claims and add roughly two dozen figures. Hand
transcription is exactly where an error survives review, and these numbers already moved
once in slice 1 when a calibration map was read for the wrong cycle.

THE COMPLETENESS RULE. Every numeric literal in the revised passages falls into exactly one
of two classes, and each is machine-verified:

  (a) ARTIFACT-ASSERTED -- equal to a value read from out/v3/ or the frozen
      out/e1*_summary*.json. This covers figures RETAINED from draft v3 as well as new ones,
      because draft v3's numbers were correct readings of the frozen `uncapped` arm (its
      quoted 0.502-0.554 is that arm's 0.50174 and 0.55439 across the cycle-1 strata). What
      was wrong was the LABEL, not the arithmetic. A literal presented as a quotation is
      ADDITIONALLY verified to appear in the pinned pre-slice draft, on top of the artifact
      assertion, never instead of it.

  (b) STRUCTURAL -- matched by a declared pattern: an ISO date, a source reference
      <path>.<py|yaml|md>:<line>[-<line>], a section number, or a draft version identifier.
      P2 is required to add such literals, so a rule without this class would reject the
      very paper this slice must produce.

A literal in neither class fails. That is the point: an enumeration would silently permit
any figure added later.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EVIDENCE_COMMIT = "e63f946"
PANELS = ("c1_local", "c1_openrouter", "c2_panelA", "c2_panelB")
FROZEN_SUMMARIES = ("out/e1_summary.json", "out/e1_summary_openrouter.json",
                    "out/e1_v2_summary_panelA.json", "out/e1_v2_summary_panelB.json")

# class (b): declared patterns, not a free-text exemption
STRUCTURAL = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                       # ISO date
    # (?!\.\d) stops a partial match: without it "notaref.md:0.7714" is consumed as
    # "notaref.md:0" and the remaining ".7714" evades the numeric scanner completely
    re.compile(r"\b[\w/]+\.(?:py|yaml|md):\d+(?:-\d+)?(?!\.?\d)\b"),  # source reference
    re.compile(r"§\s?\d+(?:\.\d+)*"),                            # section number, cited
    re.compile(r"(?m)^#{1,6}\s+\d+(?:\.\d+)*\b"),                 # section number, as a heading
    re.compile(r"(?m)^\*\*\d+(?:\.\d+)*\b"),                     # section number, bolded lead
    re.compile(r"\bdraft v\d+\b", re.I),                         # draft version
    # bounded deliberately: an open \d+ would exempt "cycle 999" and any other invented
    # count dressed as a label
    re.compile(r"\bcycle[- ][123]\b", re.I),
    re.compile(r"\bslice [1-4]\b", re.I),
    re.compile(r"\btop_k = ?8\b"),
    re.compile(r"\bM = ?[345]\b"),
    re.compile(r"\bpanel [AB]\b"),
    re.compile(r"\be63f946\b"),

    re.compile(r"\bdepth-[1-5]\b"),                    # corpus labels that exist (1-5)
    re.compile(r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|"
               r"September|October|November|December) \d{4}\b"),   # prose date
    re.compile(r"\bcontribution [1-5]\b", re.I),       # the paper has five contributions
    re.compile(r"(?m)^\s*[1-5]\.\s"),                  # numbered list marker (contributions)
)
NUMERIC = re.compile(r"(?<![\w.])-?\d+\.\d+"          # 0.9001
                     r"|(?<![\w])-?\.\d+"                # .7714 — a bare decimal must
                                                          # not be invisible to the scan
                     # (?!\.?\d) not (?![\w.]): the latter made an integer at the END OF A
                     # SENTENCE invisible, because the full stop blocked the match. Decimals
                     # are still caught by the first alternative, which is tried first.
                     r"|(?<![\w.])-?\d+(?!\.?\d)")        # 150, and 999 in "per depth-999."


def _artifact_values(root: Path) -> set[str]:
    """Every number the artifacts and frozen summaries contain, as rendered strings.

    Rendered at the precisions a paper would plausibly quote (as-is, and rounded to 4, 3 and
    2 decimals) so that a correctly-quoted figure matches regardless of how it was rounded,
    while a wrong digit does not.
    """
    vals: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, bool):
            pass
        elif isinstance(o, (int, float)):
            f = float(o)
            vals.add(repr(o) if isinstance(o, int) else f"{f}")
            for nd in (5, 4, 3, 2):
                vals.add(f"{f:.{nd}f}")
                vals.add(f"{f:.{nd}f}".rstrip("0").rstrip("."))
            vals.add(str(int(f)) if f == int(f) else f"{f}")

    for p in PANELS:
        fp = root / "out/v3" / f"reanalysis_{p}.json"
        if fp.exists():
            walk(json.loads(fp.read_text()))
    # the uncapped-minus-capped deltas 6.1 reports are a DEFINED function of the cells,
    # so they belong in the artifact set; arbitrary differences do not
    for p in PANELS:
        fp = root / "out/v3" / f"reanalysis_{p}.json"
        if fp.exists():
            c = json.loads(fp.read_text()).get("m6_2x2", {}).get("cells", {})
            if "uncapped_signed" in c and "capped_signed" in c:
                walk(round(c["uncapped_signed"]["raw_auroc"]
                           - c["capped_signed"]["raw_auroc"], 4))
    for rel in FROZEN_SUMMARIES:
        fp = root / rel
        if fp.exists():
            walk(json.loads(fp.read_text()))
    return vals          # signs are significant: a flipped interval must not match


def _pinned_draft(root: Path) -> str:
    try:
        return subprocess.run(["git", "show", f"{EVIDENCE_COMMIT}:paper.md"],
                              cwd=root, capture_output=True, text=True,
                              check=True).stdout
    except subprocess.CalledProcessError:
        return ""            # caller treats this as a failure, never as "nothing to check"


MARKED = re.compile(r"<!-- slice2:begin -->(.*?)<!-- slice2:end -->", re.S)


def revised_passages(text: str) -> str:
    """Exactly the passages this slice rewrote, delimited in the paper itself.

    Heading-based scoping pulled in neighbouring prose that the slice never touched (§8's
    pre-existing bullets, whose "53/150 GLM-5.2" is not a figure this slice is responsible
    for), which would have forced the completeness rule to be loosened until it stopped
    catching real errors. Explicit markers keep the rule strict AND the scope honest, and
    they double as the record of what changed.
    """
    found = MARKED.findall(text)
    if found:
        return "\n".join(found)
    return text                      # fixtures and unit tests carry no markers


ROW_2X2 = re.compile(r"^[ \t]*\|\s*(c1_local|c1_openrouter|c2_panelA|c2_panelB)\s*\|"
                     r"\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|",
                     re.M)
ROW_SS = re.compile(r"^[ \t]*\|\s*(c1_local|c1_openrouter|c2_panelA|c2_panelB)\s*\|\s*(\w+)\s*\|"
                    r"\s*(\S+)\s*\|\s*([+-][\d.]+)\s*\[([+-][\d.]+),\s*([+-][\d.]+)\]\s*\|"
                    r"\s*\*\*(\w+)\*\*\s*\|", re.M)


def _positional(passages: str, root: Path, require_tables: bool) -> list[str]:
    """Each table row must match ITS OWN panel's values, in order, including the decision
    string. Global membership would accept a row whose cells were shuffled between panels,
    a sign-flipped interval, or a swapped go/inconclusive."""
    fails = []
    D = {}
    for p in PANELS:
        fp = root / "out/v3" / f"reanalysis_{p}.json"
        if fp.exists():
            D[p] = json.loads(fp.read_text())
    seen2x2 = seen_ss = 0
    order = ("capped_signed", "capped_unsigned", "uncapped_signed", "uncapped_unsigned")
    for m in ROW_2X2.finditer(passages):
        panel, *cells = m.groups()
        if panel not in D:
            continue
        seen2x2 += 1
        want = D[panel]["m6_2x2"]["cells"]
        for key, got in zip(order, cells):
            exp = f'{want[key]["raw_auroc"]:.4f}'
            if got != exp:
                fails.append(f"2x2 {panel}.{key}: paper says {got}, artifact says {exp}")
    for m in ROW_SS.finditer(passages):
        panel, mapname, src, pt, lo, hi, dec = m.groups()
        if panel not in D:
            continue
        seen_ss += 1
        d = D[panel]
        wm = d["frozen_reproduction"]["map"]
        v = d["panel_vs_single_best_calibration_selected"][wm]["WCT-EM"]
        dl = v["delta_log_loss"]
        for label, got, exp in (("map", mapname, wm),
                                ("source", src, d["single_source"]["by_map"][wm]["calibration_selected"]),
                                ("point", pt, f'{dl["point"]:+.4f}'),
                                ("lo", lo, f'{dl["lo"]:+.4f}'),
                                ("hi", hi, f'{dl["hi"]:+.4f}'),
                                ("decision", dec, v["decision"])):
            if got != exp:
                fails.append(f"single-source {panel}.{label}: paper says {got!r}, "
                             f"artifact says {exp!r}")
    # absence must FAIL: a regex that silently stops matching would otherwise turn the
    # whole positional check into a vacuous pass
    # probe values are quoted per cycle; global membership would accept them swapped,
    # since both numbers exist somewhere in the artifacts
    mp = re.search(r"scores ([\d.]+) against cycle 1's ([\d.]+)", passages)
    if mp and D:
        got2, got1 = mp.groups()
        exp2 = D["c2_panelA"]["alignment_audit"]["aligner_self_identification"]["accuracy"]
        exp1 = D["c1_local"]["alignment_audit"]["aligner_self_identification"]["accuracy"]
        if got2 != f"{exp2}":
            fails.append(f"probe cycle-2 value: paper says {got2}, artifact says {exp2}")
        if got1 != f"{exp1}":
            fails.append(f"probe cycle-1 value: paper says {got1}, artifact says {exp1}")
    # narrative claims about a MAXIMUM must be checked against the computed maximum, not
    # against "is this number somewhere in the artifacts"
    if D:
        want = max(D[p]["m6_2x2"]["cells"][k]["raw_auroc"]
                   for p in PANELS if p in D
                   for k in ("capped_unsigned", "uncapped_unsigned"))
        for mm in re.finditer(r"no unsigned arm exceeds ([\d.]+)", passages):
            if mm.group(1) != f"{want:.4f}":
                fails.append(f"unsigned maximum: paper says {mm.group(1)}, artifacts give "
                             f"{want:.4f}")
    # NARRATIVE claims, asserted against derived values. Membership alone would accept a
    # contextually wrong figure that happens to equal some unrelated artifact field.
    if D:
        deltas = {p: round(D[p]["m6_2x2"]["cells"]["uncapped_signed"]["raw_auroc"]
                           - D[p]["m6_2x2"]["cells"]["capped_signed"]["raw_auroc"], 4)
                  for p in PANELS if p in D}
        beats = sorted((v for v in deltas.values() if v > 0), reverse=True)
        worst = min(deltas.values()) if deltas else 0.0
        m = re.search(r"beats capped on\s+three of four panel-cycles \(by ([\d.]+), ([\d.]+) and "
                      r"([\d.]+)\)", passages, re.S)
        if m:
            got = sorted((float(g) for g in m.groups()), reverse=True)
            if [f"{g:.4f}" for g in got] != [f"{b:.4f}" for b in beats]:
                fails.append(f"narrative deltas: paper says {got}, artifacts give {beats}")
        m = re.search(r"is ([\d.]+) lower on the fourth", passages)
        if m and m.group(1) != f"{abs(worst):.4f}":
            fails.append(f"narrative shortfall: paper says {m.group(1)}, artifacts give "
                         f"{abs(worst):.4f}")
        # the single-source range quoted in prose must be the true min/max of the go margins
        gos = []
        for pn in PANELS:
            if pn not in D:
                continue
            wm = D[pn]["frozen_reproduction"]["map"]
            v = D[pn]["panel_vs_single_best_calibration_selected"][wm]["WCT-EM"]
            if v["decision"] == "go":
                gos.append(v["delta_log_loss"]["point"])
        if gos:
            for m in re.finditer(r"\+([\d.]+) to \+([\d.]+) nats", passages):
                lo_s, hi_s = m.groups()
                if lo_s != f"{min(gos):.4f}" or hi_s != f"{max(gos):.4f}":
                    fails.append(f"single-source range: paper says +{lo_s} to +{hi_s}, "
                                 f"artifacts give +{min(gos):.4f} to +{max(gos):.4f}")
        # "N of 4 panel-cycles" is evidential, not a label: exempting it as structural
        # would let "3 of 4" become "4 of 4" unchallenged
        words = {1: "one", 2: "two", 3: "three", 4: "four"}
        n_go = len(gos)
        for m in re.finditer(r"\b(one|two|three|four|\d) of (?:four|4) panel-cycles", passages):
            got = m.group(1)
            if got not in (words.get(n_go), str(n_go)):
                fails.append(f"panel count: paper says {got!r} of four panel-cycles, "
                             f"artifacts give {n_go}")
        n_beats = sum(1 for v in deltas.values() if v > 0)
        for m in re.finditer(r"beats capped on\s+(one|two|three|four|\d) of four", passages):
            got = m.group(1)
            if got not in (words.get(n_beats), str(n_beats)):
                fails.append(f"beats-capped count: paper says {got!r}, artifacts give {n_beats}")

        # the abstract's approximate ranges must BRACKET the real extremes, not merely be
        # numbers that occur somewhere: "0.5-0.6" and "0.89-1.00" are rounded restatements
        signed = [D[p]["m6_2x2"]["cells"][k]["raw_auroc"] for p in PANELS if p in D
                  for k in ("capped_signed", "uncapped_signed")]
        unsigned = [D[p]["m6_2x2"]["cells"][k]["raw_auroc"] for p in PANELS if p in D
                    for k in ("capped_unsigned", "uncapped_unsigned")]
        m = re.search(r"AUROC ≈ ?([\d.]+)–([\d.]+) from AUROC ([\d.]+)–([\d.]+)", passages)
        if m and signed and unsigned:
            ul, uh, sl, sh = (float(g) for g in m.groups())
            if not (ul <= min(unsigned) and uh >= max(unsigned)):
                fails.append(f"abstract unsigned range {ul}-{uh} does not bracket the actual "
                             f"{min(unsigned):.4f}-{max(unsigned):.4f}")
            if not (sl <= min(signed) and sh >= max(signed)):
                fails.append(f"abstract signed range {sl}-{sh} does not bracket the actual "
                             f"{min(signed):.4f}-{max(signed):.4f}")

        # 9's inline restatement of c2_panelB
        if "c2_panelB" in D:
            wm = D["c2_panelB"]["frozen_reproduction"]["map"]
            dl = D["c2_panelB"]["panel_vs_single_best_calibration_selected"][wm]["WCT-EM"]["delta_log_loss"]
            for m in re.finditer(r"it is ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]", passages):
                exp = (f'{dl["point"]:+.4f}', f'{dl["lo"]:+.4f}', f'{dl["hi"]:+.4f}')
                if m.groups() != exp:
                    fails.append(f"c2_panelB inline: paper says {m.groups()}, artifacts give {exp}")
    if not require_tables:
        return fails          # unit-test snippets legitimately carry no tables
    if seen2x2 != len(PANELS):
        fails.append(f"2x2 table matched {seen2x2} panel rows, expected {len(PANELS)} — "
                     f"the positional check did not run over it")
    if seen_ss != len(PANELS):
        fails.append(f"single-source table matched {seen_ss} rows, expected {len(PANELS)} — "
                     f"the positional check did not run over it")
    return fails


# registered headline figures, with the exact artifact path each is read from. They sit
# OUTSIDE the slice markers, so nothing else in this checker would notice if a correction
# moved one. Compared NUMERICALLY at the paper's own precision: the summaries store
# unrounded values (0.21985), the paper quotes +0.220.
FROZEN_HEADLINES = (
    ("+0.220", "out/e1_v2_summary_panelA.json",
     ("strata", "all_items", "instrument_primary", "primary",
      "WCT-EM_vs_covariate_gd", "delta_log_loss", "point"), "cycle-2 panel A primary"),
    ("+0.272", "out/e1_v2_summary_panelB.json",
     ("strata", "all_items", "instrument_primary", "primary",
      "WCT-EM_vs_covariate_gd", "delta_log_loss", "point"), "cycle-2 panel B primary"),
    ("\u22120.159", "out/e1_summary.json",
     ("strata", "all_items", "primary_delta_log_loss_vs_covariate",
      "WCT-EM", "delta_log_loss", "point"), "cycle-1 panel A primary (the flip)"),
    ("+0.122", "out/e1_summary_openrouter.json",
     ("strata", "all_items", "primary_delta_log_loss_vs_covariate",
      "WCT-EM", "delta_log_loss", "point"), "cycle-1 panel B primary (the flip)"),
)


def _frozen_headlines_intact(text: str, root: Path) -> list[str]:
    """A correction must not remove or move a registered number. Checking only the marked
    passages would never notice if it did."""
    fails = []
    pinned = _pinned_draft(root)
    for lit, rel, path, what in FROZEN_HEADLINES:
        # presence alone is too weak: these figures recur (abstract, §3.2, §5.2), so
        # altering ONE occurrence leaves the others and a presence check still passes.
        # The count must not drop below the pinned draft's.
        if pinned:
            before, now = pinned.count(lit), text.count(lit)
            if now < before:
                fails.append(f"registered headline {lit} ({what}) appears {now} times, down "
                             f"from {before} in the pinned draft — an occurrence was altered "
                             f"or removed")
        if lit not in text:
            fails.append(f"registered headline {lit} ({what}) is no longer present in the "
                         f"paper; a correction must not remove a registered figure")
            continue
        fp = root / rel
        if not fp.exists():
            fails.append(f"frozen summary {rel} missing; cannot verify {lit}")
            continue
        node = json.loads(fp.read_text())
        for k in path:
            node = node[k]
        want = f"{float(node):+.3f}".replace("-", "\u2212")
        if want != lit:
            fails.append(f"registered headline {lit} ({what}) does not match {rel}, "
                         f"which gives {want}")
    return fails


def _derived_counts(root: Path):
    """(digit, word, phrase) for each count the paper may state, computed from artifacts."""
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    D = {}
    for p in PANELS:
        fp = root / "out/v3" / f"reanalysis_{p}.json"
        if fp.exists():
            D[p] = json.loads(fp.read_text())
    if not D:
        return []
    n_go = sum(1 for p in D
               if D[p]["panel_vs_single_best_calibration_selected"][
                   D[p]["frozen_reproduction"]["map"]]["WCT-EM"]["decision"] == "go")
    n_beats = sum(1 for p in D
                  if D[p]["m6_2x2"]["cells"]["uncapped_signed"]["raw_auroc"]
                  > D[p]["m6_2x2"]["cells"]["capped_signed"]["raw_auroc"])
    return [(n_go, words.get(n_go, n_go), "panel-cycles"),
            (n_beats, words.get(n_beats, n_beats), "panel-cycles")]


def check(paper: Path, root: Path) -> list[str]:
    text = paper.read_text()
    passages = revised_passages(text)
    artifacts = _artifact_values(root)
    if not artifacts:
        return ["no artifact values loaded — out/v3/ missing?"]
    pinned = _pinned_draft(root)
    # the real paper carries slice2 markers; a snippet under test does not. Table presence
    # is required only where the tables are supposed to exist, so the absence guard cannot
    # be satisfied by simply testing something smaller.
    fails: list[str] = _positional(passages, root, require_tables=bool(MARKED.search(text)))
    if MARKED.search(text):
        fails += _frozen_headlines_intact(text, root)
    if not pinned.strip():
        fails.append(f"could not read {EVIDENCE_COMMIT}:paper.md — the quotation check "
                     f"cannot run, and passing without it would be a vacuous pass")

    # blank out structural matches first so their digits are not re-scanned as figures
    scan = passages
    for pat in STRUCTURAL:
        scan = pat.sub(" ", scan)
    # "N of 4 panel-cycles" is exempted ONLY at its derived value: a wrong count fails both
    # the positional assertion above and, being unexempted, the completeness rule below
    for lo, hi, phrase in _derived_counts(root):
        scan = re.sub(rf"\b(?:{lo}|{hi}) of (?:four|4) {phrase}", " ", scan, flags=re.I)

    for m in NUMERIC.finditer(scan):
        lit = m.group(0)
        # sign-SENSITIVE: stripping "-" here would accept a flipped interval bound
        cands = {lit, lit.lstrip("+"), lit.rstrip("0").rstrip(".")}
        if cands & artifacts:
            continue
        ctx = scan[max(0, m.start() - 60):m.start() + 40].replace("\n", " ")
        fails.append(f"unclassified figure {lit!r} (neither artifact-asserted nor "
                     f"structural) near: ...{ctx.strip()}...")

    # A quotation must appear in the pinned draft AS A WHOLE. Checking its numbers one by
    # one accepted fabricated ranges like "0.569-0.554", because each component occurs
    # somewhere in the draft even though that pairing never did.
    for q in re.findall(r'"([^"]+?)"', passages):
        if not NUMERIC.search(q):
            continue
        if not pinned:
            continue
        norm = lambda s: re.sub(r"\s+", " ", s.replace("\u2013", "-").replace("\u2014", "-")).strip()
        if norm(q) not in norm(pinned):
            fails.append(f"quoted passage is not verbatim in {EVIDENCE_COMMIT}:paper.md "
                         f"-> {q[:80]!r}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default="paper.md")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    fails = check(Path(args.paper) if Path(args.paper).is_absolute()
                  else root / args.paper, root)
    if fails:
        print(f"PAPER CHECK FAILED ({len(fails)}):", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)
        return 1
    result = {"ok": True, "paper": str(args.paper),
              "checks": ["positional 2x2", "positional single-source", "narrative deltas",
                         "panel counts", "unsigned maximum", "probe values",
                         "frozen headline occurrences", "whole-span quotations",
                         "completeness (artifact-asserted or structural)"]}
    # NOT out/v3/: that directory is pinned evidence, immutable against e63f946, and
    # adding a file to it would put an unpinned artifact inside the pinned set
    out = root / "out/slice2/paper_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print("paper check OK: every figure in the revised passages is artifact-asserted "
          f"or structural ({len(result['checks'])} checks; wrote {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
