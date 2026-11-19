#!/usr/bin/env python3
"""Entry point: python3 scripts/xcp.py <command> [options]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xcp_hardening.cli import main

if __name__ == "__main__":
    main()
