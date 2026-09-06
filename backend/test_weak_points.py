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
        r = p.get("/api/admin/weak-points?unit_id=&selected_kid=" + a)
        assert r.status_code == 200, r.text
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t1], "note": "默写"})
        assert r.status_code == 200, r.text
        assert [x["tag_id"] for x in r.json()] == [t1]
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2]})
        assert [x["tag_id"] for x in r.json()] == [t2]
        r0 = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": []})
        assert r0.status_code == 200 and r0.json() == []
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2]})
        assert [x["tag_id"] for x in r.json()] == [t2]
        from datetime import date
        today = date.today().isoformat()
        p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": []})
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2], "first_review": today})
        assert r.status_code == 200
        due = p.get("/api/admin/review-due", params={"selected_kid": a}).json()
        assert any(x["tag_id"] == t2 for x in due)
        wid = next(x["id"] for x in due if x["tag_id"] == t2)
        # 过关升档：间隔 1→3 天，今天不再到期
        assert p.post(f"/api/admin/weak-points/{wid}/judge", json={"action": "pass"}).status_code == 200
        assert not any(x["id"] == wid for x in p.get("/api/admin/review-due", params={"selected_kid": a}).json())
        # 还在错降档：清空重设今天到期后再 fail，归到 1 天（明天）
        p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": []})
        p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2], "first_review": today})
        wid2 = next(x["id"] for x in p.get("/api/admin/review-due", params={"selected_kid": a}).json() if x["tag_id"] == t2)
        assert p.post(f"/api/admin/weak-points/{wid2}/judge", json={"action": "fail"}).status_code == 200
        assert not any(x["id"] == wid2 for x in p.get("/api/admin/review-due", params={"selected_kid": a}).json())
        # 已巩固：结束留历史
        assert p.post(f"/api/admin/weak-points/{wid2}/judge", json={"action": "done"}).status_code == 200
        r = p.put("/api/admin/weak-points", json={"kid_id": a, "unit_id": uid, "tag_ids": [t2], "first_review": today})
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
