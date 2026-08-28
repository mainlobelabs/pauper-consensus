#!/usr/bin/env python3
"""Derive per-proposition pool metadata (fact_role, trap_type, polarity) for
corpus v2 by the registered mechanical rule (see prereg-v2.yaml, metadata:).

The rule was calibrated against the curated v1 metadata
(corpus/pool/metadata.json, tag prereg-waveconsensus-v1) BEFORE being applied
to v2. Run: python3 make_metadata.py [--v1]  (default: corpus-v2)

Backtest vs v1 curation (1200 props): trap_type 91.8% agreement,
polarity 98.7%; derived unit_swap count matches v1 curation exactly (82).
Residual gaps are v1 curation noise (see prereg-v2.yaml, metadata:).
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

NEGATION = [
    r"\bnot\b", r"\bno\b", r"\bnone\b", r"\bneither\b", r"\bnor\b", r"\bnever\b",
    # "without" is a state predicate, not claim negation ("were without power")
    r"\bnobody\b", r"\bno one\b", r"\bno-one\b", r"\bnowhere\b",
    r"\bcannot\b", r"\bcould not\b", r"\bwould not\b", r"\bshould not\b",
    r"\bshall not\b", r"\bwill not\b", r"\bdid not\b", r"\bdoes not\b",
    r"\bdo not\b", r"\bhas not\b", r"\bhave not\b", r"\bhad not\b",
    r"\bwas not\b", r"\bwere not\b", r"\bare not\b", r"\bis not\b",
    r"\bcan't\b", r"\bcan not\b", r"\bcouldn't\b", r"\bwouldn't\b",
    r"\bshouldn't\b", r"\bdoesn't\b", r"\bdon't\b", r"\bdidn't\b",
    r"\bisn't\b", r"\baren't\b", r"\bwasn't\b", r"\bweren't\b", r"\bwon't\b",
    r"\bain't\b", r"\bnothing\b", r"\bno longer\b", r"\bfailed to\b",
]
NEG_RE = re.compile("|".join(NEGATION))
# tokens that look like negations but are not (proper nouns / compound words)
NEG_FALSE_POS = re.compile(r"\b(norway|norwegian|nor'easter)\b", re.I)

NUM_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b")
DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2}(?:,\s*\d{4})?"
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
WORD_NUM = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
EXACTLY_RE = re.compile(
    rf"\bexactly\s+(?:{WORD_NUM}\b|\d{{1,3}}(?:,\d{{3}})+|\d+)", re.I
)
MONTHS = {}
for _full in [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]:
    _low = _full.lower()
    for _abbr in (_low, _low[:3], _low[:4]):
        MONTHS[_abbr] = _full
MONTHS["sept"] = "September"


def norm_months(text: str) -> str:
    def rep(m):
        return MONTHS[m.group(0).lower().rstrip(".")]
    return re.sub(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
                  r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
                  r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b\.?", rep, text)


def digits(s: str) -> str:
    return s.replace(",", "").replace(".", "")


def nums_in(text: str) -> list[str]:
    return NUM_RE.findall(text)


def sentence_around(article: str, evidence: str) -> str:
    i = article.find(evidence)
    if i < 0:
        return evidence
    a = article.rfind(". ", 0, i)
    b = article.find(". ", i + len(evidence))
    a = a + 1 if a >= 0 else 0
    b = b + 1 if b >= 0 else len(article)
    return article[a:b].strip()


def hamming1(a: str, b: str) -> bool:
    if len(a) != len(b) or not a:
        return False
    return sum(1 for x, y in zip(a, b, strict=True) if x != y) == 1


def _unit_of(text: str, num: str) -> str:
    j = text.find(num)
    tail = text[j + len(num):j + len(num) + 12].lower()
    m = re.match(r"\s*([a-z/°%.]{2,12})", tail)
    return m.group(1) if m else ""


def _is_year(d: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", d))


def unit_swap_test(prop: str, sentence: str) -> bool:
    """The proposition's number is a variant of the article's number:
    (i)  x10^k (k in 1..3), (ii) same digit count (>=3), hamming distance 1,
    excluding year-like 4-digit numbers, (iii) same number with a different
    adjacent unit word."""
    for p in nums_in(prop):
        pd = digits(p)
        for s in nums_in(sentence):
            sd = digits(s)
            if not pd or not sd:
                continue
            if pd == sd:
                if p != s and ("." in p) != ("." in s):
                    # same digits, decimal point moved (e.g. $57M vs $5.7M)
                    return True
                if (_unit_of(prop, p) and _unit_of(sentence, s)
                        and _unit_of(prop, p) != _unit_of(sentence, s)):
                    return True
                continue
            try:
                pf, sf = float(pd), float(sd)
            except ValueError:
                continue
            if pf and sf and (pf / sf in (10, 100, 1000) or sf / pf in (10, 100, 1000)):
                return True
            if _is_year(pd) or _is_year(sd):
                continue
            # single-digit perturbation (e.g. 77->37, July 20->10)
            if len(pd) >= 2 and len(pd) == len(sd) and hamming1(pd, sd):
                return True
            # digit transposition (e.g. 2922 -> 2299, 94 -> 49)
            if len(pd) >= 2 and len(pd) == len(sd) and sorted(pd) == sorted(sd):
                return True
            # digit drop (e.g. 123 -> 23, 1137 -> 113), one side not a year
            a, b = sorted((pd, sd), key=len)
            if (len(a) >= 2 and len(b) - len(a) <= 2
                    and _is_subseq(a, b)):
                return True
    return False


def _is_subseq(a: str, b: str) -> bool:
    it = iter(b)
    return all(ch in it for ch in a)


def figure_conflict_test(prop: str, article: str) -> bool:
    """The proposition pins a specific value the article does not state:
    (i)  a month+day or month+year date (normalized) absent from the article,
    (ii) a >=2-digit number absent from the article's number set,
    (iii) 'exactly N' (digit or word number), pinning exactness."""
    art_nums = {digits(n) for n in nums_in(article)}
    art_norm = norm_months(article)
    for dm in DATE_RE.finditer(prop):
        dn = re.escape(norm_months(dm.group(0)))
        if not re.search(dn + r"\b", art_norm):
            return True
    for yr in YEAR_RE.findall(prop):
        if not re.search(rf"\b{yr}\b", art_norm):
            return True
    for n in nums_in(prop):
        nd = digits(n)
        if len(nd) >= 2 and not _is_year(nd) and nd not in art_nums:
            return True
    if EXACTLY_RE.search(prop):
        return True
    return False


def polarity(prop: str) -> str:
    low = prop.lower()
    if NEG_RE.search(low) and not NEG_FALSE_POS.search(low):
        # a negation inside a double-quoted title does not negate the claim
        # (apostrophes are not quote delimiters: "agency's" must survive)
        stripped = re.sub(r'"[^"]*"', "", low)
        if NEG_RE.search(stripped):
            return "negative"
    return "affirmative"


def derive(corpus: Path, disputed: dict[str, list[str]]) -> tuple[dict, dict]:
    out: dict[str, list[dict]] = {}
    review: dict[str, list[str]] = {"unit_swap": [], "figure_conflict": [],
                                    "disputed_pin": [], "negative": []}
    for lbl in sorted((corpus / "labels").glob("*.json")):
        tid = lbl.stem
        recs = json.loads(lbl.read_text())
        article = (corpus / "articles" / f"{tid}.md").read_text()
        rows = []
        for r in recs:
            label = r["label"]
            fact_role = "silence" if label == "UNSPECIFIED" else "direct_fact"
            pol = polarity(r["proposition"])
            if tid in disputed and r["id"] in disputed[tid]:
                trap = "disputed_pin"
            elif label == "CONTRADICT" and r["evidence"] and unit_swap_test(
                r["proposition"], sentence_around(article, r["evidence"])
            ):
                trap = "unit_swap"
            elif label == "UNSPECIFIED" and figure_conflict_test(
                r["proposition"], article
            ):
                trap = "figure_conflict"
            else:
                trap = "none"
            rows.append({"id": r["id"], "fact_role": fact_role,
                         "trap_type": trap, "polarity": pol})
            key = trap if trap != "none" else None
            if key:
                review[key].append(f"{r['id']} | {r['proposition']}")
            if pol == "negative":
                review["negative"].append(f"{r['id']} | {r['proposition']}")
        out[tid] = rows
    return out, review


def main() -> None:
    mode = "v1" if "--v1" in sys.argv else "v2"
    corpus = REPO / ("corpus" if mode == "v1" else "corpus-v2")
    disputed: dict[str, list[str]] = {}
    if mode == "v1":
        # identity for the curated tag, so the backtest isolates the
        # mechanical rules (unit_swap / figure_conflict / polarity)
        curated = json.loads((REPO / "corpus" / "pool" / "metadata.json").read_text())
        disputed = {t: [r["id"] for r in rows if r["trap_type"] == "disputed_pin"]
                    for t, rows in curated.items()}
    if mode == "v2":
        # DISPUTED-toll notes in corpus-v2/topics.md: V2-020 (survived gate),
        # V2-077 (dropped by gate). Props pinning the disputed toll figures.
        disputed = {"V2-020": ["V2-020-001", "V2-020-017", "V2-020-018",
                               "V2-020-019", "V2-020-021", "V2-020-028",
                               "V2-020-029", "V2-020-040"]}
    meta, review = derive(corpus, disputed)
    if mode == "v1":
        curated = json.loads((REPO / "corpus" / "pool" / "metadata.json").read_text())
        import collections
        agree_tt = agree_po = tot = 0
        miss_us, fp_us, miss_fc, fp_fc, miss_dp, fp_dp = [], [], [], [], [], []
        for tid, rows in curated.items():
            mine = {r["id"]: r for r in meta[tid]}
            for r in rows:
                m = mine[r["id"]]
                tot += 1
                agree_tt += m["trap_type"] == r["trap_type"]
                agree_po += m["polarity"] == r["polarity"]
                if r["trap_type"] == "unit_swap" and m["trap_type"] != "unit_swap":
                    miss_us.append(f"{r['id']} | {mine[r['id']]['proposition'] if False else ''}")
                if m["trap_type"] == "unit_swap" and r["trap_type"] != "unit_swap":
                    fp_us.append(r["id"])
                if r["trap_type"] == "figure_conflict" and m["trap_type"] != "figure_conflict":
                    miss_fc.append(r["id"])
                if m["trap_type"] == "figure_conflict" and r["trap_type"] != "figure_conflict":
                    fp_fc.append(r["id"])
                if r["trap_type"] == "disputed_pin" and m["trap_type"] != "disputed_pin":
                    miss_dp.append(r["id"])
                if m["trap_type"] == "disputed_pin" and r["trap_type"] != "disputed_pin":
                    fp_dp.append(r["id"])
        print(f"v1 backtest: trap_type {agree_tt}/{tot} "
              f"({100*agree_tt/tot:.1f}%), polarity {agree_po}/{tot} "
              f"({100*agree_po/tot:.1f}%)")
        print(f"  unit_swap   missed {len(miss_us)} false-positives {len(fp_us)} {fp_us[:20]}")
        print(f"  fig_conflict missed {len(miss_fc)} {miss_fc} "
              f"false-positives {len(fp_fc)} {fp_fc}")
        print(f"  disputed_pin missed {len(miss_dp)} {miss_dp} "
              f"false-positives {len(fp_dp)} {fp_dp}")
        c = collections.Counter(m["trap_type"] for rows in meta.values() for m in rows)
        print("  derived dist:", dict(c))
        pc = collections.Counter(m["polarity"] for rows in meta.values() for m in rows)
        print("  polarity dist:", dict(pc))
    else:
        dest = corpus / "pool" / "metadata.json"
        dest.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {dest} ({sum(len(v) for v in meta.values())} props)")
        import collections
        c = collections.Counter(r["trap_type"] for rows in meta.values() for r in rows)
        print("trap dist:", dict(c))
        pc = collections.Counter(r["polarity"] for rows in meta.values() for r in rows)
        print("polarity dist:", dict(pc))
        for k in ("unit_swap", "figure_conflict", "disputed_pin", "negative"):
            print(f"\n== review {k} ({len(review[k])}) ==")
            for line in review[k]:
                print(" ", line)


if __name__ == "__main__":
    main()
