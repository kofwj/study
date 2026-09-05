# -*- coding: utf-8 -*-
"""P2 多娃隔离。python3 test_kids.py"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient
import main  # noqa: E402


def main_fn():
    db.init_db()
    with TestClient(main.app) as cli:
        r = cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"})
        assert r.status_code == 200 and r.json()["force_pin_change"] is True
        assert cli.post("/api/auth/logout").status_code == 200
        assert cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "弟弟", "account": "didi", "pin": "2222", "term_id": "g5s1"})
        assert r.status_code == 200, r.text
        didi = r.json()["id"]
        kids = cli.get("/api/admin/kids").json()
        lele = next(k["id"] for k in kids if k["account"] == "lele")

        assert cli.get("/api/tasks").json()["kid_id"] == lele
        t = cli.get("/api/tasks?selected_kid=" + didi).json()
        assert t["kid_id"] == didi and t["kid_name"] == "弟弟"

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

        r = cli.post("/api/admin/kids", json={"name": "老三", "account": "san", "pin": "3333"})
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
        r = cli.put("/api/admin/kids/" + didi, json={"name": "弟弟", "term_id": "g5s1", "pin": "2222"})
        assert r.status_code == 200, r.text
        assert cli.post("/api/auth/logout").status_code == 200
        r = cli.post("/api/auth/login", json={"account": "didi", "pin": "2222"})
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
        print("kids ok", lele[:8], didi[:8], "earned", e_lele, e_didi, "cursors", cur_l, cur_d)


if __name__ == "__main__":
    main_fn()
