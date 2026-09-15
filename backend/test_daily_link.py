# -*- coding: utf-8 -*-
"""每日任务的「去哪做」链接：孩子端点卡片直接跳过去（如大队委题库 /quiz/）。

重点不在功能本身，而在**链接校验**：这个值会被渲染成孩子端的 <a href>，
放行 javascript: 就等于给了家长一个往孩子端塞存储型 XSS 的口子。
所以非法值一律存成 NULL（= 没有链接），而不是报错打断家长。
"""
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


def _setup(cli):
    r = cli.post("/api/auth/register",
                 json={"account": "lnk", "pin": "dailylink", "family_name": "链接家"})
    assert r.status_code == 200, r.text
    kid = cli.post("/api/admin/kids",
                   json={"name": "乐乐", "account": "lnklele", "pin": "111222"}).json()["id"]
    return kid


def _stored(kid):
    c = db.connect(admin=True)
    row = c.execute("SELECT link FROM daily_tasks WHERE id=?", (kid,)).fetchone()
    return row["link"] if row else None


def test_link_roundtrip_to_kid():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        r = cli.post("/api/admin/daily", json={
            "subject_id": "综合", "name": "大队委竞选复习", "sunshine": 5, "link": "/quiz/"})
        assert r.status_code == 200, r.text
        did = r.json()["id"]

        # 孩子端拿得到，才能渲染出「去做」按钮
        t = cli.get("/api/tasks?selected_kid=" + kid).json()
        row = next(d for d in t["daily"] if d["id"] == did)
        assert row["link"] == "/quiz/"

        # https 也放行
        assert cli.put("/api/admin/daily/" + did, json={
            "subject_id": "综合", "name": "大队委竞选复习",
            "link": "https://study.anemy.org/quiz/"}).status_code == 200
        t = cli.get("/api/tasks?selected_kid=" + kid).json()
        row = next(d for d in t["daily"] if d["id"] == did)
        assert row["link"] == "https://study.anemy.org/quiz/"

        # 清空 = 回到「没有跳转」
        assert cli.put("/api/admin/daily/" + did, json={
            "subject_id": "综合", "name": "大队委竞选复习", "link": ""}).status_code == 200
        t = cli.get("/api/tasks?selected_kid=" + kid).json()
        row = next(d for d in t["daily"] if d["id"] == did)
        assert not row["link"]


def test_link_rejects_dangerous_schemes():
    """非法写法一律落成 NULL，不是报错 —— 家长填错不该被弹窗拦住。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        bad = [
            "javascript:alert(1)",
            "JavaScript:alert(document.cookie)",
            "  javascript:alert(1)  ",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "//evil.example.com/steal",   # 协议相对：会跳到站外
            "/\\evil.example.com",        # 反斜杠变体
            "http://study.anemy.org/quiz/",  # 站点是 https，不放行明文 http
            "ftp://x/y",
        ]
        for i, raw in enumerate(bad):
            did = cli.post("/api/admin/daily", json={
                "subject_id": "综合", "name": f"坏链接{i}", "link": raw}).json()["id"]
            assert _stored(did) is None, f"{raw!r} 不该被存下来"

        # 对照组：合法的能存下来，证明上面不是因为「整条写入都失败」才为 NULL
        ok = cli.post("/api/admin/daily", json={
            "subject_id": "综合", "name": "好链接", "link": "/quiz/"}).json()["id"]
        assert _stored(ok) == "/quiz/"


def test_link_is_per_task_not_global():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        with_link = cli.post("/api/admin/daily", json={
            "subject_id": "综合", "name": "带链接", "link": "/quiz/"}).json()["id"]
        without = cli.post("/api/admin/daily", json={
            "subject_id": "体育", "name": "跳绳打卡"}).json()["id"]

        t = cli.get("/api/tasks?selected_kid=" + kid).json()
        rows = {d["id"]: d for d in t["daily"]}
        assert rows[with_link]["link"] == "/quiz/"
        assert not rows[without]["link"], "没填链接的任务不该凭空长出链接"
