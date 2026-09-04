# -*- coding: utf-8 -*-
"""阳光学习工作台 — P0 后端。

核心不变式：ledger 是唯一真相源；余额/累计/等级/连击全部由 ledger+日期推导。
「点错取消」= 一条负 delta 流水 + completion 置 cancelled，不删历史。
"""
import json
import uuid
from datetime import datetime, timedelta

from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db

app = FastAPI(title="阳光学习工作台")
# 前端由 StaticFiles 同源托管，无需跨域；删掉 CORS 避免任何外部站点能调用接口

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
        "WHERE t.subject_id=? ORDER BY COALESCE(u.seq,99), t.sort", (subject_id,)).fetchall()
    return [r["id"] for r in rows]


def is_past(c, task_id, subject_id):
    cur = db.get_setting(c, "cursor_" + subject_id, "")
    if not cur:
        return False
    ids = subject_order(c, subject_id)
    if task_id not in ids or cur not in ids:
        return False
    return ids.index(task_id) < ids.index(cur)


def streak(c):
    # 连击 = 连续几天有「任何学习活动」（签到 / 完成任务 / 每日打卡 / 兑换成功）
    dates = {r["date"] for r in c.execute("SELECT DISTINCT date FROM checkins").fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM completions WHERE status='completed'").fetchall()}
    dates |= {r["date"] for r in c.execute(
        "SELECT DISTINCT date FROM redemptions WHERE status='done'").fetchall()}
    d = datetime.now().date()
    n = 0
    while d.isoformat() in dates:
        n += 1
        d -= timedelta(days=1)
    return n


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
    out = {
        "level": level_info(c),
        "streak": streak(c),
        "kid_name": db.get_setting(c, "kid_name", "乐乐"),
        "today": today_label(),
        "cursors": {r["key"][7:]: r["value"] for r in c.execute(
            "SELECT key,value FROM settings WHERE key LIKE 'cursor_%'").fetchall()},
        "today_checkin": c.execute(
            "SELECT 1 FROM checkins WHERE date=?", (db.today(),)).fetchone() is not None,
        "subjects": [dict(r) for r in c.execute("SELECT * FROM subjects").fetchall()],
        "units": [{"id": r["id"], "name": r["name"], "subject_id": r["subject_id"]}
                  for r in c.execute("SELECT id, name, subject_id FROM units").fetchall()],
    }
    # 单元任务 + 完成状态
    tasks_rows = c.execute(
        "SELECT t.* FROM tasks t LEFT JOIN units u ON u.id=t.unit_id "
        "ORDER BY t.subject_id, COALESCE(u.seq,99), t.sort").fetchall()
    done_ids = {r["task_id"] for r in c.execute(
        "SELECT DISTINCT task_id FROM completions WHERE status='completed'").fetchall()}
    out["tasks"] = [{**dict(t), "done": t["id"] in done_ids,
                     "past": is_past(c, t["id"], t["subject_id"])} for t in tasks_rows]
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
    cur = c.execute("INSERT OR IGNORE INTO checkins(date,sunshine,created_at) VALUES(?,?,?)",
                    (t, CHECKIN_SUN, db.now()))
    if cur.rowcount == 0:
        c.close()
        raise HTTPException(409, "今天已经签到过啦")
    db.insert_ledger(c, t, CHECKIN_SUN, "checkin", None, "每日签到")
    c.commit()
    res = {"delta": CHECKIN_SUN, "level": level_info(c), "streak": streak(c)}
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
        delta = row["sunshine"]
        cur = c.execute("INSERT OR IGNORE INTO completions(task_id,date,status,sunshine,metrics,kind,created_at) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (tid, t, "completed", delta, None, "unit", db.now()))
        if cur.rowcount == 0:
            c.close()
            raise HTTPException(409, "这项已经完成过啦")
        db.insert_ledger(c, t, delta, "task", f"cmp-{cur.lastrowid}", row["title"])
        c.commit()
        res = {"delta": delta, "bonus": 0, "level": level_info(c)}
        c.close()
        return res
    d = c.execute("SELECT * FROM daily_tasks WHERE id=?", (tid,)).fetchone()
    if d:
        bonus, detail = compute_daily_bonus(c, d, body.metrics)
        delta = d["sunshine"] + bonus
        mj = json.dumps(body.metrics) if body.metrics else None
        cur = c.execute("INSERT OR IGNORE INTO completions(task_id,date,status,sunshine,metrics,kind,created_at) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (tid, t, "completed", delta, mj, "daily", db.now()))
        if cur.rowcount == 0:
            c.close()
            raise HTTPException(409, "今天这项已完成过啦")
        db.insert_ledger(c, t, delta, "daily", f"cmp-{cur.lastrowid}",
                         d["name"] + ("（破纪录 +%d）" % bonus if bonus else ""))
        c.commit()
        res = {"delta": delta, "bonus": bonus, "bonus_detail": detail, "level": level_info(c)}
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


@app.post("/api/custom-task")
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
    c.execute("INSERT OR IGNORE INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?)",
              (unit_id, body.subject_id, "g5s1", 99, "自定义"))
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort,custom) VALUES(?,?,?,?,?,?,99,1)",
              (tid, body.subject_id, unit_id, "自定义", title, body.sunshine or 5))
    c.commit()
    c.close()
    return {"id": tid}


@app.delete("/api/tasks/{tid}")
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
    db.insert_ledger(c, t, delta, "cancel", f"cmp-{comp['id']}", "点错取消")
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
        c.execute("INSERT INTO redemptions(reward_id,date,price,status,created_at) VALUES(?,?,?,?,?)",
                  (r["id"], db.today(), r["price"], "pending", db.now()))
        c.commit()
        res = {"pending": True, "reward": r["name"], "level": level_info(c)}
        c.close()
        return res
    if balance(c) < r["price"]:
        c.close()
        raise HTTPException(409, "阳光不够哦，还差 %d" % (r["price"] - balance(c)))
    cur = c.execute("INSERT INTO redemptions(reward_id,date,price,status,created_at) VALUES(?,?,?,?,?)",
              (r["id"], db.today(), r["price"], "done", db.now()))
    db.insert_ledger(c, db.today(), -r["price"], "redeem", f"red-{cur.lastrowid}", r["name"])
    c.commit()
    res = {"delta": -r["price"], "reward": r["name"], "level": level_info(c)}
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

def require_admin(x_admin_pin: Optional[str] = Header(None)):
    c = get_conn()
    try:
        ok = x_admin_pin == db.get_setting(c, "admin_pin", "8888")
    finally:
        c.close()
    if not ok:
        raise HTTPException(401, "家长密码不对")


class CursorBody(BaseModel):
    subject_id: str
    task_id: str


@app.post("/api/admin/cursor", dependencies=[Depends(require_admin)])
def set_cursor(b: CursorBody):
    c = get_conn()
    db.set_setting(c, "cursor_" + b.subject_id, b.task_id)
    c.commit()
    return {"ok": True}


class PinBody(BaseModel):
    pin: str


@app.post("/api/admin/verify")
def admin_verify(b: PinBody):
    c = get_conn()
    ok = b.pin == db.get_setting(c, "admin_pin", "8888")
    c.close()
    if not ok:
        raise HTTPException(401, "家长密码不对")
    return {"ok": True}


@app.post("/api/admin/pin", dependencies=[Depends(require_admin)])
def admin_change_pin(b: PinBody):
    c = get_conn()
    db.set_setting(c, "admin_pin", b.pin)
    c.commit(); c.close()
    return {"ok": True}


# --- 商店 ---
class RewardIn(BaseModel):
    name: str
    price: int
    category: str = "其他"


@app.post("/api/admin/rewards", dependencies=[Depends(require_admin)])
def reward_create(b: RewardIn):
    c = get_conn()
    rid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO rewards(id,name,price,category,need_approval) VALUES(?,?,?,?,0)",
              (rid, b.name, b.price, b.category))
    c.commit(); c.close()
    return {"id": rid}


@app.put("/api/admin/rewards/{rid}", dependencies=[Depends(require_admin)])
def reward_update(rid: str, b: RewardIn):
    c = get_conn()
    c.execute("UPDATE rewards SET name=?, price=?, category=? WHERE id=?",
              (b.name, b.price, b.category, rid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/rewards/{rid}", dependencies=[Depends(require_admin)])
def reward_delete(rid: str):
    c = get_conn()
    c.execute("DELETE FROM rewards WHERE id=?", (rid,))
    c.commit(); c.close()
    return {"ok": True}


# --- 兑换审批 ---
@app.get("/api/admin/redemptions", dependencies=[Depends(require_admin)])
def redemptions_admin():
    c = get_conn()
    rows = c.execute(
        "SELECT rd.id, rd.date, rd.price, rd.status, rw.name FROM redemptions rd "
        "LEFT JOIN rewards rw ON rw.id=rd.reward_id ORDER BY rd.id DESC LIMIT 50").fetchall()
    c.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/redemptions/{rid}/approve", dependencies=[Depends(require_admin)])
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
    db.insert_ledger(c, db.today(), -rd["price"], "redeem", f"red-{rid}", rw["name"] if rw else "兑换")
    c.commit(); c.close()
    return {"ok": True}


@app.post("/api/admin/redemptions/{rid}/reject", dependencies=[Depends(require_admin)])
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


# --- 等级 ---
class RankIn(BaseModel):
    name: str
    min_sunshine: int


@app.get("/api/admin/ranks")
def ranks_admin():
    c = get_conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM ranks ORDER BY min_sunshine").fetchall()]
    c.close()
    return rows


@app.post("/api/admin/ranks", dependencies=[Depends(require_admin)])
def rank_create(b: RankIn):
    c = get_conn()
    c.execute("INSERT INTO ranks(id,name,min_sunshine,sort) VALUES(?,?,?,?)",
              (uuid.uuid4().hex[:8], b.name, b.min_sunshine, b.min_sunshine))
    c.commit(); c.close()
    return {"ok": True}


@app.put("/api/admin/ranks/{rid}", dependencies=[Depends(require_admin)])
def rank_update(rid: str, b: RankIn):
    c = get_conn()
    c.execute("UPDATE ranks SET name=?, min_sunshine=? WHERE id=?",
              (b.name, b.min_sunshine, rid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/ranks/{rid}", dependencies=[Depends(require_admin)])
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


@app.post("/api/admin/tasks", dependencies=[Depends(require_admin)])
def task_create(b: TaskIn):
    c = get_conn()
    tid = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO tasks(id,subject_id,unit_id,action,title,sunshine,sort) VALUES(?,?,?,?,?,?,99)",
              (tid, b.subject_id, b.unit_id, b.action, b.title, b.sunshine))
    c.commit(); c.close()
    return {"id": tid}


@app.put("/api/admin/tasks/{tid}", dependencies=[Depends(require_admin)])
def task_update(tid: str, b: TaskIn):
    c = get_conn()
    c.execute("UPDATE tasks SET subject_id=?, unit_id=?, action=?, title=?, sunshine=? WHERE id=?",
              (b.subject_id, b.unit_id, b.action, b.title, b.sunshine, tid))
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/tasks/{tid}", dependencies=[Depends(require_admin)])
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


@app.post("/api/admin/daily", dependencies=[Depends(require_admin)])
def daily_create(b: DailyTaskIn):
    c = get_conn()
    did = uuid.uuid4().hex[:8]
    c.execute("INSERT INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric) "
              "VALUES(?,?,?,?,'daily','personal_best',?)",
              (did, b.subject_id, b.name, b.sunshine, b.bonus_per_metric))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"id": did}


@app.put("/api/admin/daily/{did}", dependencies=[Depends(require_admin)])
def daily_update(did: str, b: DailyTaskIn):
    c = get_conn()
    c.execute("UPDATE daily_tasks SET subject_id=?, name=?, sunshine=?, bonus_per_metric=? WHERE id=?",
              (b.subject_id, b.name, b.sunshine, b.bonus_per_metric, did))
    _replace_metrics(c, did, b.metrics)
    c.commit(); c.close()
    return {"ok": True}


@app.delete("/api/admin/daily/{did}", dependencies=[Depends(require_admin)])
def daily_delete(did: str):
    c = get_conn()
    c.execute("DELETE FROM daily_metrics WHERE task_id=?", (did,))
    c.execute("DELETE FROM daily_tasks WHERE id=?", (did,))
    c.commit(); c.close()
    return {"ok": True}


# ---------------- 周报（家长端） -------------


@app.get("/api/admin/weekly", dependencies=[Depends(require_admin)])
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
        "by_subject": [dict(r) for r in by_subject],
    }
    c.close()
    return out


# ---------------- 静态前端（构建后由本后端直接托管） ----------------

_DIST = db.BASE.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")