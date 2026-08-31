"""Load API credentials from the owner's harness env file into the process.

~/.config/solon/harness.env (chmod 600) is the single sanctioned key store for
this machine, referenced by ~/dev/solon-harness/harness.toml. Keys are loaded
into os.environ only if not already set, values are never logged, and nothing
here writes anywhere.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "solon" / "harness.env"


def load_harness_env() -> list[str]:
    """Returns the NAMES loaded (never values)."""
    if not ENV_FILE.exists():
        return []
    loaded = []
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
            loaded.append(k)
    return loaded
