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


@pytest.fixture(autouse=True)
def _never_write_the_frozen_cache(monkeypatch):
    """No test in this file may write an NLI entry.

    This module computes fp32 NLI. The frozen cache holds cycles 1-2's fp16 entries, and
    the slice-4 gate pins its entry count precisely so a stray fp32 write is caught. Two
    tests here previously wrote through: one patched cache.get but not cache.put, and one
    exercised install() whose patched measure.nli defaults to use_cache=True.
    """
    monkeypatch.setattr(cache, "put", lambda *a, **k: None)


def test_cache_key_matches_measure_exactly():
    """A GPU-written entry must be findable by the CPU path's key, and vice versa."""
    h = measure._h([f"{a}\x01{b}" for a, b in PAIRS])
    expected = cache.cache_key(kind="nli", model=measure.NLI_MODEL, h=h, n=len(PAIRS))
    seen = {}
    real_get, real_put = cache.get, cache.put
    cache.get = lambda kind, key: seen.setdefault("key", key) and None
    # cache.put MUST be neutralised too: patching only `get` made this test compute a
    # result and WRITE it, which put an fp32 entry into the frozen fp16 cache and was
    # caught by the slice-4 gate's entry-count assertion.
    wrote = []
    cache.put = lambda kind, key, value: wrote.append(key)
    try:
        gpu.nli_gpu(PAIRS, device="cpu", use_cache=True)
    finally:
        cache.get, cache.put = real_get, real_put
    assert seen["key"] == expected
    assert wrote == [expected], "the write path must use the same key as the read path"


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


def test_install_returns_a_handle_that_restores_the_exact_prior_callable():
    """Reversibility must be a property of install(), not of the caller's finally block."""
    original = measure.nli
    handle = gpu.install(device="cpu")
    assert handle == "cpu"                       # back-compat with the device-string use
    assert measure.nli is not original
    out = measure.nli(PAIRS)
    assert out.shape == (len(PAIRS), 3)
    assert handle.uninstall() is True
    assert measure.nli is original               # restored BY the API, not by the test


def test_install_works_as_a_context_manager():
    original = measure.nli
    with gpu.install(device="cpu") as h:
        assert measure.nli is not original
        assert h.device == "cpu"
    assert measure.nli is original


def test_uninstall_is_idempotent():
    original = measure.nli
    h = gpu.install(device="cpu")
    assert h.uninstall() is True
    assert h.uninstall() is False, "a second uninstall must be a no-op, not a re-restore"
    assert measure.nli is original


def test_nested_installs_restore_in_lifo_order():
    original = measure.nli
    outer = gpu.install(device="cpu")
    outer_patch = measure.nli
    inner = gpu.install(device="cpu")
    assert inner.uninstall() is True
    assert measure.nli is outer_patch, "inner must restore exactly what it replaced"
    assert outer.uninstall() is True
    assert measure.nli is original


def test_uninstalling_an_older_handle_does_not_clobber_a_newer_install():
    original = measure.nli
    older = gpu.install(device="cpu")
    newer = gpu.install(device="cpu")
    newer_patch = measure.nli
    assert older.uninstall() is True
    assert measure.nli is newer_patch, "the live install was yanked out from under its owner"
    newer.uninstall()
    measure.nli = original          # older's patch is now unreachable by design (LIFO)
