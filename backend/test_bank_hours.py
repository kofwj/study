# -*- coding: utf-8 -*-
"""阳光储蓄所营业时间：默认每天 8:00–20:00（上海时间），**家长可以在家长端按家配置**。"""
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

def _new_family(account, fam_name):
    """建一个家 + 一个孩子（各自独立的 cookie 会话）。调用方负责设好环境变量。"""
    from fastapi.testclient import TestClient
    cli = TestClient(main.app)
    r = cli.post("/api/auth/register", json={"account": account, "pin": account + "pin8",
                                            "family_name": fam_name})
    assert r.status_code == 200, r.text
    r = cli.post("/api/admin/kids", json={"name": "甲", "account": account + "k", "pin": "111222"})
    assert r.status_code == 200, r.text
    return cli, r.json()["id"]


def test_bank_hours_configurable_and_validated():
    """储蓄所营业时间现在是家族级设置：能读能写、两端 clamp、开门必须早于打烊、能关。"""
    os.environ["SECRET_KEY"] = "prod-secret"
    os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "bank-cfg.db")
    db.init_db()
    try:
        cli, _kid = _new_family("bankcfg", "配置家")
        fam = cli.get("/api/admin/family").json()
        assert (fam["bank_hours"]["from"], fam["bank_hours"]["until"]) == ("08:00", "20:00"), fam["bank_hours"]

        r = cli.put("/api/admin/family/bank-hours", json={"enabled": True, "open_hour": 6, "close_hour": 22})
        assert r.status_code == 200, r.text
        assert (r.json()["bank_hours"]["from"], r.json()["bank_hours"]["until"]) == ("06:00", "22:00")
        fam = cli.get("/api/admin/family").json()
        assert fam["bank_hours"]["open_hour"] == 6 and fam["bank_hours"]["close_hour"] == 22

        r = cli.put("/api/admin/family/bank-hours", json={"enabled": True, "open_hour": -3, "close_hour": 99})
        assert r.status_code == 200, r.text
        assert (r.json()["bank_hours"]["open_hour"], r.json()["bank_hours"]["close_hour"]) == (0, 24)

        r = cli.put("/api/admin/family/bank-hours", json={"enabled": True, "open_hour": 20, "close_hour": 8})
        assert r.status_code == 400 and "打烊" in r.json()["detail"], r.text

        r = cli.put("/api/admin/family/bank-hours", json={"enabled": False, "open_hour": 20, "close_hour": 8})
        assert r.status_code == 200 and r.json()["bank_hours"]["enabled"] is False, r.text
    finally:
        os.environ.pop("SUNSHINE_DB", None)
        os.environ["SECRET_KEY"] = "test-secret"


def test_bank_window_follows_configured_hours():
    """bank_window 按传进来的设置判定：6:00–22:00 那家 21:00 还开着，默认那家已经打烊。"""
    os.environ["SUNSHINE_FORCE_BANK_WINDOW"] = "1"
    try:
        wide = {"enabled": True, "open_hour": 6, "close_hour": 22, "from": "06:00", "until": "22:00"}
        at21 = main.bank_window(_at(21, 0), hours=wide)
        assert at21["open"] is True and at21["hint"] == ""
        at5 = main.bank_window(_at(5, 30), hours=wide)
        assert at5["open"] is False and "太早" in at5["hint"] and "06:00" in at5["hint"], at5
        # 同一时刻（21:00），没配过的家已经打烊
        default_closed = main.bank_window(_at(21, 0))
        assert default_closed["open"] is False and "打烊" in default_closed["hint"], default_closed
        assert default_closed["from"] == "08:00" and default_closed["until"] == "20:00"
        # 关掉 = 任何时候都能存取
        off = main.bank_window(_at(3, 0), hours={"enabled": False})
        assert off["open"] is True and off["hint"] == ""
    finally:
        os.environ.pop("SUNSHINE_FORCE_BANK_WINDOW", None)


def test_bank_hours_are_per_family():
    """两家互不影响：甲改成 6:00–22:00，乙还是 8:00–20:00。"""
    os.environ["SECRET_KEY"] = "prod-secret"
    os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "bank-iso.db")
    db.init_db()
    try:
        cli_a, _ka = _new_family("bankiso1", "甲家")
        assert cli_a.put("/api/admin/family/bank-hours",
                         json={"enabled": True, "open_hour": 6, "close_hour": 22}).status_code == 200
        cli_b, _kb = _new_family("bankiso2", "乙家")
        assert cli_b.get("/api/admin/family").json()["bank_hours"]["open_hour"] == 8
        assert cli_a.get("/api/admin/family").json()["bank_hours"]["open_hour"] == 6
    finally:
        os.environ.pop("SUNSHINE_DB", None)
        os.environ["SECRET_KEY"] = "test-secret"


def test_checkin_hours_endpoint_reachable():
    """打卡时间窗这次才做成家族设置并接上家长端——端点要有测试钉住。"""
    os.environ["SECRET_KEY"] = "prod-secret"
    os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "ck-cfg.db")
    db.init_db()
    try:
        cli, _kid = _new_family("ckcfg", "打卡家")
        hours = cli.get("/api/admin/family").json()["checkin_hours"]
        assert (hours["from"], hours["until"]) == ("07:00", "21:00"), hours
        r = cli.put("/api/admin/family/checkin-hours", json={"enabled": True, "open_hour": 6, "close_hour": 23})
        assert r.status_code == 200, r.text
        assert (r.json()["checkin_hours"]["from"], r.json()["checkin_hours"]["until"]) == ("06:00", "23:00")
        r = cli.put("/api/admin/family/checkin-hours", json={"enabled": True, "open_hour": 21, "close_hour": 7})
        assert r.status_code == 400, r.text
    finally:
        os.environ.pop("SUNSHINE_DB", None)
        os.environ["SECRET_KEY"] = "test-secret"


if __name__ == "__main__":
    test_bank_window_hours()
    test_tests_skip_bank_window_by_default()
    test_bank_api_rejects_after_hours()
    test_bank_hours_configurable_and_validated()
    test_bank_window_follows_configured_hours()
    test_bank_hours_are_per_family()
    test_checkin_hours_endpoint_reachable()
    print("bank hours ok")
