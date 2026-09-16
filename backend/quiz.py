# -*- coding: utf-8 -*-
"""家长指定的短期冲刺题库（quiz）：题库种子、会话、判题、闸门检查。
不做通用题库，不推题；题来自 seed JSON。
判分（2026-09-16 改）：**选择 / 多选 / 填空由后端自动判**（客户端传上来的对错一律不信）；
问答的参考答案是整句，机器判不可靠 —— 仍由孩子自评，但必须先把答案写下来并存库，家长才能抽查。"""
import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta

import db

QUIZ_SEED = db.BASE.parent / "data" / "quiz.seed.json"
QUIZ_MODES = ("study", "practice", "exam")

# 填空题：孩子每个空一个答案，前端用这个不可见字符连接后提交（答案里不会出现它）
BLANK_SEP = "\u001f"

# 哪些题型是机器判的（可信）；其余（qa）是孩子自评（仅供参考）
AUTO_KINDS = ("choice", "multi", "blank")
KIND_LABEL = {"choice": "单选", "multi": "多选", "blank": "填空", "qa": "问答"}
JUDGE_LABEL = {"auto": "机器判", "self": "孩子自评", "legacy": "改版前，分不清"}


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
                "INSERT INTO quiz_questions(id,bank_id,family_id,is_system,n,kind,stem,sort,answer_json,accept_json,options_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET stem=excluded.stem, kind=excluded.kind, "
                "sort=excluded.sort, answer_json=excluded.answer_json, accept_json=excluded.accept_json, "
                "options_json=excluded.options_json, updated_at=excluded.updated_at",
                (qid, bid, "", 1, int(q.get("n") or 0), kind, stem,
                 int(q.get("sort") or 0), json.dumps(q.get("answer") or [], ensure_ascii=False),
                 json.dumps(q.get("accept") or [], ensure_ascii=False),
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


_PUNCT_RE = re.compile(r"[，,。.、；;：:！!？?“”\"'‘’（）()《》〈〉【】\[\]{}—\-–~·…／/\\|]+")


def _norm_text(s):
    """只用于比较的规范化：全角→半角、去所有空白、去中英文标点、统一小写。
    **不改写孩子的原话** —— 存库和给家长看的都是原文。"""
    t = unicodedata.normalize("NFKC", str(s or "")).strip().lower()
    t = re.sub(r"\s+", "", t)
    return _PUNCT_RE.sub("", t)


def _judge_blank(qrow, answer):
    """填空题自动判分。孩子每个空一个答案、用 BLANK_SEP 连接；按空位顺序比，
    规范化后相等即算对；每题还能带 accept（按空位给的同义写法清单）兜底。
    返回 (correct: bool | None, normalized_answer: str)。"""
    try:
        correct_list = [str(x) for x in json.loads(qrow["answer_json"] or "[]")]
    except Exception:
        correct_list = []
    raw = str(answer or "")
    if not correct_list:
        return None, raw.strip()
    try:
        accept_list = json.loads(qrow["accept_json"] or "[]")
    except Exception:
        accept_list = []
    if not isinstance(accept_list, list):
        accept_list = []
    parts = raw.split(BLANK_SEP)
    stored = BLANK_SEP.join(p.strip() for p in parts)
    if len(parts) != len(correct_list):
        return False, stored            # 空位数对不上：不可能对（也堵住「少填几个蒙对」）
    for i, want in enumerate(correct_list):
        got = _norm_text(parts[i])
        if not got:
            return False, stored
        ok_set = {_norm_text(want)}
        if i < len(accept_list) and isinstance(accept_list[i], list):
            ok_set |= {_norm_text(x) for x in accept_list[i]}
        ok_set.discard("")
        if got not in ok_set:
            return False, stored
    return True, stored


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
    """获取今天指定 bank+mode 的 session 状态。mode 为 study / practice / exam。"""

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
    if mode not in QUIZ_MODES:
        raise QuizError(400, "练习方式不对")
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
        judged_by = "auto"
    elif kind == "blank":
        # 填空由后端判分：**忽略前端传来的 correct**，孩子点什么都不算数
        judged, norm_answer = _judge_blank(qrow, answer)
        correct = judged
        answer = norm_answer
        judged_by = "auto"
    else:
        # 问答：整句参考答案，机器判不可靠 —— 仍由孩子自评，但必须先把答案写下来（家长要抽查）
        answer = (answer or "").strip()
        if not answer and correct is not None:
            raise QuizError(400, "先写下你的答案，再判自己对不对")
        correct = None if correct is None else bool(correct)
        judged_by = "self"
    # 去重：同一题只保留最新一次
    c.execute(
        "DELETE FROM quiz_attempts WHERE session_id=? AND kid_id=? AND question_id=?",
        (session_id, kid, question_id),
    )
    c.execute(
        "INSERT INTO quiz_attempts(session_id,kid_id,family_id,question_id,item_order,answer,correct,judged_by,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (session_id, kid, fam, question_id, item_order, answer,
         1 if correct else 0 if correct is False else None, judged_by, _now()),
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


def _display_got(kind, raw, legacy=False):
    """把库里存的作答变成一句给家长看的话（填空题每个空用 ／ 分隔）。"""
    t = str(raw or "").strip()
    if not t and legacy:
        return "（改版前没记录）"
    if kind == "blank" and BLANK_SEP in t:
        return " ／ ".join((x.strip() or "（空）") for x in t.split(BLANK_SEP))
    return t


def admin_summary(c, kid):
    """家长端：孩子在每个题库上练得怎么样。

    这个接口存在的理由是**把可信的数字和不那么可信的数字分开**：
    选择/多选/填空是机器判的，问答是孩子自评的；改版前的老记录分不清是谁判的，
    单独算一类（legacy），不硬塞进任何一边。"""
    banks = c.execute(
        "SELECT id, name, end_at FROM quiz_banks WHERE is_system=1 ORDER BY sort"
    ).fetchall()
    out = []
    for b in banks:
        sessions = c.execute(
            "SELECT id, study_date, mode, state FROM quiz_sessions "
            "WHERE kid_id=? AND bank_id=? ORDER BY study_date DESC, started_at DESC",
            (kid, b["id"]),
        ).fetchall()
        done = [r for r in sessions if r["state"] == "completed"]
        totals = {"answered": 0, "right": 0, "wrong": 0, "unjudged": 0}
        per_kind = {}
        judged = {"auto": {"right": 0, "total": 0}, "self": {"right": 0, "total": 0},
                  "legacy": {"right": 0, "total": 0}}
        if done:
            ids = [r["id"] for r in done]
            ph = ",".join("?" for _ in ids)
            rows = c.execute(
                "SELECT a.correct AS correct, a.judged_by AS judged_by, q.kind AS kind "
                "FROM quiz_attempts a LEFT JOIN quiz_questions q ON q.id=a.question_id "
                "WHERE a.session_id IN (" + ph + ")",
                tuple(ids),
            ).fetchall()
            for r in rows:
                k = r["kind"] or ""
                slot = per_kind.setdefault(
                    k, {"answered": 0, "right": 0, "wrong": 0, "unjudged": 0, "legacy": 0})
                slot["answered"] += 1
                totals["answered"] += 1
                cb = r["correct"]
                if cb is None:
                    slot["unjudged"] += 1
                    totals["unjudged"] += 1
                    is_right = False
                else:
                    is_right = int(cb) == 1
                    key = "right" if is_right else "wrong"
                    slot[key] += 1
                    totals[key] += 1
                who = (r["judged_by"] or "").strip()
                if who not in judged:
                    who = "legacy"
                    slot["legacy"] += 1
                judged[who]["total"] += 1
                if cb is not None and is_right:
                    judged[who]["right"] += 1
        by_kind = []
        for k in ("choice", "multi", "blank", "qa"):
            if k not in per_kind:
                continue
            slot = dict(per_kind[k])
            slot["kind"] = k
            slot["label"] = KIND_LABEL.get(k, k)
            slot["judged_by"] = "auto" if k in AUTO_KINDS else "self"
            if slot["legacy"] <= 0:
                slot["judged_label"] = JUDGE_LABEL[slot["judged_by"]]
            elif slot["legacy"] >= slot["answered"]:
                slot["judged_label"] = JUDGE_LABEL["legacy"]
            else:
                slot["judged_label"] = "%s + 改版前" % JUDGE_LABEL[slot["judged_by"]]
            by_kind.append(slot)
        questions = []
        if done:
            last = done[0]
            det = c.execute(
                "SELECT a.answer AS got, a.correct AS correct, a.judged_by AS judged_by, "
                "q.n AS qn, q.kind AS kind, q.stem AS stem, q.answer_json AS answer_json "
                "FROM quiz_attempts a LEFT JOIN quiz_questions q ON q.id=a.question_id "
                "WHERE a.session_id=? ORDER BY a.item_order",
                (last["id"],),
            ).fetchall()
            for d in det:
                k = d["kind"] or ""
                try:
                    ref = [str(x) for x in json.loads(d["answer_json"] or "[]")]
                except Exception:
                    ref = []
                who = (d["judged_by"] or "").strip() or "legacy"
                cb = d["correct"]
                questions.append({
                    "n": int(d["qn"] or 0),
                    "kind": k,
                    "label": KIND_LABEL.get(k, k),
                    "stem": d["stem"] or "",
                    "answer": ref,
                    "got": _display_got(k, d["got"], who == "legacy"),
                    "correct": None if cb is None else int(cb) == 1,
                    "judged_by": who,
                    "judged_label": JUDGE_LABEL.get(who, who),
                    "date": last["study_date"],
                })
        out.append({
            "bank_id": b["id"],
            "name": b["name"] or b["id"],
            "end_at": b["end_at"],
            "sessions": len(done),
            "days": len({r["study_date"] for r in done}),
            "last_date": done[0]["study_date"] if done else "",
            "last_mode": done[0]["mode"] if done else "",
            "totals": totals,
            "auto": judged["auto"],
            "self": judged["self"],
            "legacy": judged["legacy"],
            "by_kind": by_kind,
            "questions": questions,
        })
    return {"banks": out}
