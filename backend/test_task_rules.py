# -*- coding: utf-8 -*-
"""教材任务只读、自定义任务可管理、测试奖励只影响新成绩。"""
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


def test_system_tasks_readonly_and_custom_kid_scope():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "tr", "pin": "taskrule", "family_name": "规家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "jia2", "pin": "111222"})
        assert r.status_code == 200, r.text
        a = r.json()["id"]
        r = cli.post("/api/admin/kids", json={"name": "乙", "account": "yi2", "pin": "222333"})
        b = r.json()["id"]
        sys_id = "g5s1-cn-1-1"
        body = {"subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "改", "title": "不该改", "sunshine": 1}
        assert cli.put(f"/api/admin/tasks/{sys_id}", json=body).status_code == 403
        assert cli.delete(f"/api/admin/tasks/{sys_id}").status_code == 403

        r = cli.post("/api/admin/tasks", json={
            "subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "练", "title": "全家订正", "sunshine": 4,
        })
        assert r.status_code == 200, r.text
        fam_tid = r.json()["id"]
        r = cli.post("/api/admin/tasks", json={
            "subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "练", "title": "甲的口算", "sunshine": 3, "kid_id": a,
        })
        assert r.status_code == 200, r.text
        a_tid = r.json()["id"]
        ids_a = {x["id"] for x in cli.get("/api/tasks?selected_kid=" + a).json()["tasks"]}
        ids_b = {x["id"] for x in cli.get("/api/tasks?selected_kid=" + b).json()["tasks"]}
        assert fam_tid in ids_a and fam_tid in ids_b
        assert a_tid in ids_a and a_tid not in ids_b
        assert cli.put(f"/api/admin/tasks/{a_tid}", json={
            "subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "写", "title": "甲的口算改", "sunshine": 6, "kid_id": a,
        }).status_code == 200
        titles = {x["id"]: x["title"] for x in cli.get("/api/tasks?selected_kid=" + a).json()["tasks"]}
        assert titles[a_tid] == "甲的口算改"
        assert cli.delete(f"/api/admin/tasks/{a_tid}").status_code == 200
        ids_a = {x["id"] for x in cli.get("/api/tasks?selected_kid=" + a).json()["tasks"]}
        assert a_tid not in ids_a
        other = "kid-not-here"
        assert cli.post("/api/admin/tasks", json={
            "subject_id": "语文", "unit_id": "g5s1-cn-1", "action": "练", "title": "串台", "sunshine": 1, "kid_id": other,
        }).status_code == 404


def test_custom_bands_only_affect_new_scores():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "tb", "pin": "testband", "family_name": "档家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "丙", "account": "bing", "pin": "111222"})
        kid = r.json()["id"]
        q = "?selected_kid=" + kid
        first = cli.post("/api/admin/tests" + q, json={"subject_id": "数学", "score": 100})
        assert first.status_code == 200, first.text
        old_sun = first.json()["sunshine"]
        assert old_sun == 30
        bands = [[100, 40], [95, 25], [90, 15], [85, 10], [0, 0]]
        assert cli.put("/api/admin/insight-rules", json={"test_bands": bands}).status_code == 200
        second = cli.post("/api/admin/tests" + q, json={"subject_id": "数学", "score": 100})
        assert second.status_code == 200 and second.json()["sunshine"] == 40
        rows = cli.get("/api/admin/tests" + q).json()
        by_id = {str(x["id"]): x for x in rows}
        assert by_id[str(first.json()["id"])]["sunshine"] == old_sun
        assert by_id[str(second.json()["id"])]["sunshine"] == 40
