#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清空孩子活动数据：流水/完成记录/签到/每日计量(个人纪录)/兑换。
保留课程种子、商店、等级、游标等配置。执行前先跑 backup_db.py。
注意：DB 文件归属 root（容器写入），需以 root 执行：
  ssh root@VPS 'cd ~/sunshine && SUNSHINE_DB=/home/kofwj/sunshine/data/sunshine.db python3 scripts/reset_data.py'
"""
import os
import sqlite3
from pathlib import Path

src = Path(os.environ.get("SUNSHINE_DB", "data/sunshine.db"))
if not src.exists():
    print("无数据库:", src)
    raise SystemExit(1)

TABLES = ["ledger", "completions", "checkins", "daily_metrics", "redemptions", "tests"]
c = sqlite3.connect(src)
for t in TABLES:
    c.execute(f"DELETE FROM {t}")
c.execute("DELETE FROM settings WHERE key LIKE 'milestone_%'")  # 连击里程碑标记也重置
c.execute("DELETE FROM settings WHERE key = 'box_opened'")  # 宝箱已开数重置
c.commit()
c.close()
print("已清空:", ", ".join(TABLES), "+ 里程碑标记")