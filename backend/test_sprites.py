# -*- coding: utf-8 -*-
"""阳光图鉴 2.0：开箱、星尘、基地、值班、晨间。尘不进 ledger。"""
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
import sprites as spritemod  # noqa: E402


def _parent(cli, account, pin, family):
    r = cli.post("/api/auth/register", json={"account": account, "pin": pin, "family_name": family})
    assert r.status_code == 200, r.text
    r = cli.post("/api/admin/kids", json={"name": "娃", "account": account + "k", "pin": "111222"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _give_boxes(kid, n):
    today = date.today()
    c = db.connect()
    for i in range(3 * n):
        d = (today - timedelta(days=i)).isoformat()
        c.execute(
            "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)",
            (d, 0, db.now(), kid),
        )
    c.commit()
    c.close()


def _ledger_n(kid):
    c = db.connect()
    n = c.execute("SELECT COUNT(*) FROM ledger WHERE kid_id=?", (kid,)).fetchone()[0]
    c.close()
    return n


def _earned(kid):
    c = db.connect()
    n = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE reason NOT IN ('redeem','bank_deposit','bank_withdraw') AND kid_id=?",
        (kid,),
    ).fetchone()[0]
    c.close()
    return n


def test_no_box_unchanged():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "s0", "wordpass", "空箱家")
        n0 = _ledger_n(kid)
        g = cli.get("/api/sprites").json()
        assert g["enabled"] is True and g["owned"] == 0 and g["dust"] == 0
        r = cli.post("/api/open_box")
        assert r.status_code == 409
        assert "宝箱" in r.json()["detail"]
        c = db.connect()
        assert c.execute("SELECT COUNT(*) FROM kid_sprites WHERE kid_id=?", (kid,)).fetchone()[0] == 0
        assert db.get_kid_setting(c, kid, "sprite_dust", None) is None
        c.close()
        assert _ledger_n(kid) == n0


def test_first_box_grants_sprite():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "s1", "wordpass", "开箱家")
        _give_boxes(kid, 1)
        e0 = _earned(kid)
        r = cli.post("/api/open_box")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kind"] == "sprite"
        assert body["delta"] in (1, 2, 3)
        assert body["duplicate"] is False
        assert body["dust_gain"] == 0
        assert body["item"].startswith("sp-")
        assert body["sprite"]["name"]
        c = db.connect()
        assert c.execute("SELECT COUNT(*) FROM kid_sprites WHERE kid_id=?", (kid,)).fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sprite_opens WHERE kid_id=?", (kid,)).fetchone()[0] == 1
        row = c.execute(
            "SELECT reason, ref_id, delta FROM ledger WHERE kid_id=? AND reason='box'", (kid,)
        ).fetchone()
        assert row["ref_id"] == "box-1" and row["delta"] == body["delta"]
        assert db.get_kid_setting(c, kid, "box_opened", "0") == "1"
        c.close()
        assert _earned(kid) == e0 + body["delta"]


def test_unowned_first_then_duplicate():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "s2", "wordpass", "图鉴家")
        _give_boxes(kid, 13)
        ids = []
        for i in range(12):
            r = cli.post("/api/open_box")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["duplicate"] is False
            ids.append(b["item"])
            assert cli.get("/api/sprites").json()["owned"] == i + 1
        assert len(set(ids)) == 12
        r = cli.post("/api/open_box")
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["duplicate"] is True
        assert b["dust"] == 6 and b["dust_gain"] == 6
        c = db.connect()
        assert c.execute("SELECT COUNT(*) FROM kid_sprites WHERE kid_id=?", (kid,)).fetchone()[0] == 12
        stars = [r[0] for r in c.execute("SELECT stars FROM kid_sprites WHERE kid_id=?", (kid,))]
        assert stars == [0] * 12
        n13 = c.execute("SELECT COUNT(*) FROM sprite_opens WHERE kid_id=?", (kid,)).fetchone()[0]
        dust = int(db.get_kid_setting(c, kid, "sprite_dust", "0"))
        c.close()
        assert n13 == 13 and dust == 6
        r = cli.post("/api/open_box")
        assert r.status_code == 409
        assert cli.get("/api/sprites").json()["dust"] == 6


def test_star_and_profile_and_ledger_untouched():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "s3", "wordpass", "升星家")
        _give_boxes(kid, 1)
        sid = cli.post("/api/open_box").json()["item"]
        n0 = _ledger_n(kid)
        assert cli.post(f"/api/sprites/{sid}/star").status_code == 400
        c = db.connect()
        db.set_kid_setting(c, kid, "sprite_dust", "12")
        c.commit()
        c.close()
        r = cli.post(f"/api/sprites/{sid}/star")
        assert r.status_code == 200, r.text
        assert r.json()["stars"] == 1 and r.json()["dust"] == 0
        assert _ledger_n(kid) == n0
        c = db.connect()
        db.set_kid_setting(c, kid, "sprite_dust", "36")
        c.commit()
        c.close()
        assert cli.post(f"/api/sprites/{sid}/star").json()["stars"] == 2
        assert cli.post(f"/api/sprites/{sid}/star").json()["stars"] == 3
        r = cli.post(f"/api/sprites/{sid}/star")
        assert r.status_code == 400 and "三颗星" in r.json()["detail"]
        assert cli.post("/api/sprites/nope/star").status_code == 400
        other = next(d["id"] for d in spritemod.SPRITE_DEFS if d["id"] != sid)
        assert cli.post(f"/api/sprites/{other}/star").status_code == 400
        assert cli.post(f"/api/sprites/{sid}/profile", json={"nickname": "", "flavor": ""}).status_code == 400
        assert cli.post(f"/api/sprites/{sid}/profile", json={"nickname": "一二三四五六七八九", "flavor": ""}).status_code == 400
        assert cli.post(f"/api/sprites/{sid}/profile", json={"nickname": "小暖", "flavor": "x" * 17}).status_code == 400
        assert cli.post(f"/api/sprites/{other}/profile", json={"nickname": "弯弯", "flavor": ""}).status_code == 404
        r = cli.post(f"/api/sprites/{sid}/profile", json={"nickname": "小暖", "flavor": "喜欢晒太阳"})
        assert r.status_code == 200 and r.json()["nickname"] == "小暖"
        assert _ledger_n(kid) == n0


def test_switch_off_plain_sunshine():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "s4", "wordpass", "开关家")
        _give_boxes(kid, 1)
        r = cli.put("/api/admin/sprites-config", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False and r.json()["base_enabled"] is True
        r = cli.put("/api/admin/sprites-config", json={"base_enabled": True})
        assert r.status_code == 200 and r.json()["base_enabled"] is True
        r = cli.post("/api/open_box")
        assert r.status_code == 200, r.text
        b = r.json()
        assert "kind" not in b
        assert b["delta"] in range(3, 11)
        c = db.connect()
        assert c.execute("SELECT COUNT(*) FROM kid_sprites WHERE kid_id=?", (kid,)).fetchone()[0] == 0
        c.close()
        g = cli.get("/api/sprites").json()
        assert g["enabled"] is False and g["owned"] == 0 and g["base_enabled"] is True


def test_family_isolation():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        ka = _parent(a, "alice_s", "alice888", "A图")
        kb = _parent(b, "bob_s", "bob88888", "B图")
        _give_boxes(ka, 1)
        a.post("/api/open_box")
        ga = a.get("/api/sprites").json()
        gb = b.get("/api/sprites").json()
        assert ga["owned"] >= 1
        assert gb["owned"] == 0
        assert gb["base_items"] == [] and gb["on_duty"] == ""


def test_base_buy_duty_morning():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        ka = _parent(a, "alice_b", "alice888", "A基")
        kb = _parent(b, "bob_b", "bob88888", "B基")
        _give_boxes(ka, 2)
        sid = a.post("/api/open_box").json()["item"]
        sid2 = a.post("/api/open_box").json()["item"]
        n0 = _ledger_n(ka)
        assert a.post("/api/sprites/base/sun-rocket/buy").status_code == 400
        assert a.post("/api/sprites/base/leaf-ladder/buy").status_code == 400
        assert a.post("/api/sprites/base/sun-pinwheel/buy").status_code == 400
        c = db.connect()
        db.set_kid_setting(c, ka, "sprite_dust", "40")
        c.commit()
        c.close()
        r = a.post("/api/sprites/base/sun-telescope/buy")
        assert r.status_code == 200, r.text
        assert "sun-telescope" in r.json()["base_items"]
        assert r.json()["dust"] == 20
        assert a.post("/api/sprites/base/sun-telescope/buy").status_code == 409
        assert _ledger_n(ka) == n0
        assert a.post("/api/sprites/sp-moon/duty").status_code == 404
        r = a.post(f"/api/sprites/{sid}/duty")
        assert r.json()["on_duty"] == sid
        r = a.post(f"/api/sprites/{sid2}/duty")
        assert r.json()["on_duty"] == sid2
        assert a.post("/api/sprites/duty-clear").json()["on_duty"] == ""
        gb = b.get("/api/sprites").json()
        assert gb["base_items"] == [] and gb["on_duty"] == ""

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        c = db.connect()
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,kind,created_at,kid_id) VALUES(?,?,?,?,?,?,?)",
            ("u-test", yesterday, "completed", 0, "unit", db.now(), ka),
        )
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,kind,created_at,kid_id) VALUES(?,?,?,?,?,?,?)",
            ("u-test2", yesterday, "completed", 0, "unit", db.now(), ka),
        )
        c.execute(
            "INSERT INTO word_sessions(id,kid_id,family_id,study_date,book_ids_json,task_json,state,started_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("ws1", ka, "f", yesterday, "[]", "[]", "completed", db.now()),
        )
        c.commit()
        c.close()
        g = a.get("/api/sprites").json()
        assert g["morning"]["new"] is True
        assert "2" in g["morning"]["text"]
        assert "1" in g["morning"]["text"] or "星" in g["morning"]["text"]
        n1 = _ledger_n(ka)
        assert a.post("/api/sprites/morning-ack").status_code == 200
        assert _ledger_n(ka) == n1
        assert a.get("/api/sprites").json()["morning"]["new"] is False

        # 无精灵的孩子：昨天有学习 → 无人称句
        y = (date.today() - timedelta(days=1)).isoformat()
        c = db.connect()
        c.execute(
            "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)",
            (y, 0, db.now(), kb),
        )
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,kind,created_at,kid_id) VALUES(?,?,?,?,?,?,?)",
            ("d1", y, "completed", 0, "daily", db.now(), kb),
        )
        c.commit()
        c.close()
        gm = b.get("/api/sprites").json()
        assert gm["morning"]["new"] is True
        assert gm["morning"]["who"] == ""
        assert "秘密基地" in gm["morning"]["text"]

        # 昨天无学习
        kc_cli = TestClient(main.app)
        kc = _parent(kc_cli, "carol_b", "carol888", "C基")
        assert kc_cli.get("/api/sprites").json()["morning"]["new"] is False


def test_migration_recorded():
    db.init_db()
    c = db.connect()
    migs = {r[0] for r in c.execute("SELECT id FROM schema_migrations").fetchall()}
    c.close()
    assert "034_sprites" in migs
    assert len(spritemod.SPRITE_DEFS) == 12
    assert len(spritemod.BASE_ITEMS) == 6
    cap = next(x for x in spritemod.BASE_LAYOUT["leaf"] if x["id"] == "memo-capsule")
    assert cap["y"] < 70 and cap["x"] > 50
    wheel = next(x for x in spritemod.BASE_LAYOUT["sun"] if x["id"] == "trace-pinwheel")
    assert wheel["kind"] == "trace"
