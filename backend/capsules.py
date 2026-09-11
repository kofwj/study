# -*- coding: utf-8 -*-
"""时间胶囊第一刀：同时一封，到期才拆，不发阳光。"""
import json
import uuid
from datetime import date, datetime, timedelta

import db

TEXT_MAX = 40
WHEN_NEXT_TERM = "next_term"
WHEN_STREAK30 = "streak30"
WHEN_KINDS = (WHEN_NEXT_TERM, WHEN_STREAK30)
ACTIVE = ("sealed", "ready")


class CapsuleError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _parse_day(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _today():
    return datetime.strptime(db.today(), "%Y-%m-%d").date()


def next_term_open_on(today=None):
    """下一档开学锚点：2月16日或9月1日，取严格晚于今天的最近一个（江苏中小学，第一刀写死）。"""
    today = today or _today()
    for y in (today.year, today.year + 1, today.year + 2):
        for d in (date(y, 2, 16), date(y, 9, 1)):
            if d > today:
                return d
    return date(today.year + 1, 9, 1)


def _clean_text(s, label):
    t = " ".join(str(s or "").split())
    if not t:
        raise CapsuleError(400, f"「{label}」还没写")
    if len(t) > TEXT_MAX:
        raise CapsuleError(400, f"「{label}」最多 {TEXT_MAX} 个字")
    if all(not ch.isalnum() and not ("\u4e00" <= ch <= "\u9fff") for ch in t):
        raise CapsuleError(400, f"「{label}」要写一句人话")
    return t


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
    if row["when_kind"] == WHEN_NEXT_TERM:
        if row["open_on"] and today >= _parse_day(row["open_on"]):
            ready = True
    elif row["when_kind"] == WHEN_STREAK30:
        ready = _streak30_ready(row, today, streak)
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
    if row["when_kind"] == WHEN_NEXT_TERM and row["open_on"]:
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
    d = next_term_open_on()
    term = {"kind": WHEN_NEXT_TERM, "label": "下个学期开学", "hint": f"{d.year}年{d.month}月{d.day}日拆开", "open_on": d.isoformat()}
    if int(streak or 0) >= 30:
        day = _today() + timedelta(days=30)
        streak_opt = {
            "kind": WHEN_STREAK30,
            "label": "再等 30 天",
            "hint": f"已经连打 30 天了，从今天再等 30 天，{day.year}年{day.month}月{day.day}日拆开",
            "open_on": day.isoformat(),
        }
    else:
        left = max(0, 30 - int(streak or 0))
        streak_opt = {
            "kind": WHEN_STREAK30,
            "label": "再连续打卡 30 天",
            "hint": f"还要再连打 {left} 天，而且至少过一夜",
            "open_on": None,
        }
    return [term, streak_opt]


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


def get_payload(c, kid, streak, now_snap):
    row = promote_ready(c, kid, streak)
    if row and row["state"] in ACTIVE:
        hide = row["state"] != "opened"
        return {
            "state": row["state"],
            "capsule": _row_public(row, hide_body=hide),
            "wait": wait_hint(row, streak),
            "options": options(streak),
            "now": now_snap,
        }
    last = _last_opened(c, kid)
    return {
        "state": "empty",
        "capsule": _row_public(last, hide_body=False) if last else None,
        "wait": "",
        "options": options(streak),
        "now": now_snap,
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
    open_on = None
    if kind == WHEN_NEXT_TERM:
        open_on = next_term_open_on(today).isoformat()
    elif int(streak or 0) >= 30:
        open_on = (today + timedelta(days=30)).isoformat()
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
