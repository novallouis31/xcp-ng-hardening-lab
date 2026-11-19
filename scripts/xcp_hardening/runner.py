"""Test-cycle state machine: baseline -> apply -> verify -> deharden."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import ROOT
from .ssh import SSH, script_remote

GUEST = ROOT / "guest"
ART = ROOT / "artifacts"
SCRIPTS = ("audit-xcp.sh", "apply-xcp.sh", "deharden-xcp.sh", "func-test-xcp.sh")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _upload_all(ssh: SSH) -> None:
    for name in SCRIPTS:
        ssh.put(GUEST / name, script_remote(name), 0o700)


def audit(ssh: SSH, label: str, run_func: bool = True) -> Path:
    out = ART / f"{label}-{_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    _upload_all(ssh)
    ssh.exec(f"bash {script_remote('audit-xcp.sh')} /tmp/xcp-audit-{label}")
    ssh.get(f"/tmp/xcp-audit-{label}/audit.txt", out / "audit.txt")
    ssh.get(f"/tmp/xcp-audit-{label}/checks.tsv", out / "checks.tsv")
    if run_func:
        ssh.exec(f"bash {script_remote('func-test-xcp.sh')} /tmp/xcp-func-{label}")
        ssh.get(f"/tmp/xcp-func-{label}/fonctionnel.txt", out / "fonctionnel.txt")
    print(f"[{label}] {out}")
    return out


def apply(ssh: SSH, level: int = 1, dry_run: bool = False, syslog: str = "") -> None:
    _upload_all(ssh)
    key = ROOT / ".keys" / "id_ed25519.pub"
    if key.exists():
        ssh.put(key, "/root/xcp-lab-key.pub", 0o600)
    env = f"LEVEL={level} DRY_RUN={'1' if dry_run else '0'}"
    if syslog:
        env += f" SYSLOG_SERVER={syslog}"
    rc, out, err = ssh.exec(f"{env} bash {script_remote('apply-xcp.sh')}", timeout=1200)
    print(out)
    if err.strip():
        print("stderr:", err[-1000:])
    if rc != 0:
        raise RuntimeError(f"hardening failed (rc={rc})")


def deharden(ssh: SSH, dry_run: bool = False) -> Path:
    out = ART / f"deharden-{_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    _upload_all(ssh)
    flag = " --dry-run" if dry_run else ""
    rc, stdout, stderr = ssh.exec(
        f"bash {script_remote('deharden-xcp.sh')}{flag} --report /tmp/xcp-deharden.md",
        timeout=1200,
    )
    (out / "deharden.log").write_text(stdout + stderr, encoding="utf-8")
    try:
        ssh.get("/tmp/xcp-deharden.md", out / "deharden.md")
    except Exception:
        pass
    print(stdout)
    if rc != 0:
        raise RuntimeError(f"de-hardening failed (rc={rc})")
    return out
