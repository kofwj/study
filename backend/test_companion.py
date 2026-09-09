# -*- coding: utf-8 -*-
"""主屏伙伴：阳光精灵只读 earned/streak，不写 ledger。"""
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient
import main  # noqa: E402


def _parent(cli, account, pin, family):
    r = cli.post("/api/auth/register", json={"account": account, "pin": pin, "family_name": family})
    assert r.status_code == 200, r.text
    r = cli.post("/api/admin/kids", json={"name": "娃", "account": account + "k", "pin": "111222"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_earned(kid, n, ref="cmp-sun"):
    c = db.connect()
    db.insert_ledger(c, db.today(), int(n), "task", ref, "测", kid_id=kid)
    c.commit()
    c.close()


def test_companion_first_get_silent_align():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "c0", "wordpass", "蛋家")
        t = cli.get("/api/tasks").json()
        cp = t["companion"]
        assert cp["stage"] == "egg" and cp["stage_name"] == "阳光蛋"
        assert cp["evolve"] is False and cp["aura"] is None
        assert cp["next_stage"] == "sprout" and cp["next_need"] == 50
        c = db.connect()
        seen = db.get_kid_setting(c, kid, "companion_stage_seen", "")
        c.close()
        assert seen == "egg"


def test_companion_sprout_new_account_no_evolve():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "c1", "wordpass", "芽家")
        _add_earned(kid, 50)
        t = cli.get("/api/tasks").json()
        cp = t["companion"]
        assert cp["stage"] == "sprout" and cp["earned"] == 50
        assert cp["evolve"] is False
        assert abs(cp["progress"] - 0.0) < 0.01
        c = db.connect()
        assert db.get_kid_setting(c, kid, "companion_stage_seen", "") == "sprout"
        n = c.execute("SELECT COUNT(*) FROM ledger WHERE kid_id=?", (kid,)).fetchone()[0]
        c.close()
        assert n == 1


def test_companion_evolve_and_ack():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "c2", "wordpass", "长大家")
        cli.get("/api/tasks")
        _add_earned(kid, 50)
        c = db.connect()
        db.set_kid_setting(c, kid, "companion_stage_seen", "egg")
        c.commit()
        c.close()
        t = cli.get("/api/tasks").json()
        assert t["companion"]["stage"] == "sprout" and t["companion"]["evolve"] is True
        before = cli.get("/api/overview").json()["earned"]
        c = db.connect()
        n0 = c.execute("SELECT COUNT(*) FROM ledger WHERE kid_id=?", (kid,)).fetchone()[0]
        c.close()
        r = cli.post("/api/companion/ack-evolve")
        assert r.status_code == 200, r.text
        assert r.json()["evolve"] is False
        assert r.json()["stage"] == "sprout"
        r2 = cli.post("/api/companion/ack-evolve")
        assert r2.status_code == 200 and r2.json()["evolve"] is False
        assert cli.get("/api/overview").json()["earned"] == before
        c = db.connect()
        n1 = c.execute("SELECT COUNT(*) FROM ledger WHERE kid_id=?", (kid,)).fetchone()[0]
        c.close()
        assert n1 == n0


def test_companion_name_and_isolation():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        _parent(a, "alicec", "alice888", "A伴")
        _parent(b, "bobc", "bob88888", "B伴")
        r = a.post("/api/companion/name", json={"name": "小芽"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "小芽"
        assert a.get("/api/tasks").json()["companion"]["name"] == "小芽"
        assert b.get("/api/tasks").json()["companion"]["name"] == ""
        assert a.post("/api/companion/name", json={"name": ""}).status_code == 400
        assert a.post("/api/companion/name", json={"name": "一二三四五六七八九"}).status_code == 400
        r = a.post("/api/companion/name", json={"name": "  阳光花  "})
        assert r.status_code == 200 and r.json()["name"] == "阳光花"


def test_companion_aura_not_stage():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "c3", "wordpass", "光晕家")
        today = date.today()
        c = db.connect()
        for i in range(7):
            d = (today - timedelta(days=i)).isoformat()
            c.execute(
                "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)",
                (d, 0, db.now(), kid),
            )
        c.commit()
        c.close()
        cp = cli.get("/api/tasks").json()["companion"]
        assert cp["aura"] == "week"
        assert cp["stage"] == "egg"
