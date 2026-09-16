# -*- coding: utf-8 -*-
"""B4 家庭共同目标。python3 -m pytest -q test_family_goal.py

口径（2026-09-16 定）：完成卡数 = 窗口内 completed（取消不算）；
运动次数 = 体育类「每日任务」完成次数；签到天数 = 各娃之和（同日重复签到不重复算）。
周窗口 = 本周一 → 本周日；达标每人发一次 0–20 阳光（默认 5，家长定）；过期/关闭都不扣分。
"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SUNSHINE_NOW"] = "2026-09-16T12:00:00"   # 周三 12:00：打卡窗口内，周窗口 = 09-14 ~ 09-20

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


def _family(cli, tag):
    r = cli.post("/api/auth/register",
                 json={"account": tag + "p", "pin": tag + "pin123", "family_name": tag + "家"})
    assert r.status_code == 200, r.text
    kids = []
    for i, name in enumerate(("乐乐", "弟弟")):
        r = cli.post("/api/admin/kids",
                     json={"name": name, "account": f"{tag}k{i}", "pin": "111222"})
        assert r.status_code == 200, r.text
        kids.append(r.json()["id"])
    return kids


def _login(tag, i):
    cli = TestClient(main.app)
    r = cli.post("/api/auth/login", json={"account": f"{tag}k{i}", "pin": "111222"})
    assert r.status_code == 200, r.text
    return cli


def _daily(cli, name, subject="体育"):
    r = cli.post("/api/admin/daily", json={"subject_id": subject, "name": name, "sunshine": 5})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _balances(cli):
    return {x["name"]: x["balance"] for x in cli.get("/api/admin/family-today").json()["kids"]}


def _goal_rows(reason="family_goal"):
    c = db.connect()
    n = c.execute("SELECT COUNT(*) FROM ledger WHERE reason=?", (reason,)).fetchone()[0]
    c.close()
    return n


def test_create_and_single_active_goal():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "ga")
        r = cli.get("/api/admin/family-goal")
        assert r.status_code == 200 and r.json()["goal"] is None, r.text

        r = cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 2, "reward": 5})
        assert r.status_code == 200, r.text
        assert r.json()["goal"]["status"] == "active" and r.json()["progress"]["value"] == 0, r.text

        # 越界 / 非法指标
        assert cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 0, "reward": 5}).status_code == 400
        assert cli.put("/api/admin/family-goal", json={"metric": "nope", "target": 3, "reward": 5}).status_code == 400
        assert cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 3, "reward": 21}).status_code == 400

        # 再建一个：旧的关掉，同时只有 1 个 active
        r = cli.put("/api/admin/family-goal", json={"metric": "sport", "target": 3, "reward": 0})
        assert r.status_code == 200 and r.json()["goal"]["metric"] == "sport", r.text
        c = db.connect()
        n_active = c.execute("SELECT COUNT(*) FROM family_goals WHERE status='active'").fetchone()[0]
        n_closed = c.execute("SELECT COUNT(*) FROM family_goals WHERE status='closed'").fetchone()[0]
        c.close()
        assert n_active == 1 and n_closed == 1, (n_active, n_closed)


def test_cards_goal_grants_once_per_kid():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gb")
        task = _daily(cli, "全家跳绳")
        r = cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 2, "reward": 5})
        assert r.status_code == 200, r.text
        before = _balances(cli)
        ledger_before = _goal_rows()

        with _login("gb", 0) as k0:
            assert k0.post("/api/complete", json={"task_id": task}).status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["progress"]["value"] == 1 and g["progress"]["remaining"] == 1, g
        assert _goal_rows() == ledger_before, "没达标不该发"
        assert _balances(cli)["乐乐"] - before["乐乐"] == 5, "只该拿任务本身那 5"

        with _login("gb", 1) as k1:
            assert k1.post("/api/complete", json={"task_id": task}).status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["goal"]["status"] == "reached", g
        # 乐乐只多目标奖 5；弟弟多「任务 5 + 目标奖 5」
        after = _balances(cli)
        assert after["乐乐"] - before["乐乐"] == 10, (before, after)
        assert after["弟弟"] - before["弟弟"] == 10, (before, after)
        assert _goal_rows() == ledger_before + 2, "两个娃各一笔 family_goal"


def test_sport_only_counts_pe_daily():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gc")
        pe = _daily(cli, "全家跳绳", "体育")
        other = _daily(cli, "朗读十分钟", "语文")
        r = cli.put("/api/admin/family-goal", json={"metric": "sport", "target": 5, "reward": 0})
        assert r.status_code == 200, r.text
        with _login("gc", 0) as k0:
            assert k0.post("/api/complete", json={"task_id": pe}).status_code == 200
            assert k0.post("/api/complete", json={"task_id": other}).status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["progress"]["value"] == 1, g       # 只算体育那条每日任务
        assert {x["name"]: x["value"] for x in g["by_kid"]}["乐乐"] == 1, g["by_kid"]


def test_checkin_days_sum_over_kids():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gd")
        r = cli.put("/api/admin/family-goal", json={"metric": "checkin_days", "target": 7, "reward": 0})
        assert r.status_code == 200, r.text
        with _login("gd", 0) as k0, _login("gd", 1) as k1:
            assert k0.post("/api/checkin").status_code == 200
            assert k0.post("/api/checkin").status_code == 409          # 同日重复签到
            assert k1.post("/api/checkin").status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["progress"]["value"] == 2, g          # 各娃之和：两个娃同日各算 1 天
        assert {x["name"]: x["value"] for x in g["by_kid"]} == {"乐乐": 1, "弟弟": 1}, g["by_kid"]


def test_no_double_grant_on_reread():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "ge")
        task = _daily(cli, "全家跳绳")
        cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 1, "reward": 5})
        before = _balances(cli)
        with _login("ge", 0) as k0:
            assert k0.post("/api/complete", json={"task_id": task}).status_code == 200
        assert cli.get("/api/admin/family-goal").json()["goal"]["status"] == "reached"
        n1 = _goal_rows()
        # 再读两次 + 另一个娃再打一次卡：都不该再多发
        cli.get("/api/admin/family-goal")
        cli.get("/api/admin/family-today")
        with _login("ge", 1) as k1:
            assert k1.post("/api/complete", json={"task_id": task}).status_code == 200
        assert _goal_rows() == n1, "达标后不该重复发"
        after = _balances(cli)
        # 弟弟：目标奖 5（达标时按人发）+ 自己那条任务 5；关键断言是上面 ledger 笔数没涨
        assert after["弟弟"] - before["弟弟"] == 10, (before, after)


def test_zero_reward_grants_nothing():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gf")
        task = _daily(cli, "全家跳绳")
        before_ledger = _goal_rows()
        before = _balances(cli)
        cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 1, "reward": 0})
        with _login("gf", 0) as k0:
            assert k0.post("/api/complete", json={"task_id": task}).status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["goal"]["status"] == "reached", g
        assert _goal_rows() == before_ledger, "reward=0 不写流水"
        assert _balances(cli)["乐乐"] - before["乐乐"] == 5, "只该拿任务本身那 5"


def test_family_isolation():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        _family(a, "gg")
        _family(b, "gh")
        task_a = _daily(a, "A家跳绳")
        a.put("/api/admin/family-goal", json={"metric": "cards", "target": 5, "reward": 5})
        b.put("/api/admin/family-goal", json={"metric": "cards", "target": 5, "reward": 5})
        with _login("gg", 0) as ka:
            assert ka.post("/api/complete", json={"task_id": task_a}).status_code == 200
        assert a.get("/api/admin/family-goal").json()["progress"]["value"] == 1
        assert b.get("/api/admin/family-goal").json()["progress"]["value"] == 0, "B 家不该看到 A 家的完成量"


def test_kid_forbidden_on_parent_endpoints():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gi")
        with _login("gi", 0) as k0:
            assert k0.get("/api/admin/family-goal").status_code == 403
            assert k0.put("/api/admin/family-goal",
                          json={"metric": "cards", "target": 1, "reward": 5}).status_code == 403
            assert k0.post("/api/admin/family-goal/close").status_code == 403


def test_expired_goal_grants_nothing():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gj")
        task = _daily(cli, "全家跳绳")
        cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 1, "reward": 5})
        c = db.connect()
        c.execute("UPDATE family_goals SET started_at='2026-09-07', ends_at='2026-09-13' WHERE status='active'")
        c.commit()
        c.close()
        ledger_before = _goal_rows()
        with _login("gj", 0) as k0:
            assert k0.post("/api/complete", json={"task_id": task}).status_code == 200
        g = cli.get("/api/admin/family-goal").json()
        assert g["goal"] is None, g                    # 过期的不再是「当前目标」
        assert _goal_rows() == ledger_before, "过期不发放"
        c = db.connect()
        assert c.execute("SELECT status FROM family_goals ORDER BY id DESC LIMIT 1").fetchone()[0] == "expired"
        assert c.execute("SELECT COUNT(*) FROM ledger WHERE delta<0").fetchone()[0] == 0, "不扣分"
        c.close()


def test_kid_payload_has_family_goal_without_siblings():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gk")
        task = _daily(cli, "全家跳绳")
        with _login("gk", 0) as k0:
            assert k0.get("/api/tasks").json()["family_goal"] is None      # 没目标就不给这行
        cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 2, "reward": 5})
        with _login("gk", 0) as k0:
            fg = k0.get("/api/tasks").json()["family_goal"]
            assert fg["remaining"] == 2 and "还差 2 张" in fg["text"], fg
            assert "by_kid" not in fg, "孩子端不给别的娃明细"
            assert k0.post("/api/complete", json={"task_id": task}).status_code == 200
            fg = k0.get("/api/tasks").json()["family_goal"]
            assert fg["progress"] == 1 and fg["remaining"] == 1 and not fg["reached"], fg
        with _login("gk", 1) as k1:
            assert k1.post("/api/complete", json={"task_id": task}).status_code == 200
        with _login("gk", 0) as k0:
            fg = k0.get("/api/tasks").json()["family_goal"]
            assert fg["reached"] is True and "达成" in fg["text"], fg


def test_goal_error_does_not_break_core_pages(monkeypatch):
    """B4 是可选功能：目标这块出任何问题，概览页（family-today）和孩子端 payload 都必须照常返回，
    打卡也要照常成功（结算失败不冒泡）。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "gl")
        task = _daily(cli, "全家跳绳")
        cli.put("/api/admin/family-goal", json={"metric": "cards", "target": 5, "reward": 5})

        def boom(*a, **k):
            raise RuntimeError("goal side broken")

        monkeypatch.setattr(main, "_goal_breakdown", boom)

        r = cli.get("/api/admin/family-today")
        assert r.status_code == 200, r.text
        assert r.json()["family_goal"]["goal"] is None, r.text
        assert "kids" in r.json(), r.text

        with _login("gl", 0) as k0:
            r = k0.get("/api/tasks")
            assert r.status_code == 200, r.text
            assert r.json()["family_goal"] is None, r.text
            r = k0.post("/api/complete", json={"task_id": task})
            assert r.status_code == 200, r.text
