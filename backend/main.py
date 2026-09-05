# -*- coding: utf-8 -*-
"""阳光学习工作台 — P0 后端。

核心不变式：ledger 是唯一真相源；余额/累计/等级/连击全部由 ledger+日期推导。
「点错取消」= 一条负 delta 流水 + completion 置 cancelled，不删历史。
"""
import contextvars
import json
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
from pydantic import BaseModel

import db

_kid = contextvars.ContextVar("kid", default=None)
_fam = contextvars.ContextVar("fam", default=None)
COOKIE_PARENT, COOKIE_KID = "pid", "sid"
TOKEN_MAX_AGE = 7 * 24 * 3600
_fails = {}


def _serializer():
    return URLSafeTimedSerializer(db.secret_key(), salt="sunshine-sid")


@asynccontextmanager
async def lifespan(app):
    db.init_db()  # 启动时建库/迁移一次，请求路径不再重复初始化
    yield


app = FastAPI(title="阳光学习工作台", lifespan=lifespan)
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


def insert_ledger(c, date, delta, reason, ref_id, note, kid=None):
    db.insert_ledger(c, date, delta, reason, ref_id, note, kid_id=kid or kid_id())


def active_term(c):
    r = c.execute("SELECT term_id, name FROM users WHERE id=?", (kid_id(),)).fetchone()
    if not r:
        return "g5s1"
    return r["term_id"] or "g5s1"


def _client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else ""))


def _rate_ok(key: str):
    now = time.time()
    xs = [t for t in _fails.get(key, []) if now - t < 600]
    _fails[key] = xs
    if len(xs) >= 5:
        raise HTTPException(429, "试太多次了，过一会儿再试")


def _cookie_secure(request: Request) -> bool:
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def _set_auth_cookie(resp: Response, request: Request, name: str, payload: dict):
    resp.set_cookie(
        name, _serializer().dumps(payload),
        max_age=TOKEN_MAX_AGE, httponly=True, samesite="lax",
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


PUBLIC_API = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/register", "/api/auth/join"}


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_API:
        return await call_next(request)
    u = _user_from_request(request)
    if not u:
        return JSONResponse({"detail": "未登录"}, 401)
    if u["role"] == "observer" and request.method not in ("GET", "HEAD", "OPTIONS"):
        return JSONResponse({"detail": "观察员只能看"}, 403)
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
    elif len(pin) < 4:
        raise HTTPException(400, "孩子密码至少 4 位")
    return pin


def require_parent(request: Request):
    u = getattr(request.state, "user", None)
    if not u or u["role"] != "parent":
        raise HTTPException(403, "需要家长账号")
    return u


def earned(c, kid=None):
    # 累计获得：赚/取消都算（正负抵消），唯独「兑换消费(redeem)」不算 → 消费不掉级
    return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE reason != 'redeem' AND kid_id=?",
                     (kid or kid_id(),)).fetchone()[0]


def balance(c, kid=None):
    return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=?", (kid or kid_id(),)).fetchone()[0]


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


def subject_order(c, subject_id):
    rows = c.execute(
        "SELECT t.id FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "WHERE t.subject_id=? AND (u.term_id=? OR (COALESCE(t.custom,0)=1 AND (t.kid_id IS NULL OR t.kid_id=?))) "
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
        "WHERE u.term_id=? OR (COALESCE(t.custom,0)=1 AND (t.kid_id IS NULL OR t.kid_id=?))", (term, kid_id())).fetchall()}
    custom_ids = {r["id"] for r in c.execute(
        "SELECT id FROM tasks WHERE custom=1 AND (kid_id IS NULL OR kid_id=?)", (kid_id(),)).fetchall()}
    locked = set()
    for sid in {r[0] for r in c.execute(
            "SELECT DISTINCT t.subject_id FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
            "WHERE u.term_id=? OR (COALESCE(t.custom,0)=1 AND (t.kid_id IS NULL OR t.kid_id=?))", (term, kid_id())).fetchall()}:
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
    # 连击 = 连续几天有「任何学习活动」（签到 / 完成任务 / 每日打卡 / 兑换成功）
    kid = kid or kid_id()
    dates = {r["date"] for r in c.execute("SELECT DISTINCT date FROM checkins WHERE kid_id=?", (kid,)).fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM completions WHERE status='completed' AND kid_id=?", (kid,)).fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM redemptions WHERE status IN ('done','delivered') AND kid_id=?", (kid,)).fetchall()}
    d = datetime.now().date()
    n = 0
    while d.isoformat() in dates:
        n += 1
        d -= timedelta(days=1)
    return n


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
            db.set_kid_setting(c, kid, key, db.today())
            insert_ledger(c, db.today(), bonus, "milestone", key, f"连续坚持 {days} 天", kid=kid)
            got.append((days, bonus))
    return got


# 成就徽章（孩子端「成就墙」）
ACHIEVEMENTS = [
    {"id": "first",    "icon": "sprout", "name": "初来乍到", "desc": "完成第 1 张任务卡", "target": 1},
    {"id": "cn10",     "icon": "book", "name": "语文十卡", "desc": "完成 10 张语文卡", "target": 10},
    {"id": "ma10",     "icon": "calc", "name": "数学十卡", "desc": "完成 10 张数学卡", "target": 10},
    {"id": "en10",     "icon": "globe", "name": "英语十卡", "desc": "完成 10 张英语卡", "target": 10},
    {"id": "all100",   "icon": "medal", "name": "百卡达成", "desc": "累计完成 100 张单元卡", "target": 100},
    {"id": "sport",    "icon": "sport", "name": "运动健将", "desc": "每日运动打卡 10 次", "target": 10},
    {"id": "daily30",  "icon": "calendar", "name": "每日全勤", "desc": "每日任务累计打卡 30 次", "target": 30},
    {"id": "go10",     "icon": "go", "name": "围棋小棋手", "desc": "围棋对弈打卡 10 次", "target": 10},
    {"id": "calc10",   "icon": "mental", "name": "口算达人", "desc": "每日口算打卡 10 次", "target": 10},
    {"id": "streak7",  "icon": "flame", "name": "坚持一周", "desc": "连续坚持 7 天", "target": 7},
    {"id": "streak14", "icon": "rocket", "name": "坚持半月", "desc": "连续坚持 14 天", "target": 14},
    {"id": "streak30", "icon": "moon", "name": "坚持满月", "desc": "连续坚持 30 天", "target": 30},
    {"id": "test100",  "icon": "award", "name": "满分学霸", "desc": "单元测试考 100 分", "target": 100},
    {"id": "shop1",    "icon": "cart", "name": "初尝战果", "desc": "第一次兑换奖励", "target": 1},
    {"id": "shop5",    "icon": "gift", "name": "兑换小能手", "desc": "累计兑换 5 次", "target": 5},
    {"id": "box5",     "icon": "dices", "name": "盲盒收藏家", "desc": "开 5 个连击盲盒", "target": 5},
    {"id": "custom10", "icon": "sparkles", "name": "自律之星", "desc": "完成家长任务 10 次", "target": 10},
    {"id": "sun500",   "icon": "coins", "name": "阳光富翁", "desc": "累计获得 500 阳光", "target": 500},
    {"id": "sun2000",  "icon": "gem", "name": "阳光大佬", "desc": "累计获得 2000 阳光", "target": 2000},
    {"id": "sun5000",  "icon": "crown", "name": "阳光传说", "desc": "累计获得 5000 阳光", "target": 5000},
]


@app.get("/api/achievements")
def achievements():
    c = get_conn()
    kid = kid_id()
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
    box_n = int(db.get_kid_setting(c, kid_id(), "box_opened", "0"))
    s = streak(c)
    e = earned(c)
    done_by_subj = {r[0]: r[1] for r in c.execute(
        "SELECT t.subject_id, COUNT(*) FROM completions c JOIN tasks t ON t.id=c.task_id "
        "WHERE c.status='completed' AND c.kid_id=? GROUP BY t.subject_id", (kid,)).fetchall()}
    cur = {
        "first": total, "all100": unit_done,
        "sport": sport, "daily30": sport, "go10": go_n, "calc10": calc_n,
        "streak7": s, "streak14": s, "streak30": s,
        "cn10": done_by_subj.get("语文", 0), "ma10": done_by_subj.get("数学", 0), "en10": done_by_subj.get("英语", 0),
        "test100": best_test, "shop1": shop_n, "shop5": shop_n, "box5": box_n,
        "custom10": custom_n, "sun500": e, "sun2000": e, "sun5000": e,
    }
    out = []
    for a in ACHIEVEMENTS:
        v = cur[a["id"]]
        out.append({**a, "current": v, "earned": v >= a["target"]})
    c.close()
    return out


# 连击宝箱：连续打卡每 3 天解锁一个，随机 +3~+10（期望 ≈ 每天 +2，防通胀）
BOX_INTERVAL = 3


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
    s = streak(c)
    opened = int(db.get_kid_setting(c, kid_id(), "box_opened", "0"))
    if s // BOX_INTERVAL <= opened:
        c.close()
        raise HTTPException(409, "还没有可开的宝箱，再坚持坚持吧！")
    bonus = random.randint(3, 10)
    db.set_kid_setting(c, kid_id(), "box_opened", str(opened + 1))
    insert_ledger(c, db.today(), bonus, "box", f"box-{opened + 1}", "连击宝箱")
    c.commit()
    res = {"delta": bonus, "streak": streak(c), "level": level_info(c)}
    c.close()
    return res


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
    return {"ok": True}


@app.get("/api/overview")
def overview():
    return level_info(get_conn())


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
        "units": [{"id": r["id"], "name": r["name"], "subject_id": r["subject_id"]}
                  for r in c.execute(
                      "SELECT id, name, subject_id FROM units WHERE term_id=? OR id LIKE ?",
                      (term, "custom-%")).fetchall()],
    }
    # 单元测试成绩（unit_id → 最近一次分），孩子端单元旁展示
    unit_scores = {}
    for r in c.execute("SELECT unit_id, score, date FROM tests WHERE unit_id IS NOT NULL "
                       "ORDER BY date DESC, id DESC").fetchall():
        if r["unit_id"] not in unit_scores:
            unit_scores[r["unit_id"]] = {"score": r["score"], "date": r["date"]}
    out["unit_scores"] = unit_scores
    # 单元任务 + 完成状态（只看当前学期 + 自定义）
    tasks_rows = c.execute(
        "SELECT t.* FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "WHERE u.term_id=? OR (COALESCE(t.custom,0)=1 AND (t.kid_id IS NULL OR t.kid_id=?)) "
        "ORDER BY t.subject_id, COALESCE(u.seq,99), t.sort", (term, kid_id())).fetchall()
    done_ids = {r["task_id"] for r in c.execute(
        "SELECT DISTINCT task_id FROM completions WHERE status='completed' AND kid_id=?", (kid_id(),)).fetchall()}
    out["progress_lock"] = db.get_setting(c, "progress_lock", "1")
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
    t = db.today()
    tid = body.task_id
    row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if row:
        if is_past(c, tid, row["subject_id"]):
            c.close()
            raise HTTPException(409, "这课已经学过了，不加阳光")
        if tid in locked_task_ids(c):
            c.close()
            raise HTTPException(409, "这课还没学到，先把前面的学完哦")
        delta = row["sunshine"]
        cid = db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (tid, t, "completed", delta, None, "unit", db.now(), kid_id()))
        if cid is None:
            c.close()
            raise HTTPException(409, "这项已经完成过啦")
        insert_ledger(c, t, delta, "task", f"cmp-{cid}", row["title"])
        m = maybe_milestone(c)
        c.commit()
        res = {"delta": delta, "bonus": 0, "milestone": m, "level": level_info(c)}
        c.close()
        return res
    d = c.execute("SELECT * FROM daily_tasks WHERE id=? AND (family_id IS NULL OR family_id=?)",
                  (tid, _fam.get())).fetchone()
    if d:
        bonus, detail = compute_daily_bonus(c, d, body.metrics)
        delta = d["sunshine"] + bonus
        mj = json.dumps(body.metrics) if body.metrics else None
        cid = db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (tid, t, "completed", delta, mj, "daily", db.now(), kid_id()))
        if cid is None:
            c.close()
            raise HTTPException(409, "今天这项已完成过啦")
        insert_ledger(c, t, delta, "daily", f"cmp-{cid}",
                         d["name"] + ("（破纪录 +%d）" % bonus if bonus else ""))
        m = maybe_milestone(c)
        c.commit()
        res = {"delta": delta, "bonus": bonus, "bonus_detail": detail, "milestone": m, "level": level_info(c)}
        c.close()
        return res
    c.close()
    raise HTTPException(404, "没找到这个任务")


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
    if not c.execute("SELECT 1 FROM subjects WHERE id=?", (body.subject_id,)).fetchone():
        c.close()
        raise HTTPException(404, "没有这个学科")
    owner = body.kid_id or None
    if owner:
        u = request.state.user
        row = c.execute("SELECT family_id FROM users WHERE id=? AND role='kid'", (owner,)).fetchone()
        if not row or row["family_id"] != u["family_id"]:
            c.close(); raise HTTPException(404, "没找到这个孩子")
    unit_id = f"custom-{body.subject_id}"
    c.execute("INSERT INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
              (unit_id, body.subject_id, active_term(c), 99, "自定义"))
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom,family_id,kid_id) VALUES(?,?,?,?,?,?,99,1,?,?)",
              (tid, body.subject_id, unit_id, "自定义", title, body.sunshine or 5, request.state.user["family_id"], owner))
    c.commit()
    c.close()
    return {"id": tid}


@app.delete("/api/tasks/{tid}", dependencies=[Depends(require_parent)])
def delete_task_kid(tid: str):
    c = get_conn()
    row = c.execute("SELECT custom FROM tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "没找到这个任务")
    if not row["custom"]:
        c.close()
        raise HTTPException(403, "系统任务请在家长端删除")
    c.execute("DELETE FROM tasks WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?", (tid, _fam.get()))
    c.commit()
    c.close()
    return {"ok": True}


@app.post("/api/cancel")
def cancel(body: CompleteBody):
    c = get_conn()
    t = db.today()
    # 单元任务：整个学期内有已完成记录即可取消；每日任务：只取消今天这条
    comp = c.execute(
        "SELECT * FROM completions WHERE task_id=? AND status='completed' AND kid_id=? ORDER BY id DESC LIMIT 1",
        (body.task_id, kid_id())).fetchone()
    if not comp:
        c.close()
        raise HTTPException(404, "没有可取消的记录")
    c.execute("UPDATE completions SET status='cancelled' WHERE id=?", (comp["id"],))
    delta = -comp["sunshine"]
    insert_ledger(c, t, delta, "cancel", f"cmp-{comp['id']}", "点错取消")
    c.commit()
    res = {"delta": delta, "level": level_info(c)}
    c.close()
    return res


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
    # 需要家长同意的奖励：只挂起，不扣阳光，等家长端「审批」通过
    if r["need_approval"]:
        c.execute("INSERT INTO redemptions(reward_id,date,price,status,created_at,kid_id) VALUES(?,?,?,?,?,?)",
                  (r["id"], db.today(), r["price"], "pending", db.now(), kid_id()))
        c.commit()
        res = {"pending": True, "reward": r["name"], "level": level_info(c)}
        c.close()
        return res
    if balance(c) < r["price"]:
        c.close()
        raise HTTPException(409, "阳光不够哦，还差 %d" % (r["price"] - balance(c)))
    rid = db.insert(c, "INSERT INTO redemptions(reward_id,date,price,status,created_at,kid_id) VALUES(?,?,?,?,?,?)",
                    (r["id"], db.today(), r["price"], "done", db.now(), kid_id()))
    insert_ledger(c, db.today(), -r["price"], "redeem", f"red-{rid}", r["name"])
    m = maybe_milestone(c)
    c.commit()
    res = {"delta": -r["price"], "reward": r["name"], "milestone": m, "level": level_info(c)}
    c.close()
    return res


@app.get("/api/redemptions")
def redemptions():
    c = get_conn()
    rows = c.execute(
        "SELECT rd.id, rd.date, rd.price, rd.status, rw.name FROM redemptions rd "
        "LEFT JOIN rewards rw ON rw.id=rd.reward_id ORDER BY rd.id DESC LIMIT 30").fetchall()
    c.close()
    return [dict(r) for r in rows]


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


@app.post("/api/admin/progress-lock", dependencies=[Depends(require_parent)])
def set_progress_lock(b: LockBody):
    c = get_conn()
    db.set_setting(c, "progress_lock", "1" if b.on else "0")
    c.commit(); c.close()
    return {"ok": True}





class LoginBody(BaseModel):
    account: str
    pin: str


class PinBody(BaseModel):
    pin: str


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
        now = time.time()
        _fails.setdefault("ip:" + ip, []).append(now)
        _fails.setdefault("ac:" + account, []).append(now)
        raise HTTPException(401, "账号或密码不对")
    payload = {
        "user_id": user["id"], "family_id": user["family_id"], "role": user["role"],
        "term_id": user["term_id"], "iat": time.time(),
    }
    resp = JSONResponse({
        "ok": True, "role": user["role"], "name": user["name"], "account": user["account"],
        "force_pin_change": force,
    })
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
    c = db.connect(admin=True)
    try:
        if c.execute("SELECT 1 FROM users WHERE account=?", (account,)).fetchone():
            raise HTTPException(409, "这个账号已经有了")
        fid = "f-" + uuid.uuid4().hex[:8]
        uid = "parent-" + uuid.uuid4().hex[:8]
        c.execute("INSERT INTO families(id,name,created_at) VALUES(?,?,?)", (fid, (b.family_name or "我家").strip()[:20], db.now()))
        c.execute(
            "INSERT INTO users(id,family_id,role,name,avatar,pin_hash,term_id,account,created_at,force_pin_change) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (uid, fid, "parent", (b.name or "家长").strip()[:12], "", db.hash_pin(pin), None, account, db.now(), ""))
        c.execute("INSERT INTO profiles(user_id,family_id) VALUES(?,?) ON CONFLICT DO NOTHING", (uid, fid))
        db.initialize_family(c, fid)
        c.commit()
        user = {"id": uid, "family_id": fid, "role": "parent", "term_id": None}
    finally:
        c.close()
    resp = JSONResponse({"ok": True, "role": "parent", "account": account, "force_pin_change": False})
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
    c = db.connect(admin=True)
    try:
        inv = c.execute("SELECT * FROM invites WHERE code=?", (code,)).fetchone()
        if not inv:
            now = time.time()
            _fails.setdefault("ip:" + ip, []).append(now)
            _fails.setdefault("join:" + code, []).append(now)
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
        role = inv["role"] or "parent"
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


class InviteIn(BaseModel):
    role: str = "parent"  # parent | observer


@app.post("/api/admin/invite", dependencies=[Depends(require_parent)])
def invite_create(request: Request, b: InviteIn = InviteIn()):
    role = b.role if b.role in ("parent", "observer") else "parent"
    u = request.state.user
    code = uuid.uuid4().hex[:8].upper()
    c = get_conn()
    prot = c.execute("SELECT invite_protect FROM families WHERE id=?", (u["family_id"],)).fetchone()
    protect = int(prot["invite_protect"] or 0) if prot else 0
    max_uses = 1 if protect else 0
    expires_at = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds") if protect else None
    c.execute("INSERT INTO invites(code,family_id,role,created_at,max_uses,expires_at) VALUES(?,?,?,?,?,?)",
              (code, u["family_id"], role, db.now(), max_uses, expires_at))
    c.commit(); c.close()
    return {"code": code, "role": role, "protect": bool(protect)}


class InviteProtectIn(BaseModel):
    enabled: bool


@app.get("/api/admin/family", dependencies=[Depends(require_parent)])
def family_info(request: Request):
    u = request.state.user
    c = get_conn()
    row = c.execute("SELECT id, name, invite_protect FROM families WHERE id=?", (u["family_id"],)).fetchone()
    c.close()
    return {"name": row["name"], "invite_protect": int(row["invite_protect"] or 0)}


@app.put("/api/admin/family/invite_protect", dependencies=[Depends(require_parent)])
def family_invite_protect(b: InviteProtectIn, request: Request):
    u = request.state.user
    val = 1 if b.enabled else 0
    c = get_conn()
    c.execute("UPDATE families SET invite_protect=? WHERE id=?", (val, u["family_id"]))
    c.commit(); c.close()
    return {"invite_protect": val}


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
        "SELECT id, name, account, role FROM users WHERE family_id=? AND role IN ('parent','observer') ORDER BY created_at",
        (u["family_id"],)).fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.delete("/api/admin/members/{uid}", dependencies=[Depends(require_parent)])
def members_delete(uid: str, request: Request):
    u = request.state.user
    if uid == u["id"]:
        raise HTTPException(400, "不能删自己")
    c = get_conn()
    row = c.execute("SELECT * FROM users WHERE id=? AND family_id=?", (uid, u["family_id"])).fetchone()
    if not row or row["role"] not in ("parent", "observer"):
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


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = getattr(request.state, "user", None)
    return {"role": u["role"], "name": u["name"], "account": u["account"],
            "force_pin_change": bool(u.get("force_pin_change"))}


@app.post("/api/admin/pin", dependencies=[Depends(require_parent)])
def admin_change_pin(b: PinBody, request: Request):
    pin = _check_pin(b.pin, parent=True)
    u = request.state.user
    c = get_conn()
    c.execute("UPDATE users SET pin_hash=?, force_pin_change='' WHERE id=?", (db.hash_pin(pin), u["id"]))
    # ponytail: created_at 存 unix 浮点串，和 token.iat 比；别改成 ISO
    c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
              ("u:" + u["id"], str(time.time())))
    c.commit(); c.close()
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
    c.execute("INSERT INTO rewards(id,name,price,category,need_approval,family_id) VALUES(?,?,?,?,0,?)",
              (rid, b.name, b.price, b.category, _fam.get()))
    c.commit(); c.close()
    return {"id": rid}


@app.put("/api/admin/rewards/{rid}", dependencies=[Depends(require_parent)])
def reward_update(rid: str, b: RewardIn):
    c = get_conn()
    c.execute("UPDATE rewards SET name=?, price=?, category=? WHERE id=? AND family_id=?",
              (b.name, b.price, b.category, rid, _fam.get()))
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
    for kid in roster:
        db.apply_scope(c, fam, kid)
        pending.extend(c.execute(
            "SELECT rd.id, rd.date, rd.price, rd.status, rw.name, rd.kid_id FROM redemptions rd "
            "LEFT JOIN rewards rw ON rw.id=rd.reward_id WHERE rd.status='pending'").fetchall())
        done.extend(c.execute(
            "SELECT rd.id, rd.date, rd.price, rd.status, rw.name, rd.kid_id FROM redemptions rd "
            "LEFT JOIN rewards rw ON rw.id=rd.reward_id WHERE rd.status!='pending' ORDER BY rd.id DESC LIMIT 50").fetchall())
    db.apply_scope(c, fam, kid_id())
    c.close()
    pend = [dict(r) for r in pending]
    rest = [dict(r) for r in done]
    rest.sort(key=lambda x: x.get("id") or 0, reverse=True)
    pend.sort(key=lambda x: x.get("id") or 0, reverse=True)
    return pend + rest[:50]


@app.post("/api/admin/redemptions/{rid}/approve", dependencies=[Depends(require_parent)])
def redemption_approve(rid: str):
    c = get_conn()
    rd = c.execute("SELECT * FROM redemptions WHERE id=?", (rid,)).fetchone()
    if not rd:
        c.close(); raise HTTPException(404, "没找到这条兑换")
    if rd["status"] != "pending":
        c.close(); raise HTTPException(409, "这条已处理过")
    applicant = rd["kid_id"] or kid_id()
    if balance(c, applicant) < rd["price"]:
        c.close(); raise HTTPException(409, "阳光不够，还差 %d" % (rd["price"] - balance(c, applicant)))
    c.execute("UPDATE redemptions SET status='done' WHERE id=?", (rid,))
    rw = c.execute("SELECT name FROM rewards WHERE id=?", (rd["reward_id"],)).fetchone()
    insert_ledger(c, db.today(), -rd["price"], "redeem", f"red-{rid}", rw["name"] if rw else "兑换", kid=applicant)
    maybe_milestone(c, applicant)
    c.commit(); c.close()
    return {"ok": True}


@app.post("/api/admin/redemptions/{rid}/reject", dependencies=[Depends(require_parent)])
def redemption_reject(rid: str):
    c = get_conn()
    rd = c.execute("SELECT status FROM redemptions WHERE id=?", (rid,)).fetchone()
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
    rd = c.execute("SELECT status FROM redemptions WHERE id=?", (rid,)).fetchone()
    if not rd:
        c.close(); raise HTTPException(404, "没找到这条兑换")
    if rd["status"] != "done":
        c.close(); raise HTTPException(409, "先同意后才能标记兑现")
    c.execute("UPDATE redemptions SET status='delivered' WHERE id=?", (rid,))
    c.commit(); c.close()
    return {"ok": True}


# --- 单元测试成绩奖励 ---
TEST_BANDS = [(100, 30), (95, 20), (90, 15), (85, 10), (0, 5)]


def score_sunshine(score):
    for th, sun in TEST_BANDS:
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
    sun = score_sunshine(b.score)
    c = get_conn()
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
    rows = [dict(r) for r in c.execute("SELECT * FROM tests ORDER BY id DESC LIMIT 50").fetchall()]
    c.close()
    return rows


@app.delete("/api/admin/tests/{tid}", dependencies=[Depends(require_parent)])
def test_delete(tid: str):
    c = get_conn()
    r = c.execute("SELECT * FROM tests WHERE id=?", (tid,)).fetchone()
    if not r:
        c.close(); raise HTTPException(404, "没找到这条测试")
    c.execute("DELETE FROM tests WHERE id=?", (tid,))
    insert_ledger(c, db.today(), -r["sunshine"], "test_cancel", f"test-{tid}", "删除测试冲正")
    c.commit(); c.close()
    return {"ok": True}


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


@app.post("/api/admin/tasks", dependencies=[Depends(require_parent)])
def task_create(b: TaskIn):
    c = get_conn()
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom,family_id) VALUES(?,?,?,?,?,?,99,1,?)",
              (tid, b.subject_id, b.unit_id, b.action, b.title, b.sunshine, _fam.get()))
    c.commit(); c.close()
    return {"id": tid}


@app.put("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_update(tid: str, b: TaskIn):
    c = get_conn()
    c.execute("UPDATE tasks SET subject_id=?, unit_id=?, action=?, title=?, sunshine=? WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?",
              (b.subject_id, b.unit_id, b.action, b.title, b.sunshine, tid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_delete(tid: str):
    c = get_conn()
    c.execute("DELETE FROM tasks WHERE id=? AND COALESCE(custom,0)=1 AND family_id=?", (tid, _fam.get()))
    c.commit(); c.close()
    return {"ok": True}


# --- 每日任务（跳绳等） ---
class DailyTaskIn(BaseModel):
    subject_id: str
    name: str
    sunshine: int = 5
    bonus_per_metric: Optional[int] = 3
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
    c.execute("INSERT INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric,family_id) "
              "VALUES(?,?,?,?,'daily','personal_best',?,?)",
              (did, b.subject_id, b.name, b.sunshine, b.bonus_per_metric, _fam.get()))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"id": did}


@app.put("/api/admin/daily/{did}", dependencies=[Depends(require_parent)])
def daily_update(did: str, b: DailyTaskIn):
    c = get_conn()
    row = c.execute("SELECT family_id FROM daily_tasks WHERE id=?", (did,)).fetchone()
    if not row or not row["family_id"]:
        c.close(); raise HTTPException(403, "系统每日任务不能改")
    c.execute("UPDATE daily_tasks SET subject_id=?, name=?, sunshine=?, bonus_per_metric=? WHERE id=? AND family_id=?",
              (b.subject_id, b.name, b.sunshine, b.bonus_per_metric, did, _fam.get()))
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
        day_earned = c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date=? AND delta>0 AND kid_id=?", (d, kid)).fetchone()[0]
        day_spent = c.execute(
            "SELECT COALESCE(SUM(-delta),0) FROM ledger WHERE date=? AND reason='redeem' AND delta<0 AND kid_id=?", (d, kid)).fetchone()[0]
        days.append({"date": d, "weekday": WEEKDAYS[i], "earned": day_earned, "spent": day_spent})
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
        ") GROUP BY name ORDER BY cnt DESC", (kid, w_start, w_end, kid, w_start, w_end)).fetchall()
    checkins = c.execute(
        "SELECT COUNT(DISTINCT date) FROM checkins WHERE kid_id=? AND date BETWEEN ? AND ?", (kid, w_start, w_end)).fetchone()[0]
    weeks = []
    for i in range(3, -1, -1):
        wm = monday - timedelta(weeks=i)
        we = wm + timedelta(days=6)
        wk_earned = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ? AND delta>0 AND kid_id=?",
            (wm.isoformat(), we.isoformat(), kid)).fetchone()[0]
        weeks.append({"label": f"{wm.month}/{wm.day}", "earned": wk_earned, "week_start": wm.isoformat()})
    fam = _fam.get()
    kids_cmp = []
    if fam:
        roster = c.execute(
            "SELECT id, name FROM users WHERE family_id=? AND role='kid' ORDER BY created_at", (fam,)).fetchall()
        for kr in roster:
            db.apply_scope(c, fam, kr["id"])
            ke = c.execute(
                "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? AND delta>0",
                (kr["id"], w_start, w_end)).fetchone()[0]
            ks = c.execute(
                "SELECT COALESCE(SUM(-delta),0) FROM ledger WHERE kid_id=? AND date BETWEEN ? AND ? AND reason='redeem' AND delta<0",
                (kr["id"], w_start, w_end)).fetchone()[0]
            kids_cmp.append({"id": kr["id"], "name": kr["name"], "earned": ke, "spent": ks,
                             "streak": streak(c, kr["id"]), "current": kr["id"] == kid})
        db.apply_scope(c, fam, kid)
    out = {
        "week_start": w_start, "week_end": w_end,
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
        "kids": kids_cmp,
    }
    c.close()
    return out


class KidIn(BaseModel):
    name: str
    account: str = ""
    pin: str = ""
    term_id: str = "g5s1"


@app.get("/api/admin/kids", dependencies=[Depends(require_parent)])
def kids_list(request: Request):
    u = request.state.user
    c = get_conn()
    rows = c.execute(
        "SELECT id, name, account, term_id FROM users WHERE family_id=? AND role='kid' ORDER BY created_at",
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
    if b.term_id and not c.execute("SELECT 1 FROM terms WHERE id=?", (b.term_id,)).fetchone():
        c.close()
        raise HTTPException(404, "没有这个学期")
    kid = "kid-" + uuid.uuid4().hex[:8]
    c.execute(
        "INSERT INTO users(id,family_id,role,name,avatar,pin_hash,term_id,account,created_at,force_pin_change) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (kid, u["family_id"], "kid", name, "", db.hash_pin(pin), b.term_id or "g5s1", account, db.now(), ""))
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
    if not c.execute("SELECT 1 FROM terms WHERE id=?", (term,)).fetchone():
        c.close(); raise HTTPException(404, "没有这个学期")
    c.execute("UPDATE users SET name=?, term_id=? WHERE id=?", (name, term, kid))
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


@app.delete("/api/admin/kids/{kid}", dependencies=[Depends(require_parent)])
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


@app.get("/api/daily/{task_id}/history")
def daily_history(task_id: str):
    """孩子端查看某每日任务（跳绳等）的逐次记录（按日期升序），画趋势图用。"""
    c = get_conn()
    rows = c.execute(
        "SELECT date, metrics FROM completions WHERE task_id=? AND status='completed' AND kid_id=? "
        "ORDER BY date, id", (task_id, kid_id())).fetchall()
    c.close()
    return [{"date": r["date"], "metrics": (json.loads(r["metrics"]) if r["metrics"] else {})} for r in rows]


# ---------------- 静态前端（构建后由本后端直接托管） ----------------

_DIST = db.BASE.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    @app.get("/sw.js", include_in_schema=False)
    def _sw_js():
        from fastapi.responses import FileResponse
        return FileResponse(str(_DIST / "sw.js"), headers={"Cache-Control": "no-cache"})
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")