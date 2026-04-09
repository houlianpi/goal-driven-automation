#!/usr/bin/env python3
"""Deprecated compatibility wrapper for the canonical report entrypoint."""
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_report import main


if __name__ == "__main__":
    print("Deprecated: use scripts/generate_report.py instead.")
    raise SystemExit(main())
