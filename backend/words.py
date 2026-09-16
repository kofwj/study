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
NON_PRACTICE_ENTRY_TYPES = frozenset({"专名", "节日名", "课程名", "社团名", "菜名"})
WORDS_SEED = db.BASE.parent / "data" / "words.seed.multi.json"


class WordError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)

CFG_ENABLED = "words_enabled"
CFG_NEW = "words_new_per_day"
CFG_MAX_DUE = "words_max_due"
CFG_GAME_SIZE = "words_game_size"   # 一局多少词（独立页 /word/ 用，10–40）
CFG_DAILY_GOAL = "words_daily_goal"     # 每日目标：今天写够几个词算达标（0 = 关闭）5–40
CFG_MATCH_SIZE = "words_match_size"     # 「连一连」一块几个词 3–6
CFG_MATCH_BLOCKS = "words_match_blocks"  # 「连一连」一局最多几块 0–3（0 = 不玩连一连）
CFG_CURSOR = "words_unlock_by_cursor"
CFG_BOOK = "words_current_book"
CFG_REVIEW_MODE = "words_review_mode"
CFG_REVIEW_BOOKS = "words_review_books"
CFG_TTS = "words_tts"
CFG_TTS_AUTO = "words_tts_autoplay"
CFG_TTS_LANG = "words_tts_lang"

_SEED_BOOK_META = None


def _seed_book_meta():
    global _SEED_BOOK_META
    if _SEED_BOOK_META is not None:
        return _SEED_BOOK_META
    meta = {}
    try:
        data = json.loads(WORDS_SEED.read_text(encoding="utf-8"))
    except Exception:
        _SEED_BOOK_META = meta
        return meta
    ver = data.get("curriculum_ver") or ""
    for b in data.get("books") or []:
        bid = (b.get("id") or "").strip()
        if not bid:
            continue
        src = b.get("source") or {}
        meta[bid] = {
            "source_ver": ver,
            "source_unit": src.get("unit") or b.get("name") or "",
            "source_edition": src.get("edition") or "",
            "source_catalog": src.get("catalog") or "",
            "source_aligned_tasks": src.get("aligned_tasks") or [],
            "source_needs_spot_check": bool(src.get("needs_spot_check")),
            "source_note": src.get("note") or "",
        }
    _SEED_BOOK_META = meta
    return meta


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



def _clamp_goal(raw):
    """每日目标：0 = 关闭；否则 5–40（不取 1–4，太少没意义）。"""
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        v = 10
    if v <= 0:
        return 0
    return max(5, min(40, v))

def _parse_review_books(raw):
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        value = []
    if not isinstance(value, list):
        return []
    out = []
    seen = set()
    for item in value:
        bid = str(item or "").strip()
        if bid and bid not in seen:
            seen.add(bid)
            out.append(bid)
    return out


def kid_config(c, kid):
    enabled = db.get_kid_setting(c, kid, CFG_ENABLED, "0") == "1"
    unlock = db.get_kid_setting(c, kid, CFG_CURSOR, "1") != "0"
    mode = db.get_kid_setting(c, kid, CFG_REVIEW_MODE, "current")
    if mode not in ("current", "scope"):
        mode = "current"
    return {
        "enabled": enabled,
        "new_per_day": _clamp_int(db.get_kid_setting(c, kid, CFG_NEW, "5"), 5, 1, 10),
        "max_due": _clamp_int(db.get_kid_setting(c, kid, CFG_MAX_DUE, "10"), 10, 5, 15),
        "game_size": _clamp_int(db.get_kid_setting(c, kid, CFG_GAME_SIZE, "20"), 20, 10, 40),
        "daily_goal": _clamp_goal(db.get_kid_setting(c, kid, CFG_DAILY_GOAL, "10")),
        "match_size": _clamp_int(db.get_kid_setting(c, kid, CFG_MATCH_SIZE, "5"), 5, 3, 6),
        "match_blocks": _clamp_int(db.get_kid_setting(c, kid, CFG_MATCH_BLOCKS, "3"), 3, 0, 3),
        "unlock_by_cursor": unlock,
        "current_book": db.get_kid_setting(c, kid, CFG_BOOK, "") or "",
        "review_mode": mode,
        "review_books": _parse_review_books(db.get_kid_setting(c, kid, CFG_REVIEW_BOOKS, "[]")),
        "tts": db.get_kid_setting(c, kid, CFG_TTS, "1") != "0",
        "tts_autoplay": db.get_kid_setting(c, kid, CFG_TTS_AUTO, "0") == "1",
        "tts_lang": "en-US" if db.get_kid_setting(c, kid, CFG_TTS_LANG, "en-GB") == "en-US" else "en-GB",
    }


def set_kid_config(c, kid, **fields):
    mapping = {
        "enabled": (CFG_ENABLED, lambda v: "1" if v else "0"),
        "new_per_day": (CFG_NEW, lambda v: str(_clamp_int(v, 5, 1, 10))),
        "max_due": (CFG_MAX_DUE, lambda v: str(_clamp_int(v, 10, 5, 15))),
        "game_size": (CFG_GAME_SIZE, lambda v: str(_clamp_int(v, 20, 10, 40))),
        "daily_goal": (CFG_DAILY_GOAL, lambda v: str(_clamp_goal(v))),
        "match_size": (CFG_MATCH_SIZE, lambda v: str(_clamp_int(v, 5, 3, 6))),
        "match_blocks": (CFG_MATCH_BLOCKS, lambda v: str(_clamp_int(v, 3, 0, 3))),
        "unlock_by_cursor": (CFG_CURSOR, lambda v: "1" if v else "0"),
        "current_book": (CFG_BOOK, lambda v: (v or "").strip()),
        "review_mode": (CFG_REVIEW_MODE, lambda v: "scope" if v == "scope" else "current"),
        "review_books": (CFG_REVIEW_BOOKS, lambda v: json.dumps(_parse_review_books(json.dumps(v)), ensure_ascii=False)),
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
    if cfg.get("review_mode") == "scope":
        return int(book["enabled"] or 0) == 1
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


def sanitize_review_books(c, fam, raw):
    """Filter a requested scope to visible, enabled system books, preserving input order."""
    requested = _parse_review_books(json.dumps(raw if isinstance(raw, list) else []))
    out = []
    for bid in requested:
        row = c.execute(
            "SELECT id FROM word_books WHERE id=? AND enabled=1 AND is_system=1",
            (bid,),
        ).fetchone()
        if row and bid not in out:
            out.append(bid)
    return out


def _review_book_ids(c, kid, fam, cfg):
    """Return enabled, visible system books in deterministic sort/id order for scope mode."""
    if (cfg or {}).get("review_mode") != "scope":
        return None
    requested = sanitize_review_books(c, fam, (cfg or {}).get("review_books") or [])
    if not requested:
        return []
    marks = ",".join("?" for _ in requested)
    rows = c.execute(
        f"SELECT id FROM word_books WHERE enabled=1 AND is_system=1 AND id IN ({marks}) ORDER BY sort, id",
        tuple(requested),
    ).fetchall()
    return [r["id"] for r in rows]


def _scope_book_order(c, kid, fam, cfg):
    ids = _review_book_ids(c, kid, fam, cfg) or []
    current = (cfg.get("current_book") or "").strip()
    if current in ids:
        return ids[ids.index(current):]
    return ids


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
        sm = _seed_book_meta().get(bid) or {}
        d["source_ver"] = sm.get("source_ver") or "" if d["is_system"] else ""
        d["source_unit"] = sm.get("source_unit") or (d.get("name") or "" if d["is_system"] else "")
        d["source_edition"] = sm.get("source_edition") or "" if d["is_system"] else ""
        d["source_catalog"] = sm.get("source_catalog") or "" if d["is_system"] else ""
        d["source_aligned_tasks"] = sm.get("source_aligned_tasks") or [] if d["is_system"] else []
        d["source_needs_spot_check"] = bool(sm.get("source_needs_spot_check")) if d["is_system"] else False
        d["source_note"] = sm.get("source_note") or "" if d["is_system"] else ""
        out.append(d)
    return out


def list_words(c, fam, book_id):
    book = get_book(c, fam, book_id)
    if not book:
        return None, []
    rows = c.execute(
        "SELECT w.id, w.book_id, w.word, w.word_norm, w.cn, w.ipa, w.example_en, w.example_cn, "
        "w.accept_json, w.sort, w.active, w.page, w.entry_type, w.core FROM words w JOIN word_books b ON b.id=w.book_id "
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
            entry_type = (w.get("entry_type") or "词").strip() or "词"
            core = 1 if w.get("core", True) else 0
            active = 0 if entry_type in NON_PRACTICE_ENTRY_TYPES else 1
            cn = (w.get("cn") or "").strip()
            if not word or not cn:
                continue
            norm = normalize_word(word)
            if not norm or norm in seen_norm:
                continue
            seen_norm.add(norm)
            conn.execute(
                "INSERT INTO words(book_id,word,word_norm,cn,ipa,example_en,example_cn,accept_json,sort,active,page,entry_type,core,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(book_id, word_norm) DO UPDATE SET word=excluded.word, cn=excluded.cn, "
                "ipa=excluded.ipa, example_en=excluded.example_en, example_cn=excluded.example_cn, "
                "accept_json=excluded.accept_json, sort=excluded.sort, active=excluded.active, page=excluded.page, "
                "entry_type=excluded.entry_type, core=excluded.core, updated_at=excluded.updated_at",
                (bid, word, norm, cn, w.get("ipa") or "", w.get("example_en") or "",
                 w.get("example_cn") or "", accept_json_of(w), int(w.get("sort") or i), active,
                 w.get("page"), entry_type, core, now, now),
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


def _book_filter(book_ids):
    if book_ids is None:
        return "", []
    if not book_ids:
        return " AND 1=0", []
    return " AND w.book_id IN (" + ",".join("?" for _ in book_ids) + ")", list(book_ids)


def _due_count(c, kid, fam, today, book_ids=None):
    extra, ids = _book_filter(book_ids)
    return c.execute(
        "SELECT COUNT(*) FROM word_progress wp "
        "JOIN words w ON w.id=wp.word_id JOIN word_books b ON b.id=w.book_id "
        "WHERE wp.kid_id=? AND w.active=1 AND b.enabled=1 AND (b.is_system=1 OR b.family_id=?) "
        "AND wp.due_at IS NOT NULL AND wp.due_at!='' AND wp.due_at<=?" + extra,
        (kid, fam or "", today, *ids),
    ).fetchone()[0]


def _pick_due(c, kid, fam, today, limit, book_ids=None):
    if limit <= 0:
        return []
    extra, ids = _book_filter(book_ids)
    return [dict(r) for r in c.execute(
        "SELECT w.id AS word_id FROM word_progress wp "
        "JOIN words w ON w.id=wp.word_id JOIN word_books b ON b.id=w.book_id "
        "WHERE wp.kid_id=? AND w.active=1 AND b.enabled=1 AND (b.is_system=1 OR b.family_id=?) "
        "AND wp.due_at IS NOT NULL AND wp.due_at!='' AND wp.due_at<=?" + extra + " "
        "ORDER BY wp.due_at ASC, wp.interval_idx ASC, w.id ASC LIMIT ?",
        (kid, fam or "", today, *ids, limit),
    ).fetchall()]


def _pick_new_scope(c, kid, fam, cfg, limit):
    if limit <= 0:
        return []
    out = []
    for book_id in _scope_book_order(c, kid, fam, cfg):
        remaining = limit - len(out)
        if remaining <= 0:
            break
        out.extend(_pick_new(c, kid, fam, book_id, remaining, cfg=cfg))
    return out


def _pick_new(c, kid, fam, book_id, limit, cfg=None):
    if limit <= 0 or not book_id:
        return []
    book = get_book(c, fam, book_id)
    if not book or int(book["enabled"] or 0) != 1:
        return []
    if int(book["is_system"] or 0) and not book_selectable(c, kid, fam, book, cfg):
        return []
    return [dict(r) for r in c.execute(
        "SELECT w.id AS word_id FROM words w "
        "LEFT JOIN word_progress wp ON wp.word_id=w.id AND wp.kid_id=? "
        "WHERE w.book_id=? AND w.active=1 "
        "AND COALESCE(w.entry_type, '词') NOT IN ('专名','节日名','课程名','社团名','菜名','项目词汇') "
        "AND (wp.kid_id IS NULL OR wp.first_seen_at IS NULL OR wp.first_seen_at='') "
        "ORDER BY w.sort, w.id LIMIT ?",
        (kid, book_id, limit),
    ).fetchall()]


def _pick_items(c, kid, fam, cfg, size=None):
    """size=None 走 SPA 那条流程（SESSION_CAP + max_due + new_per_day）；
    给了 size（独立页 /word/）就按这一局要多少词取满：到期优先，不够用未学词补。"""
    today = db.today()
    scope_ids = _review_book_ids(c, kid, fam, cfg)
    cap = min(int(size), 40) if size else SESSION_CAP
    due_limit = cap if size else min(int(cfg["max_due"]), SESSION_CAP)
    due = _pick_due(c, kid, fam, today, due_limit, scope_ids)
    remain = max(0, cap - len(due))
    new_n = remain if size else min(remain, int(cfg["new_per_day"]))
    seen = {int(r["word_id"]) for r in due}
    new = []
    if new_n > 0:
        candidates = (_pick_new_scope(c, kid, fam, cfg, new_n + 5)
                      if scope_ids is not None else
                      _pick_new(c, kid, fam, cfg.get("current_book") or "", new_n + 5, cfg=cfg))
        for r in candidates:
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
        "w.word, w.cn, w.ipa, w.example_en, w.page, w.entry_type, w.core, "
        "p.interval_idx, p.streak_right, p.wrong_count, p.first_seen_at, p.last_result "
        "FROM word_session_items i "
        "JOIN words w ON w.id=i.word_id "
        "JOIN word_books b ON b.id=w.book_id "
        "LEFT JOIN word_progress p ON p.kid_id=i.kid_id AND p.word_id=i.word_id "
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
            "page": r["page"],
            "entry_type": r["entry_type"] or "词",
            "core": bool(r["core"]),
            "source": r["source"],
            "state": r["state"],
            "first_result": r["first_result"],
            "retry_used": int(r["retry_used"] or 0),
            # 掌握度：页面按它决定「先认一认 / 先连一连 / 直接写」（frontend/src/wordGame.js 的 questionPlan）
            "progress": {
                "first_seen_at": r["first_seen_at"] or "",
                "interval_idx": int(r["interval_idx"] or 0),
                "streak_right": int(r["streak_right"] or 0),
                "wrong_count": int(r["wrong_count"] or 0),
                "last_result": r["last_result"] or "",
            },
        })
    return out




def _counts(items):
    due = sum(1 for x in items if x["source"] == "due")
    new = sum(1 for x in items if x["source"] == "new")
    answered = sum(1 for x in items if x["state"] in ("done", "retry") or x.get("first_result"))
    correct = sum(1 for x in items if x.get("first_result") == "right")
    return {"due": due, "new": new, "answered": answered, "correct_first_try": correct}


def scored_words_today(c, kid):
    """今天「写过」的词数（去重）：只数 phase='spell' 的正式作答，retry 不算。
    服务端算，不信客户端 —— 和「一轮得分」的分母同一套数据。"""
    return int(c.execute(
        "SELECT COUNT(DISTINCT a.word_id) FROM word_attempts a "
        "JOIN word_sessions s ON s.id=a.session_id "
        "WHERE a.kid_id=? AND a.phase='spell' AND s.study_date=?",
        (kid, db.today()),
    ).fetchone()[0] or 0)


def goal_state(c, kid, cfg):
    """每日目标环：今天写够 goal 个词就算达标（只展示，不发钱）。goal=0 表示家长关掉了。"""
    goal = int(cfg.get("daily_goal") or 0)
    n = scored_words_today(c, kid)
    return {"scored_words": n, "goal": goal, "goal_done": bool(goal and n >= goal)}


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


def _backlog(c, kid, fam, items, cfg=None):
    today = db.today()
    book_ids = _review_book_ids(c, kid, fam, cfg or kid_config(c, kid))
    total = _due_count(c, kid, fam, today, book_ids)
    in_session = sum(1 for x in items if x["source"] == "due")
    return max(0, total - in_session)


def today_payload(c, kid, fam, create=False, size=None):
    """孩子端今天这一组（SPA 与独立页共用）。外面套一层，统一补上「每日目标环」进度。"""
    out = _today_payload(c, kid, fam, create=create, size=size)
    try:
        out["goal"] = goal_state(c, kid, kid_config(c, kid))
    except Exception:
        # 目标环只是展示：读不到也不许把今天这一组拖垮
        out["goal"] = {"scored_words": 0, "goal": 0, "goal_done": False}
    return out


def _today_payload(c, kid, fam, create=False, size=None):
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
            "backlog_due": _backlog(c, kid, fam, sess["items"], cfg),
            "config": cfg,
            "session": sess,
        }
    picked = _pick_items(c, kid, fam, cfg, size=size)
    if not picked:
        return {"enabled": True, "finished": True, "backlog_due": 0, "config": cfg, "session": None}
    if not create:
        return {
            "enabled": True,
            "finished": False,
            "backlog_due": _due_count(c, kid, fam, db.today(), _review_book_ids(c, kid, fam, cfg)),
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
            "backlog_due": _backlog(c, kid, fam, sess["items"], cfg),
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
         json.dumps(task, ensure_ascii=False), now, 0, 0),
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


def _need_active(c, kid, sid, replay=False):
    row = _session_owned(c, kid, sid)
    if not row:
        raise WordError(404, "没找到今天的单词练习")
    if row["state"] == "completed":
        # /word/ 的「再练一遍」：当天已经完成的会话也允许继续写（钱由 settle 按最好成绩幂等结算）
        if replay and row["study_date"] == db.today():
            return row
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


def _letters_only(raw):
    """只留字母（并小写）：空格、标点、撇号、大小写都不参与拼写判分。
    页面本来就只让孩子敲字母（标点由答案带出），所以判分也只比字母 —— v0.3.58 起。
    这样即使前端版本旧（撇号还当字母槽）、或答案里的标点换了写法，也不会把孩子判错。"""
    return "".join(ch for ch in (raw or "").lower() if "a" <= ch <= "z")


def _spell_ok(text, word_row):
    got = _letters_only(text)
    if not got:
        return False
    if got == _letters_only(word_row["word_norm"] or ""):
        return True
    return any(got == _letters_only(x) for x in _accepts(word_row["accept_json"]))


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
    row = _need_active(c, kid, sid, replay=True)   # 当天已完成也允许「再练一遍」
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
        # 第 1 轮每个词只判一次（防重复报分）；attempt_no>1 是 /word/ 的「再练一遍」轮，允许再判
        if it["first_result"] and attempt_no <= 1:
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
    db.insert_ledger(c, db.today(), int(delta), reason, ref, note, kid_id=kid)


def today_books(c, kid, sid):
    """今天这一局的词来自哪些书（家长端「这批词来自」那一行用）。"""
    if not sid:
        return []
    rows = c.execute(
        "SELECT b.id AS book_id, b.name AS name, COUNT(*) AS n "
        "FROM word_session_items i JOIN words w ON w.id=i.word_id "
        "JOIN word_books b ON b.id=w.book_id "
        "WHERE i.session_id=? AND i.kid_id=? GROUP BY b.id, b.name ORDER BY n DESC, b.id",
        (sid, kid),
    ).fetchall()
    return [{"id": r["book_id"], "name": r["name"], "n": int(r["n"] or 0)} for r in rows]


def new_book_note(c, kid, fam, cfg):
    """新词从哪本来（以及为什么可能出不来）：给孩子端/家长端一句话解释，别再让家长猜。"""
    bid = (cfg.get("current_book") or "").strip()
    if (cfg.get("review_mode") or "current") == "scope":
        scope = _review_book_ids(c, kid, fam, cfg) or []
        start = bid if bid in scope else (scope[0] if scope else "")
        name = ""
        if start:
            b = get_book(c, fam, start)
            name = (b["name"] if b else start) or start
        return {"id": start, "name": name, "blocked": False, "mode": "scope"}
    if not bid:
        return {"id": "", "name": "", "blocked": False, "mode": "current"}
    book = get_book(c, fam, bid)
    name = (book["name"] if book else bid) or bid
    blocked = bool(book) and not book_selectable(c, kid, fam, book, cfg)
    return {"id": bid, "name": name, "blocked": blocked, "mode": "current"}


def source_sentence(enabled, books, new_book, has_session):
    """「这批词来自：X · 新词：Y」——只解释，不给操作；纯函数，方便 pytest 钉住。"""
    if not enabled:
        return ""
    if not has_session:
        return "今天还没开局（下一局按「新词词书」取词）"
    head = "、".join("%s（%d 个）" % (b["name"], b["n"]) for b in (books or [])) or "没取到词"
    if not new_book:
        return "这批词来自：" + head
    if not new_book.get("id"):
        tail = "新词：还没选词书 → 不会出新词"
    elif new_book.get("blocked"):
        tail = "新词：%s 被词书锁挡住（先去「已学到」设英语进度）" % new_book["name"]
    elif new_book.get("mode") == "scope":
        tail = "新词：从 %s 往后取（自定义范围）" % new_book["name"]
    else:
        tail = "新词：%s" % new_book["name"]
    return "这批词来自：" + head + " · " + tail


def today_summary(c, kid, fam, cfg):
    """家长端「今天」这一排：孩子今天在 /word/ 的进展（服务端算，和页面口径同一套）。"""
    row = _today_session(c, kid)
    sid = row["id"] if row else ""
    info = _game_today(c, kid, sid) if sid else {"rounds": [], "best_score": 0, "got": 0}
    wrote = scored_words_today(c, kid)
    goal = int(cfg.get("daily_goal") or 0)
    books = today_books(c, kid, sid)
    new_book = new_book_note(c, kid, fam, cfg)
    return {
        "date": db.today(),
        "wrote": wrote,
        "rounds": len(info["rounds"]),
        "best_score": int(info["best_score"] or 0),
        "sunshine": int(info["got"] or 0),
        "sunshine_limit": GAME_MAX_SUNSHINE,
        "goal": goal,
        "goal_done": bool(goal and wrote >= goal),
        "finished": bool(row and row["state"] == "completed"),
        "books": books,
        "new_book": new_book,
    }


def week_summary(week):
    """从 week_stats 的 days 里数「练了几天 / 一共写了多少词 / 首轮正确率」。"""
    done = [d for d in week["days"] if d["completed"]]
    return {"days": len(done), "words": sum(int(d["items"]) for d in done), "rate": week["first_try_rate"]}


def today_sentence(enabled, today):
    """家长端「今天」那一句（后端拼好，前端只渲染 —— 不许有第二份文案）。"""
    if not enabled:
        return "英语单词没开"
    n = int(today["wrote"])
    if not n:
        return "今天还没练"
    goal = int(today["goal"])
    if goal > 0:
        tail = "已达标" if today["goal_done"] else ("还差 %d 词" % max(0, goal - n))
        head = "今天写了 %d 词（目标 %d，%s）" % (n, goal, tail)
    else:
        head = "今天写了 %d 个词" % n
    return " · ".join([head, "最好一轮 %d 分" % int(today["best_score"]),
                       "阳光 %d/%d" % (int(today["sunshine"]), int(today["sunshine_limit"]))])


def week_sentence(enabled, week, today):
    """家长端总览那一句：这周（练了几天 + 首轮正确率）+ 今天。"""
    if not enabled:
        return "英语单词没开"
    if int(week["days"]) <= 0:
        head = "这周还没练过英语"
    else:
        head = "这周练了 %d 天" % int(week["days"])
        if week["rate"] is not None:
            head += "，首轮正确率 %d%%" % int(week["rate"])
    n = int(today["wrote"])
    goal = int(today["goal"])
    if not n:
        tail = "今天还没练"
    elif goal > 0:
        tail = "今天写了 %d/%d 词%s" % (n, goal, "（达标）" if today["goal_done"] else "")
    else:
        tail = "今天写了 %d 个词" % n
    return head + "；" + tail


def english_empty_today():
    """读不到时的兜底（GAME_MAX_SUNSHINE 定义在后面，所以这里必须是函数、不能是模块级常量）。"""
    return {"date": db.today(), "wrote": 0, "rounds": 0, "best_score": 0, "sunshine": 0,
            "sunshine_limit": GAME_MAX_SUNSHINE, "goal": 0, "goal_done": False, "finished": False,
            "books": [], "new_book": {"id": "", "name": "", "blocked": False, "mode": "current"}}


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
            "rate": round(correct * 100 / total) if completed and total else None,
        })
    done = [x for x in days if x["completed"]]
    tot_i = sum(x["items"] for x in done)
    tot_c = sum(x["correct_first_try"] for x in done)
    out = {
        "days": days,
        "completed_sessions": sum(x["completed"] for x in days),
        "first_try_rate": round(tot_c * 100 / tot_i) if tot_i else None,
    }
    # 家长端要的「今天 + 本周一句」（只读；出错也不能把整个 stats 拖垮 —— B4 那次空白页的教训）
    week = week_summary(out)
    out["week"] = week
    try:
        cfg = kid_config(c, kid)
        today = today_summary(c, kid, fam, cfg)
        out["today"] = today
        out["today_sentence"] = today_sentence(cfg["enabled"], today)
        out["week_sentence"] = week_sentence(cfg["enabled"], week, today)
        out["today_source"] = source_sentence(cfg["enabled"], today["books"], today["new_book"],
                                             bool(today["books"]))
    except Exception:
        out["today"] = english_empty_today()
        out["today_sentence"] = "暂时读不到英语记录"
        out["week_sentence"] = "暂时读不到英语记录"
        out["today_source"] = ""
    return out


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
    # v0.3.53：单词流程不再发阳光 —— 英语阳光改由独立页 /word/ 按当天最好成绩结算（≤10/天）
    return today_payload(c, kid, fam, create=False)


# ---------------- 英语复习独立页 /word/（P2：按成绩发阳光 + 写打卡）----------------
# 口径（2026-09-16 定）：一轮得分 = 该轮答对 / 这一局词数（没答的当没对）；
# 当天按最好一轮结算一次额度：60 分以下 0，60–100 线性到 10（向下取整）。只补差额。
# 「一轮」= word_attempts.attempt_no 分组（服务端算，不信客户端）。

GAME_MAX_SUNSHINE = 10


def sunshine_for_score(score):
    """与前端 frontend/src/wordGame.js 的 sunshineFor 同一张表（两边都有测试钉住）。"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 0
    if s < 60:
        return 0
    capped = min(100.0, s)
    return max(0, min(GAME_MAX_SUNSHINE, int((capped - 60) / 40 * GAME_MAX_SUNSHINE)))


def _game_rounds(c, kid, sid):
    size = int(c.execute(
        "SELECT COUNT(*) FROM word_session_items WHERE session_id=? AND kid_id=?",
        (sid, kid)).fetchone()[0] or 0)
    rows = c.execute(
        # 只数 phase='spell'：那是这一轮的正式作答；轮内「再写一次」(retry) 不计分
        "SELECT attempt_no, COUNT(*) a, SUM(CASE WHEN result='right' THEN 1 ELSE 0 END) r "
        "FROM word_attempts WHERE session_id=? AND kid_id=? AND phase='spell' "
        "GROUP BY attempt_no ORDER BY attempt_no",
        (sid, kid),
    ).fetchall()
    out = []
    for row in rows:
        a = int(row["a"] or 0)
        r = int(row["r"] or 0)
        denom = size or a
        out.append({"attempt_no": int(row["attempt_no"]), "answered": a, "correct": r,
                    "size": denom, "score": (round(r * 100 / denom) if denom else 0)})
    return out


def _game_got(c, kid, today):
    return int(c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND reason='word_game' AND date=?",
        (kid, today)).fetchone()[0] or 0)


def _game_today(c, kid, sid):
    rounds = _game_rounds(c, kid, sid)
    best = max([r["score"] for r in rounds], default=0)
    should = sunshine_for_score(best)
    got = _game_got(c, kid, db.today())
    return {"rounds": rounds, "best_score": best, "should": should, "got": got,
            "can_grant": max(0, should - got),
            "checkin": c.execute("SELECT 1 FROM checkins WHERE date=? AND kid_id=?",
                                 (db.today(), kid)).fetchone() is not None}


def start_game(c, kid, fam):
    """独立页开局：按「一局词数」建/复用今天的会话。"""
    cfg = kid_config(c, kid)
    if not cfg["enabled"]:
        raise WordError(403, "单词练习没开，找家长打开")
    # goal（每日目标环）由 today_payload 统一补，这里不再重复设
    return today_payload(c, kid, fam, create=True, size=int(cfg["game_size"]))


def game_info(c, kid, fam):
    """独立页刷新时要的：设置（一局词数 / 连一连 / 每日目标）+ 今天的会话 + 今天的成绩/额度。"""
    cfg = kid_config(c, kid)
    row = _today_session(c, kid)
    sess = _session_public(c, kid, fam, row) if row else None
    today = _game_today(c, kid, row["id"]) if row else {"rounds": [], "best_score": 0,
                                                        "should": 0, "got": 0, "can_grant": 0, "checkin": False}
    today.pop("rounds", None)
    today.update(goal_state(c, kid, cfg))
    return {"enabled": cfg["enabled"], "size": int(cfg["game_size"]), "config": cfg,
            "session": sess, "today": today}


def settle_game(c, kid, fam, sid):
    """一轮结束：算本轮成绩 → 更新今日最好 → 补差发阳光 → 写当天打卡 → 标记会话完成。"""
    row = _session_owned(c, kid, sid)
    if not row:
        raise WordError(404, "没找到今天的单词练习")
    info = _game_today(c, kid, sid)
    rounds = info["rounds"]
    if not rounds or not rounds[-1]["answered"]:
        raise WordError(409, "这一轮还没有答题")
    round_now = rounds[-1]
    should, got = info["should"], info["got"]
    granted = max(0, should - got)
    if granted:
        db.insert_ledger(c, db.today(), granted, "word_game", "wg-%s-%d" % (db.today(), should),
                         "英语复习 · 当天最好成绩 %d 分" % info["best_score"], kid_id=kid)
    # 做完一轮就等于今天打卡（幂等；连击/全勤沿用既有逻辑）
    db.insert(c, "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
              (db.today(), 0, db.now(), kid))
    c.execute("UPDATE word_sessions SET state='completed', completed_at=? WHERE id=? AND kid_id=? AND state='active'",
              (db.now(), sid, kid))
    payload = {
        "round": round_now,
        "today": {"best_score": info["best_score"], "should": should, "got": got + granted,
                  "granted": granted, "limit": GAME_MAX_SUNSHINE, "checkin": True,
                  **goal_state(c, kid, kid_config(c, kid))},
        "day_best_hint": ("今天最好 %d 分（今天英语阳光 %d/%d）"
                          % (info["best_score"], got + granted, GAME_MAX_SUNSHINE)),
    }
    return payload
