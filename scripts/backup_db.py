#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite数据库备份脚本，使用backup API，保留最近10份。"""
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
backup_dir = Path(os.environ.get("SUNSHINE_DB", ROOT / "data" / "sunshine.db")).parent / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M%S")

def keep_recent(pattern, count=10):
    """保留最近N份备份"""
    files = sorted(backup_dir.glob(pattern))
    for f in files[:-count]:
        f.unlink()
    print(f"保留最近 {count} 份，现存 {min(len(files), count)} 份")

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
keep_recent("sunshine_*.db")
