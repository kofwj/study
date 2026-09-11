# -*- coding: utf-8 -*-
"""孩子端学科显示开关：默认隐藏道法，家长可打开。"""
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


def test_default_hides_daofa_and_can_toggle():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "sv", "pin": "subjectv", "family_name": "显家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "jia3", "pin": "111222"})
        assert r.status_code == 200, r.text
        kid = r.json()["id"]
        q = "?selected_kid=" + kid
        t = cli.get("/api/tasks" + q).json()
        assert "道法" in t["hidden_subjects"]
        assert "语文" not in t["hidden_subjects"]

        bad = cli.post("/api/admin/subject-visible" + q, json={"subject_id": "不存在", "on": True})
        assert bad.status_code == 404

        r = cli.post("/api/admin/subject-visible" + q, json={"subject_id": "道法", "on": True})
        assert r.status_code == 200, r.text
        assert "道法" not in r.json()["hidden_subjects"]
        t = cli.get("/api/tasks" + q).json()
        assert t["hidden_subjects"] == []

        r = cli.post("/api/admin/subject-visible" + q, json={"subject_id": "科学", "on": False})
        assert r.status_code == 200
        assert r.json()["hidden_subjects"] == ["科学"]
        t = cli.get("/api/tasks" + q).json()
        assert t["hidden_subjects"] == ["科学"]
