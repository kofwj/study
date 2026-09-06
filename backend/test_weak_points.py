# -*- coding: utf-8 -*-
"""M2.3 薄弱点。python3 test_weak_points.py"""
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
    with TestClient(main.app) as p:
        assert p.post("/api/auth/register", json={"account": "wp", "pin": "weakpt88", "family_name": "薄家"}).status_code == 200
        r = p.post("/api/admin/kids", json={"name": "甲", "account": "jia", "pin": "1111"})
        assert r.status_code == 200, r.text
        a = r.json()["id"]
        r = p.post("/api/admin/kids", json={"name": "乙", "account": "yi", "pin": "2222"})
        b = r.json()["id"]
        uid = "g5s1-cn-1"
        tags = p.get("/api/admin/unit-tags?unit_id=" + uid).json()
        assert tags, tags
        t1, t2 = tags[0]["tag_id"], tags[-1]["tag_id"]
        all_tags = p.get("/api/admin/unit-tags").json()
        assert len(all_tags["tags"]) >= 20 and len(all_tags["unit_tags"]) >= 50
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t1], "note": "默写"})
        assert r.status_code == 200, r.text
        assert [x["tag_id"] for x in r.json()] == [t1]
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2]})
        assert [x["tag_id"] for x in r.json()] == [t2]
        r0 = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": []})
        assert r0.status_code == 200 and r0.json() == []
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2]})
        assert [x["tag_id"] for x in r.json()] == [t2]
        with TestClient(main.app) as k:
            assert k.post("/api/auth/login", json={"account": "jia", "pin": "1111"}).status_code == 200
            mine = k.get("/api/weak-points?unit_id=" + uid).json()
            assert [x["tag_id"] for x in mine] == [t2]
            assert k.put("/api/weak-points", json={"unit_id": uid, "tag_ids": [t1]}).status_code != 200
            tasks = k.get("/api/tasks").json()
            assert t2 in str(tasks.get("weak_tags", {}).get(uid, [])) or tasks["weak_tags"].get(uid)
        with TestClient(main.app) as k2:
            assert k2.post("/api/auth/login", json={"account": "yi", "pin": "2222"}).status_code == 200
            assert k2.get("/api/weak-points?unit_id=" + uid).json() == []
        print("weak_points ok")


if __name__ == "__main__":
    main_fn()
