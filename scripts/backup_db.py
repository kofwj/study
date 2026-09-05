#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备份：SQLite 用 backup API；Postgres 用 pg_dump -Fc。只留最近 10 份。"""
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
backup_dir = Path(os.environ.get("SUNSHINE_DB", ROOT / "data" / "sunshine.db")).parent / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")
url = os.environ.get("DATABASE_URL", "")


def keep(pattern):
    files = sorted(backup_dir.glob(pattern))
    for f in files[:-10]:
        f.unlink()
    print("保留最近 10 份，现存 %d 份" % min(len(files), 10))


if url.startswith("postgres"):
    dst = backup_dir / f"sunshine_{stamp}.dump"
    try:
        subprocess.check_call(["pg_dump", "-Fc", "-d", url, "-f", str(dst)])
    except FileNotFoundError:
        with open(dst, "wb") as f:
            subprocess.check_call(
                ["docker", "exec", "sunshine-postgres", "pg_dump", "-Fc", "-U", "sunshine", "sunshine"],
                stdout=f)
    print("已备份:", dst)
    keep("sunshine_*.dump")
    sys.exit(0)

src = Path(os.environ.get("SUNSHINE_DB", ROOT / "data" / "sunshine.db"))
if not src.exists():
    print("无数据库可备份:", src)
    sys.exit(0)

dst = backup_dir / f"sunshine_{stamp}.db"
s = sqlite3.connect(f"file:{src.resolve()}?mode=ro", uri=True)
d = sqlite3.connect(dst)
with d:
    s.backup(d)
s.close()
d.close()
print("已备份:", dst)
keep("sunshine_*.db")
