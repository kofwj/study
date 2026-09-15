# -*- coding: utf-8 -*-
"""家长指定的短期冲刺题库（quiz）：题库种子、会话、判题、闸门检查。
不做通用题库，不推题；题来自 seed JSON，答案由孩子自评 + 后端自动判选择/多选。"""
import json
import uuid
from datetime import datetime, timedelta

import db

QUIZ_SEED = db.BASE.parent / "data" / "quiz.seed.json"


class QuizError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _now():
    return db.now()


def _today():
    return db.today()


def seed_system_banks(conn):
    """从 data/quiz.seed.json 导入 system 题库。支持热更新（ON CONFLICT UPDATE）。"""
    if not QUIZ_SEED.exists():
        return
    try:
        data = json.loads(QUIZ_SEED.read_text(encoding="utf-8"))
    except Exception:
        return
    now = _now()
    for b in data.get("banks") or []:
        bid = (b.get("id") or "").strip()
        if not bid:
            continue
        source = b.get("source") or {}
        conn.execute(
            "INSERT INTO quiz_banks(id,family_id,name,sort,end_at,is_system,source_json,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, sort=excluded.sort, "
            "end_at=excluded.end_at, is_system=1, source_json=excluded.source_json, updated_at=excluded.updated_at",
            (bid, "", b.get("name") or bid, int(b.get("sort") or 0), b.get("end_at") or None, 1,
             json.dumps(source, ensure_ascii=False), now, now),
        )
        for q in b.get("questions") or []:
            qid = (q.get("id") or "").strip()
            if not qid:
                continue
            kind = (q.get("kind") or "").strip()
            stem = (q.get("stem") or "").strip()
            if not kind or not stem:
                continue
            options = q.get("options") or []
            conn.execute(
                "INSERT INTO quiz_questions(id,bank_id,family_id,is_system,n,kind,stem,sort,answer_json,options_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET stem=excluded.stem, kind=excluded.kind, "
                "sort=excluded.sort, answer_json=excluded.answer_json, options_json=excluded.options_json, updated_at=excluded.updated_at",
                (qid, bid, "", 1, int(q.get("n") or 0), kind, stem,
                 int(q.get("sort") or 0), json.dumps(q.get("answer") or [], ensure_ascii=False),
                 json.dumps(options, ensure_ascii=False), now, now),
            )


def _session_row(c, kid, sid):
    return c.execute(
        "SELECT * FROM quiz_sessions WHERE id=? AND kid_id=?", (sid, kid)
    ).fetchone()


def _need_active(c, kid, sid):
    row = _session_row(c, kid, sid)
    if not row:
        raise QuizError(404, "没找到这组练习")
    if row["state"] == "completed":
        raise QuizError(409, "今天已经练完了")
    if row["state"] != "active":
        raise QuizError(409, "这组练习已经关掉了")
    return row


def _question(c, qid):
    return c.execute("SELECT * FROM quiz_questions WHERE id=?", (qid,)).fetchone()


def _judge_choice_multi(qrow, answer: str):
    """对 choice/multi 自动判题。answer 是用户提交的字符串（单选=字母，多选=逗号分隔字母）。
    返回 (correct: bool | None, normalized_answer: str)。"""
    kind = qrow["kind"]
    try:
        correct_answers = json.loads(qrow["answer_json"] or "[]")
    except Exception:
        correct_answers = []
    if kind == "choice":
        if not correct_answers:
            return None, (answer or "").strip().upper()
        ok = (answer or "").strip().upper() == str(correct_answers[0]).upper()
        return ok, (answer or "").strip().upper()
    if kind == "multi":
        user_set = set((answer or "").replace(",", "").replace(" ", "").upper())
        ok_set = set(str(x).upper() for x in correct_answers)
        # 只比较有效选项字母（A-D/E）
        if not ok_set:
            return None, (answer or "").strip().upper()
        ok = user_set == ok_set
        return ok, ",".join(sorted(user_set)) if user_set else ""
    return None, (answer or "").strip()


def list_banks(c, fam):
    """列出孩子可见的 system 题库（目前只有 system 题库）。"""
    rows = c.execute(
        "SELECT id, name, sort, end_at, source_json FROM quiz_banks WHERE is_system=1 ORDER BY sort"
    ).fetchall()
    out = []
    for r in rows:
        try:
            src = json.loads(r["source_json"] or "{}")
        except Exception:
            src = {}
        out.append({
            "id": r["id"],
            "name": r["name"],
            "sort": r["sort"],
            "end_at": r["end_at"],
            "source": src,
        })
    return out


def bank_questions(c, bank_id):
    rows = c.execute(
        "SELECT id, n, kind, stem, sort, answer_json, options_json FROM quiz_questions WHERE bank_id=? ORDER BY sort",
        (bank_id,),
    ).fetchall()
    out = []
    for r in rows:
        try:
            ans = json.loads(r["answer_json"] or "[]")
            opts = json.loads(r["options_json"] or "[]")
        except Exception:
            ans = []
            opts = []
        out.append({
            "id": r["id"],
            "n": r["n"],
            "kind": r["kind"],
            "stem": r["stem"],
            "sort": r["sort"],
            "answer": ans,
            "options": opts,
        })
    return out


def today_payload(c, kid, fam, bank_id, mode, create=False):
    """获取今天指定 bank+mode 的 session 状态。mode 为 'practice'/'exam'。"""
    t = _today()
    row = c.execute(
        "SELECT * FROM quiz_sessions WHERE kid_id=? AND study_date=? AND bank_id=? AND mode=?",
        (kid, t, bank_id, mode),
    ).fetchone()
    if row and row["state"] != "abandoned":
        return {
            "finished": row["state"] == "completed",
            "session": _session_public(c, row),
        }
    if not create:
        return {"finished": False, "session": None}
    # 创建新 session（qids 由前端传入，先空着，start_session 再填）
    sid = uuid.uuid4().hex[:12]
    now = _now()
    c.execute(
        "INSERT INTO quiz_sessions(id,kid_id,family_id,bank_id,study_date,mode,state,started_at,qids_json) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (sid, kid, fam, bank_id, t, mode, "active", now, "[]"),
    )
    row = _session_row(c, kid, sid)
    return {"finished": False, "session": _session_public(c, row)}


def start_session(c, kid, fam, bank_id, mode, qids):
    """开始（或复用）今天的 session，并写入题目顺序。"""
    payload = today_payload(c, kid, fam, bank_id, mode, create=True)
    sess = payload["session"]
    if payload["finished"]:
        return payload
    sid = sess["id"]
    qids_json = json.dumps(qids or [], ensure_ascii=False)
    c.execute(
        "UPDATE quiz_sessions SET qids_json=? WHERE id=? AND kid_id=? AND state='active'",
        (qids_json, sid, kid),
    )
    return today_payload(c, kid, fam, bank_id, mode, create=False)


def _session_public(c, row):
    """把 session 行序列化为前端可用的字典。"""
    if not row:
        return None
    sid = row["id"]
    attempts = c.execute(
        "SELECT question_id, answer, correct FROM quiz_attempts WHERE session_id=? ORDER BY item_order",
        (sid,),
    ).fetchall()
    try:
        qids = json.loads(row["qids_json"] or "[]")
    except Exception:
        qids = []
    return {
        "id": sid,
        "bank_id": row["bank_id"],
        "mode": row["mode"],
        "state": row["state"],
        "study_date": row["study_date"],
        "qids": qids,
        "attempts": [{"question_id": a["question_id"], "answer": a["answer"], "correct": a["correct"]} for a in attempts],
    }


def record_attempt(c, kid, fam, session_id, question_id, answer, correct=None):
    """记录一次答题。choice/multi 由后端自动判；blank/qa 用前端传入的 correct（None=未评）。
    返回 {'correct': bool|None, 'answer': str}。"""
    _need_active(c, kid, session_id)
    qrow = _question(c, question_id)
    if not qrow:
        raise QuizError(404, "题库里没有这道题")
    # 查找该题在 session 中的顺序
    sess = _session_row(c, kid, session_id)
    try:
        qids = json.loads(sess["qids_json"] or "[]")
    except Exception:
        qids = []
    try:
        item_order = qids.index(question_id)
    except ValueError:
        raise QuizError(400, "这道题不在当前练习里")
    kind = qrow["kind"]
    if kind in ("choice", "multi"):
        judged, norm_answer = _judge_choice_multi(qrow, answer)
        correct = judged
        answer = norm_answer
    else:
        answer = (answer or "").strip()
    # 去重：同一题只保留最新一次
    c.execute(
        "DELETE FROM quiz_attempts WHERE session_id=? AND kid_id=? AND question_id=?",
        (session_id, kid, question_id),
    )
    c.execute(
        "INSERT INTO quiz_attempts(session_id,kid_id,family_id,question_id,item_order,answer,correct,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (session_id, kid, fam, question_id, item_order, answer, 1 if correct else 0 if correct is False else None, _now()),
    )
    return {"correct": correct, "answer": answer}


def complete_session(c, kid, fam, session_id):
    """标记 session 为已完成。不直接发阳光（阳光由 daily task 完成时统一发）。"""
    row = _session_row(c, kid, session_id)
    if not row:
        raise QuizError(404, "没找到这组练习")
    if row["state"] == "completed":
        return today_payload(c, kid, fam, row["bank_id"], row["mode"], create=False)
    if row["state"] != "active":
        raise QuizError(409, "这组练习已经关掉了")
    now = _now()
    c.execute(
        "UPDATE quiz_sessions SET state='completed', completed_at=? WHERE id=? AND kid_id=? AND state='active'",
        (now, session_id, kid),
    )
    return today_payload(c, kid, fam, row["bank_id"], row["mode"], create=False)


def quiz_done_today(c, kid):
    """今天是否有任何已完成的 quiz session（任意 bank、任意 mode）。
    供 daily task 的 require_quiz 闸门使用。"""
    t = _today()
    row = c.execute(
        "SELECT 1 FROM quiz_sessions WHERE kid_id=? AND study_date=? AND state='completed' LIMIT 1",
        (kid, t),
    ).fetchone()
    return bool(row)


def today_summary(c, kid):
    """返回今天所有 quiz session 的摘要（供前端展示「已完成」状态）。"""
    t = _today()
    rows = c.execute(
        "SELECT bank_id, mode, state FROM quiz_sessions WHERE kid_id=? AND study_date=?",
        (kid, t),
    ).fetchall()
    return {
        "done": any(r["state"] == "completed" for r in rows),
        "sessions": [{"bank_id": r["bank_id"], "mode": r["mode"], "state": r["state"]} for r in rows],
    }
