"""Node generation: sequential, cached, pinned models, one retry (REQUEST.md A1).

Claim A needs model-family *diversity*, not *concurrency* (protocol 0.3), so
calls are strictly sequential and cached. Async fan-out, k-of-N gather and
straggler handling are Claim B machinery and are deliberately not built here.

No silent model substitution: the resolved model id returned by the server is
recorded on every artifact, and a mismatch against the requested id is an error
rather than a note, because a substituted model would silently break the
independence structure the whole experiment is measuring.
"""
from __future__ import annotations

import os
import time

import httpx

from . import cache
from .schema import Generation, Item

LOCAL_BASE = os.environ.get("WCT_LOCAL_BASE", "http://localhost:1234/v1")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Panels are pinned. GOTCHAS.md records that deepseek-v4-flash fails to load and
# that ornith-35b / ornith-35b-mtp-apex are two variants of ONE family, so they
# must never be counted as independent sources.
LOCAL_PANEL = {
    "qwen": "thinkingcap-qwen3.6-27b",
    "laguna": "laguna-xs-2.1",
    "ornith": "ornith-1.0-35b",
}
LOCAL_SAME_FAMILY = {
    "ornith_a": "ornith-1.0-35b",
    "ornith_b": "ornith-1.0-35b",
    "ornith_c": "ornith-1.0-35b",
}

# Role prompts are an experimental FACTOR (defect D4), not a tuning knob. Three
# roles, rotated by Latin square so role is never confounded with agent.
ROLES = {
    "neutral": "",
    "forward": (
        "Work forwards from the given facts. Apply each rule whose conditions "
        "are fully met, state the new fact you derive, and continue until you "
        "can decide the statement."
    ),
    "backward": (
        "Work backwards from the statement. Identify what would have to be true "
        "for it to hold, then check whether those conditions can be established "
        "from the facts and rules."
    ),
    "skeptic": (
        "Assume the statement is not established until forced otherwise. For "
        "each step, name the specific rule and the specific facts that license "
        "it, and reject any step whose conditions are not all satisfied."
    ),
}

PROMPT = """You are given a set of facts and rules. Determine whether the statement follows.

FACTS AND RULES:
{theory}

STATEMENT: {question}

{role}

Reason step by step. State each intermediate fact you derive and the rule that
licenses it. Then end with exactly one line:

ANSWER: True
or
ANSWER: False
"""


def build_prompt(item: Item, role: str) -> str:
    return PROMPT.format(
        theory=item.theory, question=item.question, role=ROLES[role]
    ).strip()


def latin_square(agents: list[str], roles: list[str], index: int) -> dict[str, str]:
    """Rotate roles across agents so role is orthogonal to agent identity."""
    return {a: roles[(i + index) % len(roles)] for i, a in enumerate(agents)}


HOONIFY_BASE = "https://api.hoonify.ai/v1"


class Client:
    def __init__(self, backend: str = "local", timeout: float = 900.0):
        self.backend = backend
        if backend == "local":
            self.base, self.key = LOCAL_BASE, "not-needed"
        elif backend == "openrouter":
            self.base = OPENROUTER_BASE
            self.key = os.environ.get("OPENROUTER_API_KEY", "")
            if not self.key:
                raise RuntimeError(
                    "OPENROUTER_API_KEY is unset; the OpenRouter panel cannot run. "
                    "Set it, or run with backend='local'."
                )
        elif backend == "hoonify":
            # OpenAI-compatible paid GLM lane (v2 panel A'); endpoint and key
            # location are the owner's solon-harness [providers.hoonify] config.
            self.base = HOONIFY_BASE
            self.key = os.environ.get("HOONIFY_API_KEY", "")
            if not self.key:
                raise RuntimeError(
                    "HOONIFY_API_KEY is unset; the GLM lane cannot run. "
                    "It lives in ~/.config/solon/harness.env (exp.envfile loads it)."
                )
        else:
            raise ValueError(backend)
        self.http = httpx.Client(timeout=timeout)

    def generate(
        self,
        item: Item,
        agent: str,
        model: str,
        role: str,
        seed: int = 0,
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> Generation:
        prompt = build_prompt(item, role)
        key = cache.cache_key(
            item=item.item_id,
            backend=self.backend,
            model=model,
            role=role,
            prompt=prompt,
            seed=seed,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        hit = cache.get("generation", key)
        if hit is not None:
            return Generation(**hit)

        gen = self._call(item, agent, model, role, prompt, seed, temperature, max_tokens)
        # Failures are NOT cached. The cache is write-once, so persisting an
        # error would make a transient fault permanent: a 400 caused by the
        # server swapping models under contention would be frozen in as though
        # it were the model's answer, and no later re-run could ever repair it.
        # Only successful artifacts are immutable.
        if not gen.error:
            cache.put("generation", key, gen.__dict__)
        return gen

    def _call(self, item, agent, model, role, prompt, seed, temperature, max_tokens):
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        headers = {"Authorization": f"Bearer {self.key}"}
        last = ""
        # One recorded retry is the error-handling budget for a MODEL failure
        # (REQUEST.md). Rate limiting is not a model failure: a 429 says the
        # request was never served, so retrying it after a wait is resumption,
        # not a second sample. Those get their own longer backoff and do not
        # consume the model-failure budget.
        attempt = 0
        rate_waits = 0
        while attempt < 2:
            attempt += 1
            t0 = time.time()
            try:
                r = self.http.post(
                    f"{self.base}/chat/completions", json=body, headers=headers
                )
                if r.status_code == 429 or (
                    r.status_code == 200 and '"code": 429' in r.text[:400]
                ):
                    if rate_waits < 6:
                        rate_waits += 1
                        attempt -= 1
                        time.sleep(min(60, 5 * 2 ** (rate_waits - 1)))
                        continue
                r.raise_for_status()
                j = r.json()
                # OpenRouter can return a provider error inside an http 200,
                # so status alone is not enough to know the call succeeded
                if "error" in j and "choices" not in j:
                    code = (j["error"] or {}).get("code")
                    if code == 429 and rate_waits < 6:
                        rate_waits += 1
                        attempt -= 1
                        time.sleep(min(60, 5 * 2 ** (rate_waits - 1)))
                        continue
                    raise RuntimeError(f"provider error: {str(j['error'])[:200]}")
                msg = j["choices"][0]["message"]
                resolved = j.get("model", "")
                # Local ids carry no provider prefix, so exact equality is the
                # only honest check there; substring containment would wave
                # through an extension-substitution (qwen3.8-27b-instruct for
                # qwen3.8-27b). Remote providers echo provider-prefixed or
                # revision-suffixed ids, where containment of the model's own
                # name is the strongest portable test.
                if resolved:
                    ok = (resolved == model if self.backend == "local"
                          else model.split("/")[-1] in resolved)
                    if not ok:
                        raise RuntimeError(
                            f"model substitution: asked {model}, served {resolved}"
                        )
                return Generation(
                    item_id=item.item_id,
                    agent=agent,
                    model=model,
                    role=role,
                    content=msg.get("content") or "",
                    reasoning=msg.get("reasoning_content") or msg.get("reasoning") or "",
                    seed=seed,
                    temperature=temperature,
                    resolved_model=resolved,
                    provider=j.get("provider", self.backend),
                    usage=j.get("usage", {}) or {},
                    latency_s=round(time.time() - t0, 2),
                    attempt=attempt,
                )
            except Exception as e:  # recorded, not swallowed
                last = f"{type(e).__name__}: {e}"[:400]
                time.sleep(2.0)
        return Generation(
            item_id=item.item_id,
            agent=agent,
            model=model,
            role=role,
            content="",
            reasoning="",
            seed=seed,
            temperature=temperature,
            attempt=2,
            error=last,
        )
