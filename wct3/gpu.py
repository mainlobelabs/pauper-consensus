"""GPU-resident NLI for new cycles. NOT cache-compatible with cycles 1-2.

wct/measure.py is pinned byte-clean by the prereg-v2 tag, so the CUDA path
cannot live there. This module re-implements measure.nli's algorithm exactly --
same exact-pair dedup, same longest-first batching, same canonical
(entail, neutral, contradict) column order, same cache key -- and changes two
things: where the forward pass runs, and the precision it runs at.

The precision change is the important one, and it was not the original intent.
This checkpoint's config declares dtype=float16, and transformers honours that
on CPU as well as GPU, so cycles 1-2 were computed in fp16 rather than fp32.
Measured on 800 corpus pairs:

    cpu/fp32 vs gpu/fp32    7.8e-06   0 argmax flips
    cpu/fp16 vs gpu/fp16    4.4e-03   1 argmax flip
    cpu/fp16 vs cpu/fp32    3.8e-03   0 argmax flips

fp16 is device DEPENDENT: porting it to GPU as-is would silently make results a
function of which card ran them. fp32 is device independent to 7.8e-6, and on
CPU it is also 2.7x faster than fp16 (114.7 vs 43.2 pairs/sec) because CPUs
emulate fp16 rather than implementing it.

So fp32 is the right instrument, but it differs systematically from the cached
fp16 values (3.8e-3). Those two must never be mixed inside one analysis: point
WCT_CACHE at a separate root for a GPU cycle, which keeps that cycle internally
consistent and leaves the frozen cycles byte-identical.
"""
from __future__ import annotations

import os
import time

import numpy as np

from wct import cache, measure

_STATE: dict[str, object] = {}


def pick_device() -> str:
    """Pick the GPU with the most free memory, or CPU if CUDA is unavailable."""
    import torch

    if not torch.cuda.is_available():
        return "cpu"
    free = []
    for i in range(torch.cuda.device_count()):
        f, _ = torch.cuda.mem_get_info(i)
        free.append((f, i))
    return f"cuda:{max(free)[1]}"


def _exact_fp32() -> None:
    """Disable TF32 so matmuls are true IEEE fp32.

    Ampere silently runs fp32 matmuls in TF32 (10 mantissa bits) unless told
    otherwise. Measured against the CPU path that costs max |delta| ~7.8e-3 and
    flips ~0.07% of NLI argmax labels -- a discrete change to an observation,
    which is not acceptable in a cache shared with CPU-computed cycles.
    """
    import torch

    try:                      # torch >= 2.12 precision API
        torch.backends.cuda.matmul.fp32_precision = "ieee"
        torch.backends.cudnn.conv.fp32_precision = "ieee"
    except Exception:
        pass
    try:                      # older toggles, still honoured
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
    except Exception:
        pass


def _model(model_id: str, device: str):
    key = (model_id, device)
    if key not in _STATE:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _exact_fp32()

        import torch as _t

        tok = AutoTokenizer.from_pretrained(model_id)
        # fp32 is explicit because the checkpoint config says float16; see the
        # module docstring for the measured device-dependence this avoids.
        mdl = AutoModelForSequenceClassification.from_pretrained(
            model_id, dtype=_t.float32).eval()
        mdl = mdl.to(device)
        id2label = {i: l.lower() for i, l in mdl.config.id2label.items()}
        _STATE[key] = (tok, mdl, id2label)
    return _STATE[key]


def nli_gpu(pairs: list[tuple[str, str]], model_id: str = measure.NLI_MODEL,
            batch: int = 512, device: str | None = None,
            use_cache: bool = True) -> np.ndarray:
    """P(entail), P(neutral), P(contradict), computed on GPU.

    Mirrors measure.nli exactly apart from the device and the default batch
    size (GPUs want larger batches; batching cannot change per-pair results
    because attention never crosses a sequence boundary and padding is masked).
    """
    if not pairs:
        return np.zeros((0, 3), dtype=np.float32)

    key = cache.cache_key(kind="nli", model=model_id,
                          h=measure._h([f"{a}\x01{b}" for a, b in pairs]),
                          n=len(pairs))
    if use_cache:
        hit = cache.get("nli", key)
        if hit is not None:
            return np.array(hit["probs"], dtype=np.float32)

    import torch

    device = device or pick_device()

    uniq: dict[tuple[str, str], int] = {}
    inv = np.empty(len(pairs), dtype=np.int64)
    for i, p in enumerate(pairs):
        inv[i] = uniq.setdefault(p, len(uniq))
    todo = list(uniq)
    order = sorted(range(len(todo)), key=lambda i: -(len(todo[i][0]) + len(todo[i][1])))

    tok, mdl, id2label = _model(model_id, device)
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
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = mdl(**enc).logits.softmax(-1).float().cpu().numpy()
            scored[sel] = probs[:, [cols["e"], cols["n"], cols["c"]]]

    out = scored[inv]
    if use_cache:
        cache.put("nli", key, {"probs": out.tolist()})
    return out


def install(device: str | None = None, batch: int = 512) -> str:
    """Route wct.measure.nli through the GPU. Returns the device in use."""
    device = device or pick_device()

    def _patched(pairs, model_id=measure.NLI_MODEL, batch=batch):
        return nli_gpu(pairs, model_id=model_id, batch=batch, device=device)

    measure.nli = _patched
    return device
