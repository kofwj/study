#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""restore_db.sh 冒烟：列出、dry-run、真实还原，且不会覆盖正在用的库。"""
import os
import sqlite3
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "restore_db.sh"


def _init_db(path: Path, n: int, bal: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY, delta INTEGER)")
    for i in range(n):
        c.execute("INSERT INTO ledger(delta) VALUES (?)", (bal // n if i < n - 1 else bal - (bal // n) * (n - 1),))
    c.commit()
    c.close()


def test_restore_db_script():
    assert SCRIPT.is_file()
    mode = SCRIPT.stat().st_mode
    if not (mode & stat.S_IXUSR):
        os.chmod(SCRIPT, mode | stat.S_IXUSR)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        data = td / "data"
        live = data / "sunshine.db"
        bakdir = data / "backups"
        bakdir.mkdir(parents=True)
        _init_db(live, 2, 10)
        bak = bakdir / "sqlite_20260101_000000.db"
        _init_db(bak, 5, 121)

        env = {**os.environ, "SUNSHINE_DATA": str(data), "SUNSHINE_DB": str(live), "PATH": os.environ.get("PATH", "")}

        listed = subprocess.check_output(["bash", str(SCRIPT)], cwd=str(ROOT), env=env, text=True)
        assert "sqlite_20260101_000000.db" in listed
        assert "121" in listed

        dry = subprocess.check_output(
            ["bash", str(SCRIPT), "--latest", "--dry-run"], cwd=str(ROOT), env=env, text=True)
        assert "dry-run" in dry
        c = sqlite3.connect(live)
        assert c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 2
        c.close()

        out = subprocess.check_output(["bash", str(SCRIPT), "--latest"], cwd=str(ROOT), env=env, text=True)
        assert "已还原" in out
        c = sqlite3.connect(live)
        assert c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 5
        assert c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger").fetchone()[0] == 121
        c.close()
        snaps = list(bakdir.glob("pre_restore_*.db"))
        assert snaps, "还原前应留下当前库快照"
        c = sqlite3.connect(snaps[0])
        assert c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 2
        c.close()

        bad = subprocess.run(
            ["bash", str(SCRIPT), str(live)], cwd=str(ROOT), env=env, text=True, capture_output=True)
        assert bad.returncode != 0
        assert "不能把正在用的库" in (bad.stderr + bad.stdout)
