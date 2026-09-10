# -*- coding: utf-8 -*-
"""阳光图鉴 2.0：12 只精灵、连击开箱、星尘、秘密基地。尘不进 ledger。"""
import json
import random
from datetime import datetime, timedelta

import db

SERIES_ORDER = ["sun", "leaf", "sky"]
SERIES_NAME = {"sun": "日光", "leaf": "绿意", "sky": "天气"}
DUST_PER_DUP = 6
STAR_COST = 12
MAX_STARS = 3
NICK_MAX = 8
FLAVOR_MAX = 16

CFG_ENABLED = "sprites_enabled"
CFG_BASE = "sprite_base_enabled"
CFG_DUST = "sprite_dust"
CFG_ITEMS = "sprite_base_items"
CFG_DUTY = "sprite_on_duty"
CFG_MORNING = "sprite_morning_ack"

SPRITE_DEFS = [
    {"id": "sp-sun", "series": "sun", "series_name": "日光", "name": "暖暖", "tint": "#f5a524", "feature": "sunbun", "flavor": "喜欢晒太阳，也喜欢给别人分一点光"},
    {"id": "sp-dusk", "series": "sun", "series_name": "日光", "name": "霞霞", "tint": "#e07a5f", "feature": "sleeper", "flavor": "傍晚是它的下午"},
    {"id": "sp-seed", "series": "sun", "series_name": "日光", "name": "籽籽", "tint": "#e8c547", "feature": "seedling", "flavor": "喜欢把小秘密藏在口袋里"},
    {"id": "sp-iris", "series": "sun", "series_name": "日光", "name": "虹虹", "tint": "#7c6cf0", "feature": "rainbow", "flavor": "喜欢把不同颜色排成朋友"},
    {"id": "sp-leaf", "series": "leaf", "series_name": "绿意", "name": "叶叶", "tint": "#2e8f55", "feature": "leafcloak", "flavor": "喜欢躲在课本的页角"},
    {"id": "sp-moss", "series": "leaf", "series_name": "绿意", "name": "苔苔", "tint": "#7dba6a", "feature": "mushroom", "flavor": "喜欢阴凉又安静的角落"},
    {"id": "sp-chime", "series": "leaf", "series_name": "绿意", "name": "铃铃", "tint": "#5aae8a", "feature": "windbell", "flavor": "喜欢听窗边的风"},
    {"id": "sp-fruit", "series": "leaf", "series_name": "绿意", "name": "果果", "tint": "#c46b4a", "feature": "acorn", "flavor": "喜欢圆圆的午后"},
    {"id": "sp-cloud", "series": "sky", "series_name": "天气", "name": "朵朵", "tint": "#c5ced6", "feature": "cloudpuff", "flavor": "喜欢发呆和做白日梦"},
    {"id": "sp-rain", "series": "sky", "series_name": "天气", "name": "滴滴", "tint": "#2fa6de", "feature": "raindrop", "flavor": "喜欢敲窗户的节奏"},
    {"id": "sp-moon", "series": "sky", "series_name": "天气", "name": "弯弯", "tint": "#6b7c93", "feature": "moonboat", "flavor": "喜欢把晚安送到每个房间"},
    {"id": "sp-star", "series": "sky", "series_name": "天气", "name": "闪闪", "tint": "#4a5560", "feature": "sparkstar", "flavor": "喜欢被点名，也会给人打气"},
]
DEFS_BY_ID = {d["id"]: d for d in SPRITE_DEFS}

BASE_ITEMS = [
    {"id": "sun-rocket", "name": "小火箭", "series": "sun", "price": 30},
    {"id": "sun-telescope", "name": "望远镜", "series": "sun", "price": 20},
    {"id": "leaf-hammock", "name": "吊床", "series": "leaf", "price": 25},
    {"id": "leaf-jars", "name": "萤火虫瓶", "series": "leaf", "price": 20},
    {"id": "sky-balloon", "name": "热气球", "series": "sky", "price": 30},
    {"id": "sky-moonbed", "name": "月亮床", "series": "sky", "price": 25},
]
ITEMS_BY_ID = {d["id"]: d for d in BASE_ITEMS}

# 与 docs/base-layout-preview.html SPEC / ROADMAP §4.7.6 锁定稿同一套
BASE_LAYOUT = {
    "sun": [
        {"id": "sun-rocket", "name": "火箭", "x": 13, "y": 86, "w": 22, "kind": "shop",
         "sit": {"x": 58, "y": 70, "w": 18}, "pose": "sit"},
        {"id": "sun-telescope", "name": "望远镜", "x": 46, "y": 99, "w": 16, "kind": "shop", "flip": True},
        {"id": "trace-pinwheel", "name": "风车", "x": 95, "y": 70, "w": 12, "kind": "trace", "anim": "spin-wheel"},
    ],
    "leaf": [
        {"id": "leaf-hammock", "name": "吊床", "x": 82, "y": 115, "w": 28, "kind": "shop",
         "sit": {"x": 50, "y": 52, "w": 20}, "pose": "lie"},
        {"id": "leaf-jars", "name": "萤火虫瓶", "x": 20, "y": 34, "w": 11, "kind": "shop", "anim": "glow"},
        {"id": "memo-award", "name": "奖状", "x": 45, "y": 43, "w": 10, "kind": "memo"},
        {"id": "memo-flag", "name": "小旗", "x": 11, "y": 87, "w": 10, "kind": "memo", "anim": "wave"},
    ],
    "sky": [
        {"id": "sky-balloon", "name": "热气球", "x": 19, "y": 56, "w": 18, "kind": "shop",
         "sit": {"x": 50, "y": 92, "w": 16}, "pose": "sit"},
        {"id": "sky-moonbed", "name": "月亮床", "x": 75, "y": 82, "w": 22, "kind": "shop",
         "sit": {"x": 50, "y": 72, "w": 20}, "pose": "lie", "flip": True},
    ],
}


class SpriteError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def enabled(c, kid) -> bool:
    return db.get_kid_setting(c, kid, CFG_ENABLED, "1") != "0"


def base_enabled(c, kid) -> bool:
    return db.get_kid_setting(c, kid, CFG_BASE, "1") != "0"


def dust_of(c, kid) -> int:
    raw = db.get_kid_setting(c, kid, CFG_DUST, None)
    if raw is None:
        return 0
    try:
        return max(0, min(9999, int(str(raw).strip())))
    except (TypeError, ValueError):
        return 0


def set_dust(c, kid, n):
    db.set_kid_setting(c, kid, CFG_DUST, str(max(0, min(9999, int(n)))))


def base_items_of(c, kid) -> list:
    raw = db.get_kid_setting(c, kid, CFG_ITEMS, None)
    if not raw:
        return []
    try:
        arr = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(arr, list):
        return []
    out, seen = [], set()
    for x in arr:
        i = str(x)
        if i in ITEMS_BY_ID and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _set_base_items(c, kid, items):
    db.set_kid_setting(c, kid, CFG_ITEMS, json.dumps(items, ensure_ascii=False))


def on_duty_of(c, kid) -> str:
    v = (db.get_kid_setting(c, kid, CFG_DUTY, "") or "").strip()
    return v if v in DEFS_BY_ID else ""


def config_of(c, kid) -> dict:
    return {"enabled": enabled(c, kid), "base_enabled": base_enabled(c, kid)}


def set_config(c, kid, enabled_flag=None, base_enabled_flag=None):
    if enabled_flag is not None:
        db.set_kid_setting(c, kid, CFG_ENABLED, "1" if enabled_flag else "0")
    if base_enabled_flag is not None:
        db.set_kid_setting(c, kid, CFG_BASE, "1" if base_enabled_flag else "0")
    return config_of(c, kid)


def _owned_rows(c, kid):
    rows = c.execute(
        "SELECT def_id, nickname, flavor, stars, obtained_at FROM kid_sprites WHERE kid_id=?",
        (kid,),
    ).fetchall()
    out = {}
    for r in rows:
        did = r["def_id"]
        if did not in DEFS_BY_ID:
            continue
        stars = r["stars"]
        try:
            stars = max(0, min(MAX_STARS, int(stars)))
        except (TypeError, ValueError):
            stars = 0
        out[did] = {
            "nickname": r["nickname"] or "",
            "flavor": r["flavor"] or "",
            "stars": stars,
            "obtained_at": r["obtained_at"] or "",
        }
    return out


def _item_public(defn, row=None, hide=False):
    d = {
        "id": defn["id"],
        "name": defn["name"],
        "feature": defn["feature"],
        "tint": defn["tint"],
        "owned": False,
        "nickname": "",
        "flavor": "",
        "stars": 0,
    }
    if hide or not row:
        return d
    nick = (row.get("nickname") or "").strip()
    flavor = (row.get("flavor") or "").strip() or defn["flavor"]
    d.update({
        "owned": True,
        "nickname": nick,
        "flavor": flavor,
        "stars": row.get("stars") or 0,
        "obtained_at": row.get("obtained_at") or "",
    })
    return d


def pick_def_id(c, kid):
    owned = {r["def_id"] for r in c.execute(
        "SELECT def_id FROM kid_sprites WHERE kid_id=?", (kid,))}
    fresh = [d["id"] for d in SPRITE_DEFS if d["id"] not in owned]
    if fresh:
        return random.choice(fresh), False
    return random.choice([d["id"] for d in SPRITE_DEFS]), True


def grant_from_box(c, kid, fam, ref_id) -> dict:
    def_id, dup = pick_def_id(c, kid)
    defn = DEFS_BY_ID[def_id]
    dust_gain = 0
    if not dup:
        c.execute(
            "INSERT INTO kid_sprites(kid_id,family_id,def_id,nickname,flavor,stars,obtained_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (kid, fam or "", def_id, "", "", 0, db.now()),
        )
        row = {"nickname": "", "flavor": "", "stars": 0, "obtained_at": db.now()}
    else:
        dust_gain = DUST_PER_DUP
        set_dust(c, kid, dust_of(c, kid) + dust_gain)
        row = _owned_rows(c, kid).get(def_id) or {"nickname": "", "flavor": "", "stars": 0}
    c.execute(
        "INSERT INTO sprite_opens(kid_id,family_id,def_id,duplicate,dust_gain,source,ref_id,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (kid, fam or "", def_id, 1 if dup else 0, dust_gain, "box", ref_id, db.now()),
    )
    sprite = _item_public(defn, row, hide=False)
    sprite["series"] = defn["series"]
    sprite["series_name"] = defn["series_name"]
    return {
        "item": def_id,
        "kind": "sprite",
        "duplicate": dup,
        "dust": dust_of(c, kid),
        "dust_gain": dust_gain,
        "sprite": sprite,
    }


def set_profile(c, kid, def_id, nickname, flavor):
    defn = DEFS_BY_ID.get(def_id)
    if not defn:
        raise SpriteError(400, "没有这只精灵")
    row = _owned_rows(c, kid).get(def_id)
    if not row:
        raise SpriteError(404, "还没遇到它")
    nick = (nickname or "").strip()
    flav = (flavor or "").strip()
    if not nick or len(nick) > NICK_MAX:
        raise SpriteError(400, "给它起个 1 到 8 个字的名字")
    if len(flav) > FLAVOR_MAX:
        raise SpriteError(400, "介绍最多 16 个字")
    c.execute(
        "UPDATE kid_sprites SET nickname=?, flavor=? WHERE kid_id=? AND def_id=?",
        (nick, flav, kid, def_id),
    )
    row = {**row, "nickname": nick, "flavor": flav}
    return _item_public(defn, row)


def add_star(c, kid, def_id):
    defn = DEFS_BY_ID.get(def_id)
    if not defn:
        raise SpriteError(400, "没有这只精灵")
    row = _owned_rows(c, kid).get(def_id)
    if not row:
        raise SpriteError(400, "还没遇到它")
    if row["stars"] >= MAX_STARS:
        raise SpriteError(400, "已经三颗星了")
    dust = dust_of(c, kid)
    if dust < STAR_COST:
        raise SpriteError(400, "星尘不够，先开重复的箱子")
    stars = row["stars"] + 1
    set_dust(c, kid, dust - STAR_COST)
    c.execute(
        "UPDATE kid_sprites SET stars=? WHERE kid_id=? AND def_id=?",
        (stars, kid, def_id),
    )
    return {"stars": stars, "dust": dust_of(c, kid)}


def buy_base_item(c, kid, item_id):
    item = ITEMS_BY_ID.get(item_id)
    if not item:
        raise SpriteError(400, "非法 id")
    have = base_items_of(c, kid)
    if item_id in have:
        raise SpriteError(409, "已经买过啦")
    dust = dust_of(c, kid)
    if dust < item["price"]:
        raise SpriteError(400, "星尘不够")
    set_dust(c, kid, dust - item["price"])
    have.append(item_id)
    _set_base_items(c, kid, have)
    return {"dust": dust_of(c, kid), "base_items": have}


def set_on_duty(c, kid, def_id):
    if def_id:
        if def_id not in DEFS_BY_ID:
            raise SpriteError(400, "没有这只精灵")
        if def_id not in _owned_rows(c, kid):
            raise SpriteError(404, "还没遇到它")
    db.set_kid_setting(c, kid, CFG_DUTY, def_id or "")
    return {"on_duty": def_id or ""}


def ack_morning(c, kid, today=None):
    db.set_kid_setting(c, kid, CFG_MORNING, today or db.today())
    return {"ok": True}


def _count_kind(c, kid, day, kind):
    return c.execute(
        "SELECT COUNT(*) FROM completions WHERE status='completed' AND kind=? AND kid_id=? AND date=? "
        "AND NOT EXISTS (SELECT 1 FROM ledger WHERE reason='cancel' AND ref_id='cmp-'||CAST(completions.id AS TEXT))",
        (kind, kid, day),
    ).fetchone()[0]


def _word_done(c, kid, day) -> bool:
    try:
        r = c.execute(
            "SELECT 1 FROM word_sessions WHERE kid_id=? AND study_date=? AND state='completed' LIMIT 1",
            (kid, day),
        ).fetchone()
        return bool(r)
    except Exception:
        return False


def _had_study(c, kid, day) -> bool:
    if c.execute("SELECT 1 FROM checkins WHERE kid_id=? AND date=? LIMIT 1", (kid, day)).fetchone():
        return True
    if c.execute(
        "SELECT 1 FROM completions WHERE kid_id=? AND date=? AND status='completed' LIMIT 1",
        (kid, day),
    ).fetchone():
        return True
    try:
        if c.execute(
            "SELECT 1 FROM word_sessions WHERE kid_id=? AND study_date=? LIMIT 1",
            (kid, day),
        ).fetchone():
            return True
    except Exception:
        pass
    return False


def traces_of(c, kid, day, review_clear: bool) -> dict:
    unit_n = int(_count_kind(c, kid, day, "unit") or 0)
    daily_n = int(_count_kind(c, kid, day, "daily") or 0)
    return {
        "unit_done": unit_n,
        "word_done": _word_done(c, kid, day),
        "daily_done": daily_n,
        "review_clear": bool(review_clear),
    }


def _has_award(c, kid) -> bool:
    r = c.execute(
        "SELECT 1 FROM ledger WHERE kid_id=? AND reason='word_perfect' LIMIT 1",
        (kid,),
    ).fetchone()
    return bool(r)


def _morning_text(who_name, y):
    bits = []
    if y["unit_done"]:
        bits.append(f"试飞了 {y['unit_done']} 架纸飞机")
    if y["word_done"]:
        bits.append("夜空多了 1 颗星")
    if y["daily_done"]:
        bits.append("风车转了一晚上")
    if y["review_clear"]:
        bits.append("看见云散月圆")
    if not bits:
        bits.append("在秘密基地待了一晚")
    body = "，".join(bits)
    if who_name:
        return f"昨晚{who_name}{body}。它说：今天也加油！"
    if y["daily_done"] and not y["unit_done"] and not y["word_done"]:
        return "秘密基地昨晚自己转了一晚风车。"
    return f"秘密基地昨晚自己{body}。"


def morning_of(c, kid, today, y_traces, owned):
    ack = db.get_kid_setting(c, kid, CFG_MORNING, "") or ""
    yday = (datetime.fromisoformat(today) - timedelta(days=1)).date().isoformat()
    if ack == today or not _had_study(c, kid, yday):
        return {"new": False, "who": "", "text": ""}
    duty = on_duty_of(c, kid)
    who = ""
    if duty and duty in owned:
        who = duty
    else:
        y_owned = [
            did for did, row in owned.items()
            if (row.get("obtained_at") or "")[:10] <= yday
        ]
        if y_owned:
            who = y_owned[0]
    who_name = ""
    if who:
        row = owned.get(who) or {}
        who_name = (row.get("nickname") or "").strip() or DEFS_BY_ID[who]["name"]
    return {"new": True, "who": who, "text": _morning_text(who_name, y_traces)}


def catalog(c, kid, fam, *, review_clear, review_clear_yesterday, streak) -> dict:
    en = enabled(c, kid)
    base_on = base_enabled(c, kid)
    owned = _owned_rows(c, kid) if en else {}
    hide = not en
    series = []
    owned_n = 0
    for sid in SERIES_ORDER:
        items = []
        for defn in SPRITE_DEFS:
            if defn["series"] != sid:
                continue
            row = owned.get(defn["id"])
            it = _item_public(defn, row, hide=hide)
            if it["owned"]:
                owned_n += 1
            items.append(it)
        series.append({
            "id": sid,
            "name": SERIES_NAME[sid],
            "owned": sum(1 for x in items if x["owned"]),
            "total": len(items),
            "items": items,
        })
    today = db.today()
    yday = (datetime.fromisoformat(today) - timedelta(days=1)).date().isoformat()
    today_tr = traces_of(c, kid, today, review_clear)
    y_tr = traces_of(c, kid, yday, review_clear_yesterday)
    morning = morning_of(c, kid, today, y_tr, owned) if en and base_on else {"new": False, "who": "", "text": ""}
    have = base_items_of(c, kid) if en else []
    shop = [{**it, "owned": it["id"] in have} for it in BASE_ITEMS]
    return {
        "enabled": en,
        "base_enabled": base_on,
        "dust": dust_of(c, kid) if en else 0,
        "base_items": have,
        "on_duty": on_duty_of(c, kid) if en else "",
        "today": today_tr,
        "morning": morning,
        "owned": owned_n,
        "total": 12,
        "series": series,
        "layout": BASE_LAYOUT,
        "shop": shop,
        "memos": {
            "award": _has_award(c, kid) if en else False,
            "flag": bool(en and streak >= 7),
        },
        "star_cost": STAR_COST,
    }
