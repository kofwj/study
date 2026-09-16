# -*- coding: utf-8 -*-
"""英语复习独立页 /word/ 的发钱与打卡（P2）。python3 -m pytest -q test_word_game.py

口径（2026-09-16 定）：一轮得分 = 该轮答对 / 这一局词数（没答的当没对）；当天按最好一轮结算一次额度：
60 分以下 0，60–100 线性到 10（向下取整，70→2、80→5、95→8、100→10）；只补差额。
「一轮」= word_attempts 里 phase='spell' 的 attempt_no 分组（服务端算，不信客户端）。
做完一轮就等于今天打卡（不再单独发打卡阳光）；不发星尘、不碰宝箱。
"""
import os
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
    """与 frontend/src/wordGame.js 同一张表（前端那边由 scripts/check_word_game.mjs 钉住）。"""
    for score, want in [(0, 0), (59, 0), (60, 0), (70, 2), (75, 3), (80, 5), (95, 8), (100, 10), (120, 10)]:
        assert wordmod.sunshine_for_score(score) == want, (score, want)


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


def test_round_scores_grant_topup_and_checkin():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _family(cli, "wh")
        with _kid("wh") as k:
            sess = k.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            assert len(items) == 20

            _play(k, sid, items, 14, 1)                       # 14/20 = 70 分
            b = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b["round"]["score"] == 70 and b["today"]["granted"] == 2, b
            assert b["today"]["checkin"] is True and b["today"]["got"] == 2, b
            assert _sum_ledger(kid) == 2
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid,)) == 1

            # 重复结算（连点/刷新）：不多发
            b2 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b2["today"]["granted"] == 0 and _sum_ledger(kid) == 2, b2

            _play(k, sid, items, 16, 2)                       # 16/20 = 80 分 → 补 3
            b3 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b3["round"]["score"] == 80 and b3["today"]["granted"] == 3, b3
            assert b3["today"]["got"] == 5 and _sum_ledger(kid) == 5

            _play(k, sid, items, 15, 3)                       # 15/20 = 75 分：低于当天最好
            b4 = k.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b4["today"]["granted"] == 0 and b4["today"]["best_score"] == 80, b4
            assert _sum_ledger(kid) == 5                      # 一天最多 10，这里没有超发

            info = k.get("/api/words/game").json()
            assert info["today"]["best_score"] == 80 and info["today"]["got"] == 5 and info["size"] == 20, info

            # 手动签到不冲突（幂等）
            assert k.post("/api/checkin").status_code in (200, 409)
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid,)) == 1


def test_low_score_no_money_but_checkin_and_family_isolation():
    db.init_db()
    with TestClient(main.app) as cli, TestClient(main.app) as cli2:
        kid_a = _family(cli, "wi")
        kid_b = _family(cli2, "wj")
        with _kid("wi") as ka, _kid("wj") as kb:
            sa = ka.post("/api/words/game/start").json()["session"]
            _play(ka, sa["id"], sa["items"], 11, 1)           # 11/20 = 55 分
            ba = ka.post("/api/words/game/settle", json={"session_id": sa["id"]}).json()
            assert ba["round"]["score"] == 55 and ba["today"]["granted"] == 0, ba
            assert ba["today"]["checkin"] is True                 # 不发钱但照样打卡
            assert _sum_ledger(kid_a) == 0
            assert _count("SELECT COUNT(*) FROM checkins WHERE kid_id=?", (kid_a,)) == 1

            # 乙家不受影响
            assert _sum_ledger(kid_b) == 0
            assert cli2.get("/api/words/today").json()["config"]["game_size"] == 20
            sb = kb.post("/api/words/game/start").json()["session"]
            _play(kb, sb["id"], sb["items"], 20, 1)           # 100 分 → 10
            bb = kb.post("/api/words/game/settle", json={"session_id": sb["id"]}).json()
            assert bb["today"]["granted"] == 10 and _sum_ledger(kid_b) == 10, bb
            assert _sum_ledger(kid_a) == 0                    # 甲家没被带发


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
    """跳过/没答按这一局词数当分母：20 词只对 14 个、其余没交 → 70 分，不是 100。"""
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
            assert b["round"]["size"] == 20 and b["today"]["granted"] == 2, b
            assert _sum_ledger(kid) == 2
