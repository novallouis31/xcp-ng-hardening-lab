"""VirtualBox snapshot helper (host side)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import load_config

VBOX = Path(r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe")


def vbox(*args: str) -> str:
    cmd = [str(VBOX)] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"VBoxManage failed: {r.stderr.strip()}")
    return r.stdout.strip()


def vm_name() -> str:
    return load_config()["vm_name"]


def snapshot_take(name: str, description: str = "") -> str:
    args = ["snapshot", vm_name(), "take", name]
    if description:
        args.append("--description=" + description)
    return vbox(*args)


def snapshot_list() -> str:
    return vbox("snapshot", vm_name(), "list")


def snapshot_restore(name: str) -> str:
    return vbox("snapshot", vm_name(), "restore", name)
