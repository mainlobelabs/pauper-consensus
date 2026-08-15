"""Immutable, content-hashed, write-once artifact cache (REQUEST.md A3).

The cache key covers everything that could change a generation: the item, the
resolved model and provider metadata, the prompt template, decode parameters,
the requested seed, and SCHEMA_VERSION. Analysis re-runs therefore cost no API
calls, and a changed prompt cannot quietly reuse an old completion.

Write-once is enforced: a second write to an existing key raises unless the
payload is byte-identical, which turns an accidental overwrite into a failure
rather than a silent rewrite of history.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .schema import SCHEMA_VERSION

CACHE_ROOT = Path(os.environ.get("WCT_CACHE", "out/cache"))


class CacheConflict(RuntimeError):
    """Raised when a key would be overwritten with different content."""


def cache_key(**parts: Any) -> str:
    """Stable content hash over the full generation-determining parameter set."""
    payload = json.dumps(
        {"schema": SCHEMA_VERSION, **parts}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _path(namespace: str, key: str) -> Path:
    return CACHE_ROOT / namespace / f"{key}.json"


def get(namespace: str, key: str) -> dict | None:
    p = _path(namespace, key)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def put(namespace: str, key: str, value: dict) -> dict:
    """Write once. Returns the stored value, which may predate this call."""
    p = _path(namespace, key)
    body = json.dumps(value, sort_keys=True, indent=2)
    if p.exists():
        existing = p.read_text()
        if existing != body:
            raise CacheConflict(
                f"{namespace}/{key} already exists with different content; "
                "cache is write-once. Change the key, do not overwrite."
            )
        return json.loads(existing)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(body)
    tmp.replace(p)  # atomic: a crash mid-write cannot leave a partial artifact
    return value


def stats() -> dict[str, int]:
    if not CACHE_ROOT.exists():
        return {}
    return {
        d.name: len(list(d.glob("*.json")))
        for d in sorted(CACHE_ROOT.iterdir())
        if d.is_dir()
    }
