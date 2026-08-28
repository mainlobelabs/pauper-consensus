#!/usr/bin/env python3
"""Build corpus-v2/manifest.json from topics.md + on-disk corpus + gate run.

Run: python3 tools/corpus_v2/make_manifest.py
Deterministic: sorted article list, stable JSON, no timestamps except the
frozen date literal below. Re-running on the same tree yields the same file
except the sha256 map (which is the point).
"""
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C = REPO / "corpus-v2"
FROZEN_DATE = "2026-08-28"
TAG = "prereg-waveconsensus-v2"

GATE_RUN = C / "gate/runs/2026-08-28"

# 4 families x {base, reason_included, votes_only}; seeds from the frozen
# Phase 4 recipe (cutoff-probe/runs/2026-08-27-phase4/phase4_recipe.json,
# commit 1273339).
JURY_FAMILIES = [
    ("llama-3.2-3b-instruct", "meta-llama/Llama-3.2-3B-Instruct", "Meta", 7),
    ("gemma-3-4b-it", "google/gemma-3-4b-it", "Google", 13),
    ("phi-4-mini-instruct", "microsoft/Phi-4-mini-instruct", "Microsoft", 42),
    ("qwen35-4b", "Qwen/Qwen3.5-4B", "Qwen", 99),
]
VARIANTS = ["base", "reason_included", "votes_only"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_topics():
    """Yield (id, month, date, topic, annotation, domain, fc) from topics.md."""
    text = (C / "topics.md").read_text()
    month = None
    for line in text.splitlines():
        m = re.match(r"^## (2026-\d{2}) ", line)
        if m:
            month = m.group(1)
            continue
        if line.startswith("## Reserve"):
            month = "reserve"
            continue
        if line.startswith("## "):
            month = None
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] in ("id", "") or set(cells[0]) <= {"-"}:
            continue
        rid, date, topic, annot, domain, fc = cells
        if not re.match(r"^(V2-\d{3}|R\d{2})$", rid):
            continue
        yield rid, month, date, topic, annot, domain, fc


def src_list(annot: str):
    m = re.search(r"\bsrc: (.+)$", annot)
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",")]


def main():
    gate = json.loads((GATE_RUN / "gate_summary.json").read_text())
    dropped = set(gate["primary_dropped"])
    res_contaminated = set(gate["reserve_contaminated"])

    articles = []
    for rid, month, date, topic, annot, domain, fc in parse_topics():
        afile = C / "articles" / f"{rid}.md"
        if not afile.exists():
            # on-disk corpus == gate-clean set; anything else must be dropped
            expect_drop = (rid in dropped) or (
                rid.startswith("R") and rid in res_contaminated
            )
            assert expect_drop, f"{rid}: no article file but not gate-dropped"
            continue
        lab = json.loads((C / "labels" / f"{rid}.json").read_text())
        counts = {}
        for row in lab:
            counts[row["label"]] = counts.get(row["label"], 0) + 1
        assert counts == {"ENTAIL": 20, "CONTRADICT": 10, "UNSPECIFIED": 10}, (rid, counts)
        entry = {
            "id": rid,
            "file": f"corpus-v2/articles/{rid}.md",
            "topic": topic,
            "event_date": date,
            "selection_month": month,
            "source_type": "portal-drafted",
            "source": {
                "name": "Wikipedia Portal:Current events (2026)",
                "role": "anchor",
                "factcheck_sources": src_list(annot),
            },
            "domain": domain,
            "verification": fc,
            "label_counts": counts,
            "split_role": "test",
            "sha256": sha256(afile),
        }
        if "DISPUTED" in annot:
            m = re.search(r"DISPUTED[^\]]*", annot)
            note = "DISPUTED-toll topic"
            if m is not None:
                note = re.split(r"\bsrc:", m.group(0))[0].strip()
            entry["disputed_note"] = note
        if rid.startswith("R"):
            entry["selection"] = "reserve (gate-clean)"
        articles.append(entry)

    articles.sort(key=lambda a: a["id"])
    on_disk = [a["id"] for a in articles]
    assert len(on_disk) == 200, len(on_disk)
    n_primary = sum(1 for i in on_disk if i.startswith("V2"))
    n_reserve = sum(1 for i in on_disk if i.startswith("R"))
    assert n_primary == 179 and n_reserve == 21, (n_primary, n_reserve)
    assert not (set(on_disk) & dropped), "gate-dropped primary on disk"
    assert not (set(on_disk) & res_contaminated), "contaminated reserve on disk"

    jury = {
        "selected": FROZEN_DATE,
        "solver": None,  # no solver in v2; the 27B defendant is a separate post-jury phase
        "rule": (
            "12 members = 4 base models (Phase 4 families) x 3 variants "
            "(base weights, reason_included fine-tune, votes_only fine-tune). "
            "Fine-tunes: frozen Phase 4 adapters, MLX LoRA rank 8 scale 20 "
            "dropout 0, fused weights. See recipe below."
        ),
        "recipe": {
            "file": "cutoff-probe/runs/2026-08-27-phase4/phase4_recipe.json",
            "git_hash": "1273339",
            "lora": {"rank": 8, "dropout": 0.0, "scale": 20.0, "iters": 200,
                     "learning_rate": 0.0001, "num_layers": 16, "max_seq_length": 2048},
        },
        "members": [
            {
                "id": f"{fam}__{v}" if v != "base" else fam,
                "base_model": model,
                "org": org,
                "variant": v,
                "seed": seed if v != "base" else None,
                "fused": v != "base",
            }
            for fam, model, org, seed in JURY_FAMILIES
            for v in VARIANTS
        ],
        "head": {
            "core": "64k calls = 200 x 40 x 8 (4 base + 4 reason_included)",
            "secondary": "32k calls = 200 x 40 x 4 (votes_only, pre-registered secondary arm)",
        },
    }

    metadata_file = C / "pool/metadata.json"
    generator = REPO / "tools/corpus_v2/make_metadata.py"
    mdist = {"trap_type": {}, "polarity": {}, "fact_role": {}}
    for rows in json.loads(metadata_file.read_text()).values():
        for r in rows:
            mdist["trap_type"][r["trap_type"]] = mdist["trap_type"].get(r["trap_type"], 0) + 1
            mdist["polarity"][r["polarity"]] = mdist["polarity"].get(r["polarity"], 0) + 1
            mdist["fact_role"][r["fact_role"]] = mdist["fact_role"].get(r["fact_role"], 0) + 1
    manifest = {
        "version": 2,
        "generated": FROZEN_DATE,
        "notes": (
            "Corpus v2 manifest: 200 topics = 179 gate-surviving primaries + "
            "21 gate-clean reserves (gate run 2026-08-28 dropped 72 primaries "
            "and 9 reserves; gate_summary.json final_corpus_size 179 counts "
            "primary survivors for the floor-160 check, clean reserves remain "
            "in the corpus). All articles are drafted from verbatim Wikipedia "
            "Current events portal strings (portals/*.txt) and fact-checked "
            "2026-08-27 (verification [V] or [V*]); source.role 'anchor' "
            "means the portal string was the fact-check anchor. 40 "
            "propositions per topic: 20 ENTAIL / 10 CONTRADICT / 10 "
            "UNSPECIFIED (corpus-v2/pool). All 200 topics are split_role "
            "test (v2 is pure test material; the full-bar covariate fit is "
            "frozen from v1, tag prereg-waveconsensus-v1). "
            "corpus-v2/pool/metadata.json is derived by the registered "
            "mechanical rule in tools/corpus_v2/make_metadata.py (backtest vs "
            "v1 curation: trap_type 91.8%, polarity 98.7% agreement); see "
            "prereg-v2.yaml metadata: for the full rule text. DISPUTED-toll "
            "topics keep their contested figures as proposition material "
            "(see disputed_note)."
        ),
        "window": "2026-02-15..2026-08-27 (Aug: 08-01..08-13 and 08-26..27)",
        "jury": jury,
        "gate": {
            "run": "corpus-v2/gate/runs/2026-08-28",
            "date": gate["date"],
            "panel": gate["panel"],
            "probes_total": gate["probes_total"],
            "canaries": gate["canaries"],
            "anchors": gate["anchors"],
            "row_overrides": gate["row_overrides"],
            "drop_rule": (
                "topic dropped if >=1 probe answered CORRECT by >=1 non-flagged "
                "panel model (self-knowledge contamination)"
            ),
            "primary_dropped": gate["primary_dropped"],
            "primary_survivors": gate["primary_survivors"],
            "reserve_contaminated": sorted(res_contaminated),
            "floor": gate["floor"],
            "post_gate": (
                "179 surviving primaries >= floor 160; 21 gate-clean reserves "
                "added to reach the 200-topic target (decision 2026-08-28, "
                "recorded in session memory; on-disk set == gate-clean set, "
                "verified at freeze)"
            ),
        },
        "recheck": {
            "date": "2026-08-28",
            "n": 800,
            "raw_agreement": "794/800 (99.25%)",
            "fresh_correct": "800/800 after in-class proposition replacement "
                             "(validator enforces 20/10/10)",
            "note": "self-consistency check of the frozen label set, not "
                    "inter-annotator agreement",
        },
        "articles": articles,
        "pool": {
            "propositions": "corpus-v2/labels/{id}.json (200 files, 8000 "
                            "propositions; the authoritative pool)",
            "render_text": "corpus-v2/pool/{id}.md (40 numbered propositions, "
                           "no labels; human-readable)",
            "render_question_form": "corpus-v2/pool/question_form/{id}.md "
                                    "(jury input, 'Is it true that ...?')",
            "per_file": "40 rows in pool position order: 1-20 ENTAIL, "
                        "21-30 CONTRADICT, 31-40 UNSPECIFIED",
        },
        "metadata": {
            "file": "corpus-v2/pool/metadata.json",
            "sha256": sha256(metadata_file),
            "generator": "tools/corpus_v2/make_metadata.py",
            "generator_sha256": sha256(generator),
            "distribution": mdist,
            "note": "polarity base rate differs from v1 (v2 negative 2.0% "
                    "vs v1 curation 18.5%): v2 pools were generated with "
                    "mostly affirmative variants; registered as a known "
                    "corpus property (prereg-v2.yaml).",
        },
        "frozen": {
            "date": FROZEN_DATE,
            "tag": TAG,
            "split": "all 200 topics test (no v2 calibration split)",
            "manifest_sha256_placeholder": True,
        },
    }

    out = C / "manifest.json"
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(articles)} articles, sha256 "
          f"{sha256(out)})")


if __name__ == "__main__":
    main()
