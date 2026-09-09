# -*- coding: utf-8 -*-
"""英语单词：词表、配置、选词、session、SRS。"""
import csv
import io
import json
import sqlite3
import uuid
from datetime import datetime, timedelta

import db

WORD_INTERVALS = [1, 3, 7, 14, 30]
SESSION_CAP = 10
WORDS_SEED = db.BASE.parent / "data" / "words.seed.multi.json"


class WordError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)

CFG_ENABLED = "words_enabled"
CFG_NEW = "words_new_per_day"
CFG_MAX_DUE = "words_max_due"
CFG_BASE = "words_base_sunshine"
CFG_PERFECT = "words_perfect_sunshine"
CFG_CURSOR = "words_unlock_by_cursor"
CFG_BOOK = "words_current_book"
CFG_TTS = "words_tts"
CFG_TTS_AUTO = "words_tts_autoplay"
CFG_TTS_LANG = "words_tts_lang"


def normalize_word(raw: str) -> str:
    return " ".join((raw or "").strip().replace("’", "'").replace("‘", "'").lower().split())


def accept_json_of(item) -> str:
    extra = item.get("accept") or []
    norms = []
    seen = set()
    for x in extra:
        n = normalize_word(x)
        if n and n not in seen:
            seen.add(n)
            norms.append(n)
    return json.dumps(norms, ensure_ascii=False)


def _clamp_int(raw, default, lo, hi):
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def kid_config(c, kid):
    enabled = db.get_kid_setting(c, kid, CFG_ENABLED, "0") == "1"
    unlock = db.get_kid_setting(c, kid, CFG_CURSOR, "1") != "0"
    return {
        "enabled": enabled,
        "new_per_day": _clamp_int(db.get_kid_setting(c, kid, CFG_NEW, "5"), 5, 1, 10),
        "max_due": _clamp_int(db.get_kid_setting(c, kid, CFG_MAX_DUE, "10"), 10, 5, 15),
        "base_sunshine": _clamp_int(db.get_kid_setting(c, kid, CFG_BASE, "3"), 3, 0, 10),
        "perfect_sunshine": _clamp_int(db.get_kid_setting(c, kid, CFG_PERFECT, "2"), 2, 0, 5),
        "unlock_by_cursor": unlock,
        "current_book": db.get_kid_setting(c, kid, CFG_BOOK, "") or "",
        "tts": db.get_kid_setting(c, kid, CFG_TTS, "1") != "0",
        "tts_autoplay": db.get_kid_setting(c, kid, CFG_TTS_AUTO, "0") == "1",
        "tts_lang": "en-US" if db.get_kid_setting(c, kid, CFG_TTS_LANG, "en-GB") == "en-US" else "en-GB",
    }


def set_kid_config(c, kid, **fields):
    mapping = {
        "enabled": (CFG_ENABLED, lambda v: "1" if v else "0"),
        "new_per_day": (CFG_NEW, lambda v: str(_clamp_int(v, 5, 1, 10))),
        "max_due": (CFG_MAX_DUE, lambda v: str(_clamp_int(v, 10, 5, 15))),
        "base_sunshine": (CFG_BASE, lambda v: str(_clamp_int(v, 3, 0, 10))),
        "perfect_sunshine": (CFG_PERFECT, lambda v: str(_clamp_int(v, 2, 0, 5))),
        "unlock_by_cursor": (CFG_CURSOR, lambda v: "1" if v else "0"),
        "current_book": (CFG_BOOK, lambda v: (v or "").strip()),
        "tts": (CFG_TTS, lambda v: "1" if v else "0"),
        "tts_autoplay": (CFG_TTS_AUTO, lambda v: "1" if v else "0"),
        "tts_lang": (CFG_TTS_LANG, lambda v: "en-US" if v == "en-US" else "en-GB"),
    }
    for k, v in fields.items():
        if k not in mapping or v is None:
            continue
        key, conv = mapping[k]
        db.set_kid_setting(c, kid, key, conv(v))


def visible_book(c, fam, book_id):
    return c.execute(
        "SELECT * FROM word_books WHERE id=? AND enabled=1 AND (is_system=1 OR family_id=?)",
        (book_id, fam or ""),
    ).fetchone()


def get_book(c, fam, book_id):
    return c.execute(
        "SELECT * FROM word_books WHERE id=? AND (is_system=1 OR family_id=?)",
        (book_id, fam or ""),
    ).fetchone()


def english_cursor_unit_seq(c, kid):
    """英语游标是任务 ID，必须 JOIN tasks.unit_id 再取 units.seq。对不上就当没有游标。"""
    cur = db.get_kid_setting(c, kid, "cursor_英语", "") or ""
    if not cur:
        return None
    row = c.execute(
        "SELECT u.seq FROM tasks t JOIN units u ON u.id=t.unit_id WHERE t.id=?",
        (cur,),
    ).fetchone()
    if not row or row["seq"] is None:
        return None
    return int(row["seq"])


def book_selectable(c, kid, fam, book, cfg=None):
    if not book:
        return False
    if not book["is_system"]:
        return book["family_id"] == fam and int(book["enabled"] or 0) == 1
    cfg = cfg or kid_config(c, kid)
    if not cfg["unlock_by_cursor"]:
        return int(book["enabled"] or 0) == 1
    seq = english_cursor_unit_seq(c, kid)
    if seq is None:
        return False
    unit = book["unit_id"]
    if not unit:
        return False
    u = c.execute("SELECT seq FROM units WHERE id=?", (unit,)).fetchone()
    if not u or u["seq"] is None:
        return False
    return int(u["seq"]) <= seq


def list_books(c, kid, fam):
    rows = c.execute(
        "SELECT * FROM word_books WHERE enabled=1 AND (is_system=1 OR family_id=?) "
        "ORDER BY is_system DESC, sort, name, id",
        (fam or "",),
    ).fetchall()
    today = db.today()
    cfg = kid_config(c, kid) if kid else None
    out = []
    for r in rows:
        d = dict(r)
        bid = d["id"]
        d["word_count"] = c.execute(
            "SELECT COUNT(*) FROM words WHERE book_id=? AND active=1", (bid,)
        ).fetchone()[0]
        learned = due = problem = 0
        if kid:
            learned = c.execute(
                "SELECT COUNT(*) FROM word_progress wp JOIN words w ON w.id=wp.word_id "
                "WHERE wp.kid_id=? AND w.book_id=? AND wp.first_seen_at IS NOT NULL AND wp.first_seen_at!=''",
                (kid, bid),
            ).fetchone()[0]
            due = c.execute(
                "SELECT COUNT(*) FROM word_progress wp JOIN words w ON w.id=wp.word_id "
                "WHERE wp.kid_id=? AND w.book_id=? AND wp.due_at IS NOT NULL AND wp.due_at!='' AND wp.due_at<=?",
                (kid, bid, today),
            ).fetchone()[0]
            problem = c.execute(
                "SELECT COUNT(*) FROM word_progress wp JOIN words w ON w.id=wp.word_id "
                "WHERE wp.kid_id=? AND w.book_id=? AND COALESCE(wp.wrong_count,0)>=2",
                (kid, bid),
            ).fetchone()[0]
        d["learned_count"] = learned
        d["due_count"] = due
        d["problem_count"] = problem
        d["selectable"] = book_selectable(c, kid, fam, r, cfg) if kid else bool(d["is_system"])
        d["is_system"] = int(d["is_system"] or 0)
        d["enabled"] = int(d["enabled"] or 0)
        out.append(d)
    return out


def list_words(c, fam, book_id):
    book = get_book(c, fam, book_id)
    if not book:
        return None, []
    rows = c.execute(
        "SELECT w.id, w.book_id, w.word, w.word_norm, w.cn, w.ipa, w.example_en, w.example_cn, "
        "w.accept_json, w.sort, w.active FROM words w JOIN word_books b ON b.id=w.book_id "
        "WHERE w.book_id=? AND (b.is_system=1 OR b.family_id=?) ORDER BY w.sort, w.id",
        (book_id, fam or ""),
    ).fetchall()
    return book, [dict(r) for r in rows]


def parse_import_text(text: str):
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    nonempty = [ln for ln in raw.split("\n") if ln.strip()]
    if len(nonempty) > 500:
        raise ValueError("一次最多 500 行")
    first = nonempty[0] if nonempty else ""
    delim = "\t" if "\t" in first else ","
    reader = csv.reader(io.StringIO(raw), delimiter=delim)
    rows = []
    errors = []
    for i, cols in enumerate(reader, 1):
        if not cols or not any((c or "").strip() for c in cols):
            continue
        word = (cols[0] if len(cols) > 0 else "").strip()
        cn = (cols[1] if len(cols) > 1 else "").strip()
        ipa = (cols[2] if len(cols) > 2 else "").strip()
        if not word:
            errors.append({"line": i, "error": "缺单词"})
            continue
        if not cn:
            errors.append({"line": i, "error": "缺中文"})
            continue
        if len(word) > 60:
            errors.append({"line": i, "error": "单词太长"})
            continue
        if len(cn) > 120:
            errors.append({"line": i, "error": "中文太长"})
            continue
        rows.append({"word": word, "cn": cn, "ipa": ipa, "line": i})
    return rows, errors


def _today_date():
    return datetime.strptime(db.today(), "%Y-%m-%d").date()


def tomorrow():
    return (_today_date() + timedelta(days=1)).isoformat()


def due_on(idx):
    i = max(0, min(int(idx or 0), len(WORD_INTERVALS) - 1))
    return (_today_date() + timedelta(days=WORD_INTERVALS[i])).isoformat()


def _is_unique(exc):
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    pgcode = getattr(exc, "pgcode", None) or getattr(getattr(exc, "orig", None), "pgcode", None)
    return pgcode == "23505"


def seed_system_books(conn):
    if not WORDS_SEED.exists() or not db._has_table(conn, "word_books"):
        return
    data = json.loads(WORDS_SEED.read_text(encoding="utf-8"))
    now = db.now()
    for b in data.get("books") or []:
        bid = (b.get("id") or "").strip()
        if not bid:
            continue
        conn.execute(
            "INSERT INTO word_books(id,family_id,term_id,unit_id,name,is_system,enabled,sort,created_at,updated_at) "
            "VALUES(?,?,?,?,?,1,1,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET term_id=excluded.term_id, unit_id=excluded.unit_id, "
            "name=excluded.name, is_system=1, sort=excluded.sort, updated_at=excluded.updated_at",
            (bid, "", b.get("term_id") or "", b.get("unit_id"), b.get("name") or bid,
             int(b.get("sort") or 0), now, now),
        )
        seen_norm = set()
        for i, w in enumerate(b.get("words") or [], 1):
            word = (w.get("word") or "").strip()
            cn = (w.get("cn") or "").strip()
            if not word or not cn:
                continue
            norm = normalize_word(word)
            if not norm or norm in seen_norm:
                continue
            seen_norm.add(norm)
            conn.execute(
                "INSERT INTO words(book_id,word,word_norm,cn,ipa,example_en,example_cn,accept_json,sort,active,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,1,?,?) "
                "ON CONFLICT(book_id, word_norm) DO UPDATE SET word=excluded.word, cn=excluded.cn, "
                "ipa=excluded.ipa, example_en=excluded.example_en, example_cn=excluded.example_cn, "
                "accept_json=excluded.accept_json, sort=excluded.sort, active=1, updated_at=excluded.updated_at",
                (bid, word, norm, cn, w.get("ipa") or "", w.get("example_en") or "",
                 w.get("example_cn") or "", accept_json_of(w), int(w.get("sort") or i), now, now),
            )
        if seen_norm:
            placeholders = ",".join("?" * len(seen_norm))
            conn.execute(
                f"UPDATE words SET active=0, updated_at=? WHERE book_id=? AND word_norm NOT IN ({placeholders})",
                (now, bid, *seen_norm),
            )


def abandon_stale(c, kid):
    today = db.today()
    c.execute(
        "UPDATE word_sessions SET state='abandoned' WHERE kid_id=? AND study_date<? AND state='active'",
        (kid, today),
    )


def _today_session(c, kid):
    return c.execute(
        "SELECT * FROM word_sessions WHERE kid_id=? AND study_date=?",
        (kid, db.today()),
    ).fetchone()


def _session_owned(c, kid, sid):
    return c.execute(
        "SELECT * FROM word_sessions WHERE id=? AND kid_id=?", (sid, kid)
    ).fetchone()


def _due_count(c, kid, fam, today):
    return c.execute(
        "SELECT COUNT(*) FROM word_progress wp "
        "JOIN words w ON w.id=wp.word_id JOIN word_books b ON b.id=w.book_id "
        "WHERE wp.kid_id=? AND w.active=1 AND b.enabled=1 AND (b.is_system=1 OR b.family_id=?) "
        "AND wp.due_at IS NOT NULL AND wp.due_at!='' AND wp.due_at<=?",
        (kid, fam or "", today),
    ).fetchone()[0]


def _pick_due(c, kid, fam, today, limit):
    if limit <= 0:
        return []
    return [dict(r) for r in c.execute(
        "SELECT w.id AS word_id FROM word_progress wp "
        "JOIN words w ON w.id=wp.word_id JOIN word_books b ON b.id=w.book_id "
        "WHERE wp.kid_id=? AND w.active=1 AND b.enabled=1 AND (b.is_system=1 OR b.family_id=?) "
        "AND wp.due_at IS NOT NULL AND wp.due_at!='' AND wp.due_at<=? "
        "ORDER BY wp.due_at ASC, wp.interval_idx ASC, w.id ASC LIMIT ?",
        (kid, fam or "", today, limit),
    ).fetchall()]


def _pick_new(c, kid, fam, book_id, limit):
    if limit <= 0 or not book_id:
        return []
    book = get_book(c, fam, book_id)
    if not book or int(book["enabled"] or 0) != 1:
        return []
    if int(book["is_system"] or 0) and not book_selectable(c, kid, fam, book):
        return []
    return [dict(r) for r in c.execute(
        "SELECT w.id AS word_id FROM words w "
        "LEFT JOIN word_progress wp ON wp.word_id=w.id AND wp.kid_id=? "
        "WHERE w.book_id=? AND w.active=1 "
        "AND (wp.kid_id IS NULL OR wp.first_seen_at IS NULL OR wp.first_seen_at='') "
        "ORDER BY w.sort, w.id LIMIT ?",
        (kid, book_id, limit),
    ).fetchall()]


def _pick_items(c, kid, fam, cfg):
    today = db.today()
    due_limit = min(int(cfg["max_due"]), SESSION_CAP)
    due = _pick_due(c, kid, fam, today, due_limit)
    remain = max(0, SESSION_CAP - len(due))
    new_n = min(remain, int(cfg["new_per_day"]))
    seen = {int(r["word_id"]) for r in due}
    new = []
    if new_n > 0:
        for r in _pick_new(c, kid, fam, cfg.get("current_book") or "", new_n + 5):
            wid = int(r["word_id"])
            if wid in seen:
                continue
            new.append(r)
            seen.add(wid)
            if len(new) >= new_n:
                break
    picked = [{"word_id": int(r["word_id"]), "source": "due"} for r in due]
    picked += [{"word_id": int(r["word_id"]), "source": "new"} for r in new]
    return picked


def _ensure_items(c, row, kid, fam):
    n = c.execute(
        "SELECT COUNT(*) FROM word_session_items WHERE session_id=? AND kid_id=?",
        (row["id"], kid),
    ).fetchone()[0]
    if n:
        return
    try:
        task = json.loads(row["task_json"] or "[]")
    except (TypeError, ValueError):
        task = []
    now = db.now()
    for i, it in enumerate(task):
        c.execute(
            "INSERT INTO word_session_items(session_id,kid_id,family_id,word_id,source,item_order,state,"
            "first_result,retry_used,answered_at) VALUES(?,?,?,?,?,?, 'study', NULL, 0, NULL) "
            "ON CONFLICT(session_id, word_id) DO NOTHING",
            (row["id"], kid, fam or "", int(it["word_id"]), it.get("source") or "new",
             int(it.get("order", i))),
        )
        _ = now


def _session_items(c, kid, fam, sid):
    rows = c.execute(
        "SELECT i.word_id, i.source, i.item_order, i.state, i.first_result, i.retry_used, "
        "w.word, w.cn, w.ipa, w.example_en "
        "FROM word_session_items i "
        "JOIN words w ON w.id=i.word_id "
        "JOIN word_books b ON b.id=w.book_id "
        "WHERE i.session_id=? AND i.kid_id=? AND (b.is_system=1 OR b.family_id=?) "
        "ORDER BY i.item_order, i.word_id",
        (sid, kid, fam or ""),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "word_id": int(r["word_id"]),
            "word": r["word"],
            "cn": r["cn"],
            "ipa": r["ipa"] or "",
            "example_en": r["example_en"] or "",
            "source": r["source"],
            "state": r["state"],
            "first_result": r["first_result"],
            "retry_used": int(r["retry_used"] or 0),
        })
    return out


def _counts(items):
    due = sum(1 for x in items if x["source"] == "due")
    new = sum(1 for x in items if x["source"] == "new")
    answered = sum(1 for x in items if x["state"] in ("done", "retry") or x.get("first_result"))
    correct = sum(1 for x in items if x.get("first_result") == "right")
    return {"due": due, "new": new, "answered": answered, "correct_first_try": correct}


def _first_try_all_right(items):
    return bool(items) and all(x.get("first_result") == "right" for x in items)


def _reward(c, row):
    kid, sid = row["kid_id"], row["id"]
    base = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND reason='word_daily' AND ref_id=?",
        (kid, "word-" + sid),
    ).fetchone()[0]
    perfect = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND reason='word_perfect' AND ref_id=?",
        (kid, "word-perfect-" + sid),
    ).fetchone()[0]
    return {
        "base": int(base or 0),
        "perfect": int(perfect or 0),
        "base_sunshine": int(row["base_sunshine"] or 0),
        "perfect_sunshine": int(row["perfect_sunshine"] or 0),
    }


def _session_public(c, kid, fam, row):
    _ensure_items(c, row, kid, fam)
    items = _session_items(c, kid, fam, row["id"])
    body = {
        "id": row["id"],
        "study_date": row["study_date"],
        "state": row["state"],
        "counts": _counts(items),
        "items": items,
    }
    if row["state"] == "completed":
        body["reward"] = _reward(c, row)
    return body


def _backlog(c, kid, fam, items):
    today = db.today()
    total = _due_count(c, kid, fam, today)
    in_session = sum(1 for x in items if x["source"] == "due")
    return max(0, total - in_session)


def today_payload(c, kid, fam, create=False):
    abandon_stale(c, kid)
    cfg = kid_config(c, kid)
    if not cfg["enabled"]:
        return {"enabled": False, "finished": True, "backlog_due": 0, "config": cfg, "session": None}
    row = _today_session(c, kid)
    if row and row["state"] != "abandoned":
        sess = _session_public(c, kid, fam, row)
        finished = row["state"] == "completed"
        return {
            "enabled": True,
            "finished": finished,
            "backlog_due": _backlog(c, kid, fam, sess["items"]),
            "config": cfg,
            "session": sess,
        }
    picked = _pick_items(c, kid, fam, cfg)
    if not picked:
        return {"enabled": True, "finished": True, "backlog_due": 0, "config": cfg, "session": None}
    if not create:
        return {
            "enabled": True,
            "finished": False,
            "backlog_due": _due_count(c, kid, fam, db.today()),
            "config": cfg,
            "session": None,
        }
    return _create_session(c, kid, fam, cfg, picked)


def _create_session(c, kid, fam, cfg, picked):
    today = db.today()
    existing = _today_session(c, kid)
    if existing and existing["state"] != "abandoned":
        sess = _session_public(c, kid, fam, existing)
        return {
            "enabled": True,
            "finished": existing["state"] == "completed",
            "backlog_due": _backlog(c, kid, fam, sess["items"]),
            "config": cfg,
            "session": sess,
        }
    sid = "ws-" + uuid.uuid4().hex[:12]
    now = db.now()
    task = [{"word_id": it["word_id"], "source": it["source"], "order": i} for i, it in enumerate(picked)]
    books = []
    for it in picked:
        r = c.execute("SELECT book_id FROM words WHERE id=?", (it["word_id"],)).fetchone()
        if r and r["book_id"] not in books:
            books.append(r["book_id"])
    cur = c.execute(
        "INSERT INTO word_sessions(id,kid_id,family_id,study_date,book_ids_json,task_json,state,"
        "started_at,completed_at,base_sunshine,perfect_sunshine) "
        "VALUES(?,?,?,?,?,?, 'active', ?, NULL, ?, ?) ON CONFLICT(kid_id, study_date) DO NOTHING",
        (sid, kid, fam or "", today, json.dumps(books, ensure_ascii=False),
         json.dumps(task, ensure_ascii=False), now, int(cfg["base_sunshine"]), int(cfg["perfect_sunshine"])),
    )
    if getattr(cur, "rowcount", 1) == 0:
        row = _today_session(c, kid)
        sess = _session_public(c, kid, fam, row)
        return {
            "enabled": True,
            "finished": row["state"] == "completed",
            "backlog_due": _backlog(c, kid, fam, sess["items"]),
            "config": cfg,
            "session": sess,
        }
    for i, it in enumerate(picked):
        c.execute(
            "INSERT INTO word_session_items(session_id,kid_id,family_id,word_id,source,item_order,state,"
            "first_result,retry_used,answered_at) VALUES(?,?,?,?,?,?, 'study', NULL, 0, NULL)",
            (sid, kid, fam or "", it["word_id"], it["source"], i),
        )
    row = _session_owned(c, kid, sid)
    sess = _session_public(c, kid, fam, row)
    return {
        "enabled": True,
        "finished": False,
        "backlog_due": _backlog(c, kid, fam, sess["items"]),
        "config": cfg,
        "session": sess,
    }


def start_session(c, kid, fam):
    return today_payload(c, kid, fam, create=True)


def _need_active(c, kid, sid):
    row = _session_owned(c, kid, sid)
    if not row:
        raise WordError(404, "没找到今天的单词练习")
    if row["state"] == "completed":
        raise WordError(409, "今天已经练完了")
    if row["state"] != "active":
        raise WordError(409, "这组练习已经关掉了")
    return row


def _item(c, kid, sid, word_id):
    return c.execute(
        "SELECT * FROM word_session_items WHERE session_id=? AND kid_id=? AND word_id=?",
        (sid, kid, word_id),
    ).fetchone()


def study_item(c, kid, fam, sid, word_id, action):
    action = (action or "").strip()
    if action not in ("known", "again"):
        raise WordError(400, "动作是 known 或 again")
    row = _need_active(c, kid, sid)
    it = _item(c, kid, sid, word_id)
    if not it:
        raise WordError(404, "这组练习里没有这个词")
    if action == "again":
        mx = c.execute(
            "SELECT COALESCE(MAX(item_order),0) FROM word_session_items WHERE session_id=? AND kid_id=?",
            (sid, kid),
        ).fetchone()[0]
        c.execute(
            "UPDATE word_session_items SET item_order=? WHERE session_id=? AND kid_id=? AND word_id=?",
            (int(mx) + 1, sid, kid, word_id),
        )
    elif it["state"] == "study":
        c.execute(
            "UPDATE word_session_items SET state='spell' WHERE session_id=? AND kid_id=? AND word_id=?",
            (sid, kid, word_id),
        )
    _ = row
    return today_payload(c, kid, fam, create=False)


def _accepts(raw):
    try:
        arr = json.loads(raw or "[]")
    except (TypeError, ValueError):
        arr = []
    return [normalize_word(x) for x in arr if normalize_word(x)]


def _spell_ok(text, word_row):
    got = normalize_word(text)
    if not got:
        return False
    return got == (word_row["word_norm"] or "") or got in _accepts(word_row["accept_json"])


def _load_word(c, fam, word_id):
    return c.execute(
        "SELECT w.* FROM words w JOIN word_books b ON b.id=w.book_id "
        "WHERE w.id=? AND (b.is_system=1 OR b.family_id=?)",
        (word_id, fam or ""),
    ).fetchone()


def _progress(c, kid, word_id):
    return c.execute(
        "SELECT * FROM word_progress WHERE kid_id=? AND word_id=?", (kid, word_id)
    ).fetchone()


def _touch_first_seen(c, kid, word_id, now):
    row = _progress(c, kid, word_id)
    if not row:
        c.execute(
            "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
            "last_result,streak_right,correct_count,wrong_count) "
            "VALUES(?,?,0,NULL,?,?, '',0,0,0)",
            (kid, word_id, now, now),
        )
        return
    if not row["first_seen_at"]:
        c.execute(
            "UPDATE word_progress SET first_seen_at=?, last_seen_at=? WHERE kid_id=? AND word_id=?",
            (now, now, kid, word_id),
        )


def _apply_spell(c, kid, word_id, right, now):
    prog = _progress(c, kid, word_id)
    old_idx = int(prog["interval_idx"] or 0) if prog else 0
    correct = int(prog["correct_count"] or 0) if prog else 0
    wrong = int(prog["wrong_count"] or 0) if prog else 0
    streak = int(prog["streak_right"] or 0) if prog else 0
    if right:
        if correct == 0:
            idx, due = 0, tomorrow()
        else:
            idx = min(old_idx + 1, len(WORD_INTERVALS) - 1)
            due = due_on(idx)
        streak += 1
        correct += 1
        result = "right"
    else:
        idx, due = 0, tomorrow()
        streak = 0
        wrong += 1
        result = "wrong"
    c.execute(
        "UPDATE word_progress SET interval_idx=?, due_at=?, last_seen_at=?, last_result=?,"
        "streak_right=?, correct_count=?, wrong_count=? WHERE kid_id=? AND word_id=?",
        (idx, due, now, result, streak, correct, wrong, kid, word_id),
    )
    return {"interval_idx": idx, "due_at": due, "result": result}


def spell_item(c, kid, fam, sid, word_id, text, phase, attempt_no):
    phase = (phase or "spell").strip()
    if phase not in ("spell", "retry"):
        raise WordError(400, "阶段是 spell 或 retry")
    try:
        attempt_no = int(attempt_no)
    except (TypeError, ValueError):
        raise WordError(400, "次数要填数字")
    if attempt_no < 1:
        raise WordError(400, "次数从 1 开始")
    row = _need_active(c, kid, sid)
    it = _item(c, kid, sid, word_id)
    if not it:
        raise WordError(404, "这组练习里没有这个词")
    wrow = _load_word(c, fam, word_id)
    if not wrow:
        raise WordError(404, "没找到这个词")
    prev = c.execute(
        "SELECT result FROM word_attempts WHERE session_id=? AND word_id=? AND phase=? AND attempt_no=?",
        (sid, word_id, phase, attempt_no),
    ).fetchone()
    if prev:
        payload = today_payload(c, kid, fam, create=False)
        payload["result"] = prev["result"]
        payload["replay"] = True
        return payload
    if phase == "spell":
        if it["first_result"]:
            raise WordError(409, "这个词已经判过了")
    else:
        if it["first_result"] != "wrong":
            raise WordError(409, "只有写错的词才再写一次")
        if int(it["retry_used"] or 0):
            raise WordError(409, "今天已经再写过一次了")
    now = db.now()
    right = _spell_ok(text, wrow)
    result = "right" if right else "wrong"
    try:
        c.execute(
            "INSERT INTO word_attempts(session_id,kid_id,family_id,word_id,phase,result,attempt_no,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (sid, kid, fam or "", word_id, phase, result, attempt_no, now),
        )
    except Exception as e:
        if not _is_unique(e):
            raise
        prev = c.execute(
            "SELECT result FROM word_attempts WHERE session_id=? AND word_id=? AND phase=? AND attempt_no=?",
            (sid, word_id, phase, attempt_no),
        ).fetchone()
        payload = today_payload(c, kid, fam, create=False)
        payload["result"] = prev["result"] if prev else result
        payload["replay"] = True
        return payload
    _touch_first_seen(c, kid, word_id, now)
    srs = None
    if phase == "spell":
        srs = _apply_spell(c, kid, word_id, right, now)
        new_state = "done" if right else "retry"
        c.execute(
            "UPDATE word_session_items SET state=?, first_result=?, answered_at=? "
            "WHERE session_id=? AND kid_id=? AND word_id=?",
            (new_state, result, now, sid, kid, word_id),
        )
    else:
        c.execute(
            "UPDATE word_session_items SET state='done', retry_used=1, answered_at=? "
            "WHERE session_id=? AND kid_id=? AND word_id=?",
            (now, sid, kid, word_id),
        )
    _ = row
    payload = today_payload(c, kid, fam, create=False)
    payload["result"] = result
    payload["replay"] = False
    if srs:
        payload["progress"] = srs
    return payload


def _try_ledger(c, kid, delta, reason, ref, note):
    if int(delta or 0) <= 0:
        return
    try:
        db.insert_ledger(c, db.today(), int(delta), reason, ref, note, kid_id=kid)
    except Exception as e:
        if not _is_unique(e):
            raise


def week_stats(c, kid, fam):
    today = _today_date()
    days = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        row = c.execute(
            "SELECT id, state FROM word_sessions WHERE kid_id=? AND study_date=?",
            (kid, d),
        ).fetchone()
        completed = 1 if row and row["state"] == "completed" else 0
        items = []
        if row:
            items = c.execute(
                "SELECT first_result FROM word_session_items WHERE session_id=? AND kid_id=?",
                (row["id"], kid),
            ).fetchall()
        total = len(items)
        correct = sum(1 for x in items if x["first_result"] == "right")
        days.append({
            "date": d,
            "label": d[5:],
            "completed": completed,
            "items": total,
            "correct_first_try": correct,
            "rate": round(correct * 100 / total) if total else None,
        })
    done = [x for x in days if x["completed"]]
    tot_i = sum(x["items"] for x in done)
    tot_c = sum(x["correct_first_try"] for x in done)
    return {
        "days": days,
        "completed_sessions": sum(x["completed"] for x in days),
        "first_try_rate": round(tot_c * 100 / tot_i) if tot_i else None,
    }


def complete_session(c, kid, fam, sid):
    row = _session_owned(c, kid, sid)
    if not row:
        raise WordError(404, "没找到今天的单词练习")
    items = _session_items(c, kid, fam, sid)
    if row["state"] == "completed":
        payload = today_payload(c, kid, fam, create=False)
        return payload
    if row["state"] != "active":
        raise WordError(409, "这组练习已经关掉了")
    if not items or any(x["state"] != "done" for x in items):
        raise WordError(409, "还有单词没有完成")
    now = db.now()
    cur = c.execute(
        "UPDATE word_sessions SET state='completed', completed_at=? WHERE id=? AND kid_id=? AND state='active'",
        (now, sid, kid),
    )
    if getattr(cur, "rowcount", 0) == 0:
        return today_payload(c, kid, fam, create=False)
    row = _session_owned(c, kid, sid)
    _try_ledger(c, kid, row["base_sunshine"], "word_daily", "word-" + sid, "今日单词背默")
    if _first_try_all_right(items):
        _try_ledger(c, kid, row["perfect_sunshine"], "word_perfect", "word-perfect-" + sid, "单词默写全对")
    return today_payload(c, kid, fam, create=False)
