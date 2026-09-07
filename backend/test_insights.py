# -*- coding: utf-8 -*-
"""M1.1 结论引擎。python3 test_insights.py"""
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


def _dates():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    last_m = monday - timedelta(days=7)
    return today, monday, last_m


def main_fn():
    db.init_db()
    today, monday, last_m = _dates()
    with TestClient(main.app) as cli:
        r = cli.post("/api/auth/register", json={"account": "ins", "pin": "insight8", "family_name": "诊断家"})
        assert r.status_code == 200, r.text
        r = cli.post("/api/admin/kids", json={"name": "小测", "account": "xiaoc", "pin": "1111"})
        assert r.status_code == 200, r.text
        kid = r.json()["id"]
        q = "?selected_kid=" + kid

        got = cli.get("/api/admin/insights").json()
        assert got["rules"]["test_fail_score"] == 80
        row = next(x for x in got["kids"] if x["kid_id"] == kid)
        # 没数据：可能没有结论，或只有空周连击（周末会有 gap）
        assert row["name"] == "小测"

        c = db.connect()
        c.execute(
            "INSERT INTO tests(subject_id,unit_id,score,sunshine,note,date,created_at,kid_id) VALUES(?,?,?,?,?,?,?,?)",
            ("语文", "g5s1-cn-1", 70, 5, "", today.isoformat(), db.now(), kid))
        c.execute(
            "INSERT INTO tests(subject_id,unit_id,score,sunshine,note,date,created_at,kid_id) VALUES(?,?,?,?,?,?,?,?)",
            ("语文", "g5s1-cn-1", 75, 5, "", today.isoformat(), db.now(), kid))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert ins and ins["type"] == "weak_unit"
        assert "连续 2 次低于 80 分" in ins["text"]
        assert "语文" in ins["text"] and "cn《" not in ins["text"]
        assert ins["action"] == "单元测试"

        r = cli.put("/api/admin/insight-rules", json={"test_fail_score": 60})
        assert r.status_code == 200
        assert r.json()["test_fail_score"] == 60
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert not ins or ins["type"] != "weak_unit"

        assert cli.put("/api/admin/insight-rules", json={"test_fail_score": 101}).status_code == 400
        bands = [[100, 40], [95, 25], [90, 15], [85, 10], [0, 0]]
        r = cli.put("/api/admin/insight-rules", json={"test_bands": bands})
        assert r.status_code == 200 and r.json()["test_bands"] == bands
        r = cli.post("/api/admin/tests" + q, json={"subject_id": "数学", "score": 100})
        assert r.status_code == 200 and r.json()["sunshine"] == 40
        assert cli.put("/api/admin/insight-rules", json={"test_bands": [[100, 1], [95, 2]]}).status_code == 400
        assert cli.put("/api/admin/insight-rules", json={"drop_ratio": 0.05}).status_code == 400
        assert cli.put("/api/admin/insight-rules", json={"streak_break": 9}).status_code == 400

        cli.put("/api/admin/insight-rules", json={"test_fail_score": 80, "streak_break": 1})
        c = db.connect()
        c.execute("DELETE FROM tests WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM checkins WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM completions WHERE kid_id=?", (kid,))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert ins and ins["type"] == "streak_break"
        assert "没打卡" in ins["text"]

        cli.put("/api/admin/insight-rules", json={"streak_break": 7})
        c = db.connect()
        c.execute("DELETE FROM checkins WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM completions WHERE kid_id=?", (kid,))
        span = (today - monday).days
        last_from = monday - timedelta(days=7)
        last_to = last_from + timedelta(days=span)
        for i in range(5):
            c.execute(
                "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (f"drop-{i}", last_to.isoformat(), "completed", 5, None, "unit", db.now(), kid))
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("drop-this", today.isoformat(), "completed", 5, None, "unit", db.now(), kid))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert ins and ins["type"] == "drop"
        assert "少" in ins["text"] and "%" in ins["text"]

        # 体测：没性别跳过；低于达标命中；达到不命中
        cli.put("/api/admin/insight-rules", json={"streak_break": 7, "drop_ratio": 0.9})
        c = db.connect()
        c.execute("DELETE FROM tests WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM checkins WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM completions WHERE kid_id=?", (kid,))
        c.execute(
            "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            ("pe-jump-rope", today.isoformat(), "completed", 5, '{"n1m": 20}', "daily", db.now(), kid))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert not ins or ins["type"] != "fitness"
        assert cli.put("/api/admin/kids/" + kid, json={"name": "小测", "term_id": "g5s1", "gender": "不明"}).status_code == 400
        assert cli.put("/api/admin/kids/" + kid, json={"name": "小测", "term_id": "g5s1", "gender": "男"}).status_code == 200
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert ins and ins["type"] == "fitness"
        assert "跳绳" in ins["text"] and "还差" in ins["text"]
        c = db.connect()
        c.execute("UPDATE completions SET metrics=? WHERE kid_id=? AND task_id=?", ('{"n1m": 56}', kid, "pe-jump-rope"))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert not ins or ins["type"] != "fitness"
        n = db.connect().execute("SELECT COUNT(*) FROM fitness_standards").fetchone()[0]
        assert n >= 32
        tasks = cli.get("/api/tasks" + q).json()
        g = tasks["fitness_goals"]["pe-jump-rope"]
        assert g["pass"] == 56 and g["excellent"] == 148 and g["grade"] == 5

        # 复习到期盯点优先；本周练牢含 resolved + 第 5 轮
        cli.put("/api/admin/insight-rules", json={"streak_break": 7, "drop_ratio": 0.9})
        c = db.connect()
        c.execute("DELETE FROM tests WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM checkins WHERE kid_id=?", (kid,))
        c.execute("DELETE FROM completions WHERE kid_id=?", (kid,))
        c.execute(
            "INSERT INTO weak_points(kid_id,unit_id,tag_id,note,status,interval_idx,review_due_at,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (kid, "g5s1-cn-1", "cn-zi", "", "open", 0, today.isoformat(), db.now(), db.now()))
        c.commit(); c.close()
        ins = next(x["insight"] for x in cli.get("/api/admin/insights").json()["kids"] if x["kid_id"] == kid)
        assert ins and ins["type"] == "review_due" and ins["action"] == "今日复习"
        c = db.connect()
        c.execute("UPDATE weak_points SET status='resolved', updated_at=? WHERE kid_id=?", (db.now(), kid))
        c.execute(
            "INSERT INTO weak_points(kid_id,unit_id,tag_id,note,status,interval_idx,review_due_at,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (kid, "g5s1-cn-1", "cn-read", "", "open", 4, None, db.now(), db.now()))
        c.commit(); c.close()
        wk = cli.get("/api/admin/weekly" + q).json()
        assert "字词" in (wk.get("mastered") or []) and "阅读理解" in (wk.get("mastered") or [])
        print("insights ok")


if __name__ == "__main__":
    main_fn()
