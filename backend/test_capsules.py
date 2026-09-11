# -*- coding: utf-8 -*-
"""时间胶囊第一刀。"""
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient
import main  # noqa: E402
import capsules as capmod  # noqa: E402


def _login(cli):
    assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200


def _wipe_capsules():
    c = db.connect()
    c.execute("DELETE FROM capsules")
    c.commit()
    c.close()


def _body(**kw):
    data = {
        "when_kind": "next_term",
        "q_good": "口算很快",
        "q_wish": "英语单词再熟一点",
        "q_line": "以后的我要继续练字",
    }
    data.update(kw)
    return data


def test_next_term_anchor():
    assert capmod.next_term_open_on(date(2026, 9, 11)) == date(2027, 2, 16)
    assert capmod.next_term_open_on(date(2027, 2, 16)) == date(2027, 9, 1)
    assert capmod.next_term_open_on(date(2027, 9, 1)) == date(2028, 2, 16)


def test_capsule_seal_hide_and_reopen():
    db.init_db()
    _wipe_capsules()
    with TestClient(main.app) as cli:
        _login(cli)
        r = cli.get("/api/capsule")
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "empty"
        kinds = {o["kind"] for o in r.json()["options"]}
        assert kinds == {"week", "month", "next_term", "year", "streak30", "custom"}
        assert r.json()["questions"]
        assert r.json()["min_open_on"]

        r = cli.post("/api/capsule", json=_body())
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "sealed"
        cap = r.json()["capsule"]
        assert "q_good" not in cap
        assert cli.post("/api/capsule", json=_body()).status_code == 409
        assert cli.post("/api/capsule/open").status_code == 409

        r = cli.post("/api/capsule", json=_body(q_good=""))
        assert r.status_code == 409

        kid = cli.get("/api/tasks").json()["kid_id"]
        c = db.connect()
        c.execute("UPDATE capsules SET open_on=? WHERE kid_id=?", ("2000-01-01", kid))
        c.commit()
        c.close()
        r = cli.get("/api/capsule")
        assert r.json()["state"] == "ready"
        opened = cli.post("/api/capsule/open")
        assert opened.status_code == 200, opened.text
        assert opened.json()["q_good"] == "口算很快"
        assert opened.json()["now"]["level"]
        assert cli.get("/api/capsule").json()["state"] == "empty"
        again = cli.post("/api/capsule", json=_body(q_line="下一封"))
        assert again.status_code == 200, again.text
        led = cli.get("/api/ledger").json()
        assert not any(x.get("reason") == "capsule" for x in led)


def test_capsule_validates_text():
    db.init_db()
    _wipe_capsules()
    with TestClient(main.app) as cli:
        _login(cli)
        assert cli.post("/api/capsule", json=_body(q_good="!!!")).status_code == 400
        assert cli.post("/api/capsule", json=_body(q_line="哈" * 41)).status_code == 400
        assert cli.post("/api/capsule", json=_body(when_kind="birthday")).status_code == 400
        assert cli.post("/api/capsule", json=_body(when_kind="custom")).status_code == 400
        assert cli.post("/api/capsule", json=_body(when_kind="custom", open_on="2000-01-01")).status_code == 400


def test_streak30_needs_overnight_then_thirty():
    today = date(2026, 9, 11)
    snap = {"streak": 12}
    row = {"when_kind": "streak30", "sealed_on": today.isoformat(), "snapshot": snap}
    assert capmod._streak30_ready(row, today, 30) is False
    assert capmod._streak30_ready(row, today + timedelta(days=1), 30) is True
    row30 = {"when_kind": "streak30", "sealed_on": today.isoformat(), "snapshot": {"streak": 30}}
    assert capmod._streak30_ready(row30, today + timedelta(days=29), 40) is False
    assert capmod._streak30_ready(row30, today + timedelta(days=30), 40) is True


def test_week_and_custom_open_on():
    today = date(2026, 9, 11)
    assert capmod.open_on_for("week", today, 0) == date(2026, 9, 18)
    assert capmod.open_on_for("month", today, 0) == date(2026, 10, 11)
    assert capmod.open_on_for("year", today, 0) == date(2027, 9, 11)
    assert capmod.open_on_for("custom", today, 0, "2026-12-25") == date(2026, 12, 25)
    try:
        capmod.open_on_for("custom", today, 0, "2026-09-11")
        assert False
    except capmod.CapsuleError as e:
        assert e.status == 400


def test_custom_seal_uses_picked_day():
    db.init_db()
    _wipe_capsules()
    with TestClient(main.app) as cli:
        _login(cli)
        day = cli.get("/api/capsule").json()["min_open_on"]
        r = cli.post("/api/capsule", json=_body(when_kind="custom", open_on=day))
        assert r.status_code == 200, r.text
        assert r.json()["capsule"]["when_kind"] == "custom"
        assert r.json()["capsule"]["open_on"] == day


if __name__ == "__main__":
    test_next_term_anchor()
    test_capsule_seal_hide_and_reopen()
    test_capsule_validates_text()
    test_streak30_needs_overnight_then_thirty()
    test_week_and_custom_open_on()
    test_custom_seal_uses_picked_day()
    print("capsules ok")
