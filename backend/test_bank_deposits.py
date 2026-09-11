# -*- coding: utf-8 -*-
"""阳光储蓄所定存：档位、锁定、到期结息、提前支取。"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import bank_deposits as depmod  # noqa: E402
import main  # noqa: E402


def _today():
    return datetime.strptime(db.today(), "%Y-%m-%d").date()


def test_term_interest_math():
    assert depmod.interest_at_maturity(100, 8) == 8
    assert depmod.interest_early(100, 8, 0, 30) == 0
    assert depmod.interest_early(100, 8, 15, 30) == 2
    assert depmod.interest_early(100, 8, 30, 30) == 4


def test_term_deposit_locks_and_early_break():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "depparent", "pin": "bankpin8", "family_name": "定存家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "depkid", "pin": "111222"})
        assert r.status_code == 200, r.text
        kid = r.json()["id"]
        q = "?selected_kid=" + kid

        c = db.connect(admin=True)
        db.insert_ledger(c, db.today(), 80, "task", "seed-dep", "测试初始阳光", kid)
        c.commit()
        c.close()

        assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": True}).status_code == 200
        r = cli.post("/api/bank/deposit" + q, json={"amount": 50, "days": 30})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["locked"] == 50
        assert body["available"] == 0
        assert body["balance"] == 50
        assert body["deposits"][0]["days"] == 30
        assert body["deposits"][0]["rate"] == 8.0
        assert cli.post("/api/bank/withdraw" + q, json={"amount": 1}).status_code == 409

        did = body["deposits"][0]["id"]
        r = cli.post(f"/api/bank/deposits/{did}/break" + q)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["locked"] == 0
        assert out["available"] == 50
        assert out["deposit"]["state"] == "broken"
        assert out["deposit"]["interest_paid"] == 0


def test_term_deposit_matures():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "matparent", "pin": "bankpin8", "family_name": "到期家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "乙", "account": "matkid", "pin": "111222"})
        assert r.status_code == 200, r.text
        kid = r.json()["id"]
        q = "?selected_kid=" + kid
        c = db.connect(admin=True)
        db.insert_ledger(c, db.today(), 100, "task", "seed-mat", "测试初始阳光", kid)
        c.commit()
        c.close()
        assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": True}).status_code == 200
        r = cli.post("/api/bank/deposit" + q, json={"amount": 100, "days": 7})
        assert r.status_code == 200, r.text
        did = r.json()["deposits"][0]["id"]
        today = _today()
        c = db.connect(admin=True)
        c.execute(
            "UPDATE bank_deposits SET started_on=?, mature_on=? WHERE id=?",
            ((today - timedelta(days=7)).isoformat(), today.isoformat(), did),
        )
        c.commit()
        c.close()
        r = cli.get("/api/bank" + q)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["locked"] == 0
        assert body["balance"] == 102
        closed = [d for d in body["deposits"] if d["id"] == did][0]
        assert closed["state"] == "matured"
        assert closed["interest_paid"] == 2


if __name__ == "__main__":
    test_term_interest_math()
    test_term_deposit_locks_and_early_break()
    test_term_deposit_matures()
    print("bank deposits ok")
