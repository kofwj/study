#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提交前把 VERSION 最后一位 +1；到 99 进位。SKIP_VERSION_BUMP=1 可跳过。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import version  # noqa: E402


def _staged_files():
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=ROOT, text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def main():
    if os.environ.get("SKIP_VERSION_BUMP") == "1":
        print("skip version bump")
        return 0
    staged = _staged_files()
    if not staged:
        return 0
    if "VERSION" in staged:
        return 0
    nxt = version.bump_version_file()
    subprocess.check_call(["git", "add", "--", "VERSION"], cwd=ROOT)
    print(f"version -> {nxt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
