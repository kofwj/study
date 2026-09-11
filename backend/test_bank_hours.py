# -*- coding: utf-8 -*-
"""阳光储蓄所营业时间：每天 8:00–20:00（上海时间）。"""
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
import main  # noqa: E402


def _at(h, m=0):
    return datetime(2026, 9, 11, h, m, tzinfo=db.TZ)


def test_bank_window_hours():
    os.environ["SUNSHINE_FORCE_BANK_WINDOW"] = "1"
    try:
        early = main.bank_window(_at(7, 59))
        assert early["open"] is False and "太早" in early["hint"]
        open8 = main.bank_window(_at(8, 0))
        assert open8["open"] is True and open8["hint"] == ""
        open19 = main.bank_window(_at(19, 59))
        assert open19["open"] is True
        closed = main.bank_window(_at(20, 0))
        assert closed["open"] is False and "打烊" in closed["hint"]
        assert closed["from"] == "08:00" and closed["until"] == "20:00"
    finally:
        os.environ.pop("SUNSHINE_FORCE_BANK_WINDOW", None)


def test_tests_skip_bank_window_by_default():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ.pop("SUNSHINE_FORCE_BANK_WINDOW", None)
    late = main.bank_window(_at(22, 0))
    assert late["open"] is True


def test_bank_api_rejects_after_hours():
    from fastapi.testclient import TestClient
    os.environ["SECRET_KEY"] = "prod-secret"
    os.environ["SUNSHINE_FORCE_BANK_WINDOW"] = "1"
    os.environ["SUNSHINE_NOW"] = "2026-09-11T20:10:00"
    os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "bank-hours.db")
    db.init_db()
    try:
        with TestClient(main.app) as cli:
            assert cli.post("/api/auth/register", json={"account": "bankhour", "pin": "bankpin8", "family_name": "打烊家"}).status_code == 200
            r = cli.post("/api/admin/kids", json={"name": "甲", "account": "hourkid", "pin": "111222"})
            assert r.status_code == 200, r.text
            kid = r.json()["id"]
            q = "?selected_kid=" + kid
            c = db.connect(admin=True)
            db.insert_ledger(c, db.today(), 20, "task", "seed-hours", "测试初始阳光", kid)
            c.commit()
            c.close()
            assert cli.put("/api/admin/bank/enabled" + q, json={"enabled": True}).status_code == 200
            body = cli.get("/api/bank" + q).json()
            assert body["hours"]["open"] is False
            r = cli.post("/api/bank/deposit" + q, json={"amount": 1})
            assert r.status_code == 403
            assert "打烊" in r.json()["detail"]
            r = cli.post("/api/bank/withdraw" + q, json={"amount": 1})
            assert r.status_code == 403
    finally:
        os.environ.pop("SUNSHINE_NOW", None)
        os.environ.pop("SUNSHINE_FORCE_BANK_WINDOW", None)
        os.environ["SECRET_KEY"] = "test-secret"


if __name__ == "__main__":
    test_bank_window_hours()
    test_tests_skip_bank_window_by_default()
    test_bank_api_rejects_after_hours()
    print("bank hours ok")
