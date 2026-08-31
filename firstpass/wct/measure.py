"""Measurement instruments: local embeddings for retrieval, CPU NLI for relations.

plan.md 3.1 "Measurement is not evidence" is the governing constraint here.
Embedding and NLI produce O(M^2) pairwise numbers from M model outputs; those
edges are NOT independent confirmations. Their only jobs are to align claim
instances into canonical propositions and to say whether a source affirms or
denies. Cosine is used for retrieval only and is never multiplied into the
evidence score.

Raw bidirectional probabilities are stored unthresholded so thresholds can be
frozen on calibration and varied in sensitivity analysis without re-running NLI.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import httpx
import numpy as np

from . import cache

LOCAL_BASE = os.environ.get("WCT_LOCAL_BASE", "http://localhost:1234/v1")
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
NLI_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
NLI_ALT = "cross-encoder/nli-deberta-v3-base"  # shared-judge robustness stack


def _h(texts: list[str]) -> str:
    return hashlib.sha256("\x00".join(texts).encode()).hexdigest()[:24]


def embed(texts: list[str], batch: int = 64) -> np.ndarray:
    """L2-normalised embeddings from the local Nomic endpoint, cached by content."""
    if not texts:
        return np.zeros((0, 768), dtype=np.float32)
    key = cache.cache_key(kind="embed", model=EMBED_MODEL, h=_h(texts), n=len(texts))
    hit = cache.get("embed", key)
    if hit is not None:
        return np.array(hit["vectors"], dtype=np.float32)

    out: list[list[float]] = []
    with httpx.Client(timeout=300) as c:
        for i in range(0, len(texts), batch):
            chunk = [t[:2000] or " " for t in texts[i : i + batch]]
            # The server holds ONE model slot. While a generation run is in
            # flight it intermittently 400s an embedding request mid-swap
            # (GOTCHAS.md). That is contention, not malformed input, so it is
            # retried rather than raised.
            for attempt in range(6):
                r = c.post(f"{LOCAL_BASE}/embeddings",
                           json={"model": EMBED_MODEL, "input": chunk})
                if r.status_code == 200:
                    break
                if attempt == 5:
                    r.raise_for_status()
                __import__("time").sleep(2 * (attempt + 1))
            out.extend(d["embedding"] for d in r.json()["data"])
    v = np.array(out, dtype=np.float32)
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    cache.put("embed", key, {"vectors": v.tolist()})
    return v


@lru_cache(maxsize=2)
def _nli(model_id: str):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(min(32, os.cpu_count() or 8))
    tok = AutoTokenizer.from_pretrained(model_id)
    mdl = AutoModelForSequenceClassification.from_pretrained(model_id).eval()
    # label order differs across NLI checkpoints; read it, never assume it
    id2label = {i: l.lower() for i, l in mdl.config.id2label.items()}
    return tok, mdl, id2label


def nli(pairs: list[tuple[str, str]], model_id: str = NLI_MODEL,
        batch: int = 64) -> np.ndarray:
    """P(entail), P(neutral), P(contradict) for each (premise, hypothesis).

    Returned columns are canonicalised to that order regardless of the
    checkpoint's own label indexing.

    Duplicate pairs are scored ONCE and broadcast back. Agents restating the
    same derived fact is the normal case here -- it is the very thing being
    measured -- so the raw pair list carries heavy repetition, and scoring it
    verbatim was the difference between hours and minutes on CPU. Deduplication
    is exact on the (premise, hypothesis) text, so it cannot change any result.
    """
    if not pairs:
        return np.zeros((0, 3), dtype=np.float32)
    key = cache.cache_key(kind="nli", model=model_id,
                          h=_h([f"{a}\x01{b}" for a, b in pairs]), n=len(pairs))
    hit = cache.get("nli", key)
    if hit is not None:
        return np.array(hit["probs"], dtype=np.float32)

    import torch

    uniq: dict[tuple[str, str], int] = {}
    inv = np.empty(len(pairs), dtype=np.int64)
    for i, p in enumerate(pairs):
        inv[i] = uniq.setdefault(p, len(uniq))
    todo = list(uniq)
    # longest-first batching keeps padding waste down on ragged inputs
    order = sorted(range(len(todo)), key=lambda i: -(len(todo[i][0]) + len(todo[i][1])))

    tok, mdl, id2label = _nli(model_id)
    cols = {}
    for i, lab in id2label.items():
        if lab.startswith("entail"):
            cols["e"] = i
        elif lab.startswith("neutral"):
            cols["n"] = i
        elif lab.startswith("contradict"):
            cols["c"] = i

    scored = np.zeros((len(todo), 3), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(order), batch):
            sel = order[i : i + batch]
            chunk = [todo[j] for j in sel]
            enc = tok([p for p, _ in chunk], [h for _, h in chunk],
                      return_tensors="pt", padding=True, truncation=True, max_length=256)
            probs = mdl(**enc).logits.softmax(-1).numpy()
            scored[sel] = probs[:, [cols["e"], cols["n"], cols["c"]]]

    out = scored[inv]
    cache.put("nli", key, {"probs": out.tolist()})
    return out


def top_k_pairs(claim_vecs: np.ndarray, prop_vecs: np.ndarray, k: int = 8):
    """Retrieval prefilter. Returns, per claim, the k nearest proposition indices.

    Cosine decides only WHICH pairs are worth an NLI call. It carries no
    evidential weight of its own.
    """
    if len(claim_vecs) == 0 or len(prop_vecs) == 0:
        return np.zeros((len(claim_vecs), 0), dtype=int)
    sim = claim_vecs @ prop_vecs.T
    k = min(k, prop_vecs.shape[0])
    return np.argpartition(-sim, k - 1, axis=1)[:, :k]
