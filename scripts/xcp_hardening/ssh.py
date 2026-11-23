"""Minimal paramiko helper for the lab VM."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import paramiko

from .config import credentials, load_config


class SSH:
    def __init__(self) -> None:
        cfg = load_config()["ssh"]
        self.host = cfg["host"]
        self.port = int(cfg["port"])
        self.user = cfg["user"]
        # Jamais de mot de passe en dur : valeur reelle dans .local/credentials.txt
        # (ignore par git) ou variable d'environnement LAB_SSH_PASSWORD.
        self.password = credentials().get("password", os.environ.get("LAB_SSH_PASSWORD", ""))
        self.key_path = ROOT_CRED / "id_ed25519" if (ROOT_CRED := (Path(__file__).resolve().parents[2] / ".keys")).exists() else None
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, retries: int = 6) -> None:
        for i in range(retries):
            base = dict(username=self.user, timeout=8, look_for_keys=False, allow_agent=False)
            attempts: list[dict] = []
            if self.key_path and Path(self.key_path).exists():
                attempts.append({**base, "key_filename": str(self.key_path)})
            attempts.append({**base, "password": self.password})
            for kwargs in attempts:
                try:
                    self.client.connect(self.host, port=self.port, **kwargs)
                    return
                except Exception:
                    continue
            if i == retries - 1:
                raise RuntimeError("SSH authentication failed with key and password")
            time.sleep(3)

    def exec(self, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
        _, out, err = self.client.exec_command(cmd, timeout=timeout)
        rc = out.channel.recv_exit_status()
        return rc, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")

    def put(self, local: str | Path, remote: str, mode: int = 0o700) -> None:
        sftp = self.client.open_sftp()
        sftp.put(str(local), remote)
        sftp.chmod(remote, mode)
        sftp.close()

    def get(self, remote: str, local: str | Path) -> None:
        sftp = self.client.open_sftp()
        sftp.get(remote, str(local))
        sftp.close()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SSH":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def script_remote(name: str) -> str:
    return f"/root/xcp-lab-{name}"
