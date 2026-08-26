"""Phase 3 zero-shot run runner (PLAN tasks 11-14).

Stdlib-only so it runs on the fleet without a venv.

Runs (one command each, resumable via --resume):

  smoke          one contract-format call per model (task 11)
  contamination  jurors on 20 seed questions, with and without the article
                 (task 12; test articles only)
  native         jurors under the frozen contract, 30 articles x 40 claims
                 (P4 zero-shot baseline, calibration baseline fit, and the
                 exact self-distillation targets captured before any adapter
                 exists)
  solver         27B on the 10 test articles: --mode baseline (plain answer
                 run, no prompt) or --mode self-review (with the frozen
                 contract prompt, one call per pool claim) (task 13)

Prompts are read verbatim from prereg.yaml at run time, so the runner cannot
drift from the registration. tests/test_phase3_runner.py pins the extraction
against a YAML parse.

Output per run: <out>/<run>/<model>.jsonl (one record per call, raw output
kept), <out>/<run>/manifest.json, spend_state.json (persisted call caps), and
contamination.json (flag table) for run=contamination.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"
DEFAULT_RUNS = Path(os.environ.get("WAVE_RUNS_DIR", "/Volumes/nvme0/wave-consensus/runs"))

JURORS = [
    "llama-3.2-1b-instruct",
    "gemma-3-1b-it",
    "phi-4-mini-instruct",
    "olmoe-0125-instruct",
    "qwen35-4b",
]
SOLVER = "qwen3.8-27b"
# Override with WAVE_OMLX_URL when the juror server is not on 8100 (e.g.
# Andryo's managed omlx server occupies 8100 and the phase 3 serve is on
# 8101).
OMLX_URL = os.environ.get("WAVE_OMLX_URL", "http://127.0.0.1:8100")
VLLM_URL = "http://100.95.144.25:8000"
SPEND_CAP = 5000
MAX_TOKENS_CONTRACT = 512
MAX_TOKENS_BASELINE = 4096
# Families whose chat template exposes a thinking toggle (per prereg.yaml).
THINKING_TOGGLE = {"qwen3.8-27b", "qwen35-4b"}

ARTICLE_PH = "{article text, verbatim from corpus/articles/T##.md}"
CLAIM_PH = "{claim in question form, verbatim from corpus/pool/question_form/T##.md}"

MONTHS = (
    "January February March April May June July August September October November December"
).split()
NAME_STOP = {
    "The",
    "A",
    "An",
    "In",
    "On",
    "At",
    "Of",
    "For",
    "And",
    "Or",
    "But",
    "To",
    "From",
    "By",
    "With",
    "As",
    "Is",
    "Are",
    "Was",
    "Were",
    "Be",
}

_jsonl_lock = threading.Lock()


# ---------------------------------------------------------------- corpus


def load_manifest() -> dict:
    return json.loads((CORPUS / "manifest.json").read_text())


def article_ids_by_split() -> dict[str, list[str]]:
    man = load_manifest()
    out: dict[str, list[str]] = {"train": [], "calibration": [], "test": []}
    for a in man["articles"]:
        out[a["split_role"]].append(a["id"])
    for ids in out.values():
        ids.sort()
    return out


def read_article(tid: str) -> str:
    return (CORPUS / "articles" / f"{tid}.md").read_text()


def read_numbered(path: Path) -> list[str]:
    """Parse 'N. text' lines into a list indexed 0..N-1."""
    items: list[str] = []
    for line in path.read_text().splitlines():
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            n = int(m.group(1))
            while len(items) < n:
                items.append("")
            items[n - 1] = m.group(2).strip()
    return items


def read_questions(tid: str) -> list[str]:
    return read_numbered(CORPUS / "questions" / f"{tid}.md")


def read_question_form(tid: str) -> list[str]:
    return read_numbered(CORPUS / "pool" / "question_form" / f"{tid}.md")


def read_labels(tid: str) -> dict[str, str]:
    raw = json.loads((CORPUS / "labels" / f"{tid}.json").read_text())
    return {r["id"]: r["label"] for r in raw}


def read_metadata(tid: str) -> list[dict]:
    md = json.loads((CORPUS / "pool" / "metadata.json").read_text())
    return md[tid]


def _read_label_records(tid: str) -> list[dict]:
    return json.loads((CORPUS / "labels" / f"{tid}.json").read_text())


def contamination_targets_by_question(tid: str) -> dict[int, dict | None]:
    """q number -> merged fact targets of the ENTAIL proposition(s) seeded
    into it. None where the question seeds no ENTAIL proposition."""
    labels = read_labels(tid)
    props = {r["id"]: r["proposition"] for r in _read_label_records(tid)}
    out: dict[int, dict | None] = {}
    for r in read_metadata(tid):
        for q in r["seeded_by"]:
            if labels.get(r["id"]) != "ENTAIL":
                continue
            t = extract_targets(props[r["id"]])
            cur = out.get(q)
            if cur is None:
                out[q] = t
            else:
                cur["numbers"] = sorted(set(cur["numbers"]) | set(t["numbers"]))
                cur["month_day"] = sorted(set(cur["month_day"]) | set(t["month_day"]))
                cur["names"] = sorted(set(cur["names"]) | set(t["names"]))
    return out


# ---------------------------------------------------------------- prompts


def frozen_template(kind: str) -> str:
    """Extract the block scalar for `kind` from prereg.yaml (4-space indent)."""
    lines = (REPO / "prereg.yaml").read_text().splitlines()
    out: list[str] = []
    in_block = False
    for line in lines:
        if in_block:
            if line.startswith("    "):
                out.append(line[4:])
                continue
            if line.strip() == "":
                out.append("")
                continue
            break
        if line.rstrip() == f"  {kind}: |":
            in_block = True
    if not in_block:
        raise ValueError(f"template {kind!r} not found in prereg.yaml")
    return "\n".join(out).rstrip("\n") + "\n"


def jury_prompt(article: str, claim: str) -> str:
    return (
        frozen_template("jury_contract")
        .replace(ARTICLE_PH, article.rstrip("\n"))
        .replace(CLAIM_PH, claim.rstrip("\n"))
    )


def solver_baseline_prompt(article: str, questions: list[str]) -> str:
    t = frozen_template("solver_baseline")
    out = []
    for line in t.splitlines():
        m = re.match(r"^(\d+)\.\s+\{question \d+[^}]*\}\s*$", line)
        if m:
            out.append(f"{int(m.group(1))}. {questions[int(m.group(1)) - 1]}")
        elif line.strip() == "...":
            continue
        else:
            out.append(line)
    return "\n".join(out).replace(ARTICLE_PH, article.rstrip("\n")).rstrip("\n") + "\n"


def contamination_prompt(article: str, question: str, with_article: bool) -> str:
    head = "Answer this question only based on the information available on this\narticle."
    if not with_article:
        return head + "\n\n" + question.rstrip("\n") + "\n"
    return (
        head
        + "\n\n<article>\n"
        + article.rstrip("\n")
        + "\n</article>\n\n"
        + question.rstrip("\n")
        + "\n"
    )


# ---------------------------------------------------------------- http


def _post_chat(base_url: str, body: dict, timeout: int) -> dict:
    """One streamed chat-completion call."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    ttft: float | None = None
    chunks: list[str] = []
    usage: dict | None = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if payload == "[DONE]":
                break
            obj = json.loads(payload)
            choice = (obj.get("choices") or [{}])[0]
            delta = choice.get("delta") or choice.get("message") or {}
            piece = delta.get("content")
            if piece:
                if ttft is None:
                    ttft = time.monotonic() - t0
                chunks.append(piece)
            if obj.get("usage"):
                usage = obj["usage"]
    latency = time.monotonic() - t0
    return {
        "raw": "".join(chunks),
        "usage": usage,
        "latency_ms": round(latency * 1000, 1),
        "ttft_ms": round(ttft * 1000, 1) if ttft is not None else None,
    }


def ask(
    base_url: str,
    model: str,
    user_message: str,
    max_tokens: int = MAX_TOKENS_CONTRACT,
    timeout: int = 300,
    attempts: int = 3,
) -> dict:
    """Call a chat endpoint with retries. thinking off where the template has a toggle."""
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if model in THINKING_TOGGLE:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            out = _post_chat(base_url, body, timeout)
            out["attempts"] = i + 1
            return out
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 408:
                raise
            last_err = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
        time.sleep(5 * (3**i))
    raise RuntimeError(f"ask failed after {attempts} attempts: {last_err}")


def parse_contract(raw: str) -> dict | None:
    """Strict contract parse: single JSON object, answer in the closed set."""
    s = raw.strip()
    m = re.match(r"^```(?:json)?\s*(\{.*\})\s*```$", s, re.S)
    if m:
        s = m.group(1)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    ans = str(obj.get("answer", "")).strip().upper()
    if ans not in {"PASS", "FAIL", "NOT_STATED"}:
        return None
    return {"answer": ans, "reason": str(obj.get("reason", ""))}


# ---------------------------------------------------------------- spend


class Spend:
    """Persisted per-model cumulative call counter, capped at SPEND_CAP."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.state: dict[str, int] = {}
        if path.exists():
            self.state = json.loads(path.read_text())

    def check_and_add(self, model: str) -> None:
        n = self.state.get(model, 0) + 1
        if n > SPEND_CAP:
            raise RuntimeError(f"spend cap exceeded for {model} ({n} > {SPEND_CAP})")
        self.state[model] = n
        self.path.write_text(json.dumps(self.state, sort_keys=True) + "\n")


# ---------------------------------------------------------------- records


def weight_hashes(model_dir: Path) -> dict[str, str]:
    out = {}
    for f in sorted(model_dir.glob("*.safetensors")):
        h = hashlib.sha256()
        with f.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        out[f.name] = h.hexdigest()
    return out


def endpoint_info(base_url: str) -> dict:
    try:
        with urllib.request.urlopen(base_url + "/v1/models", timeout=10) as r:
            models = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        models = {"error": str(e)}
    info: dict = {"models": models}
    try:
        with urllib.request.urlopen(base_url + "/version", timeout=10) as r:
            info["version"] = json.loads(r.read())
    except Exception:  # noqa: BLE001
        pass
    return info


def new_manifest(run: str, out: Path, extra: dict) -> dict:
    man = {
        "run": run,
        "started_utc": datetime.now(UTC).isoformat(),
        "host": socket.gethostname(),
        "runner_git": os.environ.get("WAVE_GIT_HASH", "unknown"),
        "command": " ".join(sys.argv),
        **extra,
    }
    (out / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
    return man


def finish_manifest(out: Path, man: dict, stats: dict) -> None:
    man["finished_utc"] = datetime.now(UTC).isoformat()
    man["stats"] = stats
    (out / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")


def open_jsonl(path: Path, resume: bool) -> tuple:
    """Open a run JSONL (append on resume, truncate otherwise). Returns
    (file, set of done keys)."""
    done: set[tuple] = set()
    if resume and path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            done.add((r["model"], r["article"], str(r["item"]), r["variant"]))
    mode = "a" if resume and path.exists() else "w"
    return path.open(mode), done


# ---------------------------------------------------------------- runners


def base_url_for(model: str) -> str:
    return VLLM_URL if model == SOLVER else OMLX_URL


def run_smoke(args: argparse.Namespace) -> None:
    out = Path(args.out) / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    models = [SOLVER] + JURORS
    man = new_manifest(
        "smoke",
        out,
        {
            "models": {m: base_url_for(m) for m in models},
            "purpose": "task 11: one real contract call per model before any phase 3 run",
            "endpoints": {
                OMLX_URL: endpoint_info(OMLX_URL),
                VLLM_URL: endpoint_info(VLLM_URL),
            },
        },
    )
    spend = Spend(out / "spend_state.json")
    tid = "T01"
    article = read_article(tid)
    claim = read_question_form(tid)[0]
    prompt = jury_prompt(article, claim)
    records = []
    for m in models:
        res = ask(base_url_for(m), m, prompt)
        spend.check_and_add(m)
        rec = {
            "model": m,
            "endpoint": base_url_for(m),
            "article": tid,
            "item": 1,
            "variant": "contract",
            "prompt": prompt,
            "raw": res["raw"],
            "parsed": parse_contract(res["raw"]),
            "usage": res["usage"],
            "latency_ms": res["latency_ms"],
            "ttft_ms": res["ttft_ms"],
            "attempts": res["attempts"],
            "ts": datetime.now(UTC).isoformat(),
        }
        records.append(rec)
        print(json.dumps({"model": m, "parsed": rec["parsed"]}), flush=True)
    (out / "smoke.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
    finish_manifest(
        out,
        man,
        {
            "n_calls": len(records),
            "parsed_ok": sum(1 for r in records if r["parsed"]),
            "spend": spend.state,
        },
    )
    print(f"smoke done: {sum(1 for r in records if r['parsed'])}/{len(records)} parsed")


def extract_targets(text: str) -> dict:
    """Deterministic fact targets from a proposition: numbers, month-day pairs,
    multi-word capitalized names."""
    norm = text.replace(",", "")
    numbers = sorted(set(re.findall(r"\d+(?:\.\d+)?%?", norm)))
    month_day = sorted(set(re.findall(r"(?i)(" + "|".join(MONTHS) + r")\s+(\d{1,2})\b", text)))
    names: set[str] = set()
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
        words = m.group(1).split()
        if words[0] in NAME_STOP:
            continue
        names.add(" ".join(words).lower())
    return {"numbers": numbers, "month_day": month_day, "names": sorted(names)}


def answer_hits_targets(answer: str, targets: dict) -> bool:
    a_norm = answer.replace(",", "").lower()
    for n in targets["numbers"]:
        if re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", a_norm):
            return True
    for month, day in targets["month_day"]:
        if f"{month.lower()} {day}" in a_norm:
            return True
    for name in targets["names"]:
        if name in answer.lower():
            return True
    return False


def _execute(
    work: list[tuple],
    task_fn,
    model_of,
    spend: Spend,
    writers: dict[str, object],
    label: str,
) -> dict:
    counts = {"calls": 0, "parsed": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len({model_of(w) for w in work})) as ex:
        futs = {ex.submit(task_fn, w): w for w in work}
        for fut in concurrent.futures.as_completed(futs):
            rec = fut.result()
            spend.check_and_add(rec["model"])
            counts["calls"] += 1
            counts["parsed"] += 1 if rec.get("parsed") else 0
            with _jsonl_lock:
                writers[rec["model"]].write(json.dumps(rec) + "\n")
                writers[rec["model"]].flush()
            if counts["calls"] % 200 == 0:
                print(f"  {label} {counts['calls']}/{len(work)}", flush=True)
    for fh in writers.values():
        fh.close()
    return counts


def run_contamination(args: argparse.Namespace) -> None:
    out = Path(args.out) / "contamination"
    out.mkdir(parents=True, exist_ok=True)
    tids = article_ids_by_split()["test"]
    man = new_manifest(
        "contamination",
        out,
        {
            "purpose": "task 12: parametric memory check, test articles, "
            "before any fine-tuned output exists",
            "models": {m: OMLX_URL for m in JURORS},
            "articles": tids,
            "design": "20 seed questions per article, with and without the "
            "article; flag = without-article answer contains a fact target "
            "extracted from the ENTAIL proposition seeded into that question",
            "endpoints": {OMLX_URL: endpoint_info(OMLX_URL)},
        },
    )
    spend = Spend(out / "spend_state.json")
    writers: dict[str, object] = {}
    done: set[tuple] = set()
    for m in JURORS:
        fh, d = open_jsonl(out / f"{m}.jsonl", args.resume)
        writers[m] = fh
        done |= d
    targets = {tid: contamination_targets_by_question(tid) for tid in tids}
    work = [
        (m, tid, q, va)
        for m in JURORS
        for tid in tids
        for q in range(1, 21)
        for va in (True, False)
        if (m, tid, str(q), f"q{q}_{'with' if va else 'without'}") not in done
    ]
    print(f"contamination: {len(work)} calls to make ({len(done)} already done)")

    def task(item: tuple) -> dict:
        m, tid, q, va = item
        question = read_questions(tid)[q - 1]
        prompt = contamination_prompt(read_article(tid), question, with_article=va)
        res = ask(OMLX_URL, m, prompt)
        t = targets[tid].get(q)
        flag = (not va) and t is not None and answer_hits_targets(res["raw"], t)
        rec = {
            "model": m,
            "endpoint": OMLX_URL,
            "article": tid,
            "item": q,
            "variant": f"q{q}_{'with' if va else 'without'}",
            "prompt": prompt,
            "raw": res["raw"],
            "targets": t,
            "flag": flag,
            "usage": res["usage"],
            "latency_ms": res["latency_ms"],
            "ttft_ms": res["ttft_ms"],
            "attempts": res["attempts"],
            "ts": datetime.now(UTC).isoformat(),
        }
        return rec

    counts = _execute(work, task, lambda w: w[0], spend, writers, "contamination")
    table = {}
    for m in JURORS:
        rows = [
            json.loads(line)
            for line in (out / f"{m}.jsonl").read_text().splitlines()
            if line.strip()
        ]
        flagged = [r for r in rows if r.get("flag")]
        table[m] = {
            "n_calls": len(rows),
            "n_flagged_without_article": len(flagged),
            "flags": [
                {"article": r["article"], "question": r["item"], "raw": r["raw"][:400]}
                for r in flagged
            ],
        }
    (out / "contamination.json").write_text(json.dumps(table, indent=2) + "\n")
    finish_manifest(out, man, {"n_calls": counts["calls"], "spend": spend.state, "flags": table})
    for m, t in table.items():
        print(f"{m}: {t['n_flagged_without_article']} flagged")


def run_native(args: argparse.Namespace) -> None:
    out = Path(args.out) / "native"
    out.mkdir(parents=True, exist_ok=True)
    splits = article_ids_by_split()
    tids = (
        splits["train"] + splits["calibration"] + splits["test"]
        if args.split == "all"
        else splits[args.split]
    )
    man = new_manifest(
        "native",
        out,
        {
            "purpose": "zero-shot native outputs under the frozen contract; "
            "train = self-distillation targets, calibration = baseline fit + "
            "losslessness base, test = P4 zero-shot baseline",
            "models": {m: OMLX_URL for m in JURORS},
            "split": args.split,
            "articles": tids,
            "endpoints": {OMLX_URL: endpoint_info(OMLX_URL)},
        },
    )
    spend = Spend(out / "spend_state.json")
    writers: dict[str, object] = {}
    done: set[tuple] = set()
    for m in JURORS:
        fh, d = open_jsonl(out / f"{m}.jsonl", args.resume)
        writers[m] = fh
        done |= d
    work = [
        (m, tid, i)
        for m in JURORS
        for tid in tids
        for i in range(1, 41)
        if (m, tid, str(i), "contract") not in done
    ]
    print(f"native: {len(work)} calls to make ({len(done)} already done)")

    def task(item: tuple) -> dict:
        m, tid, i = item
        prompt = jury_prompt(read_article(tid), read_question_form(tid)[i - 1])
        res = ask(OMLX_URL, m, prompt)
        return {
            "model": m,
            "endpoint": OMLX_URL,
            "article": tid,
            "item": i,
            "variant": "contract",
            "prompt": prompt,
            "raw": res["raw"],
            "parsed": parse_contract(res["raw"]),
            "usage": res["usage"],
            "latency_ms": res["latency_ms"],
            "ttft_ms": res["ttft_ms"],
            "attempts": res["attempts"],
            "ts": datetime.now(UTC).isoformat(),
        }

    counts = _execute(work, task, lambda w: w[0], spend, writers, "native")
    finish_manifest(
        out,
        man,
        {
            "n_calls": counts["calls"],
            "parsed_ok": counts["parsed"],
            "spend": spend.state,
        },
    )
    print(f"native done: {counts['calls']} calls, parse {counts['parsed']}/{counts['calls']}")


def run_solver(args: argparse.Namespace) -> None:
    run_name = "solver-baseline" if args.mode == "baseline" else "self-review"
    out = Path(args.out) / run_name
    out.mkdir(parents=True, exist_ok=True)
    tids = article_ids_by_split()["test"]
    man = new_manifest(
        run_name,
        out,
        {
            "purpose": (
                "task 13: 27B null control on test articles (plain answer run)"
                if args.mode == "baseline"
                else "task 13: 27B with frozen contract on test articles "
                "(doubles as solver-as-proposer arm)"
            ),
            "model": SOLVER,
            "endpoint": VLLM_URL,
            "split": "test",
            "articles": tids,
            "max_tokens": MAX_TOKENS_BASELINE if args.mode == "baseline" else MAX_TOKENS_CONTRACT,
            "endpoints": {VLLM_URL: endpoint_info(VLLM_URL)},
        },
    )
    spend = Spend(out / "spend_state.json")
    fh, done = open_jsonl(out / f"{SOLVER}.jsonl", args.resume)
    work = []
    if args.mode == "baseline":
        work = [(tid, 0) for tid in tids if (SOLVER, tid, "0", "baseline") not in done]
    else:
        work = [
            (tid, i)
            for tid in tids
            for i in range(1, 41)
            if (SOLVER, tid, str(i), "contract") not in done
        ]
    print(f"solver {args.mode}: {len(work)} calls to make ({len(done)} already done)")

    def task(item: tuple) -> dict:
        tid, i = item
        if args.mode == "baseline":
            prompt = solver_baseline_prompt(read_article(tid), read_questions(tid))
            variant, mt, parsed = "baseline", MAX_TOKENS_BASELINE, None
        else:
            prompt = jury_prompt(read_article(tid), read_question_form(tid)[i - 1])
            variant, mt = "contract", MAX_TOKENS_CONTRACT
            parsed = None  # filled below
        res = ask(VLLM_URL, SOLVER, prompt, max_tokens=mt)
        if args.mode == "self-review":
            parsed = parse_contract(res["raw"])
        return {
            "model": SOLVER,
            "endpoint": VLLM_URL,
            "article": tid,
            "item": i,
            "variant": variant,
            "prompt": prompt,
            "raw": res["raw"],
            "parsed": parsed,
            "usage": res["usage"],
            "latency_ms": res["latency_ms"],
            "ttft_ms": res["ttft_ms"],
            "attempts": res["attempts"],
            "ts": datetime.now(UTC).isoformat(),
        }

    counts = _execute(work, task, lambda w: SOLVER, spend, {SOLVER: fh}, "solver")
    finish_manifest(
        out,
        man,
        {"n_calls": counts["calls"], "parsed_ok": counts["parsed"], "spend": spend.state},
    )
    print(f"solver {args.mode} done: {counts['calls']} calls")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", choices=["smoke", "contamination", "native", "solver"])
    p.add_argument("--out", default=str(DEFAULT_RUNS / "2026-08-26-phase3"))
    p.add_argument("--split", default="all", choices=["all", "train", "calibration", "test"])
    p.add_argument("--mode", default="baseline", choices=["baseline", "self-review"])
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    if args.run == "smoke":
        run_smoke(args)
    elif args.run == "contamination":
        run_contamination(args)
    elif args.run == "native":
        run_native(args)
    elif args.run == "solver":
        run_solver(args)


if __name__ == "__main__":
    main()
