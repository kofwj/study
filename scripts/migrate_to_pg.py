#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite → Postgres 一次性拷贝 + 指纹校验。不切流量、不改源库。

  DATABASE_URL=postgresql://sunshine:sunshine@127.0.0.1:5432/sunshine \\
  DATABASE_APP_URL=postgresql://sunshine_app:sunshine@127.0.0.1:5432/sunshine \\
    python3 scripts/migrate_to_pg.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

url = os.environ.get("DATABASE_URL", "")
if not url.startswith("postgres"):
    sys.exit("先设 DATABASE_URL=postgresql://...")

sqlite_path = Path(os.environ.get("SUNSHINE_DB", ROOT / "data" / "sunshine.db"))
if not sqlite_path.exists():
    sqlite_path = ROOT / "backend" / "sunshine.db"
if not sqlite_path.exists():
    sys.exit("找不到 SQLite：" + str(sqlite_path))

# 源库只读拷到临时文件，init/curriculum 只打副本
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
s = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
d = sqlite3.connect(tmp.name)
with d:
    s.backup(d)
s.close()
d.close()

os.environ["SUNSHINE_DB"] = tmp.name
os.environ.pop("DATABASE_URL", None)

try:
    import db  # noqa: E402

    db.init_db()
    src = db.connect()
    fp_src = db.fingerprints(src)

    TABLES = [
        "subjects", "terms", "units", "tasks", "daily_tasks", "daily_metrics",
        "rewards", "ranks", "settings", "families", "users", "profiles",
        "kid_settings", "checkins", "completions", "ledger", "redemptions", "tests",
    ]
    rows = {t: [dict(r) for r in src.execute(f"SELECT * FROM {t}").fetchall()] for t in TABLES}
    src.close()

    os.environ["DATABASE_URL"] = url
    import importlib
    importlib.reload(db)
    db.init_db()
    pg = db.connect(admin=True)

    for t in TABLES:
        pg.execute(f"DELETE FROM {t}")
        data = rows[t]
        if not data:
            continue
        cols = list(data[0])
        ph = ",".join("?" * len(cols))
        sql = f"INSERT INTO {t}({','.join(cols)}) VALUES({ph})"
        for r in data:
            pg.execute(sql, tuple(r[c] for c in cols))
        if t in ("checkins", "completions", "ledger", "redemptions", "tests"):
            mx = pg.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
            if mx is None:
                continue
            pg.execute("SELECT setval(pg_get_serial_sequence(?, 'id'), ?)", (t, mx))
    pg.commit()

    fp_dst = db.fingerprints(pg)
    diff = {k: (fp_src[k], fp_dst[k]) for k in fp_src if fp_src[k] != fp_dst[k]}
    if diff:
        pg.close()
        print("校验失败:")
        for k, v in diff.items():
            print(" ", k, v)
        sys.exit(1)

    pg.close()
    app_url = os.environ.get("DATABASE_APP_URL") or url.replace("://sunshine:", "://sunshine_app:", 1)
    os.environ["DATABASE_APP_URL"] = app_url
    app = db.connect(admin=False)
    who = app.execute("SELECT current_user").fetchone()[0]
    if who != "sunshine_app":
        app.close()
        sys.exit(f"APP 登录身份是 {who}，必须是 sunshine_app")
    db.apply_scope(app, kid_id="kid-other")
    n = app.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    app.close()
    if n != 0:
        sys.exit(f"RLS 没挡住：kid-other 看到 {n} 条 ledger")
    print("RLS ok: user=sunshine_app kid-other 看到 0 条 ledger")
    print("校验通过", {k: fp_src[k] for k in fp_src if k != "settings"})
    print("settings 键", sorted(fp_src["settings"]))
    print("未切流量。compose 打开 DATABASE_URL + DATABASE_APP_URL 并 --profile postgres 才切。")
finally:
    os.unlink(tmp.name)
