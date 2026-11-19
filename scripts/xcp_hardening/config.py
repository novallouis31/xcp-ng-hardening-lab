"""Lab configuration: VM settings and credentials (never committed)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict:
    return json.loads((ROOT / "vm-config.json").read_text(encoding="utf-8"))


def credentials() -> dict:
    """Read .local/credentials.txt: lines 'password <value>' or 'password=<value>'."""
    path = ROOT / ".local" / "credentials.txt"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or " " not in line and "=" not in line:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            else:
                key, value = line.split(None, 1)
            out[key.strip().lower()] = value.strip()
    return out
