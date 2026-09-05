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

_kid = contextvars.ContextVar("kid", default=db.DEFAULT_KID)
_fam = contextvars.ContextVar("fam", default=db.DEFAULT_FAMILY)
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
    return _kid.get()


def insert_ledger(c, date, delta, reason, ref_id, note):
    db.insert_ledger(c, date, delta, reason, ref_id, note, kid_id=kid_id())


def active_term(c):
    return db.get_setting(c, "active_term", "g5s1")


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
    c = db.connect()  # users/revoked 无 RLS；勿走 get_conn（会套当前请求 scope）
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


PUBLIC_API = {"/api/health", "/api/auth/login", "/api/auth/logout"}


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_API:
        return await call_next(request)
    u = _user_from_request(request)
    if not u:
        return JSONResponse({"detail": "未登录"}, 401)
    kid = u["id"] if u["role"] == "kid" else (request.query_params.get("selected_kid") or db.DEFAULT_KID)
    if u["role"] == "parent" and kid != db.DEFAULT_KID:
        c = db.connect()
        try:
            row = c.execute("SELECT family_id FROM users WHERE id=? AND role='kid'", (kid,)).fetchone()
        finally:
            c.close()
        if not row or row["family_id"] != u["family_id"]:
            return JSONResponse({"detail": "未登录"}, 403)
    tok_k, tok_f = _kid.set(kid), _fam.set(u["family_id"])
    request.state.user = u
    try:
        return await call_next(request)
    finally:
        _kid.reset(tok_k)
        _fam.reset(tok_f)


def require_parent(request: Request):
    u = getattr(request.state, "user", None)
    if not u or u["role"] != "parent":
        raise HTTPException(403, "需要家长账号")
    return u


def earned(c):
    # 累计获得：赚/取消都算（正负抵消），唯独「兑换消费(redeem)」不算 → 消费不掉级
    return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE reason != 'redeem'").fetchone()[0]


def balance(c):
    return c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger").fetchone()[0]


def level_info(c):
    e = earned(c)
    ranks = c.execute("SELECT * FROM ranks ORDER BY min_sunshine").fetchall()
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
        "level": cur["name"], "level_id": cur["id"], "level_icon": cur["icon"] or "⭐",
        "next": nxt["name"] if nxt else None,
        "next_icon": (nxt["icon"] or "⭐") if nxt else None,
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
        "WHERE t.subject_id=? AND (u.term_id=? OR COALESCE(t.custom,0)=1) "
        "ORDER BY COALESCE(u.seq,99), t.sort", (subject_id, active_term(c))).fetchall()
    return [r["id"] for r in rows]


def is_past(c, task_id, subject_id):
    cur = db.get_setting(c, "cursor_" + subject_id, "")
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
        "WHERE u.term_id=? OR COALESCE(t.custom,0)=1", (term,)).fetchall()}
    custom_ids = {r["id"] for r in c.execute("SELECT id FROM tasks WHERE custom=1").fetchall()}
    locked = set()
    for sid in {r[0] for r in c.execute(
            "SELECT DISTINCT t.subject_id FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
            "WHERE u.term_id=? OR COALESCE(t.custom,0)=1", (term,)).fetchall()}:
        ids = subject_order(c, sid)
        cur_seq = None
        for tid in ids:
            if tid in custom_ids:
                continue
            done = c.execute("SELECT 1 FROM completions WHERE task_id=? AND status='completed'",
                            (tid,)).fetchone() is not None
            if done or is_past(c, tid, sid):
                continue
            cur_seq = tseq.get(tid, 0)
            break
        if cur_seq is not None:
            locked |= {tid for tid in ids if tid not in custom_ids and tseq.get(tid, 0) > cur_seq}
    return locked


def streak(c):
    # 连击 = 连续几天有「任何学习活动」（签到 / 完成任务 / 每日打卡 / 兑换成功）
    dates = {r["date"] for r in c.execute("SELECT DISTINCT date FROM checkins").fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM completions WHERE status='completed'").fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM redemptions WHERE status IN ('done','delivered')").fetchall()}
    d = datetime.now().date()
    n = 0
    while d.isoformat() in dates:
        n += 1
        d -= timedelta(days=1)
    return n


# 连续坚持里程碑（一次性奖励，防通胀）：第 7/14/30 天各发一次
MILESTONES = [(7, 20), (14, 50), (30, 100)]


def maybe_milestone(c):
    """连击达 7/14/30 天各发一次一次性阳光（用 settings 标记，绝不重复）。返回 [(天数, 奖励)]。"""
    s = streak(c)
    got = []
    for days, bonus in MILESTONES:
        key = f"milestone_{days}"
        if s >= days and not db.get_setting(c, key, ""):
            db.set_setting(c, key, db.today())
            insert_ledger(c, db.today(), bonus, "milestone", key, f"连续坚持 {days} 天")
            got.append((days, bonus))
    return got


# 成就徽章（孩子端「成就墙」）
ACHIEVEMENTS = [
    {"id": "first",    "icon": "🌱", "name": "初来乍到", "desc": "完成第 1 张任务卡", "target": 1},
    {"id": "cn10",     "icon": "📖", "name": "语文十卡", "desc": "完成 10 张语文卡", "target": 10},
    {"id": "ma10",     "icon": "➗", "name": "数学十卡", "desc": "完成 10 张数学卡", "target": 10},
    {"id": "en10",     "icon": "🔤", "name": "英语十卡", "desc": "完成 10 张英语卡", "target": 10},
    {"id": "all100",   "icon": "🏅", "name": "百卡达成", "desc": "累计完成 100 张单元卡", "target": 100},
    {"id": "sport",    "icon": "🏃", "name": "运动健将", "desc": "每日运动打卡 10 次", "target": 10},
    {"id": "daily30",  "icon": "📅", "name": "每日全勤", "desc": "每日任务累计打卡 30 次", "target": 30},
    {"id": "go10",     "icon": "⚫", "name": "围棋小棋手", "desc": "围棋对弈打卡 10 次", "target": 10},
    {"id": "calc10",   "icon": "🧮", "name": "口算达人", "desc": "每日口算打卡 10 次", "target": 10},
    {"id": "streak7",  "icon": "🔥", "name": "坚持一周", "desc": "连续坚持 7 天", "target": 7},
    {"id": "streak14", "icon": "🚀", "name": "坚持半月", "desc": "连续坚持 14 天", "target": 14},
    {"id": "streak30", "icon": "🌕", "name": "坚持满月", "desc": "连续坚持 30 天", "target": 30},
    {"id": "test100",  "icon": "💯", "name": "满分学霸", "desc": "单元测试考 100 分", "target": 100},
    {"id": "shop1",    "icon": "🛒", "name": "初尝战果", "desc": "第一次兑换奖励", "target": 1},
    {"id": "shop5",    "icon": "🎁", "name": "兑换小能手", "desc": "累计兑换 5 次", "target": 5},
    {"id": "box5",     "icon": "🎰", "name": "盲盒收藏家", "desc": "开 5 个连击盲盒", "target": 5},
    {"id": "custom10", "icon": "✨", "name": "自律之星", "desc": "完成家长任务 10 次", "target": 10},
    {"id": "sun500",   "icon": "💰", "name": "阳光富翁", "desc": "累计获得 500 阳光", "target": 500},
    {"id": "sun2000",  "icon": "💎", "name": "阳光大佬", "desc": "累计获得 2000 阳光", "target": 2000},
    {"id": "sun5000",  "icon": "👑", "name": "阳光传说", "desc": "累计获得 5000 阳光", "target": 5000},
]


@app.get("/api/achievements")
def achievements():
    c = get_conn()
    total = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed'").fetchone()[0]
    unit_done = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='unit'").fetchone()[0]
    sport = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily'").fetchone()[0]
    go_n = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily' AND task_id='go-play'").fetchone()[0]
    calc_n = c.execute("SELECT COUNT(*) FROM completions WHERE status='completed' AND kind='daily' AND task_id='ma-calc'").fetchone()[0]
    custom_n = c.execute(
        "SELECT COUNT(*) FROM completions c JOIN tasks t ON t.id=c.task_id "
        "WHERE c.status='completed' AND COALESCE(t.custom,0)=1").fetchone()[0]
    shop_n = c.execute("SELECT COUNT(*) FROM redemptions WHERE status IN ('done','delivered')").fetchone()[0]
    best_test = c.execute("SELECT COALESCE(MAX(score),0) FROM tests").fetchone()[0]
    box_n = int(db.get_setting(c, "box_opened", "0"))
    s = streak(c)
    e = earned(c)
    done_by_subj = {r[0]: r[1] for r in c.execute(
        "SELECT t.subject_id, COUNT(*) FROM completions c JOIN tasks t ON t.id=c.task_id "
        "WHERE c.status='completed' GROUP BY t.subject_id").fetchall()}
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
    opened = int(db.get_setting(c, "box_opened", "0"))
    earned = s // BOX_INTERVAL
    c.close()
    return {"avail": max(0, earned - opened), "opened": opened, "earned": earned, "streak": s}


@app.post("/api/open_box")
def open_box():
    c = get_conn()
    s = streak(c)
    opened = int(db.get_setting(c, "box_opened", "0"))
    if s // BOX_INTERVAL <= opened:
        c.close()
        raise HTTPException(409, "还没有可开的宝箱，再坚持坚持吧！")
    bonus = random.randint(3, 10)
    db.set_setting(c, "box_opened", str(opened + 1))
    insert_ledger(c, db.today(), bonus, "box", f"box-{opened + 1}", "连击宝箱")
    c.commit()
    res = {"delta": bonus, "streak": streak(c), "level": level_info(c)}
    c.close()
    return res


@app.get("/api/ranks")
def ranks_public():
    """成长路径地图用：返回全部等级 + 当前累计阳光。"""
    c = get_conn()
    ranks = [dict(r) for r in c.execute("SELECT * FROM ranks ORDER BY min_sunshine").fetchall()]
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
        "kid_name": db.get_setting(c, "kid_name", "乐乐"),
        "today": today_label(),
        "active_term": term,
        "term": dict(term_row) if term_row else {"id": term, "label": term},
        "terms": [dict(r) for r in c.execute("SELECT * FROM terms ORDER BY id").fetchall()],
        "cursors": {r["key"][7:]: r["value"] for r in c.execute(
            "SELECT key,value FROM settings WHERE key LIKE ?", ("cursor_%",)).fetchall()},
        "today_checkin": c.execute(
            "SELECT 1 FROM checkins WHERE date=?", (db.today(),)).fetchone() is not None,
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
        "WHERE u.term_id=? OR COALESCE(t.custom,0)=1 "
        "ORDER BY t.subject_id, COALESCE(u.seq,99), t.sort", (term,)).fetchall()
    done_ids = {r["task_id"] for r in c.execute(
        "SELECT DISTINCT task_id FROM completions WHERE status='completed'").fetchall()}
    out["progress_lock"] = db.get_setting(c, "progress_lock", "1")
    locked_ids = locked_task_ids(c)
    out["tasks"] = [{**dict(t), "done": t["id"] in done_ids,
                     "past": is_past(c, t["id"], t["subject_id"]),
                     "locked": t["id"] in locked_ids} for t in tasks_rows]
    # 每日任务 + 今日状态 + 历史最好
    dts = c.execute("SELECT * FROM daily_tasks").fetchall()
    daily = []
    for d in dts:
        dct = dict(d)
        comp_today = c.execute(
            "SELECT * FROM completions WHERE task_id=? AND date=? AND status='completed' ORDER BY id DESC LIMIT 1",
            (d["id"], db.today())).fetchone()
        dct["done_today"] = comp_today is not None
        dct["today_metrics"] = json.loads(comp_today["metrics"]) if comp_today and comp_today["metrics"] else None
        dct["metrics"] = [dict(m) for m in c.execute(
            "SELECT * FROM daily_metrics WHERE task_id=?", (d["id"],)).fetchall()]
        # 历史最好（个人纪录）
        pb = {}
        for m in c.execute("SELECT * FROM daily_metrics WHERE task_id=?", (d["id"],)).fetchall():
            best = None
            for comp in c.execute(
                "SELECT metrics FROM completions WHERE task_id=? AND status='completed' AND metrics IS NOT NULL",
                (d["id"],)).fetchall():
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
            "SELECT metrics FROM completions WHERE task_id=? AND status='completed' AND metrics IS NOT NULL",
            (d["id"],)).fetchall():
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
    d = c.execute("SELECT * FROM daily_tasks WHERE id=?", (tid,)).fetchone()
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


@app.post("/api/kid-name")
def set_kid_name(body: KidNameBody):
    name = (body.name or "").strip()[:12]
    if not name:
        raise HTTPException(400, "名字不能为空")
    c = get_conn()
    db.set_setting(c, "kid_name", name)
    c.commit()
    c.close()
    return {"name": name}


class CustomTaskBody(BaseModel):
    subject_id: str
    title: str
    sunshine: int = 5


@app.post("/api/custom-task", dependencies=[Depends(require_parent)])
def custom_task(body: CustomTaskBody):
    title = (body.title or "").strip()[:40]
    if not title:
        raise HTTPException(400, "填一下任务名称")
    c = get_conn()
    if not c.execute("SELECT 1 FROM subjects WHERE id=?", (body.subject_id,)).fetchone():
        c.close()
        raise HTTPException(404, "没有这个学科")
    # 自定义任务归到独立的「自定义」单元（seq=99 排最后），不混进教材单元
    unit_id = f"custom-{body.subject_id}"
    c.execute("INSERT INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
              (unit_id, body.subject_id, active_term(c), 99, "自定义"))
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom,family_id) VALUES(?,?,?,?,?,?,99,1,?)",
              (tid, body.subject_id, unit_id, "自定义", title, body.sunshine or 5, db.DEFAULT_FAMILY))
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
    c.execute("DELETE FROM tasks WHERE id=?", (tid,))
    c.commit()
    c.close()
    return {"ok": True}


@app.post("/api/cancel")
def cancel(body: CompleteBody):
    c = get_conn()
    t = db.today()
    # 单元任务：整个学期内有已完成记录即可取消；每日任务：只取消今天这条
    comp = c.execute(
        "SELECT * FROM completions WHERE task_id=? AND status='completed' ORDER BY id DESC LIMIT 1",
        (body.task_id,)).fetchone()
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
    return [dict(r) for r in c.execute("SELECT * FROM rewards ORDER BY price").fetchall()]


class RedeemBody(BaseModel):
    reward_id: str


@app.post("/api/rewards/redeem")
def redeem(body: RedeemBody):
    c = get_conn()
    r = c.execute("SELECT * FROM rewards WHERE id=?", (body.reward_id,)).fetchone()
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
        "SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# ---------------- 管理端（家长，需 PIN） -------------


class CursorBody(BaseModel):
    subject_id: str
    task_id: str


@app.post("/api/admin/cursor", dependencies=[Depends(require_parent)])
def set_cursor(b: CursorBody):
    c = get_conn()
    db.set_setting(c, "cursor_" + b.subject_id, b.task_id)
    c.commit()
    return {"ok": True}


class LockBody(BaseModel):
    on: bool = True


@app.post("/api/admin/progress-lock", dependencies=[Depends(require_parent)])
def set_progress_lock(b: LockBody):
    c = get_conn()
    db.set_setting(c, "progress_lock", "1" if b.on else "0")
    c.commit(); c.close()
    return {"ok": True}


class TermBody(BaseModel):
    term_id: str


@app.post("/api/admin/term", dependencies=[Depends(require_parent)])
def set_active_term(b: TermBody):
    c = get_conn()
    if not c.execute("SELECT 1 FROM terms WHERE id=?", (b.term_id,)).fetchone():
        c.close()
        raise HTTPException(404, "没有这个学期")
    db.set_setting(c, "active_term", b.term_id)
    c.commit(); c.close()
    return {"ok": True, "term_id": b.term_id}


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
    c = db.connect()
    try:
        u = c.execute("SELECT * FROM users WHERE account=?", (account,)).fetchone()
        ok = bool(u) and db.verify_pin(b.pin, u["pin_hash"] or "")
        force = bool(db.get_setting(c, "force_pin_change", "")) if ok else False
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


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = getattr(request.state, "user", None)
    c = get_conn()
    force = bool(db.get_setting(c, "force_pin_change", ""))
    c.close()
    return {"role": u["role"], "name": u["name"], "account": u["account"], "force_pin_change": force}


@app.post("/api/admin/pin", dependencies=[Depends(require_parent)])
def admin_change_pin(b: PinBody, request: Request):
    pin = (b.pin or "").strip()
    if len(pin) < 4:
        raise HTTPException(400, "密码至少 4 位")
    u = request.state.user
    c = get_conn()
    c.execute("UPDATE users SET pin_hash=? WHERE id=?", (db.hash_pin(pin), u["id"]))
    # ponytail: created_at 存 unix 浮点串，和 token.iat 比；别改成 ISO
    c.execute("INSERT INTO revoked(jti,created_at) VALUES(?,?) ON CONFLICT(jti) DO UPDATE SET created_at=excluded.created_at",
              ("u:" + u["id"], str(time.time())))
    db.set_setting(c, "force_pin_change", "")
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
              (rid, b.name, b.price, b.category, db.DEFAULT_FAMILY))
    c.commit(); c.close()
    return {"id": rid}


@app.put("/api/admin/rewards/{rid}", dependencies=[Depends(require_parent)])
def reward_update(rid: str, b: RewardIn):
    c = get_conn()
    c.execute("UPDATE rewards SET name=?, price=?, category=? WHERE id=?",
              (b.name, b.price, b.category, rid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/rewards/{rid}", dependencies=[Depends(require_parent)])
def reward_delete(rid: str):
    c = get_conn()
    c.execute("DELETE FROM rewards WHERE id=?", (rid,))
    c.commit(); c.close()
    return {"ok": True}


# --- 兑换审批 ---
@app.get("/api/admin/redemptions", dependencies=[Depends(require_parent)])
def redemptions_admin():
    c = get_conn()
    rows = c.execute(
        "SELECT rd.id, rd.date, rd.price, rd.status, rw.name FROM redemptions rd "
        "LEFT JOIN rewards rw ON rw.id=rd.reward_id ORDER BY rd.id DESC LIMIT 50").fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/redemptions/{rid}/approve", dependencies=[Depends(require_parent)])
def redemption_approve(rid: str):
    c = get_conn()
    rd = c.execute("SELECT * FROM redemptions WHERE id=?", (rid,)).fetchone()
    if not rd:
        c.close(); raise HTTPException(404, "没找到这条兑换")
    if rd["status"] != "pending":
        c.close(); raise HTTPException(409, "这条已处理过")
    if balance(c) < rd["price"]:
        c.close(); raise HTTPException(409, "阳光不够，还差 %d" % (rd["price"] - balance(c)))
    c.execute("UPDATE redemptions SET status='done' WHERE id=?", (rid,))
    rw = c.execute("SELECT name FROM rewards WHERE id=?", (rd["reward_id"],)).fetchone()
    insert_ledger(c, db.today(), -rd["price"], "redeem", f"red-{rid}", rw["name"] if rw else "兑换")
    maybe_milestone(c)
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
    rows = [dict(r) for r in c.execute("SELECT * FROM ranks ORDER BY min_sunshine").fetchall()]
    c.close()
    return rows


@app.post("/api/admin/ranks", dependencies=[Depends(require_parent)])
def rank_create(b: RankIn):
    c = get_conn()
    c.execute("INSERT INTO ranks(id,name,min_sunshine,sort,family_id) VALUES(?,?,?,?,?)",
              (uuid.uuid4().hex[:8], b.name, b.min_sunshine, b.min_sunshine, db.DEFAULT_FAMILY))
    c.commit(); c.close()
    return {"ok": True}


@app.put("/api/admin/ranks/{rid}", dependencies=[Depends(require_parent)])
def rank_update(rid: str, b: RankIn):
    c = get_conn()
    c.execute("UPDATE ranks SET name=?, min_sunshine=? WHERE id=?",
              (b.name, b.min_sunshine, rid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/ranks/{rid}", dependencies=[Depends(require_parent)])
def rank_delete(rid: str):
    c = get_conn()
    r = c.execute("SELECT min_sunshine FROM ranks WHERE id=?", (rid,)).fetchone()
    if r and r["min_sunshine"] == 0:
        c.close()
        raise HTTPException(400, "基础等级（0阳光）不能删")
    c.execute("DELETE FROM ranks WHERE id=?", (rid,))
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
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort) VALUES(?,?,?,?,?,?,99)",
              (tid, b.subject_id, b.unit_id, b.action, b.title, b.sunshine))
    c.commit(); c.close()
    return {"id": tid}


@app.put("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_update(tid: str, b: TaskIn):
    c = get_conn()
    c.execute("UPDATE tasks SET subject_id=?, unit_id=?, action=?, title=?, sunshine=? WHERE id=?",
              (b.subject_id, b.unit_id, b.action, b.title, b.sunshine, tid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/tasks/{tid}", dependencies=[Depends(require_parent)])
def task_delete(tid: str):
    c = get_conn()
    c.execute("DELETE FROM tasks WHERE id=?", (tid,))
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
    c.execute("INSERT INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric) "
              "VALUES(?,?,?,?,'daily','personal_best',?)",
              (did, b.subject_id, b.name, b.sunshine, b.bonus_per_metric))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"id": did}


@app.put("/api/admin/daily/{did}", dependencies=[Depends(require_parent)])
def daily_update(did: str, b: DailyTaskIn):
    c = get_conn()
    c.execute("UPDATE daily_tasks SET subject_id=?, name=?, sunshine=?, bonus_per_metric=? WHERE id=?",
              (b.subject_id, b.name, b.sunshine, b.bonus_per_metric, did))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/daily/{did}", dependencies=[Depends(require_parent)])
def daily_delete(did: str):
    c = get_conn()
    c.execute("DELETE FROM daily_metrics WHERE task_id=?", (did,))
    c.execute("DELETE FROM daily_tasks WHERE id=?", (did,))
    c.commit(); c.close()
    return {"ok": True}


# ---------------- 周报（家长端） -------------


@app.get("/api/admin/weekly", dependencies=[Depends(require_parent)])
def weekly():
    c = get_conn()
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    days = []
    for i in range(7):
        d = (monday + timedelta(days=i)).isoformat()
        day_earned = c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date=? AND delta>0", (d,)).fetchone()[0]
        day_spent = c.execute(
            "SELECT COALESCE(SUM(-delta),0) FROM ledger WHERE date=? AND reason='redeem' AND delta<0", (d,)).fetchone()[0]
        days.append({"date": d, "weekday": WEEKDAYS[i], "earned": day_earned, "spent": day_spent})
    w_start, w_end = days[0]["date"], days[6]["date"]
    net = c.execute(
        "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ?", (w_start, w_end)).fetchone()[0]
    # 单元任务 + 每日任务（跳绳等）都计入学科完成
    by_subject = c.execute(
        "SELECT name, SUM(cnt) cnt, SUM(sun) sun FROM ("
        "  SELECT s.name name, COUNT(*) cnt, COALESCE(SUM(c.sunshine),0) sun "
        "  FROM completions c JOIN tasks t ON t.id=c.task_id JOIN subjects s ON s.id=t.subject_id "
        "  WHERE c.status='completed' AND c.date BETWEEN ? AND ? GROUP BY s.name "
        "  UNION ALL "
        "  SELECT s.name, COUNT(*), COALESCE(SUM(c.sunshine),0) "
        "  FROM completions c JOIN daily_tasks t ON t.id=c.task_id JOIN subjects s ON s.id=t.subject_id "
        "  WHERE c.status='completed' AND c.date BETWEEN ? AND ? GROUP BY s.name "
        ") GROUP BY name ORDER BY cnt DESC", (w_start, w_end, w_start, w_end)).fetchall()
    checkins = c.execute(
        "SELECT COUNT(DISTINCT date) FROM checkins WHERE date BETWEEN ? AND ?", (w_start, w_end)).fetchone()[0]
    weeks = []
    for i in range(3, -1, -1):
        wm = monday - timedelta(weeks=i)
        we = wm + timedelta(days=6)
        wk_earned = c.execute(
            "SELECT COALESCE(SUM(delta),0) FROM ledger WHERE date BETWEEN ? AND ? AND delta>0",
            (wm.isoformat(), we.isoformat())).fetchone()[0]
        weeks.append({"label": f"{wm.month}/{wm.day}", "earned": wk_earned, "week_start": wm.isoformat()})
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
    }
    c.close()
    return out


@app.get("/api/daily/{task_id}/history")
def daily_history(task_id: str):
    """孩子端查看某每日任务（跳绳等）的逐次记录（按日期升序），画趋势图用。"""
    c = get_conn()
    rows = c.execute(
        "SELECT date, metrics FROM completions WHERE task_id=? AND status='completed' "
        "ORDER BY date, id", (task_id,)).fetchall()
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