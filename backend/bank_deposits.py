# -*- coding: utf-8 -*-
"""阳光储蓄所定存：小孩自选天数，到期一次结息；提前支取按进度打五折。"""
import uuid
from datetime import datetime, timedelta

import db

# 一次性到期利率（不是年化）。存越久越高，让孩子能看见「多等几天会多一点」。
TERMS = (
    (7, 2.0),
    (10, 3.0),
    (15, 5.0),
    (30, 8.0),
    (60, 12.0),
)
TERM_MAP = {d: r for d, r in TERMS}
EARLY_FACTOR = 0.5
ACTIVE = "active"
MATURED = "matured"
BROKEN = "broken"


class DepositError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _parse_day(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _today():
    return datetime.strptime(db.today(), "%Y-%m-%d").date()


def term_catalog():
    return [
        {
            "days": d,
            "rate": r,
            "label": f"{d} 天",
            "hint": f"到期多 {r:g}%",
        }
        for d, r in TERMS
    ]


def rate_for(days):
    try:
        d = int(days)
    except (TypeError, ValueError):
        raise DepositError(400, "选一个存款天数") from None
    if d not in TERM_MAP:
        raise DepositError(400, "天数只能是 7 / 10 / 15 / 30 / 60")
    return d, TERM_MAP[d]


def interest_at_maturity(amount, rate):
    return int(int(amount) * float(rate) / 100)


def interest_early(amount, rate, elapsed, days):
    elapsed = max(0, min(int(elapsed), int(days)))
    if elapsed <= 0 or days <= 0:
        return 0
    return int(int(amount) * float(rate) * elapsed * EARLY_FACTOR / (100 * days))


def _public(row, today=None):
    if not row:
        return None
    today = today or _today()
    started = _parse_day(row["started_on"])
    mature = _parse_day(row["mature_on"])
    elapsed = max(0, (today - started).days)
    days = int(row["days"])
    amount = int(row["amount"])
    rate = float(row["rate"])
    due = max(0, (mature - today).days)
    matured_pay = interest_at_maturity(amount, rate)
    early_pay = interest_early(amount, rate, elapsed, days)
    return {
        "id": row["id"],
        "amount": amount,
        "days": days,
        "rate": rate,
        "started_on": row["started_on"],
        "mature_on": row["mature_on"],
        "state": row["state"],
        "closed_on": row["closed_on"],
        "interest_paid": int(row["interest_paid"] or 0),
        "left_days": due if row["state"] == ACTIVE else 0,
        "elapsed_days": min(elapsed, days),
        "mature_interest": matured_pay,
        "early_interest": early_pay if row["state"] == ACTIVE else int(row["interest_paid"] or 0),
    }


def locked_on(c, kid, day):
    date_str = day if isinstance(day, str) else day.isoformat()
    r = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM bank_deposits WHERE kid_id=? AND started_on<=? "
        "AND (state=? OR (closed_on IS NOT NULL AND closed_on>?))",
        (kid, date_str, ACTIVE, date_str),
    ).fetchone()
    return int(r[0] or 0)


def locked_now(c, kid):
    r = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM bank_deposits WHERE kid_id=? AND state=?",
        (kid, ACTIVE),
    ).fetchone()
    return int(r[0] or 0)


def list_deposits(c, kid, *, include_closed=False, limit=20):
    today = _today()
    if include_closed:
        rows = c.execute(
            "SELECT * FROM bank_deposits WHERE kid_id=? ORDER BY started_on DESC, created_at DESC LIMIT ?",
            (kid, limit),
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM bank_deposits WHERE kid_id=? AND state=? ORDER BY mature_on, created_at",
            (kid, ACTIVE),
        ).fetchall()
    return [_public(r, today) for r in rows]


def open_deposit(c, kid, fam, amount, days):
    days, rate = rate_for(days)
    amount = int(amount)
    if amount < 1:
        raise DepositError(400, "至少存 1 颗")
    today = _today()
    mature = today + timedelta(days=days)
    did = uuid.uuid4().hex[:12]
    c.execute(
        "INSERT INTO bank_deposits(id,kid_id,family_id,amount,days,rate,started_on,mature_on,"
        "state,closed_on,interest_paid,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (did, kid, fam or "", amount, days, rate, today.isoformat(), mature.isoformat(),
         ACTIVE, None, 0, db.now()),
    )
    row = c.execute("SELECT * FROM bank_deposits WHERE id=?", (did,)).fetchone()
    return _public(row, today)


def _pay_interest(c, kid, deposit_id, amount, note):
    if amount <= 0:
        return None
    ref = f"term-interest-{deposit_id}"
    return db.insert_ledger(c, db.today(), amount, "bank_interest", ref, note, kid, "bank")


def _close(c, row, state, interest, today):
    cur = c.execute(
        "UPDATE bank_deposits SET state=?, closed_on=?, interest_paid=? WHERE id=? AND state=?",
        (state, today.isoformat(), int(interest), row["id"], ACTIVE),
    )
    if getattr(cur, "rowcount", 0) == 0:
        return c.execute("SELECT * FROM bank_deposits WHERE id=?", (row["id"],)).fetchone()
    if interest > 0:
        label = "到期利息" if state == MATURED else "提前支取利息"
        _pay_interest(c, row["kid_id"], row["id"], interest, f"{row['days']}天存单{label}")
    return c.execute("SELECT * FROM bank_deposits WHERE id=?", (row["id"],)).fetchone()


def promote_matured(c, kid):
    today = _today()
    rows = c.execute(
        "SELECT * FROM bank_deposits WHERE kid_id=? AND state=? AND mature_on<=?",
        (kid, ACTIVE, today.isoformat()),
    ).fetchall()
    out = []
    for row in rows:
        pay = interest_at_maturity(row["amount"], row["rate"])
        closed = _close(c, row, MATURED, pay, today)
        out.append(_public(closed, today))
    return out


def break_deposit(c, kid, deposit_id):
    row = c.execute(
        "SELECT * FROM bank_deposits WHERE id=? AND kid_id=?", (deposit_id, kid)
    ).fetchone()
    if not row:
        raise DepositError(404, "没找到这张存单")
    today = _today()
    if row["state"] != ACTIVE:
        raise DepositError(409, "这张存单已经结束了")
    if today >= _parse_day(row["mature_on"]):
        pay = interest_at_maturity(row["amount"], row["rate"])
        closed = _close(c, row, MATURED, pay, today)
        return _public(closed, today)
    started = _parse_day(row["started_on"])
    elapsed = (today - started).days
    pay = interest_early(row["amount"], row["rate"], elapsed, row["days"])
    closed = _close(c, row, BROKEN, pay, today)
    return _public(closed, today)
