# -*- coding: utf-8 -*-
"""英语复习独立页 /word/ 的发钱与打卡（P2）。python3 -m pytest -q test_word_game.py

口径（2026-09-16 定）：一轮得分 = 该轮答对 / 这一局词数（没答的当没对）；当天按最好一轮结算一次额度：
60 分以下 0，60–100 线性到 10（向下取整，70→2、80→5、95→8、100→10）；只补差额。
「一轮」= word_attempts 里 phase='spell' 的 attempt_no 分组（服务端算，不信客户端）。
做完一轮就等于今天打卡（不再单独发打卡阳光）；不发星尘、不碰宝箱。
"""
import os
import random
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SUNSHINE_NOW"] = "2026-09-16T12:00:00"

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import words as wordmod  # noqa: E402


def _family(cli, tag):
    r = cli.post("/api/auth/register", json={"account": tag + "p", "pin": tag + "pin123", "family_name": tag + "家"})
    assert r.status_code == 200, r.text
    kid = cli.post("/api/admin/kids", json={"name": "乐乐", "account": tag + "k", "pin": "111222"}).json()["id"]
    assert cli.post("/api/admin/cursor", json={"subject_id": "英语", "task_id": "g5s1-en-1-1"}).status_code == 200
    r = cli.put("/api/admin/words/config", json={"enabled": True, "current_book": "g5s1-en-1",
                                                 "new_per_day": 5, "max_due": 10})
    assert r.status_code == 200, r.text
    return kid


def _kid(tag):
    cli = TestClient(main.app)
    assert cli.post("/api/auth/login", json={"account": tag + "k", "pin": "111222"}).status_code == 200
    return cli


def _play(kcli, sid, items, right_n, round_no):
    """把这一轮答完：前 right_n 个写对，其余写错（phase='spell'）。"""
    for i, it in enumerate(items):
        r = kcli.post(f"/api/words/session/{sid}/spell",
                      json={"word_id": it["word_id"], "text": it["word"] if i < right_n else "zzz",
                            "phase": "spell", "attempt_no": round_no})
        assert r.status_code == 200, r.text


def _sum_ledger(kid, reason="word_game"):
    c = db.connect()
    n = c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger WHERE kid_id=? AND reason=?", (kid, reason)).fetchone()[0]
    c.close()
    return int(n or 0)


def _count(sql, args=()):
    c = db.connect()
    n = c.execute(sql, args).fetchone()[0]
    c.close()
    return int(n or 0)


def test_sunshine_table_matches_frontend():
    """与 frontend/src/wordGame.js 同一张表（前端那边由 scripts/check_word_game.mjs 钉住）。
    新口径（2026-09-16 改）：写了 d 个词、其中对 r 个 → floor((d+r)*0.25)，上限 10，**错题不扣分**。"""
    cases = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (4, 0, 1), (2, 2, 1),
             (10, 0, 2), (10, 10, 5), (20, 0, 5), (20, 10, 7), (20, 14, 8), (20, 20, 10),
             (100, 100, 10),                    # 超范围按满分
             (3, 99, 1),                        # 写对的不会多于写过的
             (None, None, 0), (-5, -5, 0), ("20", "14", 8)]
    for done, right, want in cases:
        assert wordmod.sunshine_for_progress(done, right) == want, (done, right, want)


def test_game_start_uses_game_size_and_default():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wg")
        cfg = cli.get("/api/words/today").json()["config"]
        assert cfg["game_size"] == 20, cfg
        full = {"enabled": True, "current_book": "g5s1-en-1", "new_per_day": 5, "max_due": 10}
        assert cli.put("/api/admin/words/config", json=dict(full, game_size=30)).status_code == 200
        assert cli.get("/api/words/today").json()["config"]["game_size"] == 30
        assert cli.put("/api/admin/words/config", json=dict(full, game_size=999)).status_code == 200
        assert cli.get("/api/words/today").json()["config"]["game_size"] == 40      # clamp 10–40
        # 设「一局 10 词」→ 开局就是 10 个（默认 20 会取满 20，说明设置真的生效）
        assert cli.put("/api/admin/words/config", json=dict(full, game_size=10)).status_code == 200
        with _kid("wg") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            assert len(sess["items"]) == 10, len(sess["items"])


def test_progress_grants_topup_and_checkin():
    """新口径（完成 + 进步）：20 词对 14 → (20+14)*0.25 = 8；
    下一轮累计写对 16 → (20+16)*0.25 = 9，补 1；**错题不扣分**，只增不减。"""
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _family(cli, "wh")
        with _kid("wh") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            assert len(items) == 20

            _play(k, sid, items, 14, 1)                       # 写了 20 个、对 14 个
            b = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b["round"]["score"] == 70 and b["today"]["granted"] == 8, b
            assert b["today"]["words_done"] == 20 and b["today"]["words_right"] == 14, b["today"]
            assert b["today"]["checkin"] is True and b["today"]["got"] == 8, b
            assert _sum_ledger(kid) == 8
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid,)) == 1

            # 重复结算（连点/刷新）：不多发
            b2 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b2["today"]["granted"] == 0 and _sum_ledger(kid) == 8, b2

            _play(k, sid, items, 16, 2)                       # 累计写对 16 → 9，补 1
            b3 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b3["round"]["score"] == 80 and b3["today"]["granted"] == 1, b3
            assert b3["today"]["got"] == 9 and _sum_ledger(kid) == 9
            assert b3["today"]["words_right"] == 16, b3["today"]

            _play(k, sid, items, 15, 3)                       # 这一轮没让「累计写对」变多 → 不补
            b4 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b4["today"]["granted"] == 0 and b4["today"]["best_score"] == 80, b4
            assert _sum_ledger(kid) == 9                      # 错题不扣分，一天最多 10

            info = k.get("/api/words/game").json()
            assert info["today"]["best_score"] == 80 and info["today"]["got"] == 9 and info["size"] == 20, info
            assert info["today"]["words_done"] == 20 and info["today"]["words_right"] == 16, info["today"]

            # 手动签到不冲突（幂等）
            assert k.post("/api/checkin").status_code in (200, 409)
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid,)) == 1


def test_wrong_answers_never_lose_money_and_family_isolation():
    """错题不扣分：11/20 也有保底（(20+11)*0.25 = 7）；打卡照给；乙家不受影响。"""
    db.init_db()
    with TestClient(main.app) as cli, TestClient(main.app) as cli2:
        kid_a = _family(cli, "wi")
        kid_b = _family(cli2, "wj")
        with _kid("wi") as ka, _kid("wj") as kb:
            sa = ka.post("/api/words/game/start").json()["session"]
            _play(ka, sa["id"], sa["items"], 11, 1)           # 写了 20 个、对 11 个
            ba = ka.post("/api/words/game/settle", json={"session_id": sa["id"]}).json()
            assert ba["round"]["score"] == 55 and ba["today"]["granted"] == 7, ba
            assert ba["today"]["checkin"] is True                 # 对了 11 个也照样打卡发钱
            assert _sum_ledger(kid_a) == 7
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid_a,)) == 1

            # 乙家不受影响
            assert _sum_ledger(kid_b) == 0
            assert cli2.get("/api/words/today").json()["config"]["game_size"] == 20
            sb = kb.post("/api/words/game/start").json()["session"]
            _play(kb, sb["id"], sb["items"], 20, 1)           # 全对 → (20+20)*0.25 = 10
            bb = kb.post("/api/words/game/settle", json={"session_id": sb["id"]}).json()
            assert bb["today"]["granted"] == 10 and _sum_ledger(kid_b) == 10, bb
            assert _sum_ledger(kid_a) == 7                    # 甲家没被带发


def test_kid_cannot_use_parent_endpoints_and_index_has_word_game():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wk")
        with _kid("wk") as k:
            assert k.get("/api/admin/words/config").status_code == 403
            assert k.put("/api/admin/words/config", json={"enabled": True}).status_code == 403
        c = db.connect()
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name='ux_ledger_once'").fetchone()[0]
        c.close()
        assert "word_game" in (sql or ""), sql


def test_unanswered_counts_against_score():
    """跳过/没答只影响展示的正确率（分母是这一局词数）：20 词只交 14 个 → 70 分；
    阳光按实际写过的 14 个算 → (14+14)*0.25 = 7。"""
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _family(cli, "wl")
        with _kid("wl") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            assert len(items) == 20
            for it in items[:14]:
                r = k.post(f"/api/words/session/{sid}/spell",
                           json={"word_id": it["word_id"], "text": it["word"],
                                 "phase": "spell", "attempt_no": 1})
                assert r.status_code == 200, r.text
            b = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b["round"]["score"] == 70 and b["round"]["answered"] == 14, b
            assert b["round"]["size"] == 20 and b["today"]["granted"] == 7, b
            assert b["today"]["words_done"] == 14 and b["today"]["words_right"] == 14, b["today"]
            assert _sum_ledger(kid) == 7


def test_game_settings_defaults_and_clamp():
    """P3 三个家长旋钮：每日目标（0 = 关闭，5–40）、连线每块（3–6）、一局连线块数（0–3）；
    另加「一关几步」（3–10，默认 6）—— 决定做完几题弹一次小关星星。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wm")
        cfg = cli.get("/api/admin/words/config").json()
        assert (cfg["daily_goal"], cfg["match_size"], cfg["match_blocks"], cfg["level_size"]) == (10, 5, 3, 6), cfg
        assert cli.put("/api/admin/words/config", json={"daily_goal": 0}).json()["daily_goal"] == 0
        assert cli.put("/api/admin/words/config", json={"daily_goal": 3}).json()["daily_goal"] == 5
        assert cli.put("/api/admin/words/config", json={"daily_goal": 999}).json()["daily_goal"] == 40
        assert cli.put("/api/admin/words/config", json={"match_size": 2}).json()["match_size"] == 3
        assert cli.put("/api/admin/words/config", json={"match_size": 9}).json()["match_size"] == 6
        assert cli.put("/api/admin/words/config", json={"match_blocks": 9}).json()["match_blocks"] == 3
        assert cli.put("/api/admin/words/config", json={"match_blocks": -1}).json()["match_blocks"] == 0
        assert cli.put("/api/admin/words/config", json={"level_size": 2}).json()["level_size"] == 3
        assert cli.put("/api/admin/words/config", json={"level_size": 99}).json()["level_size"] == 10
        assert cli.put("/api/admin/words/config", json={"level_size": 7}).json()["level_size"] == 7
        # 孩子端拿到的配置也带这三项（/word/ 开局时读一次）
        kid_cfg = cli.get("/api/words/today").json()["config"]
        assert (kid_cfg["daily_goal"], kid_cfg["match_size"], kid_cfg["match_blocks"],
                kid_cfg["level_size"]) == (40, 6, 0, 7), kid_cfg


def test_scored_words_counts_written_words_only():
    """每日目标环看的是「今天写过几个词」（去重、只数正式作答）：再写一次不重复计。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wn")
        with _kid("wn") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            assert len(items) == 20
            for it in items[:2]:
                r = k.post(f"/api/words/session/{sid}/spell",
                           json={"word_id": it["word_id"], "text": it["word"], "phase": "spell", "attempt_no": 1})
                assert r.status_code == 200, r.text
            w3 = items[2]
            r = k.post(f"/api/words/session/{sid}/spell",
                       json={"word_id": w3["word_id"], "text": "zzz", "phase": "spell", "attempt_no": 1})
            assert r.json()["result"] == "wrong", r.text
            r = k.post(f"/api/words/session/{sid}/spell",
                       json={"word_id": w3["word_id"], "text": w3["word"], "phase": "retry", "attempt_no": 1})
            assert r.json()["result"] == "right", r.text
            info = k.get("/api/words/game").json()
            assert info["today"]["scored_words"] == 3, info["today"]
            assert info["today"]["goal"] == 10 and info["today"]["goal_done"] is False, info["today"]
            started = k.post("/api/words/game/start").json()
            assert started["goal"]["scored_words"] == 3 and started["goal"]["goal"] == 10, started["goal"]
            assert started["config"]["match_size"] == 5 and started["config"]["match_blocks"] == 3, started["config"]


def test_daily_goal_does_not_change_money():
    """目标环只展示：阳光只看「完成 + 写对」，和有没有达标无关。"""
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _family(cli, "wo")
        assert cli.put("/api/admin/words/config", json={"daily_goal": 5}).status_code == 200
        with _kid("wo") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            _play(k, sid, items, 5, 1)                       # 写了 20 个、对 5 个 → (20+5)*0.25 = 6
            b = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b["round"]["score"] == 25 and b["today"]["granted"] == 6, b
            assert b["today"]["scored_words"] == 20 and b["today"]["goal_done"] is True, b["today"]
            assert _sum_ledger(kid) == 6
            # 目标改成 0 = 关闭：环没了，但钱的口径不变
            assert cli.put("/api/admin/words/config", json={"daily_goal": 0}).status_code == 200
            info = k.get("/api/words/game").json()
            assert info["today"]["goal"] == 0 and info["today"]["goal_done"] is False, info["today"]
            assert info["today"]["scored_words"] == 20 and info["today"]["got"] == 6, info["today"]


def test_match_blocks_zero_turns_pairing_off():
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wp")
        assert cli.put("/api/admin/words/config", json={"match_blocks": 0, "match_size": 3}).status_code == 200
        with _kid("wp") as k:
            started = k.post("/api/words/game/start").json()
            assert started["config"]["match_blocks"] == 0 and started["config"]["match_size"] == 3, started["config"]
            info = k.get("/api/words/game").json()
            assert info["config"]["match_blocks"] == 0 and info["config"]["match_size"] == 3, info["config"]
            assert info["size"] == 20, info


def test_session_items_carry_progress_for_question_plan():
    """每题带 word_progress：页面按它决定「先认一认 / 先连一连 / 直接写」；写对后进度照样回灌。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wq")
        with _kid("wq") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            it = items[0]
            assert it["progress"] == {"first_seen_at": "", "interval_idx": 0, "streak_right": 0,
                                      "wrong_count": 0, "last_result": ""}, it["progress"]
            r = k.post(f"/api/words/session/{sid}/spell",
                       json={"word_id": it["word_id"], "text": it["word"], "phase": "spell", "attempt_no": 1})
            assert r.status_code == 200, r.text
            again = [x for x in k.get("/api/words/game").json()["session"]["items"]
                     if x["word_id"] == it["word_id"]][0]
            assert again["progress"]["first_seen_at"], again["progress"]
            assert again["progress"]["streak_right"] == 1 and again["progress"]["last_result"] == "right"
            assert again["progress"]["wrong_count"] == 0 and again["progress"]["interval_idx"] == 0
            # 写错的词：下次还得出「认」，页面靠 wrong_count / last_result 判断
            it2 = items[1]
            r = k.post(f"/api/words/session/{sid}/spell",
                       json={"word_id": it2["word_id"], "text": "zzz", "phase": "spell", "attempt_no": 1})
            assert r.status_code == 200, r.text
            bad = [x for x in k.get("/api/words/game").json()["session"]["items"]
                   if x["word_id"] == it2["word_id"]][0]
            assert bad["progress"]["wrong_count"] == 1 and bad["progress"]["last_result"] == "wrong", bad["progress"]


def test_start_repicks_until_first_answer():
    """P4-c ②：还没作答 → 每次开局换一批词；答过一题 → 锁定同一批（分母口径不变）。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _family(cli, "wr")
        full = {"enabled": True, "current_book": "g5s1-en-1", "new_per_day": 5, "max_due": 10}
        # 一局 10 词、书里有 20 个 → 候选比一局多，换一批才看得出区别
        assert cli.put("/api/admin/words/config", json=dict(full, game_size=10)).status_code == 200
        saved = wordmod._rand
        wordmod._rand = random.Random(7)          # 固定随机源：断言可复现
        try:
            with _kid("wr") as k:
                first = k.post("/api/words/game/start").json()["session"]
                a = [it["word_id"] for it in first["items"]]
                assert len(a) == 10, a
                second = k.post("/api/words/game/start").json()["session"]
                b = [it["word_id"] for it in second["items"]]
                assert second["id"] == first["id"], "换词不换会话（今天还是这一条）"
                assert sorted(a) != sorted(b), (a, b)          # 换了一批
                assert len(b) == 10, b
                # 作答一题后就锁定：再开局还是这一批
                sid = first["id"]
                r = k.post(f"/api/words/session/{sid}/spell",
                           json={"word_id": b[0], "text": "zzz", "phase": "spell", "attempt_no": 1})
                assert r.status_code == 200, r.text
                locked = [it["word_id"] for it in k.post("/api/words/game/start").json()["session"]["items"]]
                assert locked == b, (locked, b)
        finally:
            wordmod._rand = saved
