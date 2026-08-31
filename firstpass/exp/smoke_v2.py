"""R0 A2 smoke test for the v2 panels: every pinned endpoint answers.

Run BEFORE the v2 freeze tag; the printed table is the freeze evidence that
each pinned (backend, model) completes a generation with usable content and,
where applicable, a separated reasoning trace. One trivial call per endpoint.

Usage:  .venv/bin/python -m exp.smoke_v2
"""
from __future__ import annotations

import time

from exp.envfile import load_harness_env
from wct import nodes
from wct.schema import Item, Proposition

CANDIDATES = [
    # (label, backend, model, base_url, expected_resolved)
    # qwen serves on the :8083 llama-server under stale launch alias
    # 'ornith35'; GGUF identity verified (Qwen3.8-27B-Q4_K_M, 27.3B params)
    ("panelA'  qwen-local", "local", "qwen3.8-27b",
     "http://127.0.0.1:8083/v1", "ornith35"),
    ("panelA'  laguna-or ", "openrouter", "poolside/laguna-xs-2.1:free", None, None),
    ("panelA'  glm-hoon  ", "hoonify", "zai-org/GLM-5.2", None, None),
    ("panelB   nemotron  ", "openrouter", "nvidia/nemotron-3-super-120b-a12b:free", None, None),
    ("panelB   gptoss    ", "openrouter", "openai/gpt-oss-20b:free", None, None),
    ("panelB   gemma     ", "openrouter", "google/gemma-4-26b-a4b-it:free", None, None),
]

# A tiny throwaway theory: real prompt shape, not an experimental item, so the
# smoke test spends requests but no experimental content leaves the box beyond
# what the registered prompts will send anyway.
_PROBE = Item(
    item_id="SMOKE::Q1",
    theory="The cat is red. If something is red then it is bright.",
    question="The cat is bright.",
    answer="True",
    qdep=1,
    stratum="smoke",
    propositions=(Proposition(pid="SMOKE::Q1", text="The cat is bright.",
                              representation='("cat" "is" "bright" "+")',
                              answer="True", qdep=1, proof=""),),
    rules=("If something is red then it is bright.",),
)


def main() -> int:
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    picked = [c for c in CANDIDATES if only in c[0] or only in c[1]]
    if any(c[1] != "local" for c in picked):
        loaded = load_harness_env()
        print(f"env: loaded {len(loaded)} keys: {', '.join(loaded) or '(none new)'}")
    failures = 0
    for label, backend, model, base, expected in picked:
        t0 = time.time()
        try:
            client = nodes.Client(backend, timeout=180.0, base_url=base)
            g = client.generate(_PROBE, agent="smoke", model=model,
                                role="neutral", seed=1, temperature=0.7,
                                max_tokens=2000, expected_resolved=expected)
            el = time.time() - t0
            if g.error:
                print(f"FAIL {label} [{backend}] {model}: {g.error[:120]}")
                failures += 1
            else:
                print(f"ok   {label} [{backend}] {model}: "
                      f"content={len(g.content)}ch reasoning={len(g.reasoning)}ch "
                      f"answer_line={'ANSWER' in g.trace.upper()} {el:.1f}s "
                      f"resolved={g.resolved_model or model}")
        except Exception as e:  # noqa: BLE001 — smoke test reports, never raises
            print(f"FAIL {label} [{backend}] {model}: {type(e).__name__}: {str(e)[:120]}")
            failures += 1
    print(f"\n{len(picked) - failures}/{len(picked)} endpoints pass")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
