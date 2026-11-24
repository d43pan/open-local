#!/usr/bin/env python3
"""Run Open Local from anywhere: python3 run.py <command> ...   (python3 run.py --help)"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from openlocal.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
