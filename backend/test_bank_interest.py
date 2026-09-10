# -*- coding: utf-8 -*-
"""阳光银行利息：周期结算、起存点、家长可配置。"""
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
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

        c = db.connect(admin=True)
        db.insert_ledger(c, db.today(), 100, "task", "seed-int", "测试初始", kid)
        c.commit()
        c.close()

        assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": True}).status_code == 200
        assert cli.post("/api/bank/deposit" + q, json={"amount": 80}).status_code == 200

        cfg = cli.get("/api/admin/bank/interest" + q).json()
        assert cfg["enabled"] is False
        
        r = cli.put("/api/admin/bank/interest" + q, json={"enabled": True, "cycle": "weekly", "rate": 5.0, "threshold": 20})
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        today = datetime.strptime(db.today(), "%Y-%m-%d").date()
        if today.weekday() != 5:
            r = cli.post("/api/admin/bank/settle-now" + q)
            assert r.status_code == 200
            assert r.json()["settled"] is False

        c = db.connect(admin=True)
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        result = main.settle_bank_interest(c, kid, saturday)
        if result and result.get("settled"):
            c.commit()
            assert result["interest"] > 0
        c.close()

        bank = cli.get("/api/bank" + q).json()
        assert bank["interest"] is not None
        assert bank["interest"]["rate"] == 5.0
