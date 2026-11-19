"""CLI for the XCP-ng hardening lab."""
from __future__ import annotations

import argparse

from . import vbox
from .config import load_config
from .report import save
from .runner import ART, apply, audit, deharden
from .ssh import SSH


def main() -> None:
    p = argparse.ArgumentParser(prog="xcp.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    sp = sub.add_parser("snapshot")
    sp.add_argument("action", choices=["list", "take", "restore"])
    sp.add_argument("--name", default="")
    sr = sub.add_parser("run")
    sr.add_argument("--phase", choices=["baseline", "apply", "verify", "all"], default="all")
    sr.add_argument("--level", type=int, default=1)
    sr.add_argument("--no-func", action="store_true")
    sh = sub.add_parser("harden")
    sh.add_argument("--level", type=int, default=1)
    sh.add_argument("--dry-run", action="store_true")
    sh.add_argument("--syslog", default="")
    sd = sub.add_parser("deharden")
    sd.add_argument("--dry-run", action="store_true")
    rp = sub.add_parser("report")
    rp.add_argument("--title", default="XCP-ng hardening")
    rp.add_argument("--dirs", nargs="+", required=True)
    args = p.parse_args()

    if args.cmd == "info":
        cfg = load_config()
        print("VM:", cfg["vm_name"])
        print("SSH:", cfg["ssh"])
        with SSH() as ssh:
            rc, out, _ = ssh.exec("hostname; grep PRODUCT_VERSION /etc/xensource-inventory; xe host-list params=name-label --minimal")
            print(out.strip())
        return
    if args.cmd == "snapshot":
        if args.action == "list":
            print(vbox.snapshot_list())
        elif args.action == "take":
            print(vbox.snapshot_take(args.name or "snapshot", "lab checkpoint"))
        else:
            print(vbox.snapshot_restore(args.name))
        return
    if args.cmd == "report":
        save([ART / d if not d.startswith("/") else __import__("pathlib").Path(d) for d in args.dirs], args.title)
        return

    with SSH() as ssh:
        if args.cmd == "harden":
            apply(ssh, args.level, args.dry_run, args.syslog)
            return
        if args.cmd == "deharden":
            deharden(ssh, args.dry_run)
            return
        run_func = not args.no_func
        if args.phase in ("baseline", "all"):
            audit(ssh, "baseline", run_func)
        if args.phase in ("apply", "all"):
            apply(ssh, args.level)
        if args.phase in ("verify", "all"):
            audit(ssh, "verify", run_func)
