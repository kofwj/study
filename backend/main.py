# -*- coding: utf-8 -*-
"""阳光学习工作台 — P0 后端。

核心不变式：ledger 是唯一真相源；余额/累计/等级/连击全部由 ledger+日期推导。
「点错取消」= 一条负 delta 流水 + completion 置 cancelled，不删历史。
"""
import json
from datetime import datetime, timedelta

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db

app = FastAPI(title="阳光学习工作台")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

CHECKIN_SUN = 5  # 每日签到领 5 阳光


def get_conn():
    db.init_db()
    conn = db.connect()
    return conn


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
        "level": cur["name"], "level_id": cur["id"],
        "next": nxt["name"] if nxt else None,
        "next_need": nxt["min_sunshine"] if nxt else None,
        "progress": progress,
    }


def streak(c):
    rows = {r["date"] for r in c.execute("SELECT DISTINCT date FROM checkins").fetchall()}
    d = datetime.now().date()
    n = 0
    while d.isoformat() in rows:
        n += 1
        d -= timedelta(days=1)
    return n


# ---------------- 状态 ----------------

@app.get("/api/overview")
def overview():
    return level_info(get_conn())


@app.get("/api/tasks")
def tasks():
    c = get_conn()
    out = {
        "level": level_info(c),
        "streak": streak(c),
        "today_checkin": c.execute(
            "SELECT 1 FROM checkins WHERE date=?", (db.today(),)).fetchone() is not None,
        "subjects": [dict(r) for r in c.execute("SELECT * FROM subjects").fetchall()],
        "units": [{"id": r["id"], "name": r["name"]} for r in c.execute("SELECT id, name FROM units").fetchall()],
    }
    # 单元任务 + 完成状态
    tasks_rows = c.execute("SELECT * FROM tasks ORDER BY subject_id, sort").fetchall()
    done_ids = {r["task_id"] for r in c.execute(
        "SELECT DISTINCT task_id FROM completions WHERE status='completed'").fetchall()}
    out["tasks"] = [{**dict(t), "done": t["id"] in done_ids} for t in tasks_rows]
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
    if c.execute("SELECT 1 FROM checkins WHERE date=?", (t,)).fetchone():
        raise HTTPException(409, "今天已经签到过啦")
    c.execute("INSERT INTO checkins(date,sunshine,created_at) VALUES(?,?,?)", (t, CHECKIN_SUN, db.now()))
    db.insert_ledger(c, t, CHECKIN_SUN, "checkin", None, "每日签到")
    c.commit()
    return {"delta": CHECKIN_SUN, "level": level_info(c), "streak": streak(c)}


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
        if c.execute("SELECT 1 FROM completions WHERE task_id=? AND status='completed'", (tid,)).fetchone():
            raise HTTPException(409, "这项已经完成过啦")
        delta = row["sunshine"]
        cur = c.execute("INSERT INTO completions(task_id,date,status,sunshine,metrics,created_at) VALUES(?,?,?,?,?,?)",
                  (tid, t, "completed", delta, None, db.now()))
        db.insert_ledger(c, t, delta, "task", f"cmp-{cur.lastrowid}", row["title"])
        c.commit()
        return {"delta": delta, "bonus": 0, "level": level_info(c)}
    d = c.execute("SELECT * FROM daily_tasks WHERE id=?", (tid,)).fetchone()
    if d:
        if c.execute("SELECT 1 FROM completions WHERE task_id=? AND date=? AND status='completed'", (tid, t)).fetchone():
            raise HTTPException(409, "今天这项已完成过啦")
        bonus, detail = compute_daily_bonus(c, d, body.metrics)
        delta = d["sunshine"] + bonus
        mj = json.dumps(body.metrics) if body.metrics else None
        cur = c.execute("INSERT INTO completions(task_id,date,status,sunshine,metrics,created_at) VALUES(?,?,?,?,?,?)",
                  (tid, t, "completed", delta, mj, db.now()))
        db.insert_ledger(c, t, delta, "daily", f"cmp-{cur.lastrowid}",
                         d["name"] + ("（破纪录 +%d）" % bonus if bonus else ""))
        c.commit()
        return {"delta": delta, "bonus": bonus, "bonus_detail": detail, "level": level_info(c)}
    raise HTTPException(404, "没找到这个任务")


@app.post("/api/cancel")
def cancel(body: CompleteBody):
    c = get_conn()
    t = db.today()
    # 单元任务：整个学期内有已完成记录即可取消；每日任务：只取消今天这条
    comp = c.execute(
        "SELECT * FROM completions WHERE task_id=? AND status='completed' ORDER BY id DESC LIMIT 1",
        (body.task_id,)).fetchone()
    if not comp:
        raise HTTPException(404, "没有可取消的记录")
    c.execute("UPDATE completions SET status='cancelled' WHERE id=?", (comp["id"],))
    delta = -comp["sunshine"]
    db.insert_ledger(c, t, delta, "cancel", f"cmp-{comp['id']}", "点错取消")
    c.commit()
    return {"delta": delta, "level": level_info(c)}


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
        raise HTTPException(404, "没找到这个奖励")
    if balance(c) < r["price"]:
        raise HTTPException(409, "阳光不够哦，还差 %d" % (r["price"] - balance(c)))
    cur = c.execute("INSERT INTO redemptions(reward_id,date,price,status,created_at) VALUES(?,?,?,?,?)",
              (r["id"], db.today(), r["price"], "done", db.now()))
    db.insert_ledger(c, db.today(), -r["price"], "redeem", f"red-{cur.lastrowid}", r["name"])
    c.commit()
    return {"delta": -r["price"], "reward": r["name"], "level": level_info(c)}


# ---------------- 流水 ----------------

@app.get("/api/ledger")
def ledger(limit: int = 20):
    c = get_conn()
    return [dict(r) for r in c.execute(
        "SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# ---------------- 静态前端（构建后由本后端直接托管） ----------------

_DIST = db.BASE.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")