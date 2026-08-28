"""v2 jury run: 12 models x 200 articles x 40 items = 96,000 calls.

Adapted from tools/phase3/runner.py (v1 Phase 3 native run): same vote
schema, same strict JSON parsing, same resume mechanics. The prompt
template is read verbatim from prereg-v2.yaml at run time, so the runner
cannot drift from the registration.

Jury set (12 models):
  core (headline): 4 base zero-shot + 4 reason_included fine-tuned
  secondary:       4 votes_only fine-tuned

Call parameters are the frozen contract values: temperature 0,
max_tokens 512, thinking off where the model exposes a toggle
(qwen35-4b via chat_template_kwargs), one call per claim.

Usage (on helium):
  python3 tools/corpus_v2/jury_run.py \
      --repo /path/to/wave-consensus \
      --mapping /tmp/jury_mapping.json \
      --out /path/to/wave-consensus/corpus-v2/runs/<run-id> \
      [--models llama-3.2-3b-instruct, ...] \
      [--start-articles N]

The mapping file maps model name -> omlx port (JSON object), written at
launch time once the omlx instances are confirmed up.

Resume: re-run with the same --out; rows already present (and not
missing) are skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

HELIUM_HOST = "100.83.162.43"

FAMILIES = [
    "llama-3.2-3b-instruct",
    "gemma-3-4b-it",
    "phi-4-mini-instruct",
    "qwen35-4b",
]

# Core (headline) first so an interrupted run still has the 4 base + 4
# reason_included arms complete; votes_only secondary last.
MODELS_CORE = [
    "llama-3.2-3b-instruct",
    "gemma-3-4b-it",
    "phi-4-mini-instruct",
    "qwen35-4b",
    "llama-3.2-3b-instruct__reason_included",
    "gemma-3-4b-it__reason_included",
    "phi-4-mini-instruct__reason_included",
    "qwen35-4b__reason_included",
]
MODELS_SECONDARY = [
    "llama-3.2-3b-instruct__votes_only",
    "gemma-3-4b-it__votes_only",
    "phi-4-mini-instruct__votes_only",
    "qwen35-4b__votes_only",
]
MODELS_ALL = MODELS_CORE + MODELS_SECONDARY

TEMPERATURE = 0
MAX_TOKENS = 512  # frozen contract value
RETRIES = 3
TIMEOUT_S = 300

VARIANT_CONTRACT = "contract"

# Placeholder lines inside the registered contract template
# (prereg-v2.yaml). Identical to the v1 frozen contract except the path
# references name corpus-v2 and <id> (two ID families: V2-### and R##).
ARTICLE_PH = "{article text, verbatim from corpus-v2/articles/<id>.md}"
QUESTION_PH = "{claim in question form, verbatim from corpus-v2/pool/question_form/<id>.md}"


def extract_jury_contract(prereg_text: str) -> str:
    """Extract the jury_contract block from prereg-v2.yaml.

    The template lives as a literal block scalar under
    `  jury_contract: |` with 4-space continuation indent, exactly like
    the v1 prereg.yaml layout.
    """
    lines = prereg_text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip() == "jury_contract: |":
            idx = i
            break
    if idx is None:
        raise ValueError("jury_contract: | not found in prereg-v2.yaml")
    body = []
    for line in lines[idx + 1:]:
        if line and not line.startswith("    "):
            break  # next key at lower indent
        body.append(line[4:] if line.startswith("    ") else "")
    text = "\n".join(body)
    text = text.rstrip("\n")
    for ph in (ARTICLE_PH, QUESTION_PH):
        if ph not in text:
            raise ValueError(f"jury_contract block missing placeholder {ph!r}")
    return text


def parse_answer(completion: str):
    """Strict JSON parse of the whole completion.

    Accepts an optional single pair of code fences. answer must be
    exactly PASS / FAIL / NOT_STATED (case-insensitive). Otherwise
    (None, None).
    """
    if completion is None:
        return None, None
    s = completion.strip()
    if s.startswith("```"):
        s2 = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s2 = re.sub(r"\s*```$", "", s2)
        s = s2
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(obj, dict):
        return None, None
    a = obj.get("answer")
    if isinstance(a, str) and a.upper() in ("PASS", "FAIL", "NOT_STATED"):
        return a.upper(), obj.get("reason")
    return None, None


def build_payload(model: str, message: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }
    if "qwen" in model:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return payload


def ask(port: int, model: str, message: str):
    """One chat completion. Returns (completion, elapsed_s, attempts, err)
    where err is None on success or the last exception string after
    RETRIES failures (completion None)."""
    payload = build_payload(model, message)
    data = json.dumps(payload).encode()
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    last_err = ""
    for attempt in range(1, RETRIES + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = json.loads(resp.read().decode())
            completion = body["choices"][0]["message"]["content"]
            return completion, time.time() - t0, attempt, None
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
                IndexError, json.JSONDecodeError, TimeoutError) as e:
            last_err = repr(e)
            if attempt < RETRIES:
                time.sleep(3 * attempt)
    return None, time.time() - t0, RETRIES, last_err


def article_ids(repo: Path) -> list[str]:
    """The 200 corpus article IDs in manifest (frozen) order.

    IDs are two families: 179 primaries (V2-###) and 21 reserves (R##).
    """
    man = json.loads((repo / "corpus-v2" / "manifest.json").read_text())
    return [a["id"] for a in man["articles"]]


def load_article(corpus: Path, tid: str) -> str:
    text = (corpus / "articles" / f"{tid}.md").read_text()
    return text.rstrip("\n")


_QNUM = re.compile(r"^(\d+)\. (.+)$")


def load_question_form(corpus: Path, tid: str) -> list[str]:
    """40 question forms in pool order.

    Frozen rendering: header line, blank, then 40 numbered lines
    "N. <question>". The number prefix is stripped; the sent question
    is the line text verbatim ("Is it true that ...").
    """
    text = (corpus / "pool" / "question_form" / f"{tid}.md").read_text()
    out = []
    for line in text.splitlines():
        m = _QNUM.match(line)
        if m:
            out.append(m.group(2))
    if len(out) != 40:
        raise ValueError(f"{tid}: expected 40 numbered question lines, got {len(out)}")
    return out


def done_keys(out_path: Path) -> set[tuple[str, str, int]]:
    keys = set()
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("missing"):
                    continue
                keys.add((row["model"], row["article"], row["pool"]))
    return keys


def spend_state(out_dir: Path, model: str, done: int, total: int) -> None:
    p = out_dir / "spend_state.json"
    if p.exists():
        st = json.loads(p.read_text())
    else:
        st = {"models": {}}
    st["models"][model] = {"done": done, "total": total}
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    p.write_text(json.dumps(st, indent=2) + "\n")


def run_model(
    model: str,
    port: int,
    template: str,
    corpus: Path,
    out_dir: Path,
    ids: list[str],
    start_articles: int = 0,
) -> int:
    out_path = out_dir / "native" / f"{model}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys(out_path)
    tids = ids[start_articles:]
    total = len(tids) * 40
    n_done = 0
    n_missing = 0
    t_start = time.time()
    with out_path.open("a") as f:
        for tid in tids:
            art = load_article(corpus, tid)
            questions = load_question_form(corpus, tid)
            for ci, q in enumerate(questions, start=1):
                if (model, tid, ci) in done:
                    continue
                msg = template.replace(ARTICLE_PH, art)
                msg = msg.replace(QUESTION_PH, q)
                completion, elapsed, attempts, err = ask(port, model, msg)
                ans, reason = parse_answer(completion)
                missing = ans is None
                row = {
                    "id": f"{model}|{VARIANT_CONTRACT}|{tid}|{ci}",
                    "model": model,
                    "variant": VARIANT_CONTRACT,
                    "article": tid,
                    "pool": ci,
                    "question": q,
                    "answer": ans,
                    "reason": reason,
                    "parse": ans is not None,
                    "missing": missing,
                    "error": err,
                    "elapsed_s": round(elapsed, 3),
                    "attempts": attempts,
                }
                f.write(json.dumps(row) + "\n")
                n_done += 1
                if missing:
                    n_missing += 1
                if n_done % 200 == 0:
                    f.flush()
                    rate = n_done / max(time.time() - t_start, 1e-9)
                    eta = (total - len(done) - n_done) / max(rate, 1e-9)
                    print(
                        f"[{model}] {n_done}/{total} missing={n_missing} "
                        f"rate={rate:.2f}/s eta={eta / 60:.0f}m",
                        flush=True,
                    )
    print(
        f"[{model}] done: {n_done} new rows, {n_missing} missing, "
        f"{time.time() - t_start:.0f}s",
        flush=True,
    )
    # Record completed-row count for spend tracking.
    n_rows = 0
    with out_path.open() as f:
        for line in f:
            if line.strip():
                n_rows += 1
    spend_state(out_dir, model, n_rows, len(ids) * 40)
    return n_done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, help="wave-consensus repo root")
    ap.add_argument("--mapping", required=True, help="JSON file: model -> omlx port")
    ap.add_argument("--out", required=True, help="run output dir")
    ap.add_argument("--models", default="", help="comma list (default: all 12, core first)")
    ap.add_argument("--start-articles", type=int, default=0)
    ap.add_argument("--expect-articles", type=int, default=200,
                    help="corpus size check (200 for the frozen run)")
    args = ap.parse_args()

    repo = Path(args.repo)
    corpus = repo / "corpus-v2"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping = json.loads(Path(args.mapping).read_text())
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = MODELS_ALL
    for m in models:
        if m not in mapping:
            raise SystemExit(f"model {m} missing from mapping file")

    template = extract_jury_contract((repo / "prereg-v2.yaml").read_text())
    ids = article_ids(repo)
    if len(ids) != args.expect_articles:
        raise SystemExit(
            f"expected {args.expect_articles} corpus articles, got {len(ids)}"
        )

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    n_total = 0
    for m in models:
        n_total += run_model(m, int(mapping[m]), template, corpus, out_dir, ids,
                             args.start_articles)

    mpath = out_dir / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text())  # keep first started
    else:
        manifest = {"started": now, "invocations": []}
    manifest.update(
        {
            "finished": now,
            "host": HELIUM_HOST,
            "git": git_sha(repo),
            "mapping": {m: mapping[m] for m in models},
            "models_run_this_invocation": models,
            "params": {
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "thinking": "off where toggle exposed (qwen35-4b)",
                "retries": RETRIES,
                "timeout_s": TIMEOUT_S,
            },
            "template_source": "prereg-v2.yaml jury_contract block (verbatim)",
            "rows_written_this_invocation": n_total,
        }
    )
    manifest["invocations"].append({"at": now, "models": models, "rows": n_total})
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    print("manifest written", flush=True)


def git_sha(repo: Path) -> str:
    try:
        import subprocess

        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
