# -*- coding: utf-8 -*-
"""P3 多家庭隔离。python3 test_family.py"""
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
    with TestClient(main.app) as a, TestClient(main.app) as b:
        r = a.post("/api/auth/register", json={"account": "alice", "pin": "alice888", "family_name": "A家"})
        assert r.status_code == 200, r.text
        r = a.post("/api/admin/kids", json={"name": "阿乐", "account": "ale", "pin": "1111"})
        assert r.status_code == 200, r.text
        r = a.post("/api/admin/rewards", json={"name": "A家奖", "price": 3, "category": "测"})
        assert r.status_code == 200, r.text
        names_a = {x["name"] for x in a.get("/api/rewards").json()}
        assert "A家奖" in names_a

        r = b.post("/api/auth/register", json={"account": "bob", "pin": "bob88888", "family_name": "B家"})
        assert r.status_code == 200, r.text
        r = b.post("/api/admin/kids", json={"name": "波波", "account": "bobo", "pin": "2222"})
        assert r.status_code == 200
        names_b = {x["name"] for x in b.get("/api/rewards").json()}
        assert "A家奖" not in names_b
        r = a.post("/api/admin/daily", json={"subject_id": "体育", "name": "A家跳绳", "sunshine": 3})
        assert r.status_code == 200, r.text
        a_daily = {d["name"] for d in a.get("/api/tasks").json()["daily"]}
        b_daily = {d["name"] for d in b.get("/api/tasks").json()["daily"]}
        assert "A家跳绳" in a_daily and "A家跳绳" not in b_daily
        kids_b = b.get("/api/admin/kids").json()
        assert all(k["account"] != "ale" for k in kids_b)

        code = a.post("/api/admin/invite").json()["code"]
        r = b.post("/api/auth/join", json={"account": "carol", "pin": "carol888", "code": code, "name": "卡卡"})
        assert r.status_code == 200, r.text
        # carol 进了 A 家，应看到 A 家奖
        with TestClient(main.app) as c:
            r = c.post("/api/auth/login", json={"account": "carol", "pin": "carol888"})
            assert r.status_code == 200
            names_c = {x["name"] for x in c.get("/api/rewards").json()}
            assert "A家奖" in names_c
        code_o = a.post("/api/admin/invite", json={"role": "observer"}).json()["code"]
        with TestClient(main.app) as o:
            r = o.post("/api/auth/join", json={"account": "oma", "pin": "oma88888", "code": code_o, "name": "奶奶"})
            assert r.status_code == 200 and r.json()["role"] == "observer"
            assert o.get("/api/admin/weekly").status_code == 403
            assert o.post("/api/checkin").status_code == 403
        mid = next(m["id"] for m in a.get("/api/admin/members").json() if m["account"] == "carol")
        assert a.delete("/api/admin/members/" + mid).status_code == 200
        with TestClient(main.app) as c2:
            r = c2.post("/api/auth/login", json={"account": "carol", "pin": "3333"})
            assert r.status_code == 401
        # 邀请码保护：开=一次性，用一次作废
        assert a.put("/api/admin/family/invite_protect", json={"enabled": True}).status_code == 200
        code1 = a.post("/api/admin/invite").json()["code"]
        assert b.post("/api/auth/join", json={"account": "dave", "pin": "dave8888", "code": code1, "name": "戴夫"}).status_code == 200
        assert b.post("/api/auth/join", json={"account": "erin", "pin": "erin8888", "code": code1, "name": "二用"}).status_code != 200
        ivs = {x["code"]: x for x in a.get("/api/admin/invites").json()}
        assert ivs[code1]["used_count"] == 1 and ivs[code1]["used_by"] == "戴夫"
        print("family ok")


if __name__ == "__main__":
    main_fn()
