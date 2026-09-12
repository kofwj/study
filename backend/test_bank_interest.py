# -*- coding: utf-8 -*-
"""阳光银行利息：周期结算、起存点、家长可配置。"""
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


def test_bank_interest_weekly_settlement():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "inttest", "pin": "interest8", "family_name": "利息家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "intkid", "pin": "111222"})
        assert r.status_code == 200
        kid = r.json()["id"]
        q = "?selected_kid=" + kid

        r = cli.put("/api/admin/bank/interest" + q, json={"enabled": True, "cycle": "weekly", "rate": 5.0, "threshold": 20})
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        today = datetime.strptime(db.today(), "%Y-%m-%d").date()
        due = today - timedelta(days=(today.weekday() - 5) % 7)  # 最近一个结息周六
        seed_date = (due - timedelta(days=2)).strftime("%Y-%m-%d")

        # 在结算周期窗口内直接落账（API 存款会记在今天，可能在窗口外）
        c = db.connect(admin=True)
        db.insert_ledger(c, seed_date, 100, "task", "seed-int", "测试初始", kid)
        db.insert_ledger(c, seed_date, 80, "bank_deposit", "seed-int-dep", "测试存入", kid, "bank")
        db.insert_ledger(c, seed_date, -80, "bank_deposit", "seed-int-dep", "测试存入", kid, "pocket")
        c.commit()

        # 补结算：无论今天星期几，首次触发都结算最近一个未结的周六周期
        r = cli.post("/api/admin/bank/settle-now" + q)
        assert r.status_code == 200
        first = r.json()
        assert first["settled"] is True
        assert first["interest"] > 0

        # 同一周期内重复触发不重复发息
        r = cli.post("/api/admin/bank/settle-now" + q)
        assert r.status_code == 200
        assert r.json()["settled"] is False

        n = c.execute(
            "SELECT COUNT(*) FROM ledger WHERE kid_id=? AND reason='bank_interest'", (kid,)
        ).fetchone()[0]
        assert n == 1
        c.close()

        bank = cli.get("/api/bank" + q).json()
        assert bank["interest"] is not None
        assert bank["interest"]["rate"] == 5.0
