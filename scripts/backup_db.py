#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备份 SQLite：用在线 backup API 安全复制（不锁写），只留最近 10 份。"""
import os
import sqlite3
import sys
import time
from pathlib import Path

src = Path(os.environ.get("SUNSHINE_DB", "data/sunshine.db"))
if not src.exists():
    print("无数据库可备份:", src)
    sys.exit(0)

backup_dir = src.parent / "backups"
backup_dir.mkdir(exist_ok=True)
dst = backup_dir / f"sunshine_{time.strftime('%Y%m%d_%H%M%S')}.db"

s = sqlite3.connect(f"file:{src.resolve()}?mode=ro", uri=True)  # 只读打开，兼容 root 所有的 DB 文件
d = sqlite3.connect(dst)
with d:
    s.backup(d)
s.close()
d.close()
print("已备份:", dst)

files = sorted(backup_dir.glob("sunshine_*.db"))
for f in files[:-10]:
    f.unlink()
print("保留最近 10 份，现存 %d 份" % len(files[-10:]))