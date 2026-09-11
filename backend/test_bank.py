# -*- coding: utf-8 -*-
"""阳光银行第一稿：分账、开关和取出审批。"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


def test_bank_switch_deposit_and_approved_withdrawal():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "banktest", "pin": "bankpin8", "family_name": "银行家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "bankkid", "pin": "111222"})
        assert r.status_code == 200, r.text
        kid = r.json()["id"]
        q = "?selected_kid=" + kid

        c = db.connect(admin=True)
        db.insert_ledger(c, db.today(), 20, "task", "seed-bank", "测试初始阳光", kid)
        c.commit()
        c.close()

        bank = cli.get("/api/bank" + q)
        assert bank.status_code == 200 and bank.json()["enabled"] is False
        assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": True}).status_code == 200
        assert cli.post("/api/admin/bank/goal" + q, json={"name": "周末去公园", "target": 15}).status_code == 200

        r = cli.post("/api/bank/deposit" + q, json={"amount": 12})
        assert r.status_code == 200, r.text
        assert r.json()["balance"] == 12 and r.json()["pocket_balance"] == 8
        assert cli.get("/api/rewards" + q).status_code == 200

        r = cli.post("/api/bank/withdraw" + q, json={"amount": 5})
        assert r.status_code == 200, r.text
        assert r.json()["balance"] == 12
        requests = cli.get("/api/admin/bank/requests" + q).json()
        rid = requests[0]["id"]
        assert requests[0]["status"] == "pending"

        r = cli.post(f"/api/admin/bank/requests/{rid}/approve" + q)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["balance"] == 7 and out["pocket_balance"] == 13
        assert cli.get("/api/bank" + q).json()["goal"]["saved"] == 7

        assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": False}).status_code == 200
        assert cli.post("/api/bank/deposit" + q, json={"amount": 1}).status_code == 403
