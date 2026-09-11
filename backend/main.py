# -*- coding: utf-8 -*-
"""阳光学习工作台 — P0 后端。

核心不变式：ledger 是唯一真相源；余额/累计/等级/连击全部由 ledger+日期推导。
「点错取消」= 一条负 delta 流水 + completion 置 cancelled，不删历史；取消后可重新打卡。
"""
import contextvars
import json
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, ConfigDict

import sqlite3

import db
import sprites as spritemod
import capsules as capmod
import words as wordmod
from version import app_label, app_revision, app_version

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_kid = contextvars.ContextVar("kid", default=None)
_fam = contextvars.ContextVar("fam", default=None)
COOKIE_PARENT, COOKIE_KID = "pid", "sid"
TOKEN_MAX_AGE = 7 * 24 * 3600
MAX_KIDS_PER_FAMILY = 5
RATE_WINDOW = 600
RATE_MAX = 5
REGISTER_WINDOW = 24 * 3600
REGISTER_MAX = 3


def _serializer():
    return URLSafeTimedSerializer(db.secret_key(), salt="sunshine-sid")


@asynccontextmanager
async def lifespan(app):
    db.init_db()  # 启动时建库/迁移一次，请求路径不再重复初始化
    yield


app = FastAPI(title="阳光学习工作台", lifespan=lifespan)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常，记录详细日志但只返回通用错误给客户端"""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None,
            "user_id": getattr(request.state, "user", {}).get("user_id") if hasattr(request.state, "user") else None
        }
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"}
    )


# 前端由 StaticFiles 同源托管，无需跨域；删掉 CORS 避免任何外部站点能调用接口

# 签到不发阳光（无门槛白拿会通胀），保留为「今天来过」记录 + 连击兜底


def get_conn():
    c = db.connect()
    db.apply_scope(c, _fam.get(), _kid.get())
    return c


def kid_id():
    k = _kid.get()
    if not k:
        raise RuntimeError("kid scope missing")
    return k


def insert_ledger(c, date, delta, reason, ref_id, note, kid=None, account="pocket"):
    return db.insert_ledger(c, date, delta, reason, ref_id, note, kid_id=kid or kid_id(), account=account)


def _begin_write(c):
    if not db.is_postgres():
        c.execute("BEGIN IMMEDIATE")


def _rollback(c):
    try:
        c.rollback()
    except Exception:
        pass


def active_term(c):
    r = c.execute("SELECT term_id, name FROM users WHERE id=?", (kid_id(),)).fetchone()
    if not r:
        return "g5s1"
    return r["term_id"] or "g5s1"


def _client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else ""))


def _new_recovery_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(10))


def _rate_ok(key: str, window: float = RATE_WINDOW, limit: int = RATE_MAX, message: str = "试太多次了，过一会儿再试"):
    now = time.time()
    cutoff = now - window
    c = db.connect(admin=True)
    try:
        c.execute("DELETE FROM rate_limits WHERE ts < ?", (now - REGISTER_WINDOW,))
        n = c.execute("SELECT COUNT(*) FROM rate_limits WHERE key=? AND ts>=?", (key, cutoff)).fetchone()[0]
        c.commit()
    finally:
        c.close()
    if n >= limit:
        raise HTTPException(429, message)


def _rate_hit(key: str):
    c = db.connect(admin=True)
    try:
        c.execute("INSERT INTO rate_limits(key, ts) VALUES(?,?)", (key, time.time()))
        c.commit()
    finally:
        c.close()


def _cookie_secure(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def _set_auth_cookie(resp: Response, request: Request, name: str, payload: dict):
    resp.set_cookie(
        name, _serializer().dumps(payload),
        max_age=TOKEN_MAX_AGE, httponly=True, samesite="strict",
        secure=_cookie_secure(request), path="/")


def _load_user(token: str):
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    c = db.connect(admin=True)  # 登录前无 family 上下文；users 已 RLS，须特权反查
    try:
        rev = c.execute("SELECT created_at FROM revoked WHERE jti=?", ("u:" + data.get("user_id", ""),)).fetchone()
        try:
            iat = float(data.get("iat") or 0)
            rts = float(rev["created_at"]) if rev else 0
        except (TypeError, ValueError):
            iat, rts = 0, 0
        if rts and rts >= iat:
            return None
        row = c.execute("SELECT * FROM users WHERE id=?", (data.get("user_id"),)).fetchone()
    finally:
        c.close()
    return dict(row) if row else None


def _user_from_request(request: Request):
    for name in (COOKIE_KID, COOKIE_PARENT):
        raw = request.cookies.get(name)
        if not raw:
            continue
        u = _load_user(raw)
        if u:
            return u
    return None


PUBLIC_API = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/register", "/api/auth/join", "/api/auth/recover"}


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_API:
        return await call_next(request)
    u = _user_from_request(request)
    if not u:
        return JSONResponse({"detail": "未登录"}, 401)
    c0 = db.connect()
    db.apply_scope(c0, u["family_id"], None)
    try:
        if u["role"] == "kid":
            kid = u["id"]
        else:
            kid = request.query_params.get("selected_kid")
            if kid:
                row = c0.execute("SELECT family_id FROM users WHERE id=? AND role='kid'", (kid,)).fetchone()
                if not row or row["family_id"] != u["family_id"]:
                    return JSONResponse({"detail": "未登录"}, 403)
            else:
                row = c0.execute(
                    "SELECT id FROM users WHERE family_id=? AND role='kid' ORDER BY created_at LIMIT 1",
                    (u["family_id"],)).fetchone()
                kid = row["id"] if row else None
    finally:
        c0.close()
    if not kid:
        if u["role"] != "parent" or not (path.startswith("/api/admin/") or path == "/api/auth/me"):
            return JSONResponse({"detail": "没有孩子"}, 400)
    tok_k, tok_f = _kid.set(kid), _fam.set(u["family_id"])
    request.state.user = u
    try:
        return await call_next(request)
    finally:
        _kid.reset(tok_k)
        _fam.reset(tok_f)


def _check_pin(pin, *, parent):
    pin = (pin or "").strip()
    if parent:
        if len(pin) < 8:
            raise HTTPException(400, "家长密码至少 8 位")
    else:
        if len(pin) < 6:
            raise HTTPException(400, "孩子密码至少 6 位")
        # 禁止弱密码：纯数字连续或重复
        if pin.isdigit():
            if len(set(pin)) == 1:  # 全是同一个数字
                raise HTTPException(400, "密码不能是重复数字（如 000000）")
            # 检查连续数字
            is_consecutive = all(int(pin[i]) == int(pin[i-1]) + 1 for i in range(1, len(pin)))
            is_reverse_consecutive = all(int(pin[i]) == int(pin[i-1]) - 1 for i in range(1, len(pin)))
            if is_consecutive or is_reverse_consecutive:
                raise HTTPException(400, "密码不能是连续数字（如 123456）")
    return pin


def require_parent(request: Request):
    u = getattr(request.state, "user", None)
    if not u or u["role"] != "parent":
        raise HTTPException(403, "需要家长账号")
    return u


def require_owner(request: Request):
    """需要家长创建者权限（owner）才能执行的操作"""
    u = require_parent(request)
    if u.get("parent_role") != "owner":
        raise HTTPException(403, "需要家长创建者权限")
    return u


def _sun(n, lo=0):
    try:
        v = int(n)
    except (TypeError, ValueError):
        raise HTTPException(400, "阳光要填数字")
    if v < lo:
        raise HTTPException(400, "阳光不能是负数")
    if v > 10000:
        raise HTTPException(400, "单次阳光数值不能超过 10000")
    return v


def earned(c, kid=None):
    # 升级用净增：赚到的减去取消和扣分；商店兑换、银行存取不计入（花钱不掉级）
    return c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE reason NOT IN "
        "('redeem','bank_deposit','bank_withdraw') AND kid_id=?",
        (kid or kid_id(),)).fetchone()[0]



def balance(c, kid=None, account="pocket"):
    return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND account=?", (kid or kid_id(), account)).fetchone()[0]


def bank_balance(c, kid=None):
    return balance(c, kid, "bank")


def level_info(c):
    e = earned(c)
    ranks = c.execute("SELECT * FROM ranks WHERE family_id=? ORDER BY min_sunshine", (_fam.get(),)).fetchall()
    cur = ranks[0]
    nxt = None
    for r in ranks:
        if r["min_sunshine"] <= e:
            cur = r
    for r in ranks:
        if r["min_sunshine"] > e:
            nxt = r
            break
    progress = 0.0
    if nxt:
        span = nxt["min_sunshine"] - cur["min_sunshine"]
        progress = round((e - cur["min_sunshine"]) / span * 100, 1) if span else 100.0
    else:
        progress = 100.0
    return {
        "earned": e, "balance": balance(c),
        "level": cur["name"], "level_id": cur["id"], "level_icon": cur["icon"] or "star",
        "next": nxt["name"] if nxt else None,
        "next_icon": (nxt["icon"] or "star") if nxt else None,
        "next_need": nxt["min_sunshine"] if nxt else None,
        "progress": progress,
    }


WEEKDAYS = "一二三四五六日"


def today_label():
    d = datetime.now()
    return "%d年%d月%d日 星期%s" % (d.year, d.month, d.day, WEEKDAYS[d.weekday()])


# 系统任务按学期；自定义任务按全家/指定孩子，不因挂在教材单元上漏给别的娃。
TASK_SCOPE = (
    "(COALESCE(t.custom,0)=0 AND u.term_id=?) OR "
    "(COALESCE(t.custom,0)=1 AND (t.kid_id IS NULL OR t.kid_id=?))"
)


def subject_order(c, subject_id):
    rows = c.execute(
        "SELECT t.id FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "WHERE t.subject_id=? AND (" + TASK_SCOPE + ") "
        "ORDER BY COALESCE(u.seq,99), t.sort", (subject_id, active_term(c), kid_id())).fetchall()
    return [r["id"] for r in rows]


def is_past(c, task_id, subject_id):
    cur = db.get_kid_setting(c, kid_id(), "cursor_" + subject_id, "")
    if not cur:
        return False
    ids = subject_order(c, subject_id)
    if task_id not in ids or cur not in ids:
        return False
    return ids.index(task_id) < ids.index(cur)


def locked_task_ids(c):
    """进度锁（默认开）：每科只有「当前单元」可打卡，之后的单元锁定，防提前刷后面的课。"""
    if db.get_setting(c, "progress_lock", "1") != "1":
        return set()
    term = active_term(c)
    tseq = {r["id"]: r["seq"] for r in c.execute(
        "SELECT t.id, COALESCE(u.seq,0) seq FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "WHERE " + TASK_SCOPE, (term, kid_id())).fetchall()}
    custom_ids = {r["id"] for r in c.execute(
        "SELECT id FROM tasks WHERE custom=1 AND (kid_id IS NULL OR kid_id=?)", (kid_id(),)).fetchall()}
    locked = set()
    for sid in {r[0] for r in c.execute(
            "SELECT DISTINCT t.subject_id FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
            "WHERE " + TASK_SCOPE, (term, kid_id())).fetchall()}:
        ids = subject_order(c, sid)
        cur_seq = None
        for tid in ids:
            if tid in custom_ids:
                continue
            done = c.execute("SELECT 1 FROM completions WHERE task_id=? AND status='completed' AND kid_id=?",
                            (tid, kid_id())).fetchone() is not None
            if done or is_past(c, tid, sid):
                continue
            cur_seq = tseq.get(tid, 0)
            break
        if cur_seq is not None:
            locked |= {tid for tid in ids if tid not in custom_ids and tseq.get(tid, 0) > cur_seq}
    return locked


def streak(c, kid=None):
    # 连击 = 连续几天有学习活动。今天还没打卡时沿用昨天，隔了一整天没活动才归零。
    kid = kid or kid_id()
    dates = {r["date"] for r in c.execute("SELECT DISTINCT date FROM checkins WHERE kid_id=?", (kid,)).fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM completions WHERE status='completed' AND kid_id=?", (kid,)).fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM redemptions WHERE status IN ('done','delivered') AND kid_id=?", (kid,)).fetchall()}
    d = datetime.now().date()
    if d.isoformat() not in dates:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in dates:
        n += 1
        d -= timedelta(days=1)
    return n


COMPANION_STAGES = [
    ("egg", "阳光蛋", 0),
    ("sprout", "阳光芽", 50),
    ("leaf", "阳光苗", 350),
    ("bloom", "阳光花", 1200),
]
CFG_COMPANION_NAME = "companion_name"
CFG_COMPANION_SEEN = "companion_stage_seen"


def _companion_aura(n):
    if n >= 30:
        return "month"
    if n >= 14:
        return "fortnight"
    if n >= 7:
        return "week"
    return None


def companion_info(c, kid=None):
    kid = kid or kid_id()
    e = int(earned(c, kid) or 0)
    s = streak(c, kid)
    cur = COMPANION_STAGES[0]
    for st in COMPANION_STAGES:
        if e >= st[2]:
            cur = st
    idx = next(i for i, st in enumerate(COMPANION_STAGES) if st[0] == cur[0])
    nxt = COMPANION_STAGES[idx + 1] if idx + 1 < len(COMPANION_STAGES) else None
    if nxt:
        span = nxt[2] - cur[2]
        progress = round((e - cur[2]) / span * 100, 1) if span else 100.0
    else:
        progress = 100.0
    name = (db.get_kid_setting(c, kid, CFG_COMPANION_NAME, "") or "").strip()
    seen = (db.get_kid_setting(c, kid, CFG_COMPANION_SEEN, "") or "").strip()
    seen_idx = next((i for i, st in enumerate(COMPANION_STAGES) if st[0] == seen), None)
    evolve = False
    if seen_idx is None:
        db.set_kid_setting(c, kid, CFG_COMPANION_SEEN, cur[0])
        evolve = False
    else:
        evolve = idx > seen_idx
    return {
        "stage": cur[0],
        "stage_name": cur[1],
        "name": name,
        "earned": e,
        "next_stage": nxt[0] if nxt else None,
        "next_stage_name": nxt[1] if nxt else None,
        "next_need": nxt[2] if nxt else None,
        "progress": progress,
        "aura": _companion_aura(s),
        "evolve": evolve,
    }


INSIGHT_DEFAULTS = {
    "test_fail_count": 2,
    "test_fail_score": 80,
    "drop_ratio": 0.3,
    "streak_break": 2,
}
FITNESS_METRIC = {
    "跳绳": ("pe-jump-rope", "n1m"),
    "仰卧起坐": ("pe-situp", "cnt"),
    "坐位体前屈": ("pe-bend", "cm"),
}


def insight_rules(c):
    row = c.execute("SELECT insight_rules FROM families WHERE id=?", (_fam.get(),)).fetchone()
    merged = dict(INSIGHT_DEFAULTS)
    raw = (row["insight_rules"] if row else "") or ""
    try:
        extra = json.loads(raw) if raw else {}
        if isinstance(extra, dict):
            merged.update(extra)
    except Exception:
        pass
    return merged


def _monday(d=None):
    d = d or datetime.now().date()
    return d - timedelta(days=d.weekday())


def _insight_weak_unit(c, kid, rules):
    n = int(rules["test_fail_count"])
    bar = int(rules["test_fail_score"])
    cutoff = (datetime.now().date() - timedelta(days=30)).isoformat()
    units = [r[0] for r in c.execute(
        "SELECT DISTINCT unit_id FROM tests WHERE kid_id=? AND unit_id IS NOT NULL AND unit_id!=''",
        (kid,)).fetchall()]
    for uid in units:
        rows = c.execute(
            "SELECT score, date FROM tests WHERE kid_id=? AND unit_id=? ORDER BY date DESC, id DESC LIMIT ?",
            (kid, uid, n)).fetchall()
        if len(rows) < n:
            continue
        if any(int(r["score"]) >= bar for r in rows):
            continue
        if rows[0]["date"] < cutoff:
            continue
        u = c.execute("SELECT name, subject_id FROM units WHERE id=?", (uid,)).fetchone()
        sid = (u["subject_id"] if u else "") or ""
        sn = c.execute("SELECT name FROM subjects WHERE id=?", (sid,)).fetchone() if sid else None
        subj = (sn["name"] if sn else sid) or ""
        uname = (u["name"] if u else uid) or uid
        return {
            "type": "weak_unit",
            "text": f"{subj}《{uname}》连续 {n} 次低于 {bar} 分",
            "action": "单元测试",
            "source": {"unit_id": uid, "scores": [int(r["score"]) for r in rows]},
        }
    return None


def _insight_streak_break(c, kid, rules):
    need = int(rules["streak_break"])
    today = datetime.now().date()
    monday = _monday(today)
    weekdays_passed = (today - monday).days + 1
    start, end = monday.isoformat(), today.isoformat()
    dates = {r[0] for r in c.execute(
        "SELECT DISTINCT date FROM checkins WHERE kid_id=? AND date BETWEEN ? AND ?", (kid, start, end)).fetchall()}
    dates |= {r[0] for r in c.execute(
        "SELECT DISTINCT date FROM completions WHERE status='completed' AND kid_id=? AND date BETWEEN ? AND ?",
        (kid, start, end)).fetchall()}
    gap = weekdays_passed - len(dates)
    if gap < need:
        return None
    return {"type": "streak_break", "text": f"这周有 {gap} 天没打卡", "action": "每日打卡",
            "source": {"gap": gap, "active_days": len(dates)}}


def _insight_drop(c, kid, rules):
    ratio = float(rules["drop_ratio"])
    today = datetime.now().date()
    monday = _monday(today)
    span = (today - monday).days
    last_from = monday - timedelta(days=7)
    last_to = last_from + timedelta(days=span)
    this = c.execute(
        "SELECT COUNT(*) FROM completions WHERE status='completed' AND kid_id=? AND date BETWEEN ? AND ?",
        (kid, monday.isoformat(), today.isoformat())).fetchone()[0]
    last = c.execute(
        "SELECT COUNT(*) FROM completions WHERE status='completed' AND kid_id=? AND date BETWEEN ? AND ?",
        (kid, last_from.isoformat(), last_to.isoformat())).fetchone()[0]
    if last <= 0 or this >= last * (1 - ratio):
        return None
    pct = round((1 - this / last) * 100)
    return {"type": "drop", "text": f"完成比上周少 {pct}%", "action": None,
            "source": {"this": this, "last": last}}


def _kid_grade(term_id):
    if not term_id or len(term_id) < 2 or term_id[0] != "g" or not term_id[1].isdigit():
        return None
    return int(term_id[1])


def _insight_fitness(c, kid):
    u = c.execute("SELECT gender, term_id FROM users WHERE id=?", (kid,)).fetchone()
    if not u or not u["gender"]:
        return None
    grade = _kid_grade(u["term_id"])
    if not grade:
        return None
    cutoff = (datetime.now().date() - timedelta(days=14)).isoformat()
    best = None
    for item, (tid, mid) in FITNESS_METRIC.items():
        std = c.execute(
            "SELECT pass_value, unit FROM fitness_standards WHERE grade=? AND gender=? AND item=?",
            (grade, u["gender"], item)).fetchone()
        if not std or std["pass_value"] is None:
            continue
        rows = c.execute(
            "SELECT metrics FROM completions WHERE task_id=? AND status='completed' AND kid_id=? "
            "AND date>=? AND metrics IS NOT NULL ORDER BY date DESC, id DESC",
            (tid, kid, cutoff)).fetchall()
        last = None
        for r in rows:
            try:
                v = (json.loads(r["metrics"]) or {}).get(mid)
            except Exception:
                v = None
            if v is not None:
                last = float(v)
                break
        if last is None:
            continue
        gap = float(std["pass_value"]) - last
        if gap <= 0:
            continue
        if best is None or gap > best["gap"]:
            unit = std["unit"] or ""
            shown = round(gap, 1) if gap % 1 else int(gap)
            best = {"gap": gap, "item": item, "last": last, "pass": float(std["pass_value"]), "unit": unit,
                    "text": f"{item}离达标还差 {shown}{unit}", "source": {"item": item, "last": last, "pass": float(std["pass_value"]), "unit": unit}}
    if not best:
        return None
    return {"type": "fitness", "text": best["text"], "action": "运动打卡", "source": best["source"]}


def _insight_review_due(c, kid):
    n = c.execute(
        "SELECT COUNT(*) FROM weak_points WHERE kid_id=? AND status='open' AND review_due_at IS NOT NULL AND review_due_at!='' AND review_due_at<=?",
        (kid, db.today())).fetchone()[0]
    if n:
        return {"type": "review_due", "text": "有 " + str(n) + " 个薄弱点该复习了", "action": "今日复习",
                "source": {"n": n}}
    return None


def build_insights(c, kid):
    rules = insight_rules(c)
    return (_insight_review_due(c, kid) or _insight_weak_unit(c, kid, rules) or _insight_fitness(c, kid)
            or _insight_streak_break(c, kid, rules) or _insight_drop(c, kid, rules))


INSIGHT_RANK = {"review_due": 0, "weak_unit": 1, "fitness": 2, "streak_break": 3, "drop": 4}


def _completed_between(c, kid, start, end):
    return c.execute(
        "SELECT COUNT(*) FROM completions WHERE status='completed' AND kid_id=? AND date BETWEEN ? AND ?",
        (kid, start, end)).fetchone()[0]


def _mastered_names(c, kid, w_start, w_end):
    return [r[0] for r in c.execute(
        "SELECT DISTINCT kt.name FROM weak_points wp JOIN knowledge_tags kt ON kt.id=wp.tag_id "
        "WHERE wp.kid_id=? AND substr(wp.updated_at,1,10) BETWEEN ? AND ? "
        "AND (wp.status='resolved' OR COALESCE(wp.interval_idx,0) >= 4) "
        "ORDER BY kt.name", (kid, w_start, w_end)).fetchall()]


def _insight_clause(name, ins):
    t = (ins or {}).get("type")
    if t == "review_due":
        n = (ins.get("source") or {}).get("n")
        if n is None:
            n = 0
        return f"{name}的复习（{n} 项到期）"
    if t == "weak_unit":
        text = ins.get("text") or ""
        subj = text.split("《")[0] if "《" in text else "单元"
        return f"{name}的{subj}测验"
    if t == "fitness":
        return f"{name}的体测"
    if t == "streak_break":
        return f"{name}的打卡"
    if t == "drop":
        return f"{name}的完成量"
    return name


def family_insight_from(rows):
    ranked = []
    for r in rows:
        ins = r.get("insight")
        if not ins:
            continue
        ranked.append((INSIGHT_RANK.get(ins.get("type"), 99), r))
    ranked.sort(key=lambda x: x[0])
    top = [r for _, r in ranked[:2]]
    if not top:
        return {"text": "这周不用特别盯。", "action": None, "kid_id": ""}
    parts = [_insight_clause(r["name"], r["insight"]) for r in top]
    text = "先看" + parts[0] + "。" if len(parts) == 1 else "先看" + parts[0] + "，再看" + parts[1] + "。"
    first = top[0]["insight"]
    return {"text": text, "action": first.get("action"), "kid_id": top[0]["kid_id"]}


# 连续坚持里程碑（一次性奖励，防通胀）：第 7/14/30 天各发一次
MILESTONES = [(7, 20), (14, 50), (30, 100)]


def maybe_milestone(c, kid=None):
    """连击达 7/14/30 天各发一次一次性阳光（用 kid_settings 标记，绝不重复）。返回 [(天数, 奖励)]。"""
    kid = kid or kid_id()
    s = streak(c, kid)
    got = []
    for days, bonus in MILESTONES:
        key = f"milestone_{days}"
        if s >= days and not db.get_kid_setting(c, kid, key, ""):
            lid = insert_ledger(c, db.today(), bonus, "milestone", key, f"连续坚持 {days} 天", kid=kid)
            if lid is None:
                continue
            db.set_kid_setting(c, kid, key, db.today())
            got.append((days, bonus))
    return got


# 成就徽章（孩子端「成就墙」）：稀有度/系列/段位是设计字段，不入库。
ACHIEVEMENTS = [
    {"id": "first", "icon": "sprout", "name": "初来乍到", "desc": "完成第 1 张任务卡", "target": 1,
     "rarity": "bronze", "series": "milestone", "tier": None},
    {"id": "cn10", "icon": "book", "name": "语文十卡", "desc": "完成 10 张语文卡", "target": 10,
     "rarity": "bronze", "series": "study", "tier": "subject"},
    {"id": "ma10", "icon": "calc", "name": "数学十卡", "desc": "完成 10 张数学卡", "target": 10,
     "rarity": "bronze", "series": "study", "tier": "subject"},
    {"id": "en10", "icon": "globe", "name": "英语十卡", "desc": "完成 10 张英语卡", "target": 10,
     "rarity": "bronze", "series": "study", "tier": "subject"},
    {"id": "all100", "icon": "medal", "name": "百卡达成", "desc": "累计完成 100 张单元卡", "target": 100,
     "rarity": "silver", "series": "milestone", "tier": None},
    {"id": "sport", "icon": "sport", "name": "运动健将", "desc": "每日运动打卡 10 次", "target": 10,
     "rarity": "bronze", "series": "habit", "tier": None},
    {"id": "daily30", "icon": "calendar", "name": "每日全勤", "desc": "每日任务累计打卡 30 次", "target": 30,
     "rarity": "silver", "series": "habit", "tier": None},
    {"id": "go10", "icon": "go", "name": "围棋小棋手", "desc": "围棋对弈打卡 10 次", "target": 10,
     "rarity": "bronze", "series": "habit", "tier": None},
    {"id": "calc10", "icon": "mental", "name": "口算达人", "desc": "每日口算打卡 10 次", "target": 10,
     "rarity": "bronze", "series": "habit", "tier": None},
    {"id": "streak7", "icon": "flame", "name": "坚持一周", "desc": "连续坚持 7 天", "target": 7,
     "rarity": "bronze", "series": "habit", "tier": "streak"},
    {"id": "streak14", "icon": "rocket", "name": "坚持半月", "desc": "连续坚持 14 天", "target": 14,
     "rarity": "silver", "series": "habit", "tier": "streak"},
    {"id": "streak30", "icon": "moon", "name": "坚持满月", "desc": "连续坚持 30 天", "target": 30,
     "rarity": "gold", "series": "habit", "tier": "streak"},
    {"id": "test100", "icon": "award", "name": "满分学霸", "desc": "单元测试考 100 分", "target": 100,
     "rarity": "bronze", "series": "milestone", "tier": None},
    {"id": "shop1", "icon": "cart", "name": "初尝战果", "desc": "第一次兑换奖励", "target": 1,
     "rarity": "bronze", "series": "milestone", "tier": None},
    {"id": "shop5", "icon": "gift", "name": "兑换小能手", "desc": "累计兑换 5 次", "target": 5,
     "rarity": "bronze", "series": "milestone", "tier": None},
    {"id": "box5", "icon": "dices", "name": "盲盒收藏家", "desc": "开 5 个连击盲盒", "target": 5,
     "rarity": "bronze", "series": "milestone", "tier": None},
    {"id": "custom10", "icon": "sparkles", "name": "自律之星", "desc": "完成家长任务 10 次", "target": 10,
     "rarity": "silver", "series": "milestone", "tier": None},
    {"id": "sun500", "icon": "coins", "name": "阳光新手", "desc": "累计获得 500 阳光", "target": 500,
     "rarity": "silver", "series": "wealth", "tier": "sun"},
    {"id": "sun2000", "icon": "gem", "name": "阳光大师", "desc": "累计获得 2000 阳光", "target": 2000,
     "rarity": "gold", "series": "wealth", "tier": "sun"},
    {"id": "sun5000", "icon": "crown", "name": "阳光传说", "desc": "累计获得 5000 阳光", "target": 5000,
     "rarity": "legend", "series": "wealth", "tier": "sun"},
    {"id": "early_bird", "icon": "sunrise", "name": "早鸟", "desc": "连续 7 天早 8 点前完成每日任务", "target": 7,
     "rarity": "silver", "series": "habit", "tier": None},
    {"id": "review_pro", "icon": "book", "name": "复习达人", "desc": "本周复习判定过关至少 5 次", "target": 5,
     "rarity": "bronze", "series": "study", "tier": None},
    {"id": "word_debut", "icon": "globe", "name": "单词首秀", "desc": "第一次完成每日背默", "target": 1,
     "rarity": "bronze", "series": "study", "tier": None},
    {"id": "perfect_week", "icon": "calendar", "name": "满分一周", "desc": "连续 7 天每日任务全打卡", "target": 7,
     "rarity": "gold", "series": "habit", "tier": None},
    {"id": "streak60", "icon": "trophy", "name": "坚持两月", "desc": "连续坚持 60 天", "target": 60,
     "rarity": "legend", "series": "habit", "tier": "streak"},
]


def _created_hour(ts):
    if not ts:
        return None
    s = str(ts).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "").replace(" ", "T", 1)).hour
    except ValueError:
        pass
    for sep in ("T", " "):
        if sep in s:
            part = s.split(sep, 1)[1]
            try:
                return int(part[0:2])
            except ValueError:
                return None
    return None


def _consecutive_days(dates, today=None):
    """从今天（若今天不在集合里则从昨天）往回数连续天数。"""
    bag = {str(x) for x in dates}
    d = today or datetime.now().date()
    if d.isoformat() not in bag:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in bag:
        n += 1
        d -= timedelta(days=1)
    return n


def _week_monday():
    d = datetime.now().date()
    return (d - timedelta(days=d.weekday())).isoformat()


def _ach_currents(c, kid):
    total = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kid_id=?", (kid,)).fetchone()[0]
    unit_done = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='unit' AND kid_id=?", (kid,)).fetchone()[0]
    sport = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily' AND kid_id=?", (kid,)).fetchone()[0]
    go_n = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily' AND task_id='go-play' AND kid_id=?", (kid,)).fetchone()[0]
    calc_n = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily' AND task_id='ma-calc' AND kid_id=?", (kid,)).fetchone()[0]
    custom_n = c.execute(
        "SELECT COUNT(*) FROM completions c JOIN tasks t ON t.id=c.task_id "
        "WHERE c.status='completed' AND COALESCE(t.custom,0)=1 AND c.kid_id=?", (kid,)).fetchone()[0]
    shop_n = c.execute("SELECT COUNT(*) FROM redemptions WHERE status IN ('done','delivered') AND kid_id=?", (kid,)).fetchone()[0]
    best_test = c.execute("SELECT COALESCE(MAX(score),0) FROM tests WHERE kid_id=?", (kid,)).fetchone()[0]
    box_n = int(db.get_kid_setting(c, kid, "box_opened", "0"))
    s = streak(c, kid)
    e = earned(c, kid)
    done_by_subj = {r[0]: r[1] for r in c.execute(
        "SELECT t.subject_id, COUNT(*) FROM completions c JOIN tasks t ON t.id=c.task_id "
        "WHERE c.status='completed' AND c.kid_id=? GROUP BY t.subject_id", (kid,)).fetchall()}
    daily_rows = c.execute(
        "SELECT date, task_id, created_at FROM completions WHERE status='completed' AND kind='daily' AND kid_id=?",
        (kid,)).fetchall()
    early_dates = {r["date"] for r in daily_rows if (_created_hour(r["created_at"]) or 99) < 8}
    daily_ids = [r[0] for r in c.execute("SELECT id FROM daily_tasks").fetchall()]
    n_daily = len(daily_ids)
    by_date = {}
    for r in daily_rows:
        by_date.setdefault(r["date"], set()).add(r["task_id"])
    perfect_dates = {d for d, ids in by_date.items() if n_daily and len(ids) >= n_daily}
    monday = _week_monday()
    # 没有 pass 事件表：本周被更新且至少升过一档 / 已巩固，作为过关次数的近似。
    review_n = c.execute(
        "SELECT COUNT(*) FROM weak_points WHERE kid_id=? AND updated_at>=? "
        "AND (status='resolved' OR COALESCE(interval_idx,0)>=1)",
        (kid, monday)).fetchone()[0]
    word_n = 0
    if db._has_table(c, "word_sessions"):
        word_n = c.execute(
            "SELECT COUNT(*) FROM word_sessions WHERE kid_id=? AND state='completed'", (kid,)
        ).fetchone()[0]
    return {
        "first": total, "all100": unit_done,
        "sport": sport, "daily30": sport, "go10": go_n, "calc10": calc_n,
        "streak7": s, "streak14": s, "streak30": s, "streak60": s,
        "cn10": done_by_subj.get("语文", 0), "ma10": done_by_subj.get("数学", 0), "en10": done_by_subj.get("英语", 0),
        "test100": best_test, "shop1": shop_n, "shop5": shop_n, "box5": box_n,
        "custom10": custom_n, "sun500": e, "sun2000": e, "sun5000": e,
        "early_bird": _consecutive_days(early_dates),
        "review_pro": review_n,
        "word_debut": word_n,
        "perfect_week": _consecutive_days(perfect_dates),
    }


def _load_earned_map(c, kid):
    rows = c.execute(
        "SELECT ach_id, earned_at, seen FROM achievement_earned WHERE kid_id=?", (kid,)).fetchall()
    return {r["ach_id"]: {"earned_at": r["earned_at"], "seen": int(r["seen"] or 0)} for r in rows}


def _sync_achievement_earned(c, kid, fam, unlocked_ids, earned_map):
    now = db.now()
    added = False
    for ach_id in unlocked_ids:
        if ach_id in earned_map:
            continue
        c.execute(
            "INSERT INTO achievement_earned(kid_id, ach_id, family_id, earned_at, seen) "
            "VALUES(?,?,?,?,0) ON CONFLICT DO NOTHING",
            (kid, ach_id, fam or "", now))
        earned_map[ach_id] = {"earned_at": now, "seen": 0}
        added = True
    if added:
        c.commit()
    return earned_map


@app.get("/api/achievements")
def achievements():
    c = get_conn()
    kid = kid_id()
    fam = _fam.get()
    cur = _ach_currents(c, kid)
    earned_map = _load_earned_map(c, kid)
    unlocked_ids = [a["id"] for a in ACHIEVEMENTS if cur.get(a["id"], 0) >= a["target"]]
    earned_map = _sync_achievement_earned(c, kid, fam, unlocked_ids, earned_map)
    tier_total, tier_got = {}, {}
    for a in ACHIEVEMENTS:
        t = a.get("tier")
        if not t:
            continue
        tier_total[t] = tier_total.get(t, 0) + 1
        if a["id"] in earned_map:
            tier_got[t] = tier_got.get(t, 0) + 1
    out = []
    for a in ACHIEVEMENTS:
        v = cur.get(a["id"], 0)
        unlocked = v >= a["target"]
        rec = earned_map.get(a["id"])
        if rec:
            earned_at, seen = rec["earned_at"], rec["seen"]
        else:
            earned_at, seen = None, (0 if unlocked else 1)
        t = a.get("tier")
        chain = f"{tier_got.get(t, 0)}/{tier_total.get(t, 0)}" if t else None
        out.append({
            **a,
            "current": v,
            "earned": unlocked,  # 兼容旧前端
            "unlocked": unlocked,
            "earned_at": earned_at,
            "seen": seen,
            "chain_progress": chain,
        })
    c.close()
    return out


@app.post("/api/achievements/{ach_id}/mark-seen")
def mark_achievement_seen(ach_id: str):
    c = get_conn()
    c.execute("UPDATE achievement_earned SET seen=1 WHERE kid_id=? AND ach_id=?", (kid_id(), ach_id))
    c.commit()
    c.close()
    return {"ok": True}


# 连击宝箱：连续打卡每 3 天解锁一个。图鉴开：+1~3 阳光 + 精灵；关：保持 +3~10。
BOX_INTERVAL = 3


def _is_unique_conflict(exc) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    name = type(exc).__name__.lower()
    return "integrity" in name or "unique" in name


@app.get("/api/boxes")
def boxes():
    c = get_conn()
    s = streak(c)
    opened = int(db.get_kid_setting(c, kid_id(), "box_opened", "0"))
    earned = s // BOX_INTERVAL
    c.close()
    return {"avail": max(0, earned - opened), "opened": opened, "earned": earned, "streak": s}


@app.post("/api/open_box")
def open_box():
    c = get_conn()
    try:
        _begin_write(c)
        kid = kid_id()
        fam = _fam.get() or ""
        s = streak(c, kid)
        opened = int(db.get_kid_setting(c, kid, "box_opened", "0") or 0)
        nxt = opened + 1
        if s // BOX_INTERVAL < nxt:
            raise HTTPException(409, "还没有可开的宝箱，再坚持坚持吧！")
        db.set_kid_setting(c, kid, "box_opened", str(nxt))
        extra = {}
        if spritemod.enabled(c, kid):
            bonus = random.randint(1, 3)
            extra = spritemod.grant_from_box(c, kid, fam, f"box-{nxt}")
        else:
            bonus = random.randint(3, 10)
        lid = insert_ledger(c, db.today(), bonus, "box", f"box-{nxt}", "连击宝箱", kid=kid)
        if lid is None:
            raise HTTPException(409, "这箱已经开过啦")
        c.commit()
        out = {"delta": bonus, "streak": streak(c, kid), "level": level_info(c)}
        out.update(extra)
        return out
    except HTTPException:
        _rollback(c)
        raise
    except Exception as e:
        _rollback(c)
        if _is_unique_conflict(e):
            raise HTTPException(409, "这箱已经开过啦")
        raise
    finally:
        c.close()


@app.get("/api/ranks")
def ranks_public():
    """成长路径地图用：返回全部等级 + 当前累计阳光。"""
    c = get_conn()
    ranks = [dict(r) for r in c.execute("SELECT * FROM ranks WHERE family_id=? ORDER BY min_sunshine", (_fam.get(),)).fetchall()]
    e = earned(c)
    current = ranks[0]["id"]
    for r in ranks:
        if r["min_sunshine"] <= e:
            current = r["id"]
    c.close()
    return {"ranks": ranks, "earned": e, "current": current}


# ---------------- 状态 ----------------

@app.get("/api/health")
def health():
    return {"ok": True, "version": app_version(), "revision": app_revision(), "label": app_label()}


@app.get("/api/overview")
def overview():
    return level_info(get_conn())


HIDDEN_SUBJECTS_KEY = "hidden_subjects"
DEFAULT_HIDDEN_SUBJECTS = ["道法"]


def _parse_hidden_subjects(raw):
    if raw is None:
        return [s for s in DEFAULT_HIDDEN_SUBJECTS if s in db.ALL_SUBJECTS]
    text = str(raw).strip()
    if not text:
        return []
    try:
        val = json.loads(text)
        names = val if isinstance(val, list) else []
    except Exception:
        names = [x.strip() for x in text.split(",") if x.strip()]
    out = []
    for n in names:
        s = str(n)
        if s in db.ALL_SUBJECTS and s not in out:
            out.append(s)
    return out


def hidden_subjects_for(c, kid):
    return _parse_hidden_subjects(db.get_kid_setting(c, kid, HIDDEN_SUBJECTS_KEY, None))


@app.get("/api/tasks")
def tasks():
    c = get_conn()
    term = active_term(c)
    term_row = c.execute("SELECT * FROM terms WHERE id=?", (term,)).fetchone()
    out = {
        "level": level_info(c),
        "streak": streak(c),
        "kid_name": (c.execute("SELECT name FROM users WHERE id=?", (kid_id(),)).fetchone() or {"name": "乐乐"})["name"],
        "kid_id": kid_id(),
        "today": today_label(),
        "active_term": term,
        "term": dict(term_row) if term_row else {"id": term, "label": term},
        "terms": [dict(r) for r in c.execute("SELECT * FROM terms ORDER BY id").fetchall()],
        "cursors": {r["key"][7:]: r["value"] for r in c.execute(
            "SELECT key,value FROM kid_settings WHERE kid_id=? AND key LIKE ?", (kid_id(), "cursor_%")).fetchall()},
        "today_checkin": c.execute(
            "SELECT 1 FROM checkins WHERE date=? AND kid_id=?", (db.today(), kid_id())).fetchone() is not None,
        "subjects": [dict(r) for r in c.execute("SELECT * FROM subjects").fetchall()],
        "units": [{"id": r["id"], "name": r["name"], "subject_id": r["subject_id"], "term_id": r["term_id"]}
                  for r in c.execute(
                      "SELECT id, name, subject_id, term_id FROM units WHERE term_id=? OR id LIKE ?",
                      (term, "custom-%")).fetchall()],
    }
    # 单元测试成绩（unit_id → 最近一次分），孩子端单元旁展示
    unit_scores = {}
    for r in c.execute("SELECT unit_id, score, date FROM tests WHERE kid_id=? AND unit_id IS NOT NULL "
                       "ORDER BY date DESC, id DESC", (kid_id(),)).fetchall():
        if r["unit_id"] not in unit_scores:
            unit_scores[r["unit_id"]] = {"score": r["score"], "date": r["date"]}
    out["unit_scores"] = unit_scores
    # 单元任务 + 完成状态（只看当前学期 + 自定义）
    tasks_rows = c.execute(
        "SELECT t.* FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "WHERE " + TASK_SCOPE + " "
        "ORDER BY t.subject_id, COALESCE(u.seq,99), t.sort", (term, kid_id())).fetchall()
    done_ids = {r["task_id"] for r in c.execute(
        "SELECT DISTINCT task_id FROM completions WHERE status='completed' AND kid_id=? AND NOT EXISTS ("
        "SELECT 1 FROM ledger WHERE reason='cancel' AND ref_id='cmp-'||completions.id)", (kid_id(),)).fetchall()}
    out["progress_lock"] = db.get_setting(c, "progress_lock", "1")
    out["hidden_subjects"] = hidden_subjects_for(c, kid_id())
    locked_ids = locked_task_ids(c)
    out["tasks"] = [{**dict(t), "done": t["id"] in done_ids,
                     "past": is_past(c, t["id"], t["subject_id"]),
                     "locked": t["id"] in locked_ids} for t in tasks_rows]
    # 每日任务 + 今日状态 + 历史最好
    dts = c.execute(
        "SELECT * FROM daily_tasks WHERE family_id IS NULL OR family_id=?", (_fam.get(),)).fetchall()
    daily = []
    for d in dts:
        dct = dict(d)
        comp_today = c.execute(
            "SELECT * FROM completions WHERE task_id=? AND date=? AND status='completed' AND kid_id=? ORDER BY id DESC LIMIT 1",
            (d["id"], db.today(), kid_id())).fetchone()
        dct["done_today"] = comp_today is not None
        dct["today_metrics"] = json.loads(comp_today["metrics"]) if comp_today and comp_today["metrics"] else None
        dct["metrics"] = [dict(m) for m in c.execute(
            "SELECT * FROM daily_metrics WHERE task_id=?", (d["id"],)).fetchall()]
        # 历史最好（个人纪录）
        pb = {}
        for m in c.execute("SELECT * FROM daily_metrics WHERE task_id=?", (d["id"],)).fetchall():
            best = None
            for comp in c.execute(
                "SELECT metrics FROM completions WHERE task_id=? AND status='completed' AND metrics IS NOT NULL AND kid_id=?",
                (d["id"], kid_id())).fetchall():
                v = (json.loads(comp["metrics"]) or {}).get(m["id"])
                if v is None:
                    continue
                if best is None or (m["direction"] == "higher_better" and v > best) or \
                   (m["direction"] == "lower_better" and v < best):
                    best = v
            pb[m["id"]] = best
        dct["pb"] = pb
        dct["bonus_per_metric"] = d["bonus_per_metric"]
        daily.append(dct)
    out["daily"] = daily
    rules = insight_rules(c)
    out["test_fail_score"] = int(rules["test_fail_score"])
    u = c.execute("SELECT gender, term_id FROM users WHERE id=?", (kid_id(),)).fetchone()
    grade = _kid_grade(u["term_id"] if u else None)
    gender = (u["gender"] if u else None) or None
    goals = {}
    if grade and gender:
        for item, (tid, mid) in FITNESS_METRIC.items():
            std = c.execute(
                "SELECT pass_value, good_value, excellent_value, unit FROM fitness_standards WHERE grade=? AND gender=? AND item=?",
                (grade, gender, item)).fetchone()
            if std and std["pass_value"] is not None:
                goals[tid] = {
                    "item": item, "metric_id": mid, "unit": std["unit"] or "",
                    "pass": float(std["pass_value"]),
                    "good": float(std["good_value"]) if std["good_value"] is not None else None,
                    "excellent": float(std["excellent_value"]) if std["excellent_value"] is not None else None,
                    "grade": grade, "gender": gender,
                }
    out["fitness_goals"] = goals
    weak = {}
    for r in _wp_rows(c, kid_id()):
        weak.setdefault(r["unit_id"], []).append(r["tag_name"] or r["tag_id"])
    out["weak_tags"] = weak
    out["companion"] = companion_info(c)
    c.commit()
    return out


# ---------------- 签到 ----------------

@app.post("/api/checkin")
def checkin():
    c = get_conn()
    t = db.today()
    if db.insert(c, "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
                 (t, 0, db.now(), kid_id())) is None:
        c.close()
        raise HTTPException(409, "今天已经签到过啦")
    m = maybe_milestone(c)
    c.commit()
    res = {"delta": 0, "milestone": m, "level": level_info(c), "streak": streak(c)}
    c.close()
    return res


# ---------------- 任务完成 / 取消 ----------------

class CompleteBody(BaseModel):
    task_id: str
    metrics: Optional[dict] = None


def _metric_num(metrics, key):
    if not metrics:
        return 0
    try:
        v = metrics.get(key)
        if v is None or v == "":
            return 0
        return float(v)
    except (TypeError, ValueError):
        return 0


def daily_award(c, d, metrics):
    """每日打卡阳光。围棋对弈：至少赢 1 局才发任务阳光，只输不给。"""
    bonus, detail = compute_daily_bonus(c, d, metrics)
    base = int(d["sunshine"] or 0)
    if d["id"] == "go-play" and _metric_num(metrics, "win") < 1:
        return 0, 0, []
    return base + bonus, bonus, detail


def compute_daily_bonus(c, d, metrics):
    per = d["bonus_per_metric"] or 0
    if not metrics or not per:
        return 0, []
    bonus, detail = 0, []
    for m in c.execute("SELECT * FROM daily_metrics WHERE task_id=?", (d["id"],)).fetchall():
        val = metrics.get(m["id"])
        if val is None:
            continue
        best = None
        for comp in c.execute(
            "SELECT metrics FROM completions WHERE task_id=? AND status='completed' AND metrics IS NOT NULL AND kid_id=?",
            (d["id"], kid_id())).fetchall():
            v = (json.loads(comp["metrics"]) or {}).get(m["id"])
            if v is None:
                continue
            if best is None or (m["direction"] == "higher_better" and v > best) or \
               (m["direction"] == "lower_better" and v < best):
                best = v
        improved = (m["direction"] == "higher_better" and best is not None and val > best) or \
                   (m["direction"] == "lower_better" and best is not None and val < best)
        if improved:
            bonus += per
            detail.append(m["label"])
    return bonus, detail


@app.post("/api/complete")
def complete(body: CompleteBody):
    c = get_conn()
    try:
        t = db.today()
        tid = body.task_id
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if row:
            if is_past(c, tid, row["subject_id"]):
                raise HTTPException(409, "这课已经学过了，不加阳光")
            if tid in locked_task_ids(c):
                raise HTTPException(409, "这课还没学到，先把前面的学完哦")
            delta = row["sunshine"]
            # 使用 ON CONFLICT 防止并发重复完成，检查返回值确保插入成功
            cid = db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                            (tid, t, "completed", delta, None, "unit", db.now(), kid_id()))
            if cid is None:
                raise HTTPException(409, "这项已经完成过啦")
            insert_ledger(c, t, delta, "task", f"cmp-{cid}", row["title"])
            m = maybe_milestone(c)
            c.commit()
            res = {"delta": delta, "bonus": 0, "milestone": m, "level": level_info(c)}
            return res
        d = c.execute("SELECT * FROM daily_tasks WHERE id=? AND (family_id IS NULL OR family_id=?)",
                      (tid, _fam.get())).fetchone()
        if d:
            delta, bonus, detail = daily_award(c, d, body.metrics)
            mj = json.dumps(body.metrics) if body.metrics else None
            cid = db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                            (tid, t, "completed", delta, mj, "daily", db.now(), kid_id()))
            if cid is None:
                raise HTTPException(409, "今天这项已完成过啦")
            note = d["name"]
            if bonus:
                note += "（破纪录 +%d）" % bonus
            elif d["id"] == "go-play" and delta == 0:
                note += "（今天没赢，阳光下次再给）"
            insert_ledger(c, t, delta, "daily", f"cmp-{cid}", note)
            m = maybe_milestone(c)
            c.commit()
            res = {"delta": delta, "bonus": bonus, "bonus_detail": detail, "milestone": m, "level": level_info(c)}
            return res
        raise HTTPException(404, "没找到这个任务")
    finally:
        c.close()


class KidNameBody(BaseModel):
    name: str


@app.post("/api/kid-name", dependencies=[Depends(require_parent)])
def set_kid_name(body: KidNameBody):
    name = (body.name or "").strip()[:12]
    if not name:
        raise HTTPException(400, "名字不能为空")
    c = get_conn()
    c.execute("UPDATE users SET name=? WHERE id=?", (name, kid_id()))
    c.commit()
    c.close()
    return {"name": name}


class CompanionNameIn(BaseModel):
    name: str = ""


@app.post("/api/companion/name")
def companion_set_name(b: CompanionNameIn):
    name = (b.name or "").strip()
    if not name or len(name) > 8:
        raise HTTPException(400, "给它起个 1 到 8 个字的名字")
    c = get_conn()
    db.set_kid_setting(c, kid_id(), CFG_COMPANION_NAME, name)
    c.commit()
    out = companion_info(c)
    c.commit()
    c.close()
    return out


@app.post("/api/companion/ack-evolve")
def companion_ack_evolve():
    c = get_conn()
    kid = kid_id()
    info = companion_info(c, kid)
    seen = (db.get_kid_setting(c, kid, CFG_COMPANION_SEEN, "") or "").strip()
    seen_idx = next((i for i, st in enumerate(COMPANION_STAGES) if st[0] == seen), -1)
    cur_idx = next(i for i, st in enumerate(COMPANION_STAGES) if st[0] == info["stage"])
    if cur_idx > seen_idx:
        db.set_kid_setting(c, kid, CFG_COMPANION_SEEN, info["stage"])
    c.commit()
    out = companion_info(c, kid)
    c.close()
    return out


class SpriteProfileIn(BaseModel):
    nickname: str = ""
    flavor: str = ""


class SpriteConfigIn(BaseModel):
    enabled: Optional[bool] = None
    base_enabled: Optional[bool] = None


def _sprite_write(fn, *args):
    c = get_conn()
    try:
        out = fn(c, *args)
        c.commit()
        return out
    except spritemod.SpriteError as e:
        _rollback(c)
        raise HTTPException(e.status, e.detail)
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.get("/api/sprites")
def sprites_get():
    c = get_conn()
    kid = kid_id()
    fam = _fam.get() or ""
    yday = (datetime.now().date() - timedelta(days=1)).isoformat()
    out = spritemod.catalog(
        c, kid, fam,
        review_clear=not _due_queue(c, kid),
        review_clear_yesterday=not _due_queue(c, kid, yday),
        streak=streak(c, kid),
    )
    c.close()
    return out


@app.post("/api/sprites/{def_id}/profile")
def sprites_profile(def_id: str, b: SpriteProfileIn):
    return _sprite_write(spritemod.set_profile, kid_id(), def_id, b.nickname, b.flavor)


@app.post("/api/sprites/{def_id}/star")
def sprites_star(def_id: str):
    return _sprite_write(spritemod.add_star, kid_id(), def_id)


@app.post("/api/sprites/base/{item_id}/buy")
def sprites_buy(item_id: str):
    return _sprite_write(spritemod.buy_base_item, kid_id(), item_id)


@app.post("/api/sprites/{def_id}/duty")
def sprites_duty(def_id: str):
    return _sprite_write(spritemod.set_on_duty, kid_id(), def_id)


@app.post("/api/sprites/duty-clear")
def sprites_duty_clear():
    return _sprite_write(spritemod.set_on_duty, kid_id(), "")


@app.post("/api/sprites/morning-ack")
def sprites_morning_ack():
    return _sprite_write(spritemod.ack_morning, kid_id())


@app.get("/api/admin/sprites-config", dependencies=[Depends(require_parent)])
def admin_sprites_config():
    c = get_conn()
    kid = _need_kid()
    out = spritemod.config_of(c, kid)
    c.close()
    return out


@app.put("/api/admin/sprites-config", dependencies=[Depends(require_parent)])
def admin_sprites_config_put(b: SpriteConfigIn):
    c = get_conn()
    kid = _need_kid()
    try:
        out = spritemod.set_config(c, kid, b.enabled, b.base_enabled)
        c.commit()
        return out
    except spritemod.SpriteError as e:
        _rollback(c)
        raise HTTPException(e.status, e.detail)
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


class CustomTaskBody(BaseModel):
    subject_id: str
    title: str
    sunshine: int = 5
    kid_id: Optional[str] = None  # None=全家


@app.post("/api/custom-task", dependencies=[Depends(require_parent)])
def custom_task(body: CustomTaskBody, request: Request):
    title = (body.title or "").strip()[:40]
    if not title:
        raise HTTPException(400, "填一下任务名称")
    c = get_conn()
    try:
        if not c.execute("SELECT 1 FROM subjects WHERE id=?", (body.subject_id,)).fetchone():
            raise HTTPException(404, "没有这个学科")
        owner = body.kid_id or None
        if owner:
            u = request.state.user
            row = c.execute("SELECT family_id FROM users WHERE id=? AND role='kid'", (owner,)).fetchone()
            if not row or row["family_id"] != u["family_id"]:
                raise HTTPException(404, "没找到这个孩子")
        unit_id = f"custom-{body.subject_id}"
        c.execute("INSERT INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                  (unit_id, body.subject_id, active_term(c), 99, "自定义"))
        tid = uuid.uuid4().hex[:8]
        c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom,family_id,kid_id) VALUES(?,?,?,?,?,?,99,1,?,?)",
                  (tid, body.subject_id, unit_id, "自定义", title, _sun(body.sunshine if body.sunshine is not None else 5), request.state.user["family_id"], owner))
        c.commit()
        return {"id": tid}
    finally:
        c.close()


@app.delete("/api/tasks/{tid}", dependencies=[Depends(require_parent)])
def delete_task_kid(tid: str):
    c = get_conn()
    try:
        row = c.execute("SELECT custom FROM tasks WHERE id=?", (tid,)).fetchone()
        if not row:
            raise HTTPException(404, "没找到这个任务")
        if not row["custom"]:
            raise HTTPException(403, "系统任务请在家长端删除")
        c.execute("DELETE FROM tasks WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?", (tid, _fam.get()))
        c.commit()
        return {"ok": True}
    finally:
        c.close()


@app.post("/api/cancel")
def cancel(body: CompleteBody):
    c = get_conn()
    try:
        _begin_write(c)
        t = db.today()
        kid = kid_id()
        kind = c.execute("SELECT kind FROM completions WHERE task_id=? AND kid_id=? AND status='completed' ORDER BY id DESC LIMIT 1",
                         (body.task_id, kid)).fetchone()
        if not kind:
            raise HTTPException(404, "没有可取消的记录")
        if kind["kind"] == "daily":
            comp = c.execute(
                "SELECT * FROM completions WHERE task_id=? AND status='completed' AND kid_id=? AND date=? ORDER BY id DESC LIMIT 1",
                (body.task_id, kid, t)).fetchone()
        else:
            comp = c.execute(
                "SELECT * FROM completions WHERE task_id=? AND status='completed' AND kid_id=? ORDER BY id DESC LIMIT 1",
                (body.task_id, kid)).fetchone()
        if not comp:
            raise HTTPException(404, "没有可取消的记录")
        ref = f"cmp-{comp['id']}"
        cur = c.execute("UPDATE completions SET status='cancelled' WHERE id=? AND status='completed'", (comp["id"],))
        if getattr(cur, "rowcount", 0) == 0:
            raise HTTPException(409, "这项已经取消过啦")
        delta = -comp["sunshine"]
        lid = insert_ledger(c, t, delta, "cancel", ref, "点错取消", kid=kid)
        if lid is None:
            raise HTTPException(409, "这项已经取消过啦")
        c.commit()
        return {"delta": delta, "level": level_info(c)}
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


# ---------------- 商店 ----------------

@app.get("/api/rewards")
def rewards():
    c = get_conn()
    return [dict(r) for r in c.execute("SELECT * FROM rewards WHERE family_id=? ORDER BY price", (_fam.get(),)).fetchall()]


class RedeemBody(BaseModel):
    reward_id: str


@app.post("/api/rewards/redeem")
def redeem(body: RedeemBody):
    c = get_conn()
    r = c.execute("SELECT * FROM rewards WHERE id=? AND family_id=?", (body.reward_id, _fam.get())).fetchone()
    if not r:
        c.close()
        raise HTTPException(404, "没找到这个奖励")
    # 一律先申请，家里任意家长批；阳光等同意再扣
    c.execute("INSERT INTO redemptions(reward_id,date,price,status,created_at,kid_id) VALUES(?,?,?,?,?,?)",
              (r["id"], db.today(), r["price"], "pending", db.now(), kid_id()))
    c.commit()
    res = {"pending": True, "reward": r["name"], "level": level_info(c)}
    c.close()
    return res


@app.get("/api/redemptions")
def redemptions():
    c = get_conn()
    rows = c.execute(
        "SELECT rd.id, rd.date, rd.price, rd.status, rw.name FROM redemptions rd "
        "LEFT JOIN rewards rw ON rw.id=rd.reward_id WHERE rd.kid_id=? ORDER BY rd.id DESC LIMIT 30",
        (kid_id(),)).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ---------------- 阳光银行利息 ----------------

from datetime import datetime, timedelta
import calendar


def _bank_interest_config(c, kid):
    """获取银行利息配置"""
    return {
        "enabled": db.get_kid_setting(c, kid, "bank_interest_enabled", "0") == "1",
        "cycle": db.get_kid_setting(c, kid, "bank_interest_cycle", "weekly"),
        "rate": float(db.get_kid_setting(c, kid, "bank_interest_rate", "5.0")),
        "threshold": int(db.get_kid_setting(c, kid, "bank_interest_threshold", "20")),
        "last_settle": db.get_kid_setting(c, kid, "bank_last_settle_date", ""),
    }


def _should_settle_interest(cfg, today):
    """判断今天是否应该结算利息"""
    if not cfg["enabled"]:
        return False
    last = cfg["last_settle"]
    if last:
        last_date = datetime.strptime(last, "%Y-%m-%d").date()
        if last_date >= today:
            return False
    cycle = cfg["cycle"]
    if cycle == "weekly":
        return today.weekday() == 5  # 周六
    elif cycle == "biweekly":
        if today.weekday() != 5:
            return False
        if not last:
            return True
        return (today - last_date).days >= 14
    elif cycle == "monthly":
        last_day = calendar.monthrange(today.year, today.month)[1]
        return today.day == last_day
    return False


def _calc_avg_bank_balance(c, kid, start_date, end_date):
    """计算时间段内银行账户的日均余额"""
    days = (end_date - start_date).days + 1
    total = 0
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        bal = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND account='bank' AND date<=?",
            (kid, date_str)
        ).fetchone()[0]
        total += bal
        current += timedelta(days=1)
    return total / days if days > 0 else 0


def settle_bank_interest(c, kid, today):
    """结算银行利息"""
    cfg = _bank_interest_config(c, kid)
    if not _should_settle_interest(cfg, today):
        return None
    
    cycle = cfg["cycle"]
    if cycle == "weekly":
        days = 7
    elif cycle == "biweekly":
        days = 14
    else:  # monthly
        days = today.day
    
    start_date = today - timedelta(days=days - 1)
    avg_balance = _calc_avg_bank_balance(c, kid, start_date, today)
    
    if avg_balance < cfg["threshold"]:
        db.set_kid_setting(c, kid, "bank_last_settle_date", today.strftime("%Y-%m-%d"))
        return {"settled": False, "reason": "below_threshold", "avg_balance": int(avg_balance)}
    
    interest = int(avg_balance * cfg["rate"] / 100)
    if interest <= 0:
        db.set_kid_setting(c, kid, "bank_last_settle_date", today.strftime("%Y-%m-%d"))
        return {"settled": False, "reason": "zero_interest", "avg_balance": int(avg_balance)}
    
    cycle_label = {"weekly": "本周", "biweekly": "两周", "monthly": "本月"}[cycle]
    ref_id = f"interest-{kid}-{today.strftime('%Y-%m-%d')}"
    lid = db.insert_ledger(c, today.strftime("%Y-%m-%d"), interest, "bank_interest", ref_id,
                          f"{cycle_label}利息", kid, "bank")
    if lid:
        db.set_kid_setting(c, kid, "bank_last_settle_date", today.strftime("%Y-%m-%d"))
        return {"settled": True, "interest": interest, "avg_balance": int(avg_balance), "ledger_id": lid}
    return None


def check_and_settle_all_interests(c):
    """检查所有孩子的利息结算，返回结算记录"""
    today = datetime.strptime(db.today(), "%Y-%m-%d").date()
    kids = c.execute("SELECT id FROM users WHERE role='kid'").fetchall()
    results = []
    for kr in kids:
        result = settle_bank_interest(c, kr["id"], today)
        if result:
            results.append({"kid_id": kr["id"], **result})
    return results


class BankInterestConfigIn(BaseModel):
    enabled: bool
    cycle: str = "weekly"
    rate: float = 5.0
    threshold: int = 20


@app.get("/api/admin/bank/interest", dependencies=[Depends(require_parent)])
def admin_bank_interest_config():
    c = get_conn()
    cfg = _bank_interest_config(c, kid_id())
    c.close()
    return cfg


@app.put("/api/admin/bank/interest", dependencies=[Depends(require_parent)])
def admin_bank_interest_update(b: BankInterestConfigIn):
    if b.cycle not in ("weekly", "biweekly", "monthly"):
        raise HTTPException(400, "周期只能是 weekly/biweekly/monthly")
    if not (0 <= b.rate <= 10):
        raise HTTPException(400, "利率要在 0% 到 10% 之间")
    if b.threshold not in (0, 10, 20, 50, 100):
        raise HTTPException(400, "起存点只能是 0/10/20/50/100")
    c = get_conn()
    kid = kid_id()
    db.set_kid_setting(c, kid, "bank_interest_enabled", "1" if b.enabled else "0")
    db.set_kid_setting(c, kid, "bank_interest_cycle", b.cycle)
    db.set_kid_setting(c, kid, "bank_interest_rate", str(b.rate))
    db.set_kid_setting(c, kid, "bank_interest_threshold", str(b.threshold))
    c.commit()
    cfg = _bank_interest_config(c, kid)
    c.close()
    return cfg


@app.post("/api/admin/bank/settle-now", dependencies=[Depends(require_parent)])
def admin_bank_settle_now():
    """手动触发当前孩子的利息结算（测试用）"""
    c = get_conn()
    try:
        today = datetime.strptime(db.today(), "%Y-%m-%d").date()
        result = settle_bank_interest(c, kid_id(), today)
        c.commit()
        return result or {"settled": False, "reason": "not_due"}
    finally:
        c.close()


# ---------------- 阳光银行 ----------------

BANK_ENABLED_KEY = "bank_enabled"


class BankAmountIn(BaseModel):
    amount: int


class BankGoalIn(BaseModel):
    name: str
    target: int


class BankEnabledIn(BaseModel):
    enabled: bool


def _bank_enabled(c, kid=None):
    return db.get_kid_setting(c, kid or kid_id(), BANK_ENABLED_KEY, "0") == "1"


def _bank_goal(c, kid):
    r = c.execute(
        "SELECT * FROM bank_goals WHERE kid_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", (kid,)
    ).fetchone()
    return dict(r) if r else None


def _bank_requests(c, kid, limit=20):
    return [dict(r) for r in c.execute(
        "SELECT * FROM bank_requests WHERE kid_id=? ORDER BY created_at DESC LIMIT ?", (kid, limit)
    ).fetchall()]


def _bank_payload(c, kid=None):
    kid = kid or kid_id()
    rows = [dict(r) for r in c.execute(
        "SELECT id,date,delta,reason,ref_id,note,created_at,account FROM ledger "
        "WHERE kid_id=? AND account='bank' ORDER BY id DESC LIMIT 30", (kid,)
    ).fetchall()]
    goal = _bank_goal(c, kid)
    if goal:
        goal["saved"] = bank_balance(c, kid)
        goal["reached"] = goal["saved"] >= goal["target"]
    interest_cfg = _bank_interest_config(c, kid)
    return {
        "enabled": _bank_enabled(c, kid),
        "balance": bank_balance(c, kid),
        "pocket_balance": balance(c, kid, "pocket"),
        "goal": goal,
        "requests": _bank_requests(c, kid),
        "ledger": rows,
        "interest": interest_cfg if interest_cfg["enabled"] else None,
    }


@app.get("/api/bank")
def bank():
    c = get_conn()
    out = _bank_payload(c)
    c.close()
    return out


def _capsule_snap(c):
    kid = kid_id()
    return capmod.snapshot_now(
        c, kid,
        term_id=active_term(c),
        level=level_info(c),
        earned=earned(c, kid),
        streak=streak(c, kid),
        companion=companion_info(c, kid),
        pocket=balance(c, kid, "pocket"),
        bank=bank_balance(c, kid),
    )


class CapsuleIn(BaseModel):
    when_kind: str
    q_good: str = ""
    q_wish: str = ""
    q_line: str = ""


@app.get("/api/capsule")
def capsule_get():
    c = get_conn()
    try:
        kid = kid_id()
        s = streak(c, kid)
        out = capmod.get_payload(c, kid, s, _capsule_snap(c))
        c.commit()
        return out
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.post("/api/capsule")
def capsule_seal(b: CapsuleIn):
    c = get_conn()
    try:
        kid = kid_id()
        s = streak(c, kid)
        snap = _capsule_snap(c)
        cap = capmod.seal(c, kid, _fam.get(), b.model_dump(), streak=s, snap=snap)
        c.commit()
        return capmod.get_payload(c, kid, s, snap)
    except capmod.CapsuleError as e:
        _rollback(c)
        raise HTTPException(e.status, e.detail)
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.post("/api/capsule/open")
def capsule_open():
    c = get_conn()
    try:
        kid = kid_id()
        s = streak(c, kid)
        snap = _capsule_snap(c)
        opened = capmod.open_capsule(c, kid, s, snap)
        c.commit()
        return opened
    except capmod.CapsuleError as e:
        _rollback(c)
        raise HTTPException(e.status, e.detail)
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()

@app.post("/api/bank/deposit")
def bank_deposit(b: BankAmountIn):
    c = get_conn()
    try:
        if not _bank_enabled(c):
            raise HTTPException(403, "阳光银行还没开启")
        amount = _sun(b.amount, lo=1)
        _begin_write(c)
        kid = kid_id()
        pocket = balance(c, kid, "pocket")
        if amount > pocket:
            raise HTTPException(409, "口袋里的阳光不够")
        ref = "bank-deposit-" + uuid.uuid4().hex
        if insert_ledger(c, db.today(), -amount, "bank_deposit", ref + "-pocket", "存入阳光银行", kid=kid, account="pocket") is None:
            raise HTTPException(409, "存入失败，请再试一次")
        insert_ledger(c, db.today(), amount, "bank_deposit", ref + "-bank", "存入阳光银行", kid=kid, account="bank")
        c.commit()
        return _bank_payload(c, kid)
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.post("/api/bank/withdraw")
def bank_withdraw(b: BankAmountIn):
    c = get_conn()
    try:
        if not _bank_enabled(c):
            raise HTTPException(403, "阳光银行还没开启")
        amount = _sun(b.amount, lo=1)
        kid = kid_id()
        available = bank_balance(c, kid) - sum(
            int(r["amount"] or 0) for r in c.execute(
                "SELECT amount FROM bank_requests WHERE kid_id=? AND kind='withdraw' AND status='pending'", (kid,)
            ).fetchall()
        )
        if amount > available:
            raise HTTPException(409, "银行里可申请取出的阳光不够")
        rid = uuid.uuid4().hex[:12]
        c.execute(
            "INSERT INTO bank_requests(id,kid_id,family_id,kind,amount,status,note,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (rid, kid, _fam.get(), "withdraw", amount, "pending", "孩子申请取出", db.now()),
        )
        c.commit()
        return {"ok": True, "request_id": rid, **_bank_payload(c, kid)}
    finally:
        c.close()


# ---------------- 流水 ----------------

@app.get("/api/ledger")
def ledger(limit: int = 20):
    c = get_conn()
    return [dict(r) for r in c.execute(
        "SELECT * FROM ledger WHERE kid_id=? ORDER BY id DESC LIMIT ?", (kid_id(), limit)).fetchall()]


# ---------------- 管理端（家长，需 PIN） -------------


class CursorBody(BaseModel):
    subject_id: str
    task_id: str


@app.post("/api/admin/cursor", dependencies=[Depends(require_parent)])
def set_cursor(b: CursorBody):
    c = get_conn()
    db.set_kid_setting(c, kid_id(), "cursor_" + b.subject_id, b.task_id)
    c.commit(); c.close()
    return {"ok": True}


class LockBody(BaseModel):
    on: bool = True


@app.get("/api/admin/bank", dependencies=[Depends(require_parent)])
def admin_bank():
    c = get_conn()
    out = _bank_payload(c)
    out["requests"] = _bank_requests(c, kid_id(), 50)
    c.close()
    return out


@app.put("/api/admin/bank/enabled", dependencies=[Depends(require_parent)])
def admin_bank_enabled(b: BankEnabledIn):
    c = get_conn()
    db.set_kid_setting(c, kid_id(), BANK_ENABLED_KEY, "1" if b.enabled else "0")
    c.commit()
    out = _bank_payload(c)
    c.close()
    return out


@app.post("/api/admin/bank/goal", dependencies=[Depends(require_parent)])
def admin_bank_goal(b: BankGoalIn):
    name = (b.name or "").strip()
    if not name or len(name) > 40:
        raise HTTPException(400, "目标名称要填 1 到 40 个字")
    target = _sun(b.target, lo=1)
    c = get_conn()
    kid = kid_id()
    existing = c.execute("SELECT id FROM bank_goals WHERE kid_id=? AND status='active'", (kid,)).fetchone()
    if existing:
        c.execute("UPDATE bank_goals SET name=?, target=?, updated_at=? WHERE id=?", (name, target, db.now(), existing["id"]))
        gid = existing["id"]
    else:
        gid = uuid.uuid4().hex[:12]
        c.execute(
            "INSERT INTO bank_goals(id,kid_id,family_id,name,target,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (gid, kid, _fam.get(), name, target, "active", db.now(), db.now()),
        )
    c.commit()
    out = _bank_payload(c, kid)
    c.close()
    return out


@app.post("/api/admin/bank/goal/deliver", dependencies=[Depends(require_parent)])
def admin_bank_goal_deliver():
    c = get_conn()
    goal = c.execute("SELECT * FROM bank_goals WHERE kid_id=? AND status='active'", (kid_id(),)).fetchone()
    if not goal:
        c.close()
        raise HTTPException(404, "还没有进行中的目标")
    if bank_balance(c, kid_id()) < goal["target"]:
        c.close()
        raise HTTPException(409, "目标还没攒够")
    c.execute("UPDATE bank_goals SET status='delivered', updated_at=?, closed_at=? WHERE id=?", (db.now(), db.now(), goal["id"]))
    c.commit()
    out = _bank_payload(c)
    c.close()
    return out


@app.get("/api/admin/bank/requests", dependencies=[Depends(require_parent)])
def admin_bank_requests():
    c = get_conn()
    fam = _fam.get()
    rows = c.execute(
        "SELECT br.*, u.name AS kid_name FROM bank_requests br JOIN users u ON u.id=br.kid_id "
        "WHERE br.family_id=? AND br.kid_id=? ORDER BY br.created_at DESC LIMIT 100", (fam, kid_id())
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def _own_bank_request(c, rid):
    r = c.execute("SELECT * FROM bank_requests WHERE id=? AND family_id=?", (rid, _fam.get())).fetchone()
    return r


@app.post("/api/admin/bank/requests/{rid}/approve", dependencies=[Depends(require_parent)])
def admin_bank_request_approve(rid: str):
    c = get_conn()
    try:
        req = _own_bank_request(c, rid)
        if not req or req["kind"] != "withdraw":
            raise HTTPException(404, "没找到这条取出申请")
        if req["status"] != "pending":
            raise HTTPException(409, "这条申请已经处理过")
        _begin_write(c)
        kid = req["kid_id"]
        amount = int(req["amount"])
        if bank_balance(c, kid) < amount:
            raise HTTPException(409, "银行余额已经不够")
        ref = "bank-withdraw-" + rid
        if insert_ledger(c, db.today(), -amount, "bank_withdraw", ref + "-bank", "从阳光银行取出", kid=kid, account="bank") is None:
            raise HTTPException(409, "这条申请已经处理过")
        insert_ledger(c, db.today(), amount, "bank_withdraw", ref + "-pocket", "从阳光银行取出", kid=kid, account="pocket")
        c.execute("UPDATE bank_requests SET status='approved', handled_at=? WHERE id=? AND status='pending'", (db.now(), rid))
        c.commit()
        return {"ok": True, **_bank_payload(c, kid)}
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.post("/api/admin/bank/requests/{rid}/reject", dependencies=[Depends(require_parent)])
def admin_bank_request_reject(rid: str):
    c = get_conn()
    req = _own_bank_request(c, rid)
    if not req or req["kind"] != "withdraw":
        c.close()
        raise HTTPException(404, "没找到这条取出申请")
    if req["status"] != "pending":
        c.close()
        raise HTTPException(409, "这条申请已经处理过")
    c.execute("UPDATE bank_requests SET status='rejected', handled_at=? WHERE id=? AND status='pending'", (db.now(), rid))
    c.commit()
    c.close()
    return {"ok": True}


@app.post("/api/admin/progress-lock", dependencies=[Depends(require_parent)])
def set_progress_lock(b: LockBody):
    c = get_conn()
    db.set_setting(c, "progress_lock", "1" if b.on else "0")
    c.commit(); c.close()
    return {"ok": True}


class SubjectVisibleBody(BaseModel):
    subject_id: str
    on: bool = True


@app.post("/api/admin/subject-visible", dependencies=[Depends(require_parent)])
def set_subject_visible(b: SubjectVisibleBody):
    sid = (b.subject_id or "").strip()
    if sid not in db.ALL_SUBJECTS:
        raise HTTPException(404, "没有这个学科")
    c = get_conn()
    hidden = set(hidden_subjects_for(c, kid_id()))
    if b.on:
        hidden.discard(sid)
    else:
        hidden.add(sid)
    ordered = [s for s in db.ALL_SUBJECTS if s in hidden]
    db.set_kid_setting(c, kid_id(), HIDDEN_SUBJECTS_KEY, json.dumps(ordered, ensure_ascii=False))
    c.commit(); c.close()
    return {"ok": True, "hidden_subjects": ordered}





class LoginBody(BaseModel):
    account: str
    pin: str


class PinBody(BaseModel):
    pin: str
    current: str = ""


@app.post("/api/auth/login")
def auth_login(b: LoginBody, request: Request):
    account = (b.account or "").strip().lower()
    ip = _client_ip(request)
    _rate_ok("ip:" + ip)
    _rate_ok("ac:" + account)
    c = db.connect(admin=True)
    try:
        u = c.execute("SELECT * FROM users WHERE account=?", (account,)).fetchone()
        ok = bool(u) and db.verify_pin(b.pin, u["pin_hash"] or "")
        force = bool(ok and u["force_pin_change"] not in (None, "", "0"))
        user = dict(u) if ok else None
    finally:
        c.close()
    if not ok:
        _rate_hit("ip:" + ip)
        _rate_hit("ac:" + account)
        raise HTTPException(401, "账号或密码不对")
    payload = {
        "user_id": user["id"], "family_id": user["family_id"], "role": user["role"],
        "term_id": user["term_id"], "iat": time.time(),
    }
    resp_data = {
        "ok": True, "role": user["role"], "name": user["name"], "account": user["account"],
        "force_pin_change": force,
    }
    # 家长账号返回角色权限
    if user["role"] == "parent":
        resp_data["parent_role"] = user.get("parent_role", "member")
    
    resp = JSONResponse(resp_data)
    name = COOKIE_PARENT if user["role"] == "parent" else COOKIE_KID
    _set_auth_cookie(resp, request, name, payload)
    other = COOKIE_KID if name == COOKIE_PARENT else COOKIE_PARENT
    resp.delete_cookie(other, path="/")
    return resp


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_PARENT, path="/")
    resp.delete_cookie(COOKIE_KID, path="/")
    return resp


class RegisterBody(BaseModel):
    account: str
    pin: str
    name: str = "家长"
    family_name: str = "我家"


class JoinBody(BaseModel):
    account: str
    pin: str
    name: str = "家长"
    code: str


def _issue_parent(resp, request, user):
    payload = {
        "user_id": user["id"], "family_id": user["family_id"], "role": user["role"],
        "term_id": user.get("term_id"), "iat": time.time(),
    }
    _set_auth_cookie(resp, request, COOKIE_PARENT, payload)
    resp.delete_cookie(COOKIE_KID, path="/")
    return resp


@app.post("/api/auth/register")
def auth_register(b: RegisterBody, request: Request):
    account = (b.account or "").strip().lower()
    pin = (b.pin or "").strip()
    if len(account) < 2:
        raise HTTPException(400, "账号至少 2 位")
    pin = _check_pin(pin, parent=True)
    ip = _client_ip(request)
    _rate_ok("ip:" + ip)
    _rate_ok("reg:" + ip, window=REGISTER_WINDOW, limit=REGISTER_MAX, message="今天开的家庭够多了，明天再试")
    recovery = _new_recovery_code()
    c = db.connect(admin=True)
    try:
        if c.execute("SELECT 1 FROM users WHERE account=?", (account,)).fetchone():
            raise HTTPException(409, "这个账号已经有了")
        fid = "f-" + uuid.uuid4().hex[:8]
        uid = "parent-" + uuid.uuid4().hex[:8]
        c.execute("INSERT INTO families(id,name,created_at,recovery_hash) VALUES(?,?,?,?)",
                  (fid, (b.family_name or "我家").strip()[:20], db.now(), db.hash_pin(recovery)))
        c.execute(
            "INSERT INTO users(id,family_id,role,name,avatar,pin_hash,term_id,account,created_at,force_pin_change,parent_role) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (uid, fid, "parent", (b.name or "家长").strip()[:12], "", db.hash_pin(pin), None, account, db.now(), "", "owner"))
        c.execute("INSERT INTO profiles(user_id,family_id) VALUES(?,?) ON CONFLICT DO NOTHING", (uid, fid))
        db.initialize_family(c, fid)
        c.commit()
        user = {"id": uid, "family_id": fid, "role": "parent", "term_id": None}
    finally:
        c.close()
    _rate_hit("reg:" + ip)
    resp = JSONResponse({"ok": True, "role": "parent", "account": account, "force_pin_change": False,
                         "recovery_code": recovery})
    return _issue_parent(resp, request, user)


@app.post("/api/auth/join")
def auth_join(b: JoinBody, request: Request):
    account = (b.account or "").strip().lower()
    pin = (b.pin or "").strip()
    code = (b.code or "").strip().upper()
    if len(account) < 2 or not code:
        raise HTTPException(400, "账号、密码、邀请码都要填")
    pin = _check_pin(pin, parent=True)
    ip = _client_ip(request)
    _rate_ok("ip:" + ip)
    _rate_ok("join:" + code)
    # 失败猜码才记次数，成功加入不占爆破额度
    c = db.connect(admin=True)
    try:
        inv = c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
        if not inv:
            _rate_hit("ip:" + ip)
            _rate_hit("join:" + code)
            raise HTTPException(404, "邀请码不对")
        expires = inv["expires_at"]
        max_uses = int(inv["max_uses"] or 0)
        used = int(inv["used_count"] or 0)
        if expires and expires < db.now():
            raise HTTPException(410, "邀请码已过期")
        if max_uses and used >= max_uses:
            raise HTTPException(410, "邀请码已被用掉")
        if c.execute("SELECT 1 FROM users WHERE account=?", (account,)).fetchone():
            raise HTTPException(409, "这个账号已经有了")
        uid = "parent-" + uuid.uuid4().hex[:8]
        role = "parent"  # 观察员已下线，旧码也当家长
        c.execute(
            "INSERT INTO users(id,family_id,role,name,avatar,pin_hash,term_id,account,created_at,force_pin_change) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (uid, inv["family_id"], role, (b.name or "家长").strip()[:12], "", db.hash_pin(pin), None, account, db.now(), ""))
        c.execute("INSERT INTO profiles(user_id,family_id) VALUES(?,?) ON CONFLICT DO NOTHING", (uid, inv["family_id"]))
        c.execute("UPDATE invites SET used_count = used_count + 1, used_by=?, used_at=? WHERE code=?",
                  ((b.name or "家长").strip()[:12], db.now(), code))
        c.commit()
        user = {"id": uid, "family_id": inv["family_id"], "role": role, "term_id": None}
    finally:
        c.close()
    resp = JSONResponse({"ok": True, "role": user["role"], "account": account, "force_pin_change": False})
    return _issue_parent(resp, request, user)


class RecoverBody(BaseModel):
    account: str
    code: str
    pin: str


@app.post("/api/auth/recover")
def auth_recover(b: RecoverBody, request: Request):
    """用一次性找回码重置家庭创建者的家长密码。"""
    account = (b.account or "").strip().lower()
    code = (b.code or "").strip().upper().replace(" ", "")
    ip = _client_ip(request)
    _rate_ok("ip:" + ip)
    _rate_ok("rec:" + account)
    if len(account) < 2 or len(code) < 8:
        _rate_hit("ip:" + ip)
        _rate_hit("rec:" + account)
        raise HTTPException(400, "账号和找回码都要填")
    pin = _check_pin(b.pin, parent=True)
    c = db.connect(admin=True)
    try:
        u = c.execute("SELECT * FROM users WHERE account=? AND role='parent'", (account,)).fetchone()
        fam = None
        if u:
            fam = c.execute("SELECT * FROM families WHERE id=?", (u["family_id"],)).fetchone()
        hashed = (fam["recovery_hash"] if fam else "") or ""
        ok = bool(u and hashed and db.verify_pin(code, hashed))
        if not ok:
            _rate_hit("ip:" + ip)
            _rate_hit("rec:" + account)
            raise HTTPException(400, "账号或找回码不对")
        owner = c.execute(
            "SELECT * FROM users WHERE family_id=? AND role='parent' AND parent_role='owner' ORDER BY created_at LIMIT 1",
            (u["family_id"],)).fetchone() or u
        c.execute("UPDATE users SET pin_hash=?, force_pin_change='' WHERE id=?", (db.hash_pin(pin), owner["id"]))
        c.execute("UPDATE families SET recovery_hash='' WHERE id=?", (u["family_id"],))
        c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
                  ("u:" + owner["id"], str(time.time())))
        c.commit()
        user = dict(owner)
    finally:
        c.close()
    resp = JSONResponse({"ok": True, "role": "parent", "account": user["account"], "force_pin_change": False})
    return _issue_parent(resp, request, user)


@app.post("/api/admin/invite", dependencies=[Depends(require_owner)])
def invite_create(request: Request):
    u = request.state.user
    code = uuid.uuid4().hex[:8].upper()
    c = get_conn()
    prot = c.execute("SELECT invite_protect FROM families WHERE id=?", (u["family_id"],)).fetchone()
    protect = int(prot["invite_protect"] or 0) if prot else 0
    max_uses = 1 if protect else 0
    expires_at = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds") if protect else None
    c.execute("INSERT INTO invites(code,family_id,role,created_at,max_uses,expires_at) VALUES(?,?,?,?,?,?)",
              (code, u["family_id"], "parent", db.now(), max_uses, expires_at))
    c.commit(); c.close()
    return {"code": code, "role": "parent", "protect": bool(protect)}


class InviteProtectIn(BaseModel):
    enabled: bool


@app.get("/api/admin/family", dependencies=[Depends(require_parent)])
def family_info(request: Request):
    u = request.state.user
    c = get_conn()
    row = c.execute("SELECT id, name, invite_protect, penalty_enabled FROM families WHERE id=?", (u["family_id"],)).fetchone()
    c.close()
    return {"name": row["name"], "invite_protect": int(row["invite_protect"] or 0),
            "penalty_enabled": int(row["penalty_enabled"] or 0)}


@app.put("/api/admin/family/invite_protect", dependencies=[Depends(require_owner)])
def family_invite_protect(b: InviteProtectIn, request: Request):
    u = request.state.user
    val = 1 if b.enabled else 0
    c = get_conn()
    c.execute("UPDATE families SET invite_protect=? WHERE id=?", (val, u["family_id"]))
    c.commit(); c.close()
    return {"invite_protect": val}


class PenaltySwitchIn(BaseModel):
    enabled: bool = False


@app.put("/api/admin/family/penalty", dependencies=[Depends(require_owner)])
def family_penalty_switch(b: PenaltySwitchIn, request: Request):
    u = request.state.user
    val = 1 if b.enabled else 0
    c = get_conn()
    c.execute("UPDATE families SET penalty_enabled=? WHERE id=?", (val, u["family_id"]))
    c.commit(); c.close()
    return {"penalty_enabled": val}


PENALTY_REASONS = ("磨蹭", "没完成约定", "没礼貌", "其他")


class PenaltyIn(BaseModel):
    amount: int
    reason: str
    note: str = ""


def _penalty_on(c, fam):
    row = c.execute("SELECT penalty_enabled FROM families WHERE id=?", (fam,)).fetchone()
    return bool(row and int(row["penalty_enabled"] or 0))


def _penalty_note(reason, note):
    reason = (reason or "").strip()
    note = (note or "").strip()[:40]
    if reason not in PENALTY_REASONS:
        raise HTTPException(400, "选一个原因")
    if reason == "其他":
        if not note:
            raise HTTPException(400, "选「其他」时要写备注")
        return "其他：" + note
    return reason if not note else reason + "：" + note


@app.post("/api/admin/penalty", dependencies=[Depends(require_parent)])
def penalty_create(b: PenaltyIn):
    amount = int(b.amount)
    if amount < 1:
        raise HTTPException(400, "扣分要是正整数")
    note = _penalty_note(b.reason, b.note)
    c = get_conn()
    fam = _fam.get()
    try:
        if not _penalty_on(c, fam):
            raise HTTPException(403, "扣分未开启")
        kid = _kid.get()
        if not kid:
            raise HTTPException(400, "没有孩子")
        _own_kid(c, kid, fam)
        
        # 并发保护：PostgreSQL用行锁，SQLite用IMMEDIATE事务
        if db.is_postgres():
            c.execute("SELECT SUM(delta) FROM ledger WHERE kid_id=? FOR UPDATE", (kid,))
        else:
            # SQLite: 使用IMMEDIATE事务防止并发写入
            c.execute("BEGIN IMMEDIATE")
        
        bal = balance(c, kid)
        if amount > bal:
            if not db.is_postgres():
                c.execute("ROLLBACK")
            raise HTTPException(400, "最多还能扣 %d" % bal)
        before = earned(c, kid)
        ref = "pen-" + uuid.uuid4().hex[:10]
        lid = db.insert(c, "INSERT INTO ledger(date,delta,reason,ref_id,note,created_at,kid_id) VALUES(?,?,?,?,?,?,?)",
                        (db.today(), -amount, "penalty", ref, note, db.now(), kid))
        c.commit()
        return {"id": lid, "ref_id": ref, "delta": -amount, "balance": balance(c, kid),
                "earned": earned(c, kid), "earned_before": before, "level": level_info(c)}
    finally:
        c.close()


def _penalty_reason_key(note):
    note = (note or "").strip()
    for r in PENALTY_REASONS:
        if note == r or note.startswith(r + "："):
            return r
    return "其他"


@app.get("/api/admin/penalty", dependencies=[Depends(require_parent)])
def penalty_list():
    c = get_conn()
    kid = _kid.get()
    if not kid:
        c.close()
        return {"items": [], "summary": {"net": 0, "count": 0, "amount": 0,
                                         "by_reason": [{"reason": r, "count": 0, "amount": 0} for r in PENALTY_REASONS]}}
    
    # 优化：单次查询使用LEFT JOIN获取扣分和撤回状态
    all_rows = c.execute("""
        SELECT p.id, p.date, p.delta, p.reason, p.ref_id, p.note, p.created_at,
               CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END AS cancelled
        FROM ledger p
        LEFT JOIN ledger c ON c.reason='penalty_cancel' AND c.ref_id=p.ref_id AND c.kid_id=p.kid_id
        WHERE p.kid_id=? AND p.reason='penalty'
        ORDER BY p.id DESC
    """, (kid,)).fetchall()
    
    by = {r: {"reason": r, "count": 0, "amount": 0} for r in PENALTY_REASONS}
    count = amount = 0
    items = []
    
    for r in all_rows:
        row = dict(r)
        row["cancelled"] = bool(row["cancelled"])
        
        # 统计未撤回的扣分
        if not row["cancelled"]:
            key = _penalty_reason_key(row.get("note"))
            n = abs(int(row.get("delta") or 0))
            by[key]["count"] += 1
            by[key]["amount"] += n
            count += 1
            amount += n
        
        # 只返回最近30条
        if len(items) < 30:
            items.append(row)
    
    c.close()
    return {"items": items, "summary": {"net": -amount, "count": count, "amount": amount,
                                        "by_reason": [by[r] for r in PENALTY_REASONS]}}


@app.post("/api/admin/penalty/{lid}/cancel", dependencies=[Depends(require_parent)])
def penalty_cancel(lid: int):
    c = get_conn()
    fam = _fam.get()
    try:
        if not _penalty_on(c, fam):
            raise HTTPException(403, "扣分未开启")
        kid = _kid.get()
        if not kid:
            raise HTTPException(400, "没有孩子")
        _own_kid(c, kid, fam)
        _begin_write(c)
        row = c.execute("SELECT * FROM ledger WHERE id=? AND kid_id=? AND reason='penalty'", (lid, kid)).fetchone()
        if not row:
            raise HTTPException(404, "没找到这笔扣分")
        ref = row["ref_id"]
        before = earned(c, kid)
        lid_new = insert_ledger(c, db.today(), abs(int(row["delta"])), "penalty_cancel", ref, "撤回扣分", kid=kid)
        if lid_new is None:
            raise HTTPException(409, "这笔已经撤回过")
        c.commit()
        return {"ok": True, "balance": balance(c, kid), "earned": earned(c, kid), "earned_before": before, "level": level_info(c)}
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.get("/api/admin/invites", dependencies=[Depends(require_parent)])
def invites_list(request: Request):
    u = request.state.user
    c = get_conn()
    rows = c.execute(
        "SELECT code, role, created_at, max_uses, expires_at, used_count, used_by, used_at FROM invites "
        "WHERE family_id=? ORDER BY created_at DESC",
        (u["family_id"],)).fetchall()
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        d["expired"] = bool(r["expires_at"] and r["expires_at"] < db.now())
        d["used_up"] = bool(r["max_uses"] and int(r["used_count"] or 0) >= int(r["max_uses"] or 0))
        out.append(d)
    return out


@app.delete("/api/admin/invites/{code}", dependencies=[Depends(require_parent)])
def invite_delete(code: str, request: Request):
    u = request.state.user
    c = get_conn()
    c.execute("DELETE FROM invites WHERE code=? AND family_id=?", (code.upper(), u["family_id"]))
    c.commit(); c.close()
    return {"ok": True}


@app.get("/api/admin/members", dependencies=[Depends(require_parent)])
def members_list(request: Request):
    u = request.state.user
    c = get_conn()
    rows = c.execute(
        "SELECT id, name, account, role, parent_role FROM users WHERE family_id=? AND role='parent' ORDER BY created_at",
        (u["family_id"],)).fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.delete("/api/admin/members/{uid}", dependencies=[Depends(require_owner)])
def members_delete(uid: str, request: Request):
    u = request.state.user
    if uid == u["id"]:
        raise HTTPException(400, "不能删自己")
    c = get_conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND family_id=?", (uid, u["family_id"])).fetchone()
    if not row or row["role"] != "parent":
        c.close(); raise HTTPException(404, "没找到这个家长")
    if row["role"] == "parent":
        n = c.execute("SELECT COUNT(*) FROM users WHERE family_id=? AND role='parent'", (u["family_id"],)).fetchone()[0]
        if n <= 1:
            c.close(); raise HTTPException(400, "至少留一个家长")
    c.execute("DELETE FROM users WHERE id=?", (uid,))
    c.execute("DELETE FROM profiles WHERE user_id=?", (uid,))
    c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
              ("u:" + uid, str(time.time())))
    c.commit(); c.close()
    return {"ok": True}


class TransferOwnerBody(BaseModel):
    new_owner_id: str


@app.post("/api/admin/transfer-owner", dependencies=[Depends(require_owner)])
def transfer_owner(body: TransferOwnerBody, request: Request):
    """转让家长创建者权限给其他家长成员"""
    u = request.state.user
    new_id = body.new_owner_id
    
    if new_id == u["id"]:
        raise HTTPException(400, "不能转让给自己")
    
    c = get_conn()
    try:
        # 检查目标是否是同一家庭的家长
        target = c.execute(
            "SELECT * FROM users WHERE id=? AND family_id=? AND role='parent'",
            (new_id, u["family_id"])
        ).fetchone()
        
        if not target:
            raise HTTPException(404, "目标用户不存在或不是本家庭家长")
        
        # 转让权限：旧创建者变成员，新成员变创建者
        c.execute("UPDATE users SET parent_role='member' WHERE id=?", (u["id"],))
        c.execute("UPDATE users SET parent_role='owner' WHERE id=?", (new_id,))
        c.commit()
        
        return {"ok": True, "new_owner": target["name"]}
    finally:
        c.close()



@app.get("/api/auth/me")
def auth_me(request: Request):
    u = getattr(request.state, "user", None)
    result = {"id": u["id"], "role": u["role"], "name": u["name"], "account": u["account"],
            "force_pin_change": bool(u.get("force_pin_change"))}
    # 家长账号返回角色权限
    if u["role"] == "parent":
        result["parent_role"] = u.get("parent_role", "member")
    return result



@app.post("/api/admin/pin", dependencies=[Depends(require_parent)])
def admin_change_pin(b: PinBody, request: Request):
    u = request.state.user
    current = (b.current or "").strip()
    if not current:
        raise HTTPException(400, "请输入当前密码")
    c = get_conn()
    try:
        row = c.execute("SELECT pin_hash FROM users WHERE id=?", (u["id"],)).fetchone()
        if not row or not db.verify_pin(current, row["pin_hash"] or ""):
            raise HTTPException(400, "当前密码不对")
        pin = _check_pin(b.pin, parent=True)
        if pin == current:
            raise HTTPException(400, "新密码不能和当前密码一样")
        c.execute("UPDATE users SET pin_hash=?, force_pin_change='' WHERE id=?", (db.hash_pin(pin), u["id"]))
        # ponytail: created_at 存 unix 浮点串，和 token.iat 比；别改成 ISO
        c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
                  ("u:" + u["id"], str(time.time())))
        c.commit()
    finally:
        c.close()
    payload = {"user_id": u["id"], "family_id": u["family_id"], "role": u["role"],
               "term_id": u.get("term_id"), "iat": time.time()}
    resp = JSONResponse({"ok": True})
    _set_auth_cookie(resp, request, COOKIE_PARENT, payload)
    return resp


# --- 商店 ---
class RewardIn(BaseModel):
    name: str
    price: int
    category: str = "其他"


@app.post("/api/admin/rewards", dependencies=[Depends(require_parent)])
def reward_create(b: RewardIn):
    c = get_conn()
    rid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO rewards(id,name,price,category,need_approval,family_id) VALUES(?,?,?,?,1,?)",
              (rid, b.name, _sun(b.price), b.category, _fam.get()))
    c.commit(); c.close()
    return {"id": rid}


@app.put("/api/admin/rewards/{rid}", dependencies=[Depends(require_parent)])
def reward_update(rid: str, b: RewardIn):
    c = get_conn()
    c.execute("UPDATE rewards SET name=?, price=?, category=? WHERE id=? AND family_id=?",
              (b.name, _sun(b.price), b.category, rid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/rewards/{rid}", dependencies=[Depends(require_parent)])
def reward_delete(rid: str):
    c = get_conn()
    c.execute("DELETE FROM rewards WHERE id=? AND family_id=?", (rid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


# --- 兑换审批 ---
@app.get("/api/admin/redemptions", dependencies=[Depends(require_parent)])
def redemptions_admin():
    c = get_conn()
    fam = _fam.get()
    roster = [r["id"] for r in c.execute(
        "SELECT id FROM users WHERE family_id=? AND role='kid'", (fam,)).fetchall()]
    pending, done = [], []
    seen_p, seen_d = set(), set()
    for kid in roster:
        db.apply_scope(c, fam, kid)
        for r in c.execute(
            "SELECT rd.id, rd.date, rd.price, rd.status, rw.name, rd.kid_id FROM redemptions rd "
            "LEFT JOIN rewards rw ON rw.id=rd.reward_id WHERE rd.status='pending' AND rd.kid_id=?",
            (kid,)).fetchall():
            if r["id"] in seen_p:
                continue
            seen_p.add(r["id"]); pending.append(r)
        for r in c.execute(
            "SELECT rd.id, rd.date, rd.price, rd.status, rw.name, rd.kid_id FROM redemptions rd "
            "LEFT JOIN rewards rw ON rw.id=rd.reward_id WHERE rd.status!='pending' AND rd.kid_id=?",
            (kid,)).fetchall():
            if r["id"] in seen_d:
                continue
            seen_d.add(r["id"]); done.append(r)
    db.apply_scope(c, fam, kid_id())
    c.close()
    pend = [dict(r) for r in pending]
    rest = [dict(r) for r in done]
    rest.sort(key=lambda x: x.get("id") or 0, reverse=True)
    pend.sort(key=lambda x: x.get("id") or 0, reverse=True)
    return pend + rest[:50]


def _own_redemption(c, rid):
    fam = _fam.get()
    for kr in c.execute("SELECT id FROM users WHERE family_id=? AND role='kid'", (fam,)).fetchall():
        db.apply_scope(c, fam, kr["id"])
        rd = c.execute("SELECT * FROM redemptions WHERE id=? AND kid_id=?", (rid, kr["id"])).fetchone()
        if rd:
            return rd
    db.apply_scope(c, fam, kid_id())
    return None


@app.post("/api/admin/redemptions/{rid}/approve", dependencies=[Depends(require_parent)])
def redemption_approve(rid: str):
    c = get_conn()
    try:
        rd = _own_redemption(c, rid)
        if not rd:
            raise HTTPException(404, "没找到这条兑换")
        if rd["status"] != "pending":
            raise HTTPException(409, "这条已处理过")
        applicant = rd["kid_id"] or kid_id()
        _begin_write(c)
        if db.is_postgres():
            c.execute("SELECT SUM(delta) FROM ledger WHERE kid_id=? FOR UPDATE", (applicant,))
        rd = c.execute("SELECT * FROM redemptions WHERE id=? AND kid_id=?", (rid, applicant)).fetchone()
        if not rd or rd["status"] != "pending":
            raise HTTPException(409, "这条已处理过")
        bal = balance(c, applicant)
        if bal < rd["price"]:
            raise HTTPException(409, "阳光不够，还差 %d" % (rd["price"] - bal))
        cur = c.execute("UPDATE redemptions SET status='done' WHERE id=? AND status='pending'", (rid,))
        if getattr(cur, "rowcount", 0) == 0:
            raise HTTPException(409, "这条已处理过")
        rw = c.execute("SELECT name FROM rewards WHERE id=?", (rd["reward_id"],)).fetchone()
        lid = insert_ledger(c, db.today(), -rd["price"], "redeem", f"red-{rid}", rw["name"] if rw else "兑换", kid=applicant)
        if lid is None:
            raise HTTPException(409, "这条已处理过")
        maybe_milestone(c, applicant)
        c.commit()
        return {"ok": True}
    except Exception:
        _rollback(c)
        raise
    finally:
        c.close()


@app.post("/api/admin/redemptions/{rid}/reject", dependencies=[Depends(require_parent)])
def redemption_reject(rid: str):
    c = get_conn()
    rd = _own_redemption(c, rid)
    if not rd:
        c.close(); raise HTTPException(404, "没找到这条兑换")
    if rd["status"] != "pending":
        c.close(); raise HTTPException(409, "这条已处理过")
    c.execute("DELETE FROM redemptions WHERE id=?", (rid,))
    c.commit(); c.close()
    return {"ok": True}


@app.post("/api/admin/redemptions/{rid}/deliver", dependencies=[Depends(require_parent)])
def redemption_deliver(rid: str):
    """家长标记「奖励已实际兑现」：done → delivered（阳光已在批准时扣除）。"""
    c = get_conn()
    rd = _own_redemption(c, rid)
    if not rd:
        c.close(); raise HTTPException(404, "没找到这条兑换")
    if rd["status"] != "done":
        c.close(); raise HTTPException(409, "先同意后才能标记兑现")
    c.execute("UPDATE redemptions SET status='delivered' WHERE id=?", (rid,))
    c.commit(); c.close()
    return {"ok": True}


# --- 单元测试成绩奖励 ---
TEST_BANDS = [(100, 30), (95, 20), (90, 15), (85, 10), (0, 5)]

def test_bands(c):
    raw = insight_rules(c).get("test_bands")
    if not isinstance(raw, list) or len(raw) != 5:
        return [list(x) for x in TEST_BANDS]
    try:
        bands = [[int(x[0]), int(x[1])] for x in raw]
    except (TypeError, ValueError, IndexError):
        return [list(x) for x in TEST_BANDS]
    return bands if _valid_test_bands(bands) else [list(x) for x in TEST_BANDS]


def _valid_test_bands(bands):
    return (len(bands) == 5 and bands[-1][0] == 0 and
            all(0 <= th <= 100 and sun >= 0 for th, sun in bands) and
            all(bands[i][0] > bands[i + 1][0] for i in range(4)))


def score_sunshine(score, bands):
    for th, sun in bands:
        if score >= th:
            return sun
    return 0


class TestIn(BaseModel):
    subject_id: str
    score: int
    note: str = ""
    unit_id: str = ""


@app.post("/api/admin/tests", dependencies=[Depends(require_parent)])
def test_create(b: TestIn):
    if not (0 <= b.score <= 100):
        raise HTTPException(400, "分数要在 0~100 之间")
    c = get_conn()
    sun = score_sunshine(b.score, test_bands(c))
    unit_name = ""
    if b.unit_id:
        u = c.execute("SELECT name FROM units WHERE id=?", (b.unit_id,)).fetchone()
        unit_name = u["name"] if u else ""
    tid = db.insert(c, "INSERT INTO tests(subject_id,unit_id,score,sunshine,note,date,created_at,kid_id) VALUES(?,?,?,?,?,?,?,?)",
                    (b.subject_id, b.unit_id or None, b.score, sun, (b.note or "").strip()[:40], db.today(), db.now(), kid_id()))
    label = unit_name or b.note or b.subject_id
    insert_ledger(c, db.today(), sun, "test", f"test-{tid}", f"{label} 测试 {b.score} 分")
    c.commit()
    res = {"id": tid, "sunshine": sun, "level": level_info(c)}
    c.close()
    return res


@app.get("/api/admin/tests", dependencies=[Depends(require_parent)])
def tests_list():
    c = get_conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM tests WHERE kid_id=? ORDER BY id DESC LIMIT 50", (kid_id(),)).fetchall()]
    c.close()
    return rows


@app.delete("/api/admin/tests/{tid}", dependencies=[Depends(require_parent)])
def test_delete(tid: str):
    c = get_conn()
    fam = _fam.get()
    try:
        r = None
        owner = None
        for kr in c.execute("SELECT id FROM users WHERE family_id=? AND role='kid'", (fam,)).fetchall():
            db.apply_scope(c, fam, kr["id"])
            r = c.execute("SELECT * FROM tests WHERE id=? AND kid_id=?", (tid, kr["id"])).fetchone()
            if r:
                owner = kr["id"]
                break
        if not r:
            raise HTTPException(404, "没找到这条测试")
        _begin_write(c)
        lid = insert_ledger(c, db.today(), -r["sunshine"], "test_cancel", f"test-{tid}", "删除测试冲正", kid=owner)
        if lid is None:
            raise HTTPException(409, "这条已经冲正过")
        c.execute("DELETE FROM tests WHERE id=?", (tid,))
        c.commit()
        return {"ok": True}
    except Exception:
        _rollback(c)
        raise
    finally:
        db.apply_scope(c, fam, kid_id())
        c.close()


WEAKPOINT_INTERVALS = [1, 3, 7, 14, 30]


def _due_date(start, idx=0):
    d = datetime.strptime(start, "%Y-%m-%d").date() if isinstance(start, str) else start
    i = max(0, min(int(idx or 0), len(WEAKPOINT_INTERVALS) - 1))
    return (d + timedelta(days=WEAKPOINT_INTERVALS[i])).isoformat()


def _wp_rows(c, kid, unit_id=None):
    q = ("SELECT wp.id, wp.kid_id, wp.unit_id, wp.tag_id, wp.note, wp.status, wp.interval_idx, wp.review_due_at, "
         "kt.name AS tag_name, u.name AS unit_name, u.subject_id "
         "FROM weak_points wp LEFT JOIN knowledge_tags kt ON kt.id=wp.tag_id "
         "LEFT JOIN units u ON u.id=wp.unit_id "
         "WHERE wp.kid_id=? AND wp.status='open'")
    args = [kid]
    if unit_id:
        q += " AND wp.unit_id=?"
        args.append(unit_id)
    q += " ORDER BY CASE WHEN wp.review_due_at IS NULL OR wp.review_due_at='' THEN 1 ELSE 0 END, wp.review_due_at, wp.id"
    return [dict(r) for r in c.execute(q, args).fetchall()]


def _due_queue(c, kid, today=None):
    today = today or db.today()
    return [r for r in _wp_rows(c, kid) if r.get("review_due_at") and r["review_due_at"] <= today]


def _own_kid(c, kid, fam):
    row = c.execute("SELECT id FROM users WHERE id=? AND family_id=? AND role='kid'", (kid, fam)).fetchone()
    if not row:
        raise HTTPException(404, "没找到这个孩子")
    return kid


@app.get("/api/admin/unit-tags")
def admin_unit_tags(request: Request, unit_id: str = ""):
    require_parent(request)
    c = get_conn()
    if unit_id:
        rows = c.execute(
            "SELECT ut.tag_id, kt.name FROM unit_tags ut JOIN knowledge_tags kt ON kt.id=ut.tag_id "
            "WHERE ut.unit_id=? ORDER BY kt.kind, kt.id", (unit_id,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    tags = [dict(r) for r in c.execute("SELECT id, subject_id, kind, name FROM knowledge_tags ORDER BY kind, id").fetchall()]
    unit_tags = [dict(r) for r in c.execute(
        "SELECT unit_id, tag_id, auto FROM unit_tags ORDER BY unit_id, tag_id").fetchall()]
    c.close()
    return {"tags": tags, "unit_tags": unit_tags}


@app.get("/api/admin/weak-points")
def admin_weak_points(request: Request, unit_id: str = ""):
    require_parent(request)
    c = get_conn()
    fam = _fam.get()
    kid = _own_kid(c, kid_id(), fam)
    db.apply_scope(c, fam, kid)
    rows = _wp_rows(c, kid, unit_id or None)
    c.close()
    return rows


class WeakIn(BaseModel):
    unit_id: str
    tag_ids: list[str]
    note: str = ""
    kid_id: str = ""
    first_review: str = ""  # YYYY-MM-DD，首次到期；空=今天


@app.put("/api/admin/weak-points")
def admin_weak_put(b: WeakIn, request: Request):
    require_parent(request)
    if not b.unit_id:
        raise HTTPException(400, "选一个单元")
    tags = [t for t in (b.tag_ids or []) if t]
    c = get_conn()
    fam = _fam.get()
    kid = _own_kid(c, b.kid_id or kid_id(), fam)
    db.apply_scope(c, fam, kid)
    for tid in tags:
        if not c.execute("SELECT 1 FROM knowledge_tags WHERE id=?", (tid,)).fetchone():
            db.apply_scope(c, fam, kid_id()); c.close()
            raise HTTPException(400, "没有这个考点")
    old = {r["tag_id"]: r for r in c.execute(
        "SELECT * FROM weak_points WHERE kid_id=? AND unit_id=? AND status='open'", (kid, b.unit_id)).fetchall()}
    c.execute("DELETE FROM weak_points WHERE kid_id=? AND unit_id=? AND status='open'", (kid, b.unit_id))
    note = (b.note or "").strip()[:40]
    now = db.now()
    first = (b.first_review or "").strip()
    if first:
        try:
            datetime.strptime(first, "%Y-%m-%d")
        except ValueError:
            db.apply_scope(c, fam, kid_id()); c.close()
            raise HTTPException(400, "日期写成 2026-09-07 这种")
    else:
        first = db.today()
    for tid in tags:
        prev = old.get(tid)
        due = prev["review_due_at"] if prev and prev["review_due_at"] else first
        idx = prev["interval_idx"] if prev else 0
        c.execute(
            "INSERT INTO weak_points(kid_id,unit_id,tag_id,note,status,interval_idx,review_due_at,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (kid, b.unit_id, tid, note, "open", idx or 0, due, now, now))
    c.commit()
    rows = _wp_rows(c, kid, b.unit_id)
    db.apply_scope(c, fam, kid_id())
    c.close()
    return rows


@app.delete("/api/admin/weak-points/{wid}")
def admin_weak_del(wid: str, request: Request):
    require_parent(request)
    c = get_conn()
    fam = _fam.get()
    row = c.execute("SELECT * FROM weak_points WHERE id=?", (wid,)).fetchone()
    if not row:
        # 可能被 RLS 挡住，按 roster 再找一次
        found = None
        for kr in c.execute("SELECT id FROM users WHERE family_id=? AND role='kid'", (fam,)).fetchall():
            db.apply_scope(c, fam, kr["id"])
            found = c.execute("SELECT * FROM weak_points WHERE id=?", (wid,)).fetchone()
            if found:
                break
        if not found:
            db.apply_scope(c, fam, kid_id()); c.close()
            raise HTTPException(404, "没找到这条")
        row = found
    else:
        db.apply_scope(c, fam, row["kid_id"])
    c.execute("DELETE FROM weak_points WHERE id=?", (wid,))
    c.commit()
    db.apply_scope(c, fam, kid_id())
    c.close()
    return {"ok": True}


@app.get("/api/weak-points")
def kid_weak_points(unit_id: str = ""):
    c = get_conn()
    rows = _wp_rows(c, kid_id(), unit_id or None)
    c.close()
    return rows


@app.get("/api/review-due")
def kid_review_due():
    c = get_conn()
    kid = kid_id()
    hidden = set(hidden_subjects_for(c, kid))
    rows = [r for r in _due_queue(c, kid) if r.get("subject_id") not in hidden]
    c.close()
    return rows


@app.get("/api/admin/review-due")
def admin_review_due(request: Request):
    require_parent(request)
    c = get_conn()
    fam = _fam.get()
    kid = _own_kid(c, kid_id(), fam)
    db.apply_scope(c, fam, kid)
    rows = _due_queue(c, kid)
    c.close()
    return rows


class ReviewJudgeIn(BaseModel):
    action: str  # pass=过关升档 / fail=还在错降档 / done=已巩固


@app.post("/api/admin/weak-points/{wid}/judge")
def admin_wp_judge(wid: str, b: ReviewJudgeIn, request: Request):
    require_parent(request)
    c = get_conn()
    fam = _fam.get()
    row = None
    for kr in c.execute("SELECT id FROM users WHERE family_id=? AND role='kid'", (fam,)).fetchall():
        db.apply_scope(c, fam, kr["id"])
        row = c.execute("SELECT * FROM weak_points WHERE id=?", (wid,)).fetchone()
        if row:
            break
    if not row:
        db.apply_scope(c, fam, kid_id()); c.close()
        raise HTTPException(404, "没找到这条")
    now, today = db.now(), db.today()
    act = (b.action or "").strip()
    if act not in ("pass", "fail", "done"):
        db.apply_scope(c, fam, kid_id()); c.close()
        raise HTTPException(400, "动作是 pass / fail / done")
    new_idx = int(row["interval_idx"] or 0)
    if act == "done":
        c.execute("UPDATE weak_points SET status='resolved', updated_at=? WHERE id=?", (now, wid))
    else:
        new_idx = min(new_idx + 1, len(WEAKPOINT_INTERVALS) - 1) if act == "pass" else max(new_idx - 1, 0)
        due = _due_date(today, new_idx)
        c.execute("UPDATE weak_points SET interval_idx=?, review_due_at=?, updated_at=? WHERE id=?",
                  (new_idx, due, now, wid))
    c.commit()
    db.apply_scope(c, fam, kid_id())
    c.close()
    return {"ok": True, "action": act, "interval_idx": new_idx}


# --- 等级 ---
class RankIn(BaseModel):
    name: str
    min_sunshine: int


@app.get("/api/admin/ranks", dependencies=[Depends(require_parent)])
def ranks_admin():
    c = get_conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM ranks WHERE family_id=? ORDER BY min_sunshine", (_fam.get(),)).fetchall()]
    c.close()
    return rows


@app.post("/api/admin/ranks", dependencies=[Depends(require_parent)])
def rank_create(b: RankIn):
    c = get_conn()
    c.execute("INSERT INTO ranks(id,name,min_sunshine,sort,family_id) VALUES(?,?,?,?,?)",
              (uuid.uuid4().hex[:8], b.name, b.min_sunshine, b.min_sunshine, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


@app.put("/api/admin/ranks/{rid}", dependencies=[Depends(require_parent)])
def rank_update(rid: str, b: RankIn):
    c = get_conn()
    c.execute("UPDATE ranks SET name=?, min_sunshine=? WHERE id=? AND family_id=?",
              (b.name, b.min_sunshine, rid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/ranks/{rid}", dependencies=[Depends(require_parent)])
def rank_delete(rid: str):
    c = get_conn()
    r = c.execute("SELECT min_sunshine FROM ranks WHERE id=? AND family_id=?", (rid, _fam.get())).fetchone()
    if r and r["min_sunshine"] == 0:
        c.close()
        raise HTTPException(400, "基础等级（0阳光）不能删")
    c.execute("DELETE FROM ranks WHERE id=? AND family_id=?", (rid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


# --- 单元任务 ---
class TaskIn(BaseModel):
    subject_id: str
    unit_id: str
    action: str
    title: str
    sunshine: int = 5
    kid_id: Optional[str] = None  # None/空=全家


def _custom_task_kid(c, kid):
    owner = (kid or "").strip() or None
    if owner:
        _own_kid(c, owner, _fam.get())
    return owner


@app.post("/api/admin/tasks", dependencies=[Depends(require_parent)])
def task_create(b: TaskIn):
    c = get_conn()
    owner = _custom_task_kid(c, b.kid_id)
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom,family_id,kid_id) VALUES(?,?,?,?,?,?,99,1,?,?)",
              (tid, b.subject_id, b.unit_id, b.action, b.title, _sun(b.sunshine), _fam.get(), owner))
    c.commit(); c.close()
    return {"id": tid}


def _own_custom_task(c, tid, verb="改"):
    row = c.execute("SELECT custom, family_id FROM tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        c.close(); raise HTTPException(404, "没找到这个任务")
    if not row["custom"]:
        c.close(); raise HTTPException(403, "教材任务不能" + verb)
    if row["family_id"] != _fam.get():
        c.close(); raise HTTPException(404, "没找到这个任务")
    return row


@app.put("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_update(tid: str, b: TaskIn):
    c = get_conn()
    _own_custom_task(c, tid)
    owner = _custom_task_kid(c, b.kid_id)
    c.execute("UPDATE tasks SET subject_id=?, unit_id=?, action=?, title=?, sunshine=?, kid_id=? WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?",
              (b.subject_id, b.unit_id, b.action, b.title, _sun(b.sunshine), owner, tid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_delete(tid: str):
    c = get_conn()
    _own_custom_task(c, tid, "删")
    c.execute("DELETE FROM tasks WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?", (tid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


# --- 每日任务（跳绳等） ---
class DailyTaskIn(BaseModel):
    subject_id: str
    name: str
    sunshine: int = 5
    bonus_per_metric: Optional[int] = 3
    note: str = ""
    metrics: Optional[list] = None


def _replace_metrics(c, did, metrics):
    c.execute("DELETE FROM daily_metrics WHERE task_id=?", (did,))
    for m in (metrics or []):
        c.execute("INSERT INTO daily_metrics(task_id,id,label,unit,direction,note) VALUES(?,?,?,?,?,?)",
                  (did, m.get("id"), m.get("label"), m.get("unit"), m.get("direction", "higher_better"), m.get("note", "")))


@app.post("/api/admin/daily", dependencies=[Depends(require_parent)])
def daily_create(b: DailyTaskIn):
    c = get_conn()
    did = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric,note,family_id) "
              "VALUES(?,?,?,?,'daily','personal_best',?,?,?)",
              (did, b.subject_id, b.name, _sun(b.sunshine), _sun(b.bonus_per_metric if b.bonus_per_metric is not None else 0), (b.note or "").strip()[:120], _fam.get()))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"id": did}


@app.put("/api/admin/daily/{did}", dependencies=[Depends(require_parent)])
def daily_update(did: str, b: DailyTaskIn):
    c = get_conn()
    row = c.execute("SELECT family_id FROM daily_tasks WHERE id=?", (did,)).fetchone()
    if not row or not row["family_id"]:
        c.close(); raise HTTPException(403, "系统每日任务不能改")
    c.execute("UPDATE daily_tasks SET subject_id=?, name=?, sunshine=?, bonus_per_metric=?, note=? WHERE id=? AND family_id=?",
              (b.subject_id, b.name, _sun(b.sunshine), _sun(b.bonus_per_metric if b.bonus_per_metric is not None else 0), (b.note or "").strip()[:120], did, _fam.get()))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/daily/{did}", dependencies=[Depends(require_parent)])
def daily_delete(did: str):
    c = get_conn()
    row = c.execute("SELECT family_id FROM daily_tasks WHERE id=?", (did,)).fetchone()
    if not row or not row["family_id"]:
        c.close(); raise HTTPException(403, "系统每日任务不能删")
    c.execute("DELETE FROM daily_metrics WHERE task_id=?", (did,))
    c.execute("DELETE FROM daily_tasks WHERE id=? AND family_id=?", (did, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


# ---------------- 周报（家长端） -------------


@app.get("/api/admin/weekly", dependencies=[Depends(require_parent)])
def weekly():
    c = get_conn()
    kid = kid_id()
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    days = []
    for i in range(7):
        d = (monday + timedelta(days=i)).isoformat()
        day_earned = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date=? AND kid_id=? "
            "AND reason NOT IN ('redeem','penalty','penalty_cancel','bank_deposit','bank_withdraw')", (d, kid)).fetchone()[0]
        day_spent = c.execute(
            "SELECT COALESCE(SUM(-delta),0) FROM ledger WHERE date=? AND reason='redeem' AND delta<0 AND kid_id=?", (d, kid)).fetchone()[0]
        day_net = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date=? AND kid_id=?", (d, kid)).fetchone()[0]
        days.append({"date": d, "weekday": WEEKDAYS[i], "earned": day_earned, "spent": day_spent, "net": day_net})
    w_start, w_end = days[0]["date"], days[6]["date"]
    net = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ? AND kid_id=?", (w_start, w_end, kid)).fetchone()[0]
    by_subject = c.execute(
        "SELECT name, SUM(cnt) cnt, SUM(sun) sun FROM ("
        "  SELECT s.name name, COUNT(*) cnt, COALESCE(SUM(c.sunshine),0) sun "
        "  FROM completions c JOIN tasks t ON t.id=c.task_id JOIN subjects s ON s.id=t.subject_id "
        "  WHERE c.status='completed' AND c.kid_id=? AND c.date BETWEEN ? AND ? GROUP BY s.name "
        "  UNION ALL "
        "  SELECT s.name, COUNT(*), COALESCE(SUM(c.sunshine),0) "
        "  FROM completions c JOIN daily_tasks t ON t.id=c.task_id JOIN subjects s ON s.id=t.subject_id "
        "  WHERE c.status='completed' AND c.kid_id=? AND c.date BETWEEN ? AND ? GROUP BY s.name "
        ") GROUP BY name ORDER BY sun DESC, name", (kid, w_start, w_end, kid, w_start, w_end)).fetchall()
    checkins = c.execute(
        "SELECT COUNT(DISTINCT date) FROM checkins WHERE kid_id=? AND date BETWEEN ? AND ?", (kid, w_start, w_end)).fetchone()[0]
    weeks = []
    for i in range(3, -1, -1):
        wm = monday - timedelta(weeks=i)
        we = wm + timedelta(days=6)
        wk_earned = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ? AND kid_id=? "
            "AND reason NOT IN ('redeem','penalty','penalty_cancel','bank_deposit','bank_withdraw')",
            (wm.isoformat(), we.isoformat(), kid)).fetchone()[0]
        wk_net = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ? AND kid_id=?",
            (wm.isoformat(), we.isoformat(), kid)).fetchone()[0]
        weeks.append({"label": f"{wm.month}/{wm.day}", "earned": wk_earned, "net": wk_net, "week_start": wm.isoformat()})
    mastered = [r[0] for r in c.execute(
        "SELECT DISTINCT kt.name FROM weak_points wp JOIN knowledge_tags kt ON kt.id=wp.tag_id "
        "WHERE wp.kid_id=? AND substr(wp.updated_at,1,10) BETWEEN ? AND ? "
        "AND (wp.status='resolved' OR COALESCE(wp.interval_idx,0) >= 4) "
        "ORDER BY kt.name", (kid, w_start, w_end)).fetchall()]
    fam = _fam.get()
    today_d = datetime.now().date()
    span = (today_d - monday).days
    last_from = (monday - timedelta(days=7)).isoformat()
    last_to = (monday - timedelta(days=7) + timedelta(days=span)).isoformat()
    this_from, this_to = monday.isoformat(), today_d.isoformat()
    kids_cmp = []
    mastered_by_kid = []
    insight_rows = []
    if fam:
        roster = c.execute(
            "SELECT id, name FROM users WHERE family_id=? AND role='kid' ORDER BY created_at", (fam,)).fetchall()
        for kr in roster:
            db.apply_scope(c, fam, kr["id"])
            ke = c.execute(
                "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? "
                "AND reason NOT IN ('redeem','penalty','penalty_cancel','bank_deposit','bank_withdraw')",
                (kr["id"], w_start, w_end)).fetchone()[0]
            ks = c.execute(
                "SELECT COALESCE(SUM(-delta),0) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? AND reason='redeem' AND delta<0",
                (kr["id"], w_start, w_end)).fetchone()[0]
            ins = build_insights(c, kr["id"])
            done = _completed_between(c, kr["id"], this_from, this_to)
            done_last = _completed_between(c, kr["id"], last_from, last_to)
            items = _mastered_names(c, kr["id"], w_start, w_end)
            kids_cmp.append({"id": kr["id"], "name": kr["name"], "earned": ke, "spent": ks,
                             "streak": streak(c, kr["id"]), "current": kr["id"] == kid,
                             "completed": done, "completed_last": done_last, "insight": ins})
            insight_rows.append({"kid_id": kr["id"], "name": kr["name"], "insight": ins})
            if items:
                mastered_by_kid.append({"kid_id": kr["id"], "name": kr["name"], "items": items})
        db.apply_scope(c, fam, kid)
    insight = build_insights(c, kid)
    penalty_net = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? "
        "AND reason IN ('penalty','penalty_cancel')", (kid, this_from, this_to)).fetchone()[0]
    penalty_count = c.execute(
        "SELECT COUNT(*) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? AND reason='penalty'",
        (kid, this_from, this_to)).fetchone()[0]
    out = {
        "week_start": w_start, "week_end": w_end,
        "insight": insight,
        "family_insight": family_insight_from(insight_rows),
        "days": days,
        "total_earned": sum(x["earned"] for x in days),
        "total_spent": sum(x["spent"] for x in days),
        "net": net,
        "balance": balance(c),
        "earned_all": earned(c),
        "streak": streak(c),
        "checkins": checkins,
        "weeks": weeks,
        "by_subject": [dict(r) for r in by_subject],
        "mastered": mastered,
        "mastered_by_kid": mastered_by_kid,
        "kids": kids_cmp,
        "penalty_net": penalty_net,
        "penalty_count": penalty_count,
    }
    c.close()
    return out


class InsightRulesIn(BaseModel):
    test_fail_count: Optional[int] = None
    test_fail_score: Optional[int] = None
    drop_ratio: Optional[float] = None
    streak_break: Optional[int] = None
    test_bands: Optional[list] = None


def _clamp_rules(b: InsightRulesIn):
    out = {}
    if b.test_fail_count is not None:
        if not (1 <= b.test_fail_count <= 10):
            raise HTTPException(400, "连续低分次数要在 1~10")
        out["test_fail_count"] = int(b.test_fail_count)
    if b.test_fail_score is not None:
        if not (0 <= b.test_fail_score <= 100):
            raise HTTPException(400, "低分线要在 0~100")
        out["test_fail_score"] = int(b.test_fail_score)
    if b.drop_ratio is not None:
        if not (0.1 <= b.drop_ratio <= 0.9):
            raise HTTPException(400, "下滑比例要在 0.1~0.9")
        out["drop_ratio"] = float(b.drop_ratio)
    if b.streak_break is not None:
        if not (1 <= b.streak_break <= 7):
            raise HTTPException(400, "连击断几天要在 1~7")
        out["streak_break"] = int(b.streak_break)
    if b.test_bands is not None:
        try:
            bands = [[int(x[0]), int(x[1])] for x in b.test_bands]
        except (TypeError, ValueError, IndexError):
            raise HTTPException(400, "奖励档位格式不对")
        if not _valid_test_bands(bands):
            raise HTTPException(400, "分数线必须从高到低，最后一档为 0 分，阳光不能为负")
        out["test_bands"] = bands
    return out


@app.get("/api/admin/insights", dependencies=[Depends(require_parent)])
def insights_admin():
    c = get_conn()
    fam = _fam.get()
    rules = insight_rules(c)
    rules["test_bands"] = test_bands(c)
    roster = c.execute(
        "SELECT id, name FROM users WHERE family_id=? AND role='kid' ORDER BY created_at", (fam,)).fetchall()
    kids = []
    for kr in roster:
        db.apply_scope(c, fam, kr["id"])
        kids.append({"kid_id": kr["id"], "name": kr["name"], "insight": build_insights(c, kr["id"])})
    db.apply_scope(c, fam, kid_id())
    c.close()
    return {"rules": rules, "kids": kids}


@app.put("/api/admin/insight-rules", dependencies=[Depends(require_parent)])
def insight_rules_put(b: InsightRulesIn):
    patch = _clamp_rules(b)
    c = get_conn()
    merged = insight_rules(c)
    merged.update(patch)
    c.execute("UPDATE families SET insight_rules=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), _fam.get()))
    c.commit()
    out = insight_rules(c)
    out["test_bands"] = test_bands(c)
    c.close()
    return out


@app.get("/api/admin/family-today", dependencies=[Depends(require_parent)])
def family_today():
    c = get_conn()
    fam = _fam.get()
    today = db.today()
    roster = c.execute(
        "SELECT id, name FROM users WHERE family_id=? AND role='kid' ORDER BY created_at", (fam,)).fetchall()
    kids = []
    for kr in roster:
        db.apply_scope(c, fam, kr["id"])
        checkin = c.execute(
            "SELECT 1 FROM checkins WHERE date=? AND kid_id=?", (today, kr["id"])).fetchone() is not None
        completed_today = c.execute(
            "SELECT COUNT(*) FROM completions WHERE status='completed' AND kid_id=? AND date=?",
            (kr["id"], today)).fetchone()[0]
        review_due = c.execute(
            "SELECT COUNT(*) FROM weak_points WHERE kid_id=? AND status='open' AND review_due_at IS NOT NULL "
            "AND review_due_at!='' AND review_due_at<=?", (kr["id"], today)).fetchone()[0]
        kids.append({
            "kid_id": kr["id"], "name": kr["name"], "checkin": checkin,
            "completed_today": completed_today, "review_due": review_due,
            "streak": streak(c, kr["id"]), "balance": balance(c, kr["id"]),
        })
    if roster:
        db.apply_scope(c, fam, kid_id())
    c.close()
    return {"today": today, "kids": kids}


def _gender(val):
    g = (val or "").strip()
    if not g:
        return None
    if g not in ("男", "女"):
        raise HTTPException(400, "性别填男或女")
    return g


class KidIn(BaseModel):
    name: str
    account: str = ""
    pin: str = ""
    term_id: str = "g5s1"
    gender: str = ""


@app.get("/api/admin/kids", dependencies=[Depends(require_parent)])
def kids_list(request: Request):
    u = request.state.user
    c = get_conn()
    rows = c.execute(
        "SELECT id, name, account, term_id, gender FROM users WHERE family_id=? AND role='kid' ORDER BY created_at",
        (u["family_id"],)).fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/kids", dependencies=[Depends(require_parent)])
def kids_create(b: KidIn, request: Request):
    name = (b.name or "").strip()[:12]
    if not name:
        raise HTTPException(400, "名字不能为空")
    account = (b.account or name).strip().lower()
    pin = _check_pin(b.pin or "0129", parent=False)
    u = request.state.user
    # 账号全局唯一：RLS 只让看本家，这里走特权连接查全部家庭
    pc = db.connect(admin=True)
    try:
        taken = pc.execute("SELECT 1 FROM users WHERE account=?", (account,)).fetchone()
    finally:
        pc.close()
    if taken:
        raise HTTPException(409, "这个账号已经有了")
    c = get_conn()
    n = c.execute("SELECT COUNT(*) FROM users WHERE family_id=? AND role='kid'", (u["family_id"],)).fetchone()[0]
    if n >= MAX_KIDS_PER_FAMILY:
        c.close()
        raise HTTPException(400, "一家最多 %d 个孩子" % MAX_KIDS_PER_FAMILY)
    if b.term_id and not c.execute("SELECT 1 FROM terms WHERE id=?", (b.term_id,)).fetchone():
        c.close()
        raise HTTPException(404, "没有这个学期")
    kid = "kid-" + uuid.uuid4().hex[:8]
    c.execute(
        "INSERT INTO users(id,family_id,role,name,avatar,pin_hash,term_id,account,created_at,force_pin_change,gender) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (kid, u["family_id"], "kid", name, "", db.hash_pin(pin), b.term_id or "g5s1", account, db.now(), "", _gender(b.gender)))
    c.execute("INSERT INTO profiles(user_id,family_id) VALUES(?,?) ON CONFLICT DO NOTHING", (kid, u["family_id"]))
    c.commit(); c.close()
    return {"id": kid, "account": account}


@app.put("/api/admin/kids/{kid}", dependencies=[Depends(require_parent)])
def kids_update(kid: str, b: KidIn, request: Request):
    u = request.state.user
    c = get_conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND role='kid'", (kid,)).fetchone()
    if not row or row["family_id"] != u["family_id"]:
        c.close(); raise HTTPException(404, "没找到这个孩子")
    name = (b.name or row["name"]).strip()[:12]
    term = b.term_id or row["term_id"] or "g5s1"
    account = (b.account or row["account"] or "").strip().lower()
    if not c.execute("SELECT 1 FROM terms WHERE id=?", (term,)).fetchone():
        c.close(); raise HTTPException(404, "没有这个学期")
    if account and account != (row["account"] or ""):
        if len(account) < 2:
            c.close(); raise HTTPException(400, "账号至少 2 位")
        pc = db.connect(admin=True)
        try:
            taken = pc.execute("SELECT 1 FROM users WHERE account=? AND id!=?", (account, kid)).fetchone()
        finally:
            pc.close()
        if taken:
            c.close(); raise HTTPException(409, "这个账号已经有了")
    gender = _gender(b.gender) if b.gender != "" else row["gender"]
    c.execute("UPDATE users SET name=?, term_id=?, account=?, gender=? WHERE id=?",
              (name, term, account or row["account"], gender, kid))
    if b.pin:
        try:
            _check_pin(b.pin, parent=False)
        except HTTPException as e:
            c.close(); raise e
        c.execute("UPDATE users SET pin_hash=?, force_pin_change='' WHERE id=?", (db.hash_pin(b.pin.strip()), kid))
        c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
                  ("u:" + kid, str(time.time())))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/kids/{kid}", dependencies=[Depends(require_owner)])
def kids_delete(kid: str, request: Request):
    u = request.state.user
    c = get_conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND role='kid'", (kid,)).fetchone()
    if not row or row["family_id"] != u["family_id"]:
        c.close(); raise HTTPException(404, "没找到这个孩子")
    n = c.execute("SELECT COUNT(*) FROM users WHERE family_id=? AND role='kid'", (u["family_id"],)).fetchone()[0]
    if n <= 1:
        c.close(); raise HTTPException(400, "至少留一个孩子")
    c.execute("DELETE FROM users WHERE id=?", (kid,))
    c.execute("DELETE FROM profiles WHERE user_id=?", (kid,))
    c.commit(); c.close()
    return {"ok": True}


class WordConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: Optional[bool] = None
    new_per_day: Optional[int] = None
    max_due: Optional[int] = None
    base_sunshine: Optional[int] = None
    perfect_sunshine: Optional[int] = None
    unlock_by_cursor: Optional[bool] = None
    current_book: Optional[str] = None
    tts: Optional[bool] = None
    tts_autoplay: Optional[bool] = None
    tts_lang: Optional[str] = None


class WordBookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    enabled: Optional[bool] = None


class WordImportIn(BaseModel):
    text: str = ""


def _need_kid():
    k = _kid.get()
    if not k:
        raise HTTPException(400, "没有孩子")
    return k


def _word_call(fn, *args):
    c = get_conn()
    try:
        out = fn(c, *args)
        c.commit()
        return out
    except wordmod.WordError as e:
        c.close()
        raise HTTPException(e.status, e.detail)
    finally:
        try:
            c.close()
        except Exception:
            pass


class WordStudyIn(BaseModel):
    word_id: int
    action: str


class WordSpellIn(BaseModel):
    word_id: int
    text: str = ""
    phase: str = "spell"
    attempt_no: int = 1


@app.get("/api/words/today")
def words_today():
    return _word_call(wordmod.today_payload, kid_id(), _fam.get())


@app.post("/api/words/session/start")
def words_session_start():
    return _word_call(wordmod.start_session, kid_id(), _fam.get())


@app.post("/api/words/session/{sid}/study")
def words_session_study(sid: str, b: WordStudyIn):
    return _word_call(wordmod.study_item, kid_id(), _fam.get(), sid, b.word_id, b.action)


@app.post("/api/words/session/{sid}/spell")
def words_session_spell(sid: str, b: WordSpellIn):
    return _word_call(wordmod.spell_item, kid_id(), _fam.get(), sid, b.word_id, b.text, b.phase, b.attempt_no)


@app.post("/api/words/session/{sid}/complete")
def words_session_complete(sid: str):
    return _word_call(wordmod.complete_session, kid_id(), _fam.get(), sid)


@app.get("/api/admin/words/stats", dependencies=[Depends(require_parent)])
def admin_words_stats():
    c = get_conn()
    kid = _need_kid()
    fam = _fam.get()
    out = wordmod.week_stats(c, kid, fam)
    c.close()
    return out


@app.get("/api/admin/words/config", dependencies=[Depends(require_parent)])
def admin_words_config():
    c = get_conn()
    kid = _need_kid()
    fam = _fam.get()
    cfg = wordmod.kid_config(c, kid)
    books = wordmod.list_books(c, kid, fam)
    c.close()
    return {**cfg, "books": books}


@app.put("/api/admin/words/config", dependencies=[Depends(require_parent)])
def admin_words_config_put(b: WordConfigIn):
    c = get_conn()
    kid = _need_kid()
    fam = _fam.get()
    fields = b.model_dump(exclude_unset=True)
    if "current_book" in fields:
        bid = (fields.get("current_book") or "").strip()
        if bid:
            book = wordmod.get_book(c, fam, bid)
            if not book or int(book["enabled"] or 0) != 1:
                c.close()
                raise HTTPException(404, "没找到这本词书")
            probe = dict(fields)
            cfg = wordmod.kid_config(c, kid)
            cfg.update({k: v for k, v in probe.items() if k != "current_book" and v is not None})
            if not wordmod.book_selectable(c, kid, fam, book, cfg):
                c.close()
                raise HTTPException(400, "先在已学到里设置英语进度，或关掉词书游标锁")
        fields["current_book"] = bid
    wordmod.set_kid_config(c, kid, **fields)
    c.commit()
    cfg = wordmod.kid_config(c, kid)
    books = wordmod.list_books(c, kid, fam)
    c.close()
    return {**cfg, "books": books}


@app.get("/api/admin/words/books", dependencies=[Depends(require_parent)])
def admin_words_books():
    c = get_conn()
    fam = _fam.get()
    kid = _kid.get()
    books = wordmod.list_books(c, kid, fam)
    c.close()
    return books


@app.get("/api/admin/words/books/{bid}", dependencies=[Depends(require_parent)])
def admin_words_book_get(bid: str):
    c = get_conn()
    fam = _fam.get()
    book, items = wordmod.list_words(c, fam, bid)
    c.close()
    if not book:
        raise HTTPException(404, "没找到这本词书")
    d = dict(book)
    d["is_system"] = int(d["is_system"] or 0)
    d["enabled"] = int(d["enabled"] or 0)
    d["words"] = items
    return d


@app.post("/api/admin/words/books", dependencies=[Depends(require_parent)])
def admin_words_book_create(b: WordBookIn):
    name = (b.name or "").strip()
    if not name or len(name) > 30:
        raise HTTPException(400, "词书名字 1–30 字")
    c = get_conn()
    fam = _fam.get()
    bid = "fam-" + uuid.uuid4().hex[:10]
    now = db.now()
    c.execute(
        "INSERT INTO word_books(id,family_id,term_id,unit_id,name,is_system,enabled,sort,created_at,updated_at) "
        "VALUES(?,?,?,?,?,0,1,?,?,?)",
        (bid, fam, "", None, name, 0, now, now),
    )
    c.commit()
    row = c.execute("SELECT * FROM word_books WHERE id=?", (bid,)).fetchone()
    c.close()
    d = dict(row)
    d["is_system"] = 0
    d["word_count"] = 0
    return d


@app.put("/api/admin/words/books/{bid}", dependencies=[Depends(require_parent)])
def admin_words_book_put(bid: str, b: WordBookIn):
    c = get_conn()
    fam = _fam.get()
    book = wordmod.get_book(c, fam, bid)
    if not book:
        c.close()
        raise HTTPException(404, "没找到这本词书")
    if int(book["is_system"] or 0):
        c.close()
        raise HTTPException(403, "系统词书不能改")
    name = book["name"]
    if b.name != "":
        name = (b.name or "").strip()
        if not name or len(name) > 30:
            c.close()
            raise HTTPException(400, "词书名字 1–30 字")
    enabled = int(book["enabled"] or 0)
    if b.enabled is not None:
        enabled = 1 if b.enabled else 0
    c.execute("UPDATE word_books SET name=?, enabled=?, updated_at=? WHERE id=? AND family_id=?",
              (name, enabled, db.now(), bid, fam))
    c.commit()
    row = c.execute("SELECT * FROM word_books WHERE id=?", (bid,)).fetchone()
    c.close()
    return dict(row)


@app.delete("/api/admin/words/books/{bid}", dependencies=[Depends(require_parent)])
def admin_words_book_del(bid: str):
    c = get_conn()
    fam = _fam.get()
    book = wordmod.get_book(c, fam, bid)
    if not book:
        c.close()
        raise HTTPException(404, "没找到这本词书")
    if int(book["is_system"] or 0):
        c.close()
        raise HTTPException(403, "系统词书不能删")
    n = c.execute("SELECT COUNT(*) FROM words WHERE book_id=?", (bid,)).fetchone()[0]
    now = db.now()
    if n:
        c.execute("UPDATE word_books SET enabled=0, updated_at=? WHERE id=? AND family_id=?", (now, bid, fam))
        c.execute("UPDATE words SET active=0, updated_at=? WHERE book_id=?", (now, bid))
        c.commit()
        c.close()
        return {"ok": True, "soft": True}
    c.execute("DELETE FROM word_books WHERE id=? AND family_id=?", (bid, fam))
    c.commit()
    c.close()
    return {"ok": True, "soft": False}


@app.post("/api/admin/words/books/{bid}/import", dependencies=[Depends(require_parent)])
def admin_words_import(bid: str, b: WordImportIn):
    c = get_conn()
    fam = _fam.get()
    book = wordmod.get_book(c, fam, bid)
    if not book:
        c.close()
        raise HTTPException(404, "没找到这本词书")
    if int(book["is_system"] or 0):
        c.close()
        raise HTTPException(403, "系统词书不能改")
    try:
        rows, errors = wordmod.parse_import_text(b.text)
    except ValueError as e:
        c.close()
        raise HTTPException(400, str(e))
    now = db.now()
    ok = 0
    max_sort = c.execute("SELECT COALESCE(MAX(sort),0) FROM words WHERE book_id=?", (bid,)).fetchone()[0]
    for i, row in enumerate(rows, 1):
        norm = wordmod.normalize_word(row["word"])
        if not norm:
            errors.append({"line": row["line"], "error": "缺单词"})
            continue
        c.execute(
            "INSERT INTO words(book_id,word,word_norm,cn,ipa,example_en,example_cn,accept_json,sort,active,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,1,?,?) "
            "ON CONFLICT(book_id, word_norm) DO UPDATE SET word=excluded.word, cn=excluded.cn, "
            "ipa=excluded.ipa, active=1, updated_at=excluded.updated_at",
            (bid, row["word"], norm, row["cn"], row["ipa"], "", "", "[]", max_sort + i, now, now),
        )
        ok += 1
    c.execute("UPDATE word_books SET updated_at=? WHERE id=?", (now, bid))
    c.commit()
    c.close()
    return {"ok": ok, "errors": errors}


@app.get("/api/admin/words/problem-words", dependencies=[Depends(require_parent)])
def admin_words_problem():
    c = get_conn()
    kid = _need_kid()
    fam = _fam.get()
    rows = c.execute(
        "SELECT w.id AS word_id, w.word, w.cn, w.ipa, b.id AS book_id, b.name AS book_name, b.unit_id, "
        "wp.wrong_count, wp.due_at, wp.last_seen_at "
        "FROM word_progress wp JOIN words w ON w.id=wp.word_id "
        "JOIN word_books b ON b.id=w.book_id "
        "WHERE wp.kid_id=? AND COALESCE(wp.wrong_count,0)>=2 AND (b.is_system=1 OR b.family_id=?) "
        "ORDER BY wp.wrong_count DESC, wp.last_seen_at DESC",
        (kid, fam or ""),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/words/{word_id}/focus", dependencies=[Depends(require_parent)])
def admin_words_focus(word_id: int):
    c = get_conn()
    kid = _need_kid()
    fam = _fam.get()
    row = c.execute(
        "SELECT w.id FROM words w JOIN word_books b ON b.id=w.book_id "
        "WHERE w.id=? AND (b.is_system=1 OR b.family_id=?)",
        (word_id, fam or ""),
    ).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "没找到这个词")
    now = db.now()
    due = wordmod.tomorrow()
    exists = c.execute("SELECT 1 FROM word_progress WHERE kid_id=? AND word_id=?", (kid, word_id)).fetchone()
    if exists:
        c.execute(
            "UPDATE word_progress SET interval_idx=0, due_at=?, last_seen_at=? WHERE kid_id=? AND word_id=?",
            (due, now, kid, word_id),
        )
    else:
        c.execute(
            "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
            "last_result,streak_right,correct_count,wrong_count) VALUES(?,?,0,?,NULL,?, '',0,0,0)",
            (kid, word_id, due, now),
        )
    c.commit()
    c.close()
    return {"ok": True, "due_at": due}


@app.get("/api/daily/{task_id}/history")
def daily_history(task_id: str):
    """孩子端查看某每日任务（跳绳等）的逐次记录（按日期升序），画趋势图用。"""
    c = get_conn()
    rows = c.execute(
        "SELECT date, metrics FROM completions WHERE task_id=? AND status='completed' AND kid_id=? "
        "ORDER BY date, id", (task_id, kid_id())).fetchall()
    c.close()
    return [{"date": r["date"], "metrics": (json.loads(r["metrics"]) if r["metrics"] else {})} for r in rows]


# ---------------- APK 更新与下载 ----------------

@app.get("/api/version")
def get_app_version():
    """返回当前应用版本号，供 Android 客户端检查更新"""
    return {
        "version": app_version(),
        "revision": app_revision(),
        "label": app_label()
    }


@app.get("/api/apk/latest")
def download_latest_apk():
    """提供最新 APK 下载"""
    from fastapi.responses import FileResponse
    import os
    
    apk_path = db.BASE / "static" / "sunshine-latest.apk"
    if not apk_path.exists():
        raise HTTPException(status_code=404, detail="APK 文件不存在，请先构建并上传")
    
    # 返回文件大小和最后修改时间供客户端参考
    stat = os.stat(apk_path)
    headers = {
        "Content-Disposition": f'attachment; filename="sunshine-{app_version()}.apk"',
        "X-APK-Version": app_version(),
        "X-APK-Size": str(stat.st_size),
        "X-APK-Modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }
    
    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        headers=headers
    )


# ---------------- 静态前端（构建后由本后端直接托管） ----------------

_DIST = db.BASE.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    @app.get("/sw.js", include_in_schema=False)
    def _sw_js():
        from fastapi.responses import FileResponse
        return FileResponse(str(_DIST / "sw.js"), headers={"Cache-Control": "no-cache"})
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")