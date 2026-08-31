"""One-off: compute the aligner self-identification probe for the cycle-2 corpus.

Runs ONLY under the recorded amendment to slice 1's no-inference constraint
(DECISIONS.md, 2026-08-28). Scope is exactly `cluster.aligner_probe` over the
150 v2 items: local in-process CPU NLI via transformers. No API call, no
OpenRouter, no :1234 endpoint, no quota.

Why it is needed at all: the probe's NLI pairs are cached only for panels whose
driver actually ran it. exp/e1.py did; exp/e1_v2.py did not — that omission is
defect D3. So cycle 2's mapper diagnostic cannot be recovered from cache.

The probe is a function of the ITEM alone (it feeds each proposition's own
surface text and its negated twin back through the aligner as pseudo-claims),
so ONE pass over the corpus serves both cycle-2 panels.

After this runs once, the entries are cached and the standard cache-only gate
passes unchanged with the probe reported as `computed`.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from exp.common import PREREG
from exp.v2_dataset import load_v2_items
from wct import cache, cluster, measure

TOP_K = PREREG["measurement"]["nli"]["top_k"]


def _harden() -> None:
    """The amendment permits local NLI and NOTHING else.

    Without this the script is merely *intended* to be offline. Three teeth:
      - embeddings must be cache hits; a miss raises rather than calling :1234
      - the endpoint is pointed at an unroutable address anyway, so any call
        that slipped past the wrapper fails instead of generating
      - transformers is forced offline, so a model cache miss cannot silently
        download weights
    """
    os.environ["WCT_LOCAL_BASE"] = "http://127.0.0.1:9"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    orig_embed = measure.embed

    def embed_cached_only(texts, batch: int = 64):
        if not texts:
            return orig_embed(texts, batch)
        key = cache.cache_key(kind="embed", model=measure.EMBED_MODEL,
                              h=measure._h(texts), n=len(texts))
        if cache.get("embed", key) is None:
            raise RuntimeError(
                f"embedding cache miss on {len(texts)} texts (key {key}). The "
                f"amendment permits local NLI only; embeddings must come from "
                f"cache. Refusing to call the endpoint.")
        return orig_embed(texts, batch)

    measure.embed = embed_cached_only


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true",
                    help="required: acknowledges the recorded amendment")
    args = ap.parse_args()
    if not args.confirm:
        print(__doc__)
        print("refusing to run without --confirm (this computes NLI locally)")
        return 2

    _harden()
    items, _, _ = load_v2_items()
    print(f"aligner probe backfill over {len(items)} v2 items (local CPU NLI only; "
          f"embeddings cache-only, endpoint unroutable, transformers offline)")
    t0 = time.time()
    computed = 0
    for i, item in enumerate(items, 1):
        cluster.aligner_probe(item, k=TOP_K)
        computed += 1
        if i % 10 == 0 or i == len(items):
            el = time.time() - t0
            print(f"  {i}/{len(items)} items, {el:.0f}s elapsed, "
                  f"{el / i:.1f}s/item", flush=True)
    print(f"done: {computed} items probed in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
