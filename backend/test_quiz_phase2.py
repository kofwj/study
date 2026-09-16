# -*- coding: utf-8 -*-
"""Quiz Phase 2 回归测试：题库种子、会话、判题、每日任务闸门。

覆盖：
  1. 迁移 042 后 system 题库自动入库；
  2. 练习/模拟考 session 生命周期（start → attempt → complete）；
  3. choice/multi/blank 由后端自动判题（客户端传的 correct 一律不信）；qa 仍自评但必须写答案；
  4. daily task require_quiz=1 时，孩子没完成 quiz 不能打卡；
  5. 孩子完成 quiz 后，require_quiz 的 daily task 可以正常打卡领阳光。
"""
import json
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

        # attempt (blank)：现在**后端自动判** —— 空答案就是错，客户端自报的 correct 不算数
        a1 = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": "ddw-2026-001", "answer": "", "correct": None}).json()
        assert a1["correct"] is False

        # attempt (blank)：答对就是对，哪怕客户端谎报「没答对」
        a2 = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": "ddw-2026-002", "answer": "中国共产党", "correct": False}).json()
        assert a2["correct"] is True

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


def test_study_mode_opens_today_gate():
    """mode=study 可以 start → complete，之后 /api/quiz/today 的 done 为 true。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)

        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "study", "qids": ["ddw-2026-001"]})
        assert r.status_code == 200, r.text
        sess = r.json()["session"]
        assert sess["state"] == "active"
        sid = sess["id"]

        assert cli.get("/api/quiz/today").json()["done"] is False

        c = cli.post("/api/quiz/complete", json={"session_id": sid})
        assert c.status_code == 200, c.text
        assert c.json()["finished"] is True
        assert cli.get("/api/quiz/today").json()["done"] is True


def test_study_start_without_complete_still_blocks_daily():
    """require_quiz 的每日任务：只 start 不 complete，打卡仍 409；complete 后可以打卡。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        did = cli.post("/api/admin/daily", json={
            "subject_id": "体育", "name": "大队委复习", "sunshine": 5,
            "require_quiz": True,
        }).json()["id"]

        _login_kid(cli)
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "study", "qids": ["ddw-2026-001"]})
        sid = r.json()["session"]["id"]

        blocked = cli.post("/api/complete", json={"task_id": did})
        assert blocked.status_code == 409
        assert "题库" in blocked.json()["detail"]

        cli.post("/api/quiz/complete", json={"session_id": sid})
        ok = cli.post("/api/complete", json={"task_id": did})
        assert ok.status_code == 200, ok.text
        assert ok.json()["delta"] == 5


def test_quiz_mode_must_be_known():
    """未知 mode 返回 400。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "nope", "qids": ["ddw-2026-001"]})
        assert r.status_code == 400
        assert "练习方式" in r.json()["detail"]


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


def _play(cli, qids, answers, mode="practice", completes=True):
    """起一组练习 → 逐题作答（answers[i] = (答案, 客户端自报的对错)）→ 可选标记完成。"""
    r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": mode, "qids": qids})
    assert r.status_code == 200, r.text
    sid = r.json()["session"]["id"]
    for qid, (ans, cor) in zip(qids, answers):
        rr = cli.post("/api/quiz/attempt", json={"session_id": sid, "question_id": qid,
                                                "answer": ans, "correct": cor})
        assert rr.status_code == 200, rr.text
    if completes:
        assert cli.post("/api/quiz/complete", json={"session_id": sid}).status_code == 200
    return sid


def _login_parent(cli, account="quizp", pin="quizphase"):
    assert cli.post("/api/auth/login", json={"account": account, "pin": pin}).status_code == 200


def test_blank_is_judged_by_backend_not_by_client():
    """填空题：**后端说了算**。客户端自报对错改不了判决；规范化差异不算错。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)
        # 答对，但客户端谎报「没答对」→ 仍然算对
        sid = _play(cli, ["ddw-2026-001"], [("中国少年先锋队", False)], completes=False)
        _ = sid
        # 重开一次拿回执（record_attempt 的返回里才有判决）
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice",
                                             "qids": ["ddw-2026-001", "ddw-2026-005"]})
        s = r.json()["session"]["id"]
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-001",
                                                "answer": "中国少年先锋队", "correct": False})
        assert rr.status_code == 200 and rr.json()["correct"] is True, rr.text
        # 答错，但客户端谎报「答对了」→ 仍然算错
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-001",
                                                "answer": "乱写", "correct": True})
        assert rr.json()["correct"] is False, rr.text
        # 规范化：书名号 / 空格差异不算错
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-005",
                                                "answer": "我们是共产主义接班人", "correct": None})
        assert rr.status_code == 200 and rr.json()["correct"] is True, rr.text


def test_blank_holes_and_accept_list():
    """填空题：空位数对不上直接算错；accept 同义答案能兜住规范化兜不住的说法。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)
        SEP = "\u001f"
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice",
                                             "qids": ["ddw-2026-023", "ddw-2026-001"]})
        s = r.json()["session"]["id"]
        # 三个空都填对
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-023",
                                                "answer": SEP.join(["三条杠", "二条杠", "一条杠"]),
                                                "correct": None})
        assert rr.json()["correct"] is True, rr.text
        # 只填两个 → 空位数对不上，算错（堵住「少填几个蒙对」）
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-023",
                                                "answer": SEP.join(["三条杠", "二条杠"]),
                                                "correct": None})
        assert rr.json()["correct"] is False, rr.text
        # 空着不写也算错
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-023",
                                                "answer": SEP.join(["", "", ""]), "correct": None})
        assert rr.json()["correct"] is False, rr.text
        # accept 兜底（题库里还没合并草稿，这里手写一条验机制）
        c = db.connect(admin=True)
        c.execute("UPDATE quiz_questions SET accept_json=? WHERE id='ddw-2026-001'",
                  (json.dumps([["少先队"]], ensure_ascii=False),))
        c.commit()
        c.close()
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-001",
                                                "answer": "少先队", "correct": None})
        assert rr.json()["correct"] is True, rr.text


def test_qa_needs_a_written_answer_but_is_self_judged():
    """问答：不写答案不能自评（400）；写了就存下来，判决仍是孩子自评。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)
        r = cli.post("/api/quiz/start", json={"bank_id": "ddw-2026", "mode": "practice",
                                             "qids": ["ddw-2026-006"]})
        s = r.json()["session"]["id"]
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-006",
                                                "answer": "", "correct": True})
        assert rr.status_code == 400, rr.text
        rr = cli.post("/api/quiz/attempt", json={"session_id": s, "question_id": "ddw-2026-006",
                                                "answer": "有理想 有道德 有文化 有纪律", "correct": True})
        assert rr.status_code == 200, rr.text
        assert rr.json()["correct"] is True
        assert "有理想" in rr.json()["answer"], rr.json()      # 原话存下来了，家长能抽查
        c = db.connect(admin=True)
        row = c.execute("SELECT answer, judged_by FROM quiz_attempts WHERE session_id=? "
                        "AND question_id='ddw-2026-006'", (s,)).fetchone()
        c.close()
        assert row["judged_by"] == "self" and "有道德" in row["answer"], dict(row)


def test_admin_quiz_summary_splits_auto_and_self():
    """家长端汇总：机器判的（填空）和孩子自评的（问答）分开报，逐题明细带孩子的原话。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)
        _play(cli, ["ddw-2026-001", "ddw-2026-006"],
              [("中国少年先锋队", None), ("有理想有道德有文化有纪律", True)])
        _login_parent(cli)
        s = cli.get("/api/admin/quiz/summary?selected_kid=" + kid).json()
        assert len(s["banks"]) == 1, s
        b = s["banks"][0]
        assert b["bank_id"] == "ddw-2026" and b["sessions"] == 1 and b["days"] == 1, b
        assert b["totals"] == {"answered": 2, "right": 2, "wrong": 0, "unjudged": 0}, b["totals"]
        assert b["auto"] == {"right": 1, "total": 1}, b["auto"]      # 填空：机器判
        assert b["self"] == {"right": 1, "total": 1}, b["self"]      # 问答：孩子自评
        assert b["legacy"] == {"right": 0, "total": 0}, b["legacy"]
        kinds = {x["kind"]: x for x in b["by_kind"]}
        assert kinds["blank"]["judged_label"] == "机器判", kinds["blank"]
        assert kinds["qa"]["judged_label"] == "孩子自评", kinds["qa"]
        q = {x["kind"]: x for x in b["questions"]}
        assert q["blank"]["correct"] is True and q["blank"]["got"] == "中国少年先锋队", q["blank"]
        assert q["blank"]["answer"] == ["中国少年先锋队"], q["blank"]
        assert q["qa"]["judged_by"] == "self" and "有理想" in q["qa"]["got"], q["qa"]


def test_admin_summary_marks_legacy_rows_separately():
    """改版前的老记录（judged_by 为空、答案也没存）单独算一类，不冒充「机器判」。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _setup(cli)
        _login_kid(cli)
        _play(cli, ["ddw-2026-001"], [("中国少年先锋队", None)])
        c = db.connect(admin=True)
        c.execute("UPDATE quiz_attempts SET judged_by='', answer='' WHERE question_id='ddw-2026-001'")
        c.commit()
        c.close()
        _login_parent(cli)
        b = cli.get("/api/admin/quiz/summary?selected_kid=" + kid).json()["banks"][0]
        assert b["legacy"]["total"] == 1 and b["auto"]["total"] == 0, b
        kinds = {x["kind"]: x for x in b["by_kind"]}
        assert kinds["blank"]["judged_label"] == "改版前，分不清", kinds["blank"]
        q = b["questions"][0]
        assert q["judged_label"] == "改版前，分不清" and q["got"] == "（改版前没记录）", q


def test_admin_quiz_summary_is_parent_only():
    """孩子调不动家长端汇总。"""
    _reset_db()
    db.init_db()
    with TestClient(main.app) as cli:
        _setup(cli)
        _login_kid(cli)
        assert cli.get("/api/admin/quiz/summary").status_code == 403


def test_quiz_judge_cases_match_page():
    """填空判分的共享用例：同一份 data/quiz_judge_cases.json，
    页面（scripts/check_quiz_judge.mjs 从 index.html 里抽那段跑）和这里都要过 ——
    两边口径不许漂移。"""
    import quiz as quizmod
    path = db.BASE.parent / "data" / "quiz_judge_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    for a, b in cases["norm_equal"]:
        assert quizmod._norm_text(a) == quizmod._norm_text(b), (a, b)
    for a, b in cases["norm_diff"]:
        assert quizmod._norm_text(a) != quizmod._norm_text(b), (a, b)
    for c in cases["blank"]:
        qrow = {"answer_json": json.dumps(c["answer"], ensure_ascii=False),
                "accept_json": json.dumps(c.get("accept") or [], ensure_ascii=False)}
        got, _ = quizmod._judge_blank(qrow, quizmod.BLANK_SEP.join(c["parts"]))
        assert got == c["want"], c
