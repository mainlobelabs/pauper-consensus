"""wct3.gpu shares measure.nli's algorithm and cache, and differs only in precision.

gpu.nli_gpu is a second copy of measure.nli's dedup/batching/canonicalisation
logic (wct/measure.py is byte-pinned by the prereg-v2 tag, so the CUDA path
could not be added there). GOTCHAS records what happens to duplicated
measurement code that is not pinned by a test: it diverges silently. These
tests pin the parts that must stay identical -- cache key, column order, dedup
broadcast -- and pin the one part that is deliberately different: precision.
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from wct import cache, measure
from wct3 import gpu

PAIRS = [
    ("The cat is red. If something is red then it is kind.", "The cat is kind."),
    ("The cat is red. If something is red then it is kind.", "The cat is not kind."),
    ("Bob is round. All round things are cold.", "Bob is cold."),
    ("Bob is round. All round things are cold.", "Erin is cold."),
]

HAS_CUDA = torch.cuda.is_available()


def test_cache_key_matches_measure_exactly():
    """A GPU-written entry must be findable by the CPU path's key, and vice versa."""
    h = measure._h([f"{a}\x01{b}" for a, b in PAIRS])
    expected = cache.cache_key(kind="nli", model=measure.NLI_MODEL, h=h, n=len(PAIRS))
    seen = {}
    real_get = cache.get
    cache.get = lambda kind, key: seen.setdefault("key", key) and None
    try:
        gpu.nli_gpu(PAIRS, device="cpu", use_cache=True)
    finally:
        cache.get = real_get
    assert seen["key"] == expected


def test_columns_are_canonical_entail_neutral_contradict():
    p = gpu.nli_gpu(PAIRS, device="cpu", use_cache=False)
    assert p.shape == (len(PAIRS), 3)
    np.testing.assert_allclose(p.sum(axis=1), 1.0, atol=1e-5)
    # pair 0 is entailed by its premise; pair 1 is its negation
    assert p[0].argmax() == 0, f"expected entail, got column {p[0].argmax()}"
    assert p[1].argmax() == 2, f"expected contradict, got column {p[1].argmax()}"


def test_duplicate_pairs_are_scored_once_and_broadcast():
    dup = [PAIRS[0], PAIRS[1], PAIRS[0], PAIRS[1], PAIRS[0]]
    p = gpu.nli_gpu(dup, device="cpu", use_cache=False)
    for i in (2, 4):
        np.testing.assert_array_equal(p[i], p[0])
    np.testing.assert_array_equal(p[3], p[1])


def test_precision_is_fp32_not_the_checkpoint_default():
    """The checkpoint declares float16; this path must override it."""
    gpu._STATE.clear()
    gpu._model(measure.NLI_MODEL, "cpu")
    _, mdl, _ = gpu._STATE[(measure.NLI_MODEL, "cpu")]
    assert next(mdl.parameters()).dtype is torch.float32


@pytest.mark.skipif(not HAS_CUDA, reason="no CUDA device")
def test_gpu_fp32_agrees_with_cpu_fp32_and_never_flips_a_label():
    """The property that makes a GPU result reproducible: device independence."""
    c = gpu.nli_gpu(PAIRS, device="cpu", use_cache=False)
    g = gpu.nli_gpu(PAIRS, device=gpu.pick_device(), use_cache=False)
    assert np.abs(c - g).max() < 1e-4
    np.testing.assert_array_equal(c.argmax(1), g.argmax(1))


def test_install_routes_measure_nli_and_is_reversible():
    original = measure.nli
    try:
        dev = gpu.install(device="cpu")
        assert dev == "cpu"
        assert measure.nli is not original
        out = measure.nli(PAIRS)
        assert out.shape == (len(PAIRS), 3)
    finally:
        measure.nli = original
    assert measure.nli is original
