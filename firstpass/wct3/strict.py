"""Cache-only enforcement for the frozen measurement layer.

Slice 1 is specified to make ZERO inference calls: it re-analyses immutable
caches. An unroutable `WCT_LOCAL_BASE` stops an embedding miss from reaching
the `:1234` endpoint, but NLI runs in-process via transformers, so a miss there
would compute locally on CPU and write the live cache — new inference by any
honest reading, and undetectable after the fact.

`install()` wraps `wct.measure.embed` and `wct.measure.nli` so that a miss
raises `CacheMiss` BEFORE anything is computed or written.

A miss is not a nuisance to tolerate. `measure.embed` keys its cache on a hash
of the WHOLE text list (`measure._h`), so a miss means the corrected path
issued a DIFFERENT call than the frozen one — which is precisely the divergence
`wct3.align`'s bit-identity test exists to catch. Failing loudly here turns a
silent 2 GB re-embed into an immediate, located error.

The frozen modules are patched at runtime by attribute assignment. `wct/`
is not edited, and `uninstall()` restores the originals.
"""
from __future__ import annotations

from wct import cache
from wct import measure


class CacheMiss(RuntimeError):
    """A measurement call missed the cache while strict mode was installed."""


_orig_embed = None
_orig_nli = None


def _embed(texts: list[str], batch: int = 64):
    if not texts:                      # frozen fast path: touches no cache
        return _orig_embed(texts, batch)
    key = cache.cache_key(kind="embed", model=measure.EMBED_MODEL,
                          h=measure._h(texts), n=len(texts))
    if cache.get("embed", key) is None:
        raise CacheMiss(
            f"embed cache miss on {len(texts)} texts (key {key}). The corrected "
            f"path issued a call the frozen path did not: measure.embed keys on "
            f"a hash of the whole list, so the text list or its ORDER differs "
            f"from cluster.align_anchored's."
        )
    return _orig_embed(texts, batch)


def _nli(pairs, model_id: str = measure.NLI_MODEL, batch: int = 64):
    if not pairs:
        return _orig_nli(pairs, model_id, batch)
    key = cache.cache_key(kind="nli", model=model_id,
                          h=measure._h([f"{a}\x01{b}" for a, b in pairs]),
                          n=len(pairs))
    if cache.get("nli", key) is None:
        raise CacheMiss(
            f"nli cache miss on {len(pairs)} pairs (key {key}). Same cause as an "
            f"embed miss: the pair list or its order differs from the frozen path's."
        )
    return _orig_nli(pairs, model_id, batch)


def install() -> None:
    """Make every cache miss in the measurement layer raise instead of compute."""
    global _orig_embed, _orig_nli
    if _orig_embed is not None:
        return                                   # idempotent
    _orig_embed, _orig_nli = measure.embed, measure.nli
    measure.embed, measure.nli = _embed, _nli


def uninstall() -> None:
    global _orig_embed, _orig_nli
    if _orig_embed is None:
        return
    measure.embed, measure.nli = _orig_embed, _orig_nli
    _orig_embed, _orig_nli = None, None


def installed() -> bool:
    return _orig_embed is not None
