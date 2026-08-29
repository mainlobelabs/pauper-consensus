"""v2 hydrogen 27B phase: defendant + judge + full-corpus self-review.

Frozen contract (prereg-v2.yaml `defendant:` / `self_review:` blocks):
  - model qwen3.8-27b on marzuki-hydrogen vLLM port 8000
  - temperature 0, max_tokens 512, thinking off
  - defendant: 200 calls (one per article, up to 3 claims)
  - judge: one call per extracted claim (~<=600)
  - self-review: 8000 calls (every pool proposition, jury_contract)

All three prompt templates are read verbatim from prereg-v2.yaml at run
time, so the runner cannot drift from the registration.

Usage (on hydrogen):
  python tools/corpus_v2/phase27b.py \
      --repo /home/frank/research/wave-consensus \
      --out /home/frank/research/wave-consensus/runs/2026-08-29-v2-27b \
      --phase all   # or defendant | judge | selfreview

Resume: re-run with the same --out; (phase, key) rows already present and
not missing are skipped. Spend cap is cumulative across re-runs (persisted
in spend_state.json, hard stop at the registered cap).
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from jury_run import (  # noqa: E402  (same directory)
    RETRIES,
    TIMEOUT_S,
    article_ids,
    git_sha,
    load_article,
    load_question_form,
    parse_answer,
)

MODEL = "qwen3.8-27b"
PORT = 8000
HYDROGEN_HOST = "100.95.144.25"
SPEND_CAP = 10000  # prereg-v2.yaml spend_caps.qwen3_8_27b
MAX_TOKENS = 512
TEMPERATURE = 0

ARTICLE_PH = "{article text, verbatim from corpus-v2/articles/<id>.md}"
JUDGE_POOL_PH = "{the 40 pool propositions for <id>, numbered 1-40, verbatim}"
JUDGE_CLAIM_PH = "{one defendant claim}"
QUESTION_PH = "{claim in question form, verbatim from corpus-v2/pool/question_form/<id>.md}"

_CLAIM_LINE = re.compile(r"^\s*(\d+)[.)]\s*(.+?)\s*$")


def extract_block(prereg_text: str, header: str, placeholders: tuple[str, ...]) -> str:
    """Extract a `header: |` literal block (4-space continuation indent)."""
    lines = prereg_text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip() == f"{header}: |":
            idx = i
            break
    if idx is None:
        raise ValueError(f"{header}: | not found in prereg-v2.yaml")
    body = []
    for line in lines[idx + 1:]:
        if line and not line.startswith("    "):
            break
        body.append(line[4:] if line.startswith("    ") else "")
    text = "\n".join(body).rstrip("\n")
    for ph in placeholders:
        if ph not in text:
            raise ValueError(f"{header} block missing placeholder {ph!r}")
    return text


def load_pool_raw(corpus: Path, tid: str) -> str:
    """40 numbered pool propositions (pool/<id>.md) without header line."""
    lines = (corpus / "pool" / f"{tid}.md").read_text().splitlines()
    lines = [l for l in lines if re.match(r"^\d+\.\s", l)]
    if len(lines) != 40:
        raise ValueError(f"{tid}: expected 40 pool lines, got {len(lines)}")
    return "\n".join(lines)


def build_payload(message: str) -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def ask(message: str):
    """One chat completion. Returns (completion, usage, elapsed, attempts, err)."""
    data = json.dumps(build_payload(message)).encode()
    url = f"http://127.0.0.1:{PORT}/v1/chat/completions"
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
            usage = body.get("usage", {})
            return completion, usage, time.time() - t0, attempt, None
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
                IndexError, json.JSONDecodeError, TimeoutError) as e:
            last_err = repr(e)
            if attempt < RETRIES:
                time.sleep(3 * attempt)
    return None, {}, time.time() - t0, RETRIES, last_err


def strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s


def parse_defendant(completion: str):
    """Parse the defendant output: numbered list of 1-3 claims.

    Returns (claims, error). Claims are stripped sentence strings.
    """
    if completion is None:
        return None, "no completion"
    s = strip_fences(completion)
    claims = []
    for line in s.splitlines():
        m = _CLAIM_LINE.match(line)
        if m:
            claims.append(m.group(2).strip())
        if len(claims) >= 3:
            break
    if not claims:
        return None, f"no numbered claims parsed: {s[:120]!r}"
    return claims, None


def parse_judge(completion: str):
    """Strict JSON: {"supported": bool, "match_pool": 0-40, "reason": str}."""
    if completion is None:
        return None, "no completion"
    s = strip_fences(completion)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None, f"not JSON: {s[:120]!r}"
    if not isinstance(obj, dict):
        return None, "not an object"
    sup = obj.get("supported")
    mp = obj.get("match_pool")
    if not isinstance(sup, bool):
        return None, f"supported not bool: {sup!r}"
    if not isinstance(mp, int) or isinstance(mp, bool) or not (0 <= mp <= 40):
        return None, f"match_pool invalid: {mp!r}"
    reason = obj.get("reason")
    if not isinstance(reason, str):
        return None, f"reason not str: {reason!r}"
    return {"supported": sup, "match_pool": mp, "reason": reason}, None


class Spend:
    def __init__(self, out_dir: Path):
        self.path = out_dir / "spend_state.json"
        if self.path.exists():
            self.st = json.loads(self.path.read_text())
        else:
            self.st = {"model": MODEL, "cap": SPEND_CAP, "calls": 0}

    def check_and_charge(self) -> bool:
        if self.st["calls"] >= self.st["cap"]:
            return False
        self.st["calls"] += 1
        self.st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.path.write_text(json.dumps(self.st, indent=2) + "\n")
        return True

    def remaining(self) -> int:
        return self.st["cap"] - self.st["calls"]


def load_done(out_path: Path) -> set[str]:
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
                keys.add(row["id"])
    return keys


def base_row(phase: str, rid: str, article: str) -> dict:
    return {
        "id": rid,
        "phase": phase,
        "model": MODEL,
        "article": article,
        "answer": None,
        "missing": True,
        "error": None,
        "elapsed_s": None,
        "attempts": None,
        "usage": None,
    }


def run_defendant(repo: Path, corpus: Path, out_dir: Path, ids: list[str],
                  tpl: str, spend: Spend) -> None:
    out_path = out_dir / "defendant.jsonl"
    done = load_done(out_path)
    total = len(ids)
    n_new = 0
    n_missing = 0
    t0 = time.time()
    with out_path.open("a") as f:
        for tid in ids:
            if f"defendant|{tid}" in done:
                continue
            art = load_article(corpus, tid)
            msg = tpl.replace(ARTICLE_PH, art)
            if not spend.check_and_charge():
                print("SPEND CAP REACHED, stopping defendant phase", flush=True)
                return
            completion, usage, elapsed, attempts, err = ask(msg)
            claims, perr = parse_defendant(completion)
            missing = claims is None
            row = base_row("defendant", f"defendant|{tid}", tid)
            row.update(
                {
                    "claims": claims,
                    "n_claims": len(claims) if claims else 0,
                    "raw": completion,
                    "parse": not missing,
                    "missing": missing,
                    "error": err or perr,
                    "elapsed_s": round(elapsed, 3),
                    "attempts": attempts,
                    "usage": usage,
                }
            )
            f.write(json.dumps(row) + "\n")
            n_new += 1
            n_missing += missing
            if n_new % 20 == 0:
                f.flush()
                rate = n_new / max(time.time() - t0, 1e-9)
                eta = (total - len(done) - n_new) / max(rate, 1e-9)
                print(
                    f"[defendant] {n_new}/{total - len(done)} new "
                    f"missing={n_missing} rate={rate:.2f}/s "
                    f"eta={eta / 60:.0f}m cap_left={spend.remaining()}",
                    flush=True,
                )
    print(f"[defendant] done: {n_new} new rows, {n_missing} missing, {time.time() - t0:.0f}s",
          flush=True)


def run_judge(repo: Path, corpus: Path, out_dir: Path, ids: list[str],
              tpl: str, spend: Spend) -> None:
    def_path = out_dir / "defendant.jsonl"
    out_path = out_dir / "judge.jsonl"
    done = load_done(out_path)
    # collect (tid, k, claim) from parsed defendant rows, in article order
    items = []
    for tid in ids:
        if not def_path.exists():
            break
        with def_path.open() as f:
            for line in f:
                row = json.loads(line)
                if row["id"] != f"defendant|{tid}" or row.get("missing"):
                    continue
                for k, claim in enumerate(row["claims"], start=1):
                    items.append((tid, k, claim))
    n_new = 0
    n_missing = 0
    t0 = time.time()
    with out_path.open("a") as f:
        for tid, k, claim in items:
            rid = f"judge|{tid}|{k}"
            if rid in done:
                continue
            art = load_article(corpus, tid)
            msg = tpl.replace(ARTICLE_PH, art)
            msg = msg.replace(JUDGE_POOL_PH, load_pool_raw(corpus, tid))
            msg = msg.replace(JUDGE_CLAIM_PH, claim)
            if not spend.check_and_charge():
                print("SPEND CAP REACHED, stopping judge phase", flush=True)
                return
            completion, usage, elapsed, attempts, err = ask(msg)
            verdict, perr = parse_judge(completion)
            missing = verdict is None
            row = base_row("judge", rid, tid)
            row.update(
                {
                    "claim": claim,
                    "claim_idx": k,
                    "supported": verdict["supported"] if verdict else None,
                    "match_pool": verdict["match_pool"] if verdict else None,
                    "reason": verdict["reason"] if verdict else None,
                    "raw": completion,
                    "parse": not missing,
                    "missing": missing,
                    "error": err or perr,
                    "elapsed_s": round(elapsed, 3),
                    "attempts": attempts,
                    "usage": usage,
                }
            )
            f.write(json.dumps(row) + "\n")
            n_new += 1
            n_missing += missing
            if n_new % 25 == 0:
                f.flush()
                rate = n_new / max(time.time() - t0, 1e-9)
                eta = (len(items) - len(done) - n_new) / max(rate, 1e-9)
                print(
                    f"[judge] {n_new}/{len(items) - len(done)} new "
                    f"missing={n_missing} rate={rate:.2f}/s "
                    f"eta={eta / 60:.0f}m cap_left={spend.remaining()}",
                    flush=True,
                )
    print(f"[judge] done: {n_new} new rows, {n_missing} missing, {time.time() - t0:.0f}s",
          flush=True)


def run_selfreview(repo: Path, corpus: Path, out_dir: Path, ids: list[str],
                   tpl: str, spend: Spend) -> None:
    out_path = out_dir / "selfreview.jsonl"
    done = load_done(out_path)
    total = len(ids) * 40
    n_new = 0
    n_missing = 0
    t0 = time.time()
    with out_path.open("a") as f:
        for tid in ids:  # group by article: prefix-cache friendly
            art = load_article(corpus, tid)
            questions = load_question_form(corpus, tid)
            for ci, q in enumerate(questions, start=1):
                rid = f"selfreview|{tid}|{ci}"
                if rid in done:
                    continue
                msg = tpl.replace(ARTICLE_PH, art)
                msg = msg.replace(QUESTION_PH, q)
                if not spend.check_and_charge():
                    print("SPEND CAP REACHED, stopping selfreview phase", flush=True)
                    return
                completion, usage, elapsed, attempts, err = ask(msg)
                ans, reason = parse_answer(completion)
                missing = ans is None
                row = base_row("selfreview", rid, tid)
                row.update(
                    {
                        "pool": ci,
                        "question": q,
                        "answer": ans,
                        "reason": reason,
                        "raw": completion,
                        "parse": not missing,
                        "missing": missing,
                        "error": err,
                        "elapsed_s": round(elapsed, 3),
                        "attempts": attempts,
                        "usage": usage,
                    }
                )
                f.write(json.dumps(row) + "\n")
                n_new += 1
                n_missing += missing
                if n_new % 100 == 0:
                    f.flush()
                    rate = n_new / max(time.time() - t0, 1e-9)
                    eta = (total - len(done) - n_new) / max(rate, 1e-9)
                    print(
                        f"[selfreview] {n_new}/{total - len(done)} new "
                        f"missing={n_missing} rate={rate:.2f}/s "
                        f"eta={eta / 60:.0f}m cap_left={spend.remaining()}",
                        flush=True,
                    )
    print(f"[selfreview] done: {n_new} new rows, {n_missing} missing, {time.time() - t0:.0f}s",
          flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--phase", default="all",
                    choices=["all", "defendant", "judge", "selfreview"])
    args = ap.parse_args()

    repo = Path(args.repo)
    corpus = repo / "corpus-v2"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    prereg = (repo / "prereg-v2.yaml").read_text()
    tpl_defendant = extract_block(prereg, "prompt", (ARTICLE_PH,))
    tpl_judge = extract_block(prereg, "judge_prompt",
                              (ARTICLE_PH, JUDGE_POOL_PH, JUDGE_CLAIM_PH))
    tpl_selfreview = extract_block(prereg, "jury_contract", (ARTICLE_PH, QUESTION_PH))

    ids = article_ids(repo)
    if len(ids) != 200:
        raise SystemExit(f"expected 200 corpus articles, got {len(ids)}")

    spend = Spend(out_dir)
    print(f"phase={args.phase} cap_left={spend.remaining()} model={MODEL} port={PORT}",
          flush=True)

    if args.phase in ("all", "defendant"):
        run_defendant(repo, corpus, out_dir, ids, tpl_defendant, spend)
    if args.phase in ("all", "judge"):
        run_judge(repo, corpus, out_dir, ids, tpl_judge, spend)
    if args.phase in ("all", "selfreview"):
        run_selfreview(repo, corpus, out_dir, ids, tpl_selfreview, spend)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    mpath = out_dir / "manifest.json"
    manifest = {"started": now, "invocations": []}
    if mpath.exists():
        manifest = json.loads(mpath.read_text())
    manifest.update(
        {
            "finished": now,
            "host": HYDROGEN_HOST,
            "git": git_sha(repo),
            "model": MODEL,
            "port": PORT,
            "params": {
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "thinking": "off (chat_template_kwargs enable_thinking False)",
                "retries": RETRIES,
                "timeout_s": TIMEOUT_S,
                "concurrency": 1,
            },
            "template_source": "prereg-v2.yaml defendant/judge_prompt/jury_contract blocks (verbatim)",
            "invocation_phase": args.phase,
        }
    )
    manifest["invocations"].append({"at": now, "phase": args.phase})
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    print("manifest written", flush=True)


if __name__ == "__main__":
    main()
