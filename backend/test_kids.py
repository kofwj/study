# -*- coding: utf-8 -*-
"""P2 多娃隔离。python3 test_kids.py"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient
import main  # noqa: E402


def test_kid_auto_pin():
    """不填密码时随机生成 6 位 PIN，不再用固定的 0129。"""
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "小满", "account": "xiaoman", "term_id": "g5s1"})
        assert r.status_code == 200, r.text
        pin = r.json().get("pin")
        assert pin and len(pin) == 6 and pin.isdigit()
        assert pin != "0129"
        # 自动生成的密码能登录孩子账号
        assert cli.post("/api/auth/logout").status_code == 200
        r = cli.post("/api/auth/login", json={"account": "xiaoman", "pin": pin})
        assert r.status_code == 200, r.text


def test_kids():
    db.init_db()
    with TestClient(main.app) as cli:
        r = cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"})
        assert r.status_code == 200 and r.json()["force_pin_change"] is True
        assert cli.post("/api/auth/logout").status_code == 200
        assert cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "弟弟", "account": "didi", "pin": "222333", "term_id": "g5s1"})
        assert r.status_code == 200, r.text
        didi = r.json()["id"]
        kids = cli.get("/api/admin/kids").json()
        lele = next(k["id"] for k in kids if k["account"] == "lele")

        assert cli.get("/api/tasks").json()["kid_id"] == lele
        t = cli.get("/api/tasks?selected_kid=" + didi).json()
        assert t["kid_id"] == didi and t["kid_name"] == "弟弟"
        assert "fitness_goals" in t and "test_fail_score" in t
        assert t["fitness_goals"] == {}
        assert cli.put("/api/admin/kids/" + didi, json={"name": "弟弟", "account": "didi", "term_id": "g5s1", "gender": "男"}).status_code == 200
        t2 = cli.get("/api/tasks?selected_kid=" + didi).json()
        assert t2["fitness_goals"]["pe-jump-rope"]["pass"] == 56
        assert t2["fitness_goals"]["pe-jump-rope"]["excellent"] == 148

        assert cli.post("/api/checkin?selected_kid=" + lele).status_code == 200
        assert cli.post("/api/checkin?selected_kid=" + didi).status_code == 200
        assert cli.post("/api/checkin?selected_kid=" + didi).status_code == 409

        daily = t["daily"][0]["id"]
        assert cli.post("/api/complete?selected_kid=" + lele, json={"task_id": daily}).status_code == 200
        assert cli.post("/api/complete?selected_kid=" + didi, json={"task_id": daily}).status_code == 200
        e_lele = cli.get("/api/overview?selected_kid=" + lele).json()["earned"]
        e_didi = cli.get("/api/overview?selected_kid=" + didi).json()["earned"]
        assert e_lele > 0 and e_didi > 0
        t_didi = cli.get("/api/tasks?selected_kid=" + didi).json()
        t_lele = cli.get("/api/tasks?selected_kid=" + lele).json()
        d_didi = next(x for x in t_didi["daily"] if x["id"] == daily)
        d_lele = next(x for x in t_lele["daily"] if x["id"] == daily)
        assert d_didi["done_today"] and d_lele["done_today"]

        r = cli.post("/api/admin/kids", json={"name": "老三", "account": "san", "pin": "333444"})
        assert r.status_code == 200, r.text
        san = r.json()["id"]
        assert cli.delete("/api/admin/kids/" + san).status_code == 200
        assert len(cli.get("/api/admin/kids").json()) == 2
        assert cli.get("/api/tasks?selected_kid=kid-other").status_code == 403
        assert cli.post("/api/admin/cursor?selected_kid=" + didi, json={"subject_id": "语文", "task_id": "g5s1-cn-1-1"}).status_code == 200
        cur_d = cli.get("/api/tasks?selected_kid=" + didi).json()["cursors"].get("语文")
        cur_l = cli.get("/api/tasks?selected_kid=" + lele).json()["cursors"].get("语文")
        assert cur_d == "g5s1-cn-1-1"
        assert cur_l != cur_d
        r = cli.put("/api/admin/kids/" + didi, json={"name": "弟弟", "account": "erzi", "term_id": "g5s1", "pin": "222333"})
        assert r.status_code == 200, r.text
        assert cli.post("/api/auth/logout").status_code == 200
        r = cli.post("/api/auth/login", json={"account": "erzi", "pin": "222333"})
        assert r.status_code == 200 and r.json()["force_pin_change"] is False
        assert cli.post("/api/auth/logout").status_code == 200
        assert cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200

        r = cli.post("/api/admin/rewards", json={"name": "小奖", "price": 1, "category": "测"})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        c = db.connect()
        c.execute("UPDATE rewards SET need_approval=1 WHERE id=?", (rid,))
        c.commit(); c.close()
        assert cli.post("/api/rewards/redeem?selected_kid=" + didi, json={"reward_id": rid}).status_code == 200
        pend = cli.get("/api/admin/redemptions?selected_kid=" + didi).json()
        pid = next(x["id"] for x in pend if x["status"] == "pending")
        before = cli.get("/api/overview?selected_kid=" + didi).json()["balance"]
        before_l = cli.get("/api/overview?selected_kid=" + lele).json()["balance"]
        assert cli.post(f"/api/admin/redemptions/{pid}/approve?selected_kid=" + lele).status_code == 200
        after = cli.get("/api/overview?selected_kid=" + didi).json()["balance"]
        after_l = cli.get("/api/overview?selected_kid=" + lele).json()["balance"]
        assert after == before - 1
        assert after_l == before_l

        wk = cli.get("/api/admin/weekly?selected_kid=" + lele).json()
        assert len(wk.get("kids") or []) >= 2
        assert all("spent" in x and "streak" in x for x in wk["kids"])

        r = cli.post("/api/custom-task", json={"subject_id": "语文", "title": "全家作业", "sunshine": 5})
        assert r.status_code == 200, r.text
        fam_tid = r.json()["id"]
        ids_l = {x["id"] for x in cli.get("/api/tasks?selected_kid=" + lele).json()["tasks"]}
        ids_d = {x["id"] for x in cli.get("/api/tasks?selected_kid=" + didi).json()["tasks"]}
        assert fam_tid in ids_l and fam_tid in ids_d
        # 取消会冲正且标记原记录，允许修正后重新完成，但不会留下额外阳光。
        tid = next(x["id"] for x in cli.get("/api/tasks?selected_kid=" + didi).json()["tasks"] if not x.get("done") and not x.get("locked") and not x.get("past"))
        before = cli.get("/api/overview?selected_kid=" + didi).json()["balance"]
        assert cli.post("/api/complete?selected_kid=" + didi, json={"task_id": tid}).status_code == 200
        mid = cli.get("/api/overview?selected_kid=" + didi).json()["balance"]
        assert mid > before
        assert cli.post("/api/cancel?selected_kid=" + didi, json={"task_id": tid}).status_code == 200
        assert cli.get("/api/overview?selected_kid=" + didi).json()["balance"] == before
        assert cli.post("/api/complete?selected_kid=" + didi, json={"task_id": tid}).status_code == 200
        assert cli.get("/api/overview?selected_kid=" + didi).json()["balance"] == mid
        c = db.connect()
        rows = c.execute("SELECT status FROM completions WHERE task_id=? AND kid_id=? ORDER BY id", (tid, didi)).fetchall()
        c.close()
        assert [r["status"] for r in rows] == ["cancelled", "completed"]
        assert cli.post("/api/admin/rewards", json={"name": "负奖", "price": -10, "category": "测"}).status_code == 400
        assert cli.post("/api/admin/tasks", json={"subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "练", "title": "负任务", "sunshine": -3}).status_code == 400
        assert cli.post("/api/custom-task", json={"subject_id": "语文", "title": "负自定义", "sunshine": -3}).status_code == 400
def test_daily_cancel_allows_recompletion():
    """每日任务取消后，当天可再次完成。"""
    import os
    db_path = os.environ.get("SUNSHINE_DB", "sunshine.db")
    for f in [db_path, f"{db_path}-shm", f"{db_path}-wal"]:
        if os.path.exists(f):
            os.remove(f)
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        task_id = cli.get("/api/tasks").json()["daily"][0]["id"]
        before = cli.get("/api/overview").json()["balance"]
        first = cli.post("/api/complete", json={"task_id": task_id})
        assert first.status_code == 200, first.text
        assert cli.post("/api/cancel", json={"task_id": task_id}).status_code == 200
        daily = next(x for x in cli.get("/api/tasks").json()["daily"] if x["id"] == task_id)
        assert not daily["done_today"]
        second = cli.post("/api/complete", json={"task_id": task_id})
        assert second.status_code == 200, second.text
        assert cli.get("/api/overview").json()["balance"] == before + second.json()["delta"]


def test_cancel_concurrent_once():
    """连点取消只冲正一次，余额回到完成前。"""
    import concurrent.futures
    import os
    db_path = os.environ.get("SUNSHINE_DB", "sunshine.db")
    for f in [db_path, f"{db_path}-shm", f"{db_path}-wal"]:
        if os.path.exists(f):
            os.remove(f)
    db.init_db()
    with TestClient(main.app) as cli1, TestClient(main.app) as cli2:
        assert cli1.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200
        kid = next(k["id"] for k in cli1.get("/api/admin/kids").json() if k["account"] == "lele")
        q = "?selected_kid=" + kid
        tid = next(x["id"] for x in cli1.get("/api/tasks" + q).json()["tasks"]
                   if not x.get("done") and not x.get("locked") and not x.get("past"))
        before = cli1.get("/api/overview" + q).json()["balance"]
        assert cli1.post("/api/complete" + q, json={"task_id": tid}).status_code == 200
        mid = cli1.get("/api/overview" + q).json()["balance"]
        assert mid > before
        assert cli2.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200

        def do_cancel(client):
            r = client.post("/api/cancel" + q, json={"task_id": tid})
            return r.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            codes = list(ex.map(do_cancel, (cli1, cli2)))
        assert 200 in codes
        assert 500 not in codes
        assert cli1.get("/api/overview" + q).json()["balance"] == before
        c = db.connect()
        n = c.execute(
            "SELECT COUNT(*) FROM ledger WHERE kid_id=? AND reason='cancel' AND ref_id LIKE 'cmp-%'",
            (kid,)).fetchone()[0]
        c.close()
        assert n == 1


def test_streak():
    from datetime import date, timedelta
    db.init_db()
    c = db.connect()
    ghost = "kid-streak"
    y = (date.today() - timedelta(days=1)).isoformat()
    yy = (date.today() - timedelta(days=2)).isoformat()
    c.execute("INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)", (y, 0, db.now(), ghost))
    c.commit()
    assert main.streak(c, ghost) == 1
    c.execute("INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)", (yy, 0, db.now(), ghost))
    c.commit()
    assert main.streak(c, ghost) == 2
    c.close()
    print("streak ok")


def _ach_by_id(items):
    return {a["id"]: a for a in items}


def test_achievement_earned_idempotent():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        kid = db.DEFAULT_KID
        before = cli.get("/api/overview").json()["earned"]
        c = db.connect()
        c.execute("DELETE FROM completions WHERE kid_id=? AND task_id=? AND date=?",
                  (kid, "cn-read", db.today()))
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("cn-read", db.today(), "completed", 5, None, "daily", db.now(), kid))
        c.commit()
        c.close()
        first = cli.get("/api/achievements")
        assert first.status_code == 200, first.text
        a1 = _ach_by_id(first.json())["first"]
        assert a1["unlocked"] and a1["earned"] and a1["earned_at"]
        assert a1["rarity"] == "bronze" and a1["series"] == "milestone"
        ts = a1["earned_at"]
        second = cli.get("/api/achievements")
        assert second.status_code == 200
        a2 = _ach_by_id(second.json())["first"]
        assert a2["earned_at"] == ts
        c = db.connect()
        n = c.execute("SELECT COUNT(*) FROM achievement_earned WHERE kid_id=? AND ach_id=?",
                      (kid, "first")).fetchone()[0]
        after = cli.get("/api/overview").json()["earned"]
        c.close()
        assert n == 1
        assert after == before  # 成就表不影响 earned()


def test_achievement_seen_toggle():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        c = db.connect()
        c.execute("DELETE FROM completions WHERE kid_id=? AND task_id=? AND date=?",
                  (db.DEFAULT_KID, "cn-read", db.today()))
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("cn-read", db.today(), "completed", 5, None, "daily", db.now(), db.DEFAULT_KID))
        c.commit()
        c.close()
        a = _ach_by_id(cli.get("/api/achievements").json())["first"]
        assert a["seen"] == 0
        r = cli.post("/api/achievements/first/mark-seen")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert _ach_by_id(cli.get("/api/achievements").json())["first"]["seen"] == 1
        assert cli.post("/api/achievements/first/mark-seen").status_code == 200
        assert _ach_by_id(cli.get("/api/achievements").json())["first"]["seen"] == 1
        assert cli.post("/api/achievements/not-a-real/mark-seen").status_code == 200


def test_achievement_chain_progress():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        kid = db.DEFAULT_KID
        items = _ach_by_id(cli.get("/api/achievements").json())
        assert items["sun500"]["chain_progress"] == "0/3"
        assert items["sun2000"]["chain_progress"] == "0/3"
        assert items["streak7"]["chain_progress"] == "0/4"
        c = db.connect()
        db.insert_ledger(c, db.today(), 500, "task", "sun-t1", "测", kid)
        c.commit()
        c.close()
        items = _ach_by_id(cli.get("/api/achievements").json())
        assert items["sun500"]["unlocked"] and items["sun500"]["chain_progress"] == "1/3"
        assert items["sun2000"]["chain_progress"] == "1/3"
        assert items["sun5000"]["chain_progress"] == "1/3"
        c = db.connect()
        db.insert_ledger(c, db.today(), 1500, "task", "sun-t2", "测", kid)
        c.commit()
        c.close()
        items = _ach_by_id(cli.get("/api/achievements").json())
        assert items["sun2000"]["unlocked"] and items["sun2000"]["chain_progress"] == "2/3"
        c = db.connect()
        db.insert_ledger(c, db.today(), 3000, "task", "sun-t3", "测", kid)
        c.commit()
        c.close()
        items = _ach_by_id(cli.get("/api/achievements").json())
        assert items["sun5000"]["unlocked"] and items["sun5000"]["rarity"] == "legend"
        assert items["sun500"]["chain_progress"] == "3/3"
        assert items["sun2000"]["chain_progress"] == "3/3"
        assert items["sun5000"]["chain_progress"] == "3/3"


def test_new_achievements_query():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        c = db.connect()
        c.execute("DELETE FROM achievement_earned WHERE kid_id=?", (db.DEFAULT_KID,))
        c.execute("DELETE FROM completions WHERE kid_id=? AND task_id=? AND date=?",
                  (db.DEFAULT_KID, "cn-read", db.today()))
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("cn-read", db.today(), "completed", 5, None, "daily", db.now(), db.DEFAULT_KID))
        db.insert_ledger(c, db.today(), 500, "task", "sun-new", "测", db.DEFAULT_KID)
        c.commit()
        c.close()
        items = cli.get("/api/achievements").json()
        unseen = [a for a in items if a["unlocked"] and a["seen"] == 0]
        assert len(unseen) >= 2
        assert {a["id"] for a in unseen} >= {"first", "sun500"}
        assert cli.post("/api/achievements/first/mark-seen").status_code == 200
        items = cli.get("/api/achievements").json()
        unseen_ids = {a["id"] for a in items if a["unlocked"] and a["seen"] == 0}
        assert "first" not in unseen_ids
        assert "sun500" in unseen_ids
        assert len(main.ACHIEVEMENTS) == 25


if __name__ == "__main__":
    test_kids()
    test_daily_cancel_allows_recompletion()
    test_cancel_concurrent_once()
    test_streak()
    test_achievement_earned_idempotent()
    test_achievement_seen_toggle()
    test_achievement_chain_progress()
    test_new_achievements_query()
