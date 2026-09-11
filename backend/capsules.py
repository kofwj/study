# -*- coding: utf-8 -*-
"""时间胶囊：同时一封，到期才拆，不发阳光。"""
import json
import uuid
from datetime import date, datetime, timedelta

import db

TEXT_MAX = 40
OPEN_MAX_DAYS = 365 * 3
WHEN_WEEK = "week"
WHEN_MONTH = "month"
WHEN_NEXT_TERM = "next_term"
WHEN_YEAR = "year"
WHEN_STREAK30 = "streak30"
WHEN_CUSTOM = "custom"
WHEN_KINDS = (WHEN_WEEK, WHEN_MONTH, WHEN_NEXT_TERM, WHEN_YEAR, WHEN_STREAK30, WHEN_CUSTOM)
ACTIVE = ("sealed", "ready")
QUESTIONS = (
    {
        "key": "q_good",
        "label": "现在最拿手的一件事",
        "placeholder": "比如：口算很快",
        "examples": ("口算很快", "跳绳能连跳很多下", "英语单词记得住"),
    },
    {
        "key": "q_wish",
        "label": "还想变好的一件事",
        "placeholder": "比如：把字写得更工整",
        "examples": ("把字写得更工整", "英语听写少错几个", "早睡早起不磨蹭"),
    },
    {
        "key": "q_line",
        "label": "想对以后的自己说的一句",
        "placeholder": "比如：别忘了现在有多努力",
        "examples": ("别忘了现在有多努力", "以后的我要对自己说加油", "希望你还喜欢运动"),
    },
)


class CapsuleError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _parse_day(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _today():
    return datetime.strptime(db.today(), "%Y-%m-%d").date()


def _fmt_day(d):
    return f"{d.year}年{d.month}月{d.day}日"


def _add_years(d, n):
    try:
        return date(d.year + n, d.month, d.day)
    except ValueError:
        return date(d.year + n, 2, 28)


def next_term_open_on(today=None):
    """下一档开学锚点：2月16日或9月1日，取严格晚于今天的最近一个（江苏中小学，第一刀写死）。"""
    today = today or _today()
    for y in (today.year, today.year + 1, today.year + 2):
        for d in (date(y, 2, 16), date(y, 9, 1)):
            if d > today:
                return d
    return date(today.year + 1, 9, 1)


def date_bounds(today=None):
    today = today or _today()
    return {
        "min_open_on": (today + timedelta(days=1)).isoformat(),
        "max_open_on": (today + timedelta(days=OPEN_MAX_DAYS)).isoformat(),
    }


def _clean_text(s, label):
    t = " ".join(str(s or "").split())
    if not t:
        raise CapsuleError(400, f"「{label}」还没写")
    if len(t) > TEXT_MAX:
        raise CapsuleError(400, f"「{label}」最多 {TEXT_MAX} 个字")
    if all(not ch.isalnum() and not ("\u4e00" <= ch <= "\u9fff") for ch in t):
        raise CapsuleError(400, f"「{label}」要写一句人话")
    return t


def _parse_custom(s, today):
    t = " ".join(str(s or "").split())
    if not t:
        raise CapsuleError(400, "选一个开封的日子")
    try:
        d = _parse_day(t)
    except ValueError:
        raise CapsuleError(400, "日子要写成 年-月-日") from None
    if d <= today:
        raise CapsuleError(400, "要选明天或更晚")
    if d > today + timedelta(days=OPEN_MAX_DAYS):
        raise CapsuleError(400, "最远只能到三年后")
    return d


def open_on_for(kind, today, streak, custom_date=None):
    if kind == WHEN_WEEK:
        return today + timedelta(days=7)
    if kind == WHEN_MONTH:
        return today + timedelta(days=30)
    if kind == WHEN_YEAR:
        return _add_years(today, 1)
    if kind == WHEN_NEXT_TERM:
        return next_term_open_on(today)
    if kind == WHEN_STREAK30:
        if int(streak or 0) >= 30:
            return today + timedelta(days=30)
        return None
    if kind == WHEN_CUSTOM:
        return _parse_custom(custom_date, today)
    raise CapsuleError(400, "选一个开封的时候")


def _row_public(row, *, hide_body):
    if not row:
        return None
    snap = row["snapshot"]
    if isinstance(snap, str):
        try:
            snap = json.loads(snap)
        except json.JSONDecodeError:
            snap = {}
    out = {
        "id": row["id"],
        "state": row["state"],
        "when_kind": row["when_kind"],
        "open_on": row["open_on"],
        "sealed_on": row["sealed_on"],
        "opened_on": row["opened_on"],
        "snapshot": snap or {},
    }
    if not hide_body:
        out["q_good"] = row["q_good"]
        out["q_wish"] = row["q_wish"]
        out["q_line"] = row["q_line"]
    return out


def _active(c, kid):
    return c.execute(
        "SELECT * FROM capsules WHERE kid_id=? AND state IN ('sealed','ready') "
        "ORDER BY sealed_on DESC LIMIT 1",
        (kid,),
    ).fetchone()


def _last_opened(c, kid):
    return c.execute(
        "SELECT * FROM capsules WHERE kid_id=? AND state='opened' "
        "ORDER BY opened_on DESC, sealed_on DESC LIMIT 1",
        (kid,),
    ).fetchone()


def _streak30_ready(row, today, streak):
    sealed = _parse_day(row["sealed_on"])
    if today < sealed + timedelta(days=1):
        return False
    snap = row["snapshot"]
    if isinstance(snap, str):
        try:
            snap = json.loads(snap) or {}
        except json.JSONDecodeError:
            snap = {}
    sealed_streak = int(snap.get("streak") or 0)
    if sealed_streak >= 30:
        return today >= sealed + timedelta(days=30)
    return int(streak or 0) >= 30


def promote_ready(c, kid, streak):
    row = _active(c, kid)
    if not row or row["state"] != "sealed":
        return row
    today = _today()
    ready = False
    if row["when_kind"] == WHEN_STREAK30:
        ready = _streak30_ready(row, today, streak)
    elif row["open_on"] and today >= _parse_day(row["open_on"]):
        ready = True
    if not ready:
        return row
    open_on = row["open_on"] or today.isoformat()
    c.execute(
        "UPDATE capsules SET state='ready', open_on=? WHERE id=? AND state='sealed'",
        (open_on, row["id"]),
    )
    return c.execute("SELECT * FROM capsules WHERE id=?", (row["id"],)).fetchone()


def wait_hint(row, streak):
    if not row:
        return ""
    today = _today()
    if row["state"] == "ready":
        return "可以拆了"
    if row["open_on"]:
        n = (_parse_day(row["open_on"]) - today).days
        return f"还要等 {max(0, n)} 天"
    snap = row["snapshot"]
    if isinstance(snap, str):
        try:
            snap = json.loads(snap) or {}
        except json.JSONDecodeError:
            snap = {}
    sealed_streak = int(snap.get("streak") or 0)
    sealed = _parse_day(row["sealed_on"])
    if sealed_streak >= 30:
        n = (sealed + timedelta(days=30) - today).days
        return f"还要等 {max(0, n)} 天"
    left = max(0, 30 - int(streak or 0))
    return f"还要再连打 {left} 天"


def options(streak):
    today = _today()
    week_d = today + timedelta(days=7)
    month_d = today + timedelta(days=30)
    term_d = next_term_open_on(today)
    year_d = _add_years(today, 1)
    opts = [
        {"kind": WHEN_WEEK, "label": "一周后", "hint": f"{_fmt_day(week_d)}拆开", "open_on": week_d.isoformat()},
        {"kind": WHEN_MONTH, "label": "一个月后", "hint": f"{_fmt_day(month_d)}拆开", "open_on": month_d.isoformat()},
        {"kind": WHEN_NEXT_TERM, "label": "下个学期开学", "hint": f"{_fmt_day(term_d)}拆开", "open_on": term_d.isoformat()},
        {"kind": WHEN_YEAR, "label": "一年后", "hint": f"{_fmt_day(year_d)}拆开", "open_on": year_d.isoformat()},
    ]
    if int(streak or 0) >= 30:
        day = today + timedelta(days=30)
        opts.append({
            "kind": WHEN_STREAK30,
            "label": "再等 30 天",
            "hint": f"已经连打 30 天了，从今天再等 30 天，{_fmt_day(day)}拆开",
            "open_on": day.isoformat(),
        })
    else:
        left = max(0, 30 - int(streak or 0))
        opts.append({
            "kind": WHEN_STREAK30,
            "label": "再连续打卡 30 天",
            "hint": f"还要再连打 {left} 天，而且至少过一夜",
            "open_on": None,
        })
    opts.append({
        "kind": WHEN_CUSTOM,
        "label": "自己选一天",
        "hint": "从日历里挑，最早明天，最远三年",
        "open_on": None,
        "needs_date": True,
    })
    return opts


def snapshot_now(c, kid, *, term_id, level, earned, streak, companion, pocket, bank):
    return {
        "date": db.today(),
        "term_id": term_id or "",
        "level": (level or {}).get("level") or "",
        "earned": int(earned or 0),
        "streak": int(streak or 0),
        "companion_stage": (companion or {}).get("stage") or "",
        "companion_stage_name": (companion or {}).get("stage_name") or "",
        "companion_name": (companion or {}).get("name") or "",
        "pocket": int(pocket or 0),
        "bank": int(bank or 0),
    }


def _form_meta():
    bounds = date_bounds()
    return {
        "questions": [dict(q, examples=list(q["examples"])) for q in QUESTIONS],
        "min_open_on": bounds["min_open_on"],
        "max_open_on": bounds["max_open_on"],
    }


def get_payload(c, kid, streak, now_snap):
    meta = _form_meta()
    row = promote_ready(c, kid, streak)
    if row and row["state"] in ACTIVE:
        hide = row["state"] != "opened"
        return {
            "state": row["state"],
            "capsule": _row_public(row, hide_body=hide),
            "wait": wait_hint(row, streak),
            "options": options(streak),
            "now": now_snap,
            **meta,
        }
    last = _last_opened(c, kid)
    return {
        "state": "empty",
        "capsule": _row_public(last, hide_body=False) if last else None,
        "wait": "",
        "options": options(streak),
        "now": now_snap,
        **meta,
    }


def seal(c, kid, fam, body, *, streak, snap):
    if _active(c, kid):
        raise CapsuleError(409, "箱子里已经有一封了")
    kind = (body.get("when_kind") or "").strip()
    if kind not in WHEN_KINDS:
        raise CapsuleError(400, "选一个开封的时候")
    q_good = _clean_text(body.get("q_good"), "现在最拿手的一件事")
    q_wish = _clean_text(body.get("q_wish"), "还想变好的一件事")
    q_line = _clean_text(body.get("q_line"), "想对以后的自己说的一句")
    today = _today()
    open_day = open_on_for(kind, today, streak, body.get("open_on"))
    open_on = open_day.isoformat() if open_day else None
    cid = uuid.uuid4().hex[:12]
    c.execute(
        "INSERT INTO capsules(id,kid_id,family_id,state,when_kind,open_on,sealed_on,opened_on,"
        "q_good,q_wish,q_line,snapshot,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, kid, fam or "", "sealed", kind, open_on, today.isoformat(), None,
         q_good, q_wish, q_line, json.dumps(snap, ensure_ascii=False), db.now()),
    )
    row = c.execute("SELECT * FROM capsules WHERE id=?", (cid,)).fetchone()
    return _row_public(row, hide_body=True)


def open_capsule(c, kid, streak, now_snap):
    row = promote_ready(c, kid, streak)
    if not row:
        raise CapsuleError(404, "还没有可以拆的信")
    if row["state"] != "ready":
        raise CapsuleError(409, "还没到能拆的那天")
    today = db.today()
    c.execute(
        "UPDATE capsules SET state='opened', opened_on=? WHERE id=? AND state='ready'",
        (today, row["id"]),
    )
    row = c.execute("SELECT * FROM capsules WHERE id=?", (row["id"],)).fetchone()
    out = _row_public(row, hide_body=False)
    out["now"] = now_snap
    return out
