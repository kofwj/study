# -*- coding: utf-8 -*-
"""Quiz Phase 2 回归测试：题库种子、会话、判题、每日任务闸门。

覆盖：
  1. 迁移 042 后 system 题库自动入库；
  2. 练习/模拟考 session 生命周期（start → attempt → complete）；
  3. choice/multi 后端自动判题；blank/qa correct 可为 null；
  4. daily task require_quiz=1 时，孩子没完成 quiz 不能打卡；
  5. 孩子完成 quiz 后，require_quiz 的 daily task 可以正常打卡领阳光。
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
                 json={"account": "quizp", "pin": "quizphase", "family_name": "Quiz家"})
    assert r.status_code == 200, r.text
    kid = cli.post("/api/admin/kids",
                   json={"name": "乐乐", "account": "quizlele", "pin": "111222"}).json()["id"]
    return kid


def _login_kid(cli, account="quizlele", pin="111222"):
    assert cli.post("/api/auth/login", json={"account": account, "pin": pin}).status_code == 200


def _reset_db():
    p = db.db_path()
    if p.exists():
        p.unlink()
    db.DB_PATH = p


def test_quiz_seed_and_list():
    """迁移后 quiz_banks / quiz_questions 自动从 seed JSON 入库。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)
        banks = cli.get("/api/quiz/banks").json()
        assert len(banks) >= 1
        bank = banks[0]
        assert bank["id"] == "ddw-2026"
        assert "name" in bank

        qs = cli.get(f"/api/quiz/banks/{bank['id']}/questions").json()
        assert len(qs) >= 1
        kinds = {q["kind"] for q in qs}
        assert kinds & {"choice", "blank", "qa", "multi"}


def test_quiz_session_lifecycle():
    """start → attempt → complete 正常走完。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)

        # start
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice", "qids": ["ddw-2026-001", "ddw-2026-002"]})
        assert r.status_code == 200, r.text
        sess = r.json()["session"]
        assert sess["state"] == "active"
        sid = sess["id"]

        # attempt (blank, correct=null)
        a1 = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": "ddw-2026-001", "answer": "", "correct": None}).json()
        assert a1["correct"] is None

        # attempt (blank, correct=false)
        a2 = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": "ddw-2026-002", "answer": "", "correct": False}).json()
        assert a2["correct"] is False

        # complete
        c = cli.post("/api/quiz/complete", json={"session_id": sid}).json()
        assert c["finished"] is True
        assert c["session"]["state"] == "completed"


def test_quiz_auto_judge_choice():
    """choice 题后端自动判题。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)

        # 找一道 choice 题
        qs = cli.get("/api/quiz/banks/ddw-2026/questions").json()
        choice_q = next((q for q in qs if q["kind"] == "choice"), None)
        assert choice_q is not None
        qid = choice_q["id"]
        correct_key = choice_q["answer"][0]
        wrong_key = next((o["k"] for o in choice_q["options"] if o["k"] != correct_key), None)
        assert wrong_key is not None

        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "exam", "qids": [qid]})
        sid = r.json()["session"]["id"]

        # 答错
        w = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": qid, "answer": wrong_key}).json()
        assert w["correct"] is False

        # 再 start 一个新的（用 practice 避免 unique 冲突）
        r2 = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice", "qids": [qid]})
        sid2 = r2.json()["session"]["id"]
        ri = cli.post("/api/quiz/attempt", json={"session_id": sid2, "question_id": qid, "answer": correct_key}).json()
        assert ri["correct"] is True


def test_quiz_done_today_gates_daily():
    """require_quiz=1 的 daily task，孩子没完成 quiz 时打卡返回 409。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)

        # 家长创建一个 require_quiz 的 daily task（此时 cli 还是家长身份）
        did = cli.post("/api/admin/daily", json={
            "subject_id": "体育", "name": "大队委复习", "sunshine": 5,
            "require_quiz": True,
        }).json()["id"]

        _login_kid(cli)
        # 孩子今天没做 quiz，打卡被拒绝
        r = cli.post("/api/complete", json={"task_id": did})
        assert r.status_code == 409
        assert "题库" in r.json()["detail"]


def test_quiz_done_today_allows_daily_after_complete():
    """孩子完成 quiz 后，require_quiz 的 daily task 可以正常打卡。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)

        did = cli.post("/api/admin/daily", json={
            "subject_id": "体育", "name": "大队委复习", "sunshine": 5,
            "require_quiz": True,
        }).json()["id"]

        _login_kid(cli)
        # 完成一个 quiz session
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice", "qids": ["ddw-2026-001"]})
        sid = r.json()["session"]["id"]
        cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": "ddw-2026-001", "answer": "", "correct": True})
        cli.post("/api/quiz/complete", json={"session_id": sid})

        # 现在可以打卡了
        r2 = cli.post("/api/complete", json={"task_id": did})
        assert r2.status_code == 200, r2.text
        assert r2.json()["delta"] == 5


def test_quiz_today_endpoint():
    """/api/quiz/today 返回今天的完成状态。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)

        # 初始未做
        t0 = cli.get("/api/quiz/today").json()
        assert t0["done"] is False

        # 完成
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice", "qids": ["ddw-2026-001"]})
        sid = r.json()["session"]["id"]
        cli.post("/api/quiz/complete", json={"session_id": sid})

        t1 = cli.get("/api/quiz/today").json()
        assert t1["done"] is True


def test_migration_042_creates_tables():
    """迁移 042 后 quiz 四张表和 daily_tasks.require_quiz 列存在。"""
    _reset_db()
    db.init_db()
    conn = db.connect(admin=True)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'quiz_%'"
    ).fetchall()]
    assert "quiz_banks" in tables
    assert "quiz_questions" in tables
    assert "quiz_sessions" in tables
    assert "quiz_attempts" in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_tasks)").fetchall()}
    assert "require_quiz" in cols
    conn.close()


if __name__ == "__main__":
    import traceback
    failures = []
    tests = list(globals().items())
    for name, fn in tests:
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print("OK", name)
        except Exception as e:
            print("FAIL", name, e)
            failures.append((name, traceback.format_exc()))
    if failures:
        print("\n--- failures ---")
        for name, tb in failures:
            print(name)
            print(tb)
        raise SystemExit(1)
    print("\nAll passed.")
