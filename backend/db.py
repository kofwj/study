# -*- coding: utf-8 -*-
"""SQLite 存储 + 初始化 + 种子数据。

流水账(ledger)是唯一真相源：余额=SUM(全部 delta)、累计获得=SUM(正 delta)、
等级/连击都由累计获得与日期推导，不单独硬存，保证「点错取消」公平可审计。
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = Path(os.environ.get("SUNSHINE_DB", BASE / "sunshine.db"))
SEED_JSON = BASE.parent / "data" / "tasks.seed.json"

# 兑换商店（P0 内置示例，家长后续在管理端增删改）
REWARDS = [
    {"id": "tv30",  "name": "看动画30分钟",  "price": 30,  "category": "娱乐", "need_approval": 0},
    {"id": "park",  "name": "周末去游乐场",  "price": 100, "category": "出行", "need_approval": 1},
    {"id": "wish",  "name": "心愿礼物",      "price": 200, "category": "礼物", "need_approval": 1},
]

# 等级（累计获得阳光阈值，消费不掉级）
# 参照 Duolingo/ClassDojo：前期密集升级给即时反馈，后期门槛递增；emoji 递进形象
RANKS_VER = "v3"
ALL_SUBJECTS = ["语文", "数学", "英语", "科学", "道法", "体育", "音美", "综合"]

# 满级 5000 = 约一学期坚持（日产出 ~60），共 10 档，前期密度后期递增
RANKS = [
    {"id": "r1",  "name": "阳光萌新",   "min_sunshine": 0,    "icon": "🌱"},
    {"id": "r2",  "name": "阳光小苗",   "min_sunshine": 50,   "icon": "🌿"},
    {"id": "r3",  "name": "阳光小能手", "min_sunshine": 150,  "icon": "🌼"},
    {"id": "r4",  "name": "阳光达人",   "min_sunshine": 350,  "icon": "⭐"},
    {"id": "r5",  "name": "阳光之星",   "min_sunshine": 700,  "icon": "🔥"},
    {"id": "r6",  "name": "阳光学霸",   "min_sunshine": 1200, "icon": "🏆"},
    {"id": "r7",  "name": "阳光大师",   "min_sunshine": 2000, "icon": "🥇"},
    {"id": "r8",  "name": "阳光传说",   "min_sunshine": 3000, "icon": "💎"},
    {"id": "r9",  "name": "阳光战神",   "min_sunshine": 4000, "icon": "🚀"},
    {"id": "r10", "name": "传奇学神",   "min_sunshine": 5000, "icon": "👑"},
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS terms (id TEXT PRIMARY KEY, label TEXT, grade TEXT, term TEXT, version TEXT);
CREATE TABLE IF NOT EXISTS units (id TEXT PRIMARY KEY, subject_id TEXT, term_id TEXT, seq INTEGER, name TEXT);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, subject_id TEXT, unit_id TEXT, action TEXT, title TEXT, detail TEXT DEFAULT '', sunshine INTEGER, sort INTEGER, custom INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS daily_tasks (
  id TEXT PRIMARY KEY, subject_id TEXT, name TEXT, sunshine INTEGER, frequency TEXT,
  bonus_type TEXT, bonus_per_metric INTEGER);
CREATE TABLE IF NOT EXISTS daily_metrics (
  task_id TEXT, id TEXT, label TEXT, unit TEXT, direction TEXT, note TEXT, PRIMARY KEY (task_id, id));
CREATE TABLE IF NOT EXISTS rewards (
  id TEXT PRIMARY KEY, name TEXT, price INTEGER, category TEXT, need_approval INTEGER);
CREATE TABLE IF NOT EXISTS ranks (
  id TEXT PRIMARY KEY, name TEXT, min_sunshine INTEGER, sort INTEGER, icon TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS checkins (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, sunshine INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS completions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'completed', sunshine INTEGER NOT NULL, metrics TEXT, created_at TEXT,
  kind TEXT NOT NULL DEFAULT 'unit');
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, delta INTEGER NOT NULL,
  reason TEXT, ref_id TEXT, note TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS redemptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, reward_id TEXT, date TEXT, price INTEGER,
  status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT, unit_id TEXT, score INTEGER, sunshine INTEGER,
  note TEXT, date TEXT, created_at TEXT);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def connect():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def seed_ranks(conn):
    """重写默认等级（含图标）+ 记录版本号；版本不变时不再覆盖，尊重家长后续改动。"""
    conn.execute("DELETE FROM ranks")
    for i, r in enumerate(RANKS):
        conn.execute("INSERT INTO ranks(id,name,min_sunshine,sort,icon) VALUES(?,?,?,?,?)",
                     (r["id"], r["name"], r["min_sunshine"], i, r.get("icon", "")))
    set_setting(conn, "ranks_ver", RANKS_VER)


def seed(conn):
    data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    term = data["term"]
    conn.execute("DELETE FROM terms")
    conn.execute("INSERT INTO terms(id,label,grade,term,version) VALUES(?,?,?,?,?)",
                 (term["id"], term["label"], term["grade"], term["term"], term["version"]))
    for s in ALL_SUBJECTS:
        conn.execute("INSERT OR REPLACE INTO subjects(id,name) VALUES(?,?)", (s, s))
    for u in data["units"]:
        conn.execute("INSERT OR REPLACE INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?)",
                     (u["id"], u["subject"], u["term_id"], u["seq"], u["name"]))
    for t in data["tasks"]:
        conn.execute("INSERT OR REPLACE INTO tasks(id,subject_id,unit_id,action,title,detail,sunshine,sort,custom) "
                     "VALUES(?,?,?,?,?,?,?,?,0)",
                     (t["id"], t["subject"], t["unit_id"], t["action"], t["title"], t.get("detail", ""), t["sunshine"], t["sort"]))
    for d in data["daily_tasks"]:
        br = d.get("bonus_rule") or {}
        conn.execute("INSERT OR REPLACE INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric) "
                     "VALUES(?,?,?,?,?,?,?)",
                     (d["id"], d["subject"], d["name"], d["sunshine"], d["frequency"],
                      br.get("type"), br.get("per_metric")))
        for m in d.get("metrics", []):
            conn.execute("INSERT OR REPLACE INTO daily_metrics(task_id,id,label,unit,direction,note) "
                         "VALUES(?,?,?,?,?,?)",
                         (d["id"], m["id"], m["label"], m["unit"], m["direction"], m.get("note")))
    # rewards/ranks 只首次写入，避免覆盖家长改动
    if conn.execute("SELECT COUNT(*) FROM rewards").fetchone()[0] == 0:
        for r in REWARDS:
            conn.execute("INSERT INTO rewards(id,name,price,category,need_approval) VALUES(?,?,?,?,?)",
                         (r["id"], r["name"], r["price"], r["category"], r["need_approval"]))
    seed_ranks(conn)
    set_setting(conn, "curriculum_ver", data.get("curriculum_ver", ""))


def apply_curriculum(conn):
    """已有库：只刷新系统任务/单元，保留自定义任务和流水。"""
    data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    ver = data.get("curriculum_ver", "")
    if get_setting(conn, "curriculum_ver", "") == ver:
        return
    conn.execute("DELETE FROM tasks WHERE COALESCE(custom,0)=0")
    conn.execute("DELETE FROM units WHERE id NOT IN (SELECT DISTINCT unit_id FROM tasks)")
    for u in data["units"]:
        conn.execute("INSERT OR REPLACE INTO units(id,subject_id,term_id,seq,name) VALUES(?,?,?,?,?)",
                     (u["id"], u["subject"], u["term_id"], u["seq"], u["name"]))
    for t in data["tasks"]:
        conn.execute("INSERT OR REPLACE INTO tasks(id,subject_id,unit_id,action,title,detail,sunshine,sort,custom) "
                     "VALUES(?,?,?,?,?,?,?,?,0)",
                     (t["id"], t["subject"], t["unit_id"], t["action"], t["title"], t.get("detail", ""), t["sunshine"], t["sort"]))
    for d in data.get("daily_tasks", []):
        br = d.get("bonus_rule") or {}
        conn.execute("INSERT OR REPLACE INTO daily_tasks(id,subject_id,name,sunshine,frequency,bonus_type,bonus_per_metric) "
                     "VALUES(?,?,?,?,?,?,?)",
                     (d["id"], d["subject"], d["name"], d["sunshine"], d["frequency"],
                      br.get("type"), br.get("per_metric")))
        conn.execute("DELETE FROM daily_metrics WHERE task_id=?", (d["id"],))
        for m in d.get("metrics", []):
            conn.execute("INSERT OR REPLACE INTO daily_metrics(task_id,id,label,unit,direction,note) "
                         "VALUES(?,?,?,?,?,?)",
                         (d["id"], m["id"], m["label"], m["unit"], m["direction"], m.get("note")))
    set_setting(conn, "curriculum_ver", ver)


def migrate_task_ids(conn):
    """把旧（无学期前缀）单元任务/游标 id 归一为 g5s1-*，保证跨学期不撞旧完成记录（幂等）。"""
    for p in ("cn-", "ma-", "en-"):
        conn.execute(
            "UPDATE completions SET task_id='g5s1-'||task_id "
            "WHERE task_id LIKE ? AND task_id NOT LIKE 'g5s1-%'", (p + "%",))
    conn.execute(
        "UPDATE settings SET value='g5s1-'||value WHERE key LIKE 'cursor_%' "
        "AND value != '' AND value NOT LIKE 'g5s1-%'")


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN custom INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN detail TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # completions 加 kind 列（unit/daily）用于防重复唯一索引
    try:
        conn.execute("ALTER TABLE completions ADD COLUMN kind TEXT NOT NULL DEFAULT 'unit'")
    except sqlite3.OperationalError:
        pass
    conn.execute("UPDATE completions SET kind='daily' WHERE task_id IN (SELECT id FROM daily_tasks)")
    for ddl in (
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_cmp_unit ON completions(task_id) WHERE status='completed' AND kind='unit'",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_cmp_daily ON completions(task_id, date) WHERE status='completed' AND kind='daily'",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_chk_date ON checkins(date)",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            # 已有重复 completed 数据时建索引可能失败，仅告警不中断
            print("[sunshine] index warn:", e)
    # 等级体系：加 icon 列；版本号变化时重排默认等级（只覆盖一次，之后尊重家长改动）
    try:
        conn.execute("ALTER TABLE ranks ADD COLUMN icon TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tests ADD COLUMN unit_id TEXT")
    except sqlite3.OperationalError:
        pass
    migrate_task_ids(conn)
    if conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0:
        seed(conn)
    else:
        apply_curriculum(conn)
    for s in ALL_SUBJECTS:
        conn.execute("INSERT OR IGNORE INTO subjects(id,name) VALUES(?,?)", (s, s))
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('admin_pin','8888')")
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('kid_name','乐乐')")
    # 语文已学到《珍珠鸟》（g5s1-cn-1-5），推荐从这里往后，前面不加阳光
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('cursor_语文','g5s1-cn-1-5')")
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('progress_lock','1')")
    if get_setting(conn, "ranks_ver", "") != RANKS_VER:
        seed_ranks(conn)
    conn.commit()
    conn.close()


def get_setting(conn, key, default=None):
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(key), str(value)))


def insert_ledger(conn, date, delta, reason, ref_id, note):
    conn.execute("INSERT INTO ledger(date,delta,reason,ref_id,note,created_at) VALUES(?,?,?,?,?,?)",
                 (date, delta, reason, ref_id, note, now()))