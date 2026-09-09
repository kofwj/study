# -*- coding: utf-8 -*-
"""单词模块 5.9.1：Unit 1 词表、迁移、家长词书 API。"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient
import main  # noqa: E402
import words as wordmod  # noqa: E402


def _parent(cli, account, pin, family):
    r = cli.post("/api/auth/register", json={"account": account, "pin": pin, "family_name": family})
    assert r.status_code == 200, r.text
    r = cli.post("/api/admin/kids", json={"name": "娃", "account": account + "k", "pin": "111222"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_unit1_seed_and_system_readonly():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "w1", "wordpass", "词家")
        books = cli.get("/api/admin/words/books").json()
        sys_ids = {b["id"] for b in books if b["is_system"]}
        assert sys_ids == {f"g5s1-en-{i}" for i in range(1, 11)}
        u1 = next(b for b in books if b["id"] == "g5s1-en-1")
        assert u1["is_system"] == 1
        assert 20 <= u1["word_count"] <= 30
        assert u1["name"] == "Unit 1 Good habits"
        u8 = next(b for b in books if b["id"] == "g5s1-en-8")
        assert u8["name"] == "Unit 8 We love festivals" and 20 <= u8["word_count"] <= 30
        p1 = next(b for b in books if b["id"] == "g5s1-en-9")
        assert "Project 1" in p1["name"] and 10 <= p1["word_count"] <= 22
        detail = cli.get("/api/admin/words/books/g5s1-en-1").json()
        words = [w["word"] for w in detail["words"] if w["active"]]
        assert words[0] == "habit"
        assert "always" in words and "blackboard" in words
        assert cli.put("/api/admin/words/books/g5s1-en-1", json={"name": "改"}).status_code == 403
        assert cli.delete("/api/admin/words/books/g5s1-en-1").status_code == 403
        assert cli.post("/api/admin/words/books/g5s1-en-1/import", json={"text": "hi\t嗨"}).status_code == 403
        today = cli.get("/api/words/today?selected_kid=" + kid).json()
        assert today["enabled"] is False and today["session"] is None
        c = db.connect()
        migs = {r[0] for r in c.execute("SELECT id FROM schema_migrations").fetchall()}
        c.close()
        assert "029_words" in migs


def test_family_book_import_and_isolation():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        _parent(a, "alicew", "alice888", "A家")
        _parent(b, "bobw", "bob88888", "B家")
        r = a.post("/api/admin/words/books", json={"name": "A家词"})
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        tsv = "always\t总是\t/ˈɔːlweɪz/\nusually\t通常\n\nbadonly\nget up\t起床\n"
        r = a.post(f"/api/admin/words/books/{bid}/import", json={"text": tsv})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] == 3
        assert any(e["error"] == "缺中文" for e in body["errors"])
        detail = a.get(f"/api/admin/words/books/{bid}").json()
        assert {w["word"] for w in detail["words"] if w["active"]} == {"always", "usually", "get up"}
        assert b.get(f"/api/admin/words/books/{bid}").status_code == 404
        assert bid not in {x["id"] for x in b.get("/api/admin/words/books").json()}
        csv_text = 'hello,你好,/həˈləʊ/\n"watch TV",看电视\n'
        r = a.post(f"/api/admin/words/books/{bid}/import", json={"text": csv_text})
        assert r.status_code == 200 and r.json()["ok"] == 2
        names = {x["name"] for x in a.get("/api/admin/words/books").json()}
        assert "A家词" in names and "Unit 1 Good habits" in names


def test_word_config_cursor_lock():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "w2", "wordpass", "锁家")
        cfg = cli.get("/api/admin/words/config").json()
        assert cfg["enabled"] is False and cfg["new_per_day"] == 5
        assert cfg["unlock_by_cursor"] is True
        u1 = next(b for b in cfg["books"] if b["id"] == "g5s1-en-1")
        assert u1["selectable"] is False
        r = cli.put("/api/admin/words/config", json={"current_book": "g5s1-en-1"})
        assert r.status_code == 400
        assert cli.post("/api/admin/cursor", json={"subject_id": "英语", "task_id": "g5s1-en-1-1"}).status_code == 200
        r = cli.put("/api/admin/words/config", json={"current_book": "g5s1-en-1", "enabled": True, "new_per_day": 3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enabled"] is True and body["current_book"] == "g5s1-en-1" and body["new_per_day"] == 3
        u2 = next(b for b in body["books"] if b["id"] == "g5s1-en-2")
        assert u2["selectable"] is False
        r = cli.put("/api/admin/words/config", json={"current_book": "g5s1-en-2"})
        assert r.status_code == 400
        r = cli.put("/api/admin/words/config", json={"unknown": 1})
        assert r.status_code == 422
        today = cli.get("/api/words/today?selected_kid=" + kid).json()
        assert today["enabled"] is True
        c = db.connect()
        wp_before = c.execute("SELECT COUNT(*) FROM weak_points").fetchone()[0]
        c.close()
        assert wp_before == 0


def test_normalize_and_focus():
    assert wordmod.normalize_word(" Always ") == "always"
    assert wordmod.normalize_word("doesn’t") == "doesn't"
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "w3", "wordpass", "盯家")
        wid = cli.get("/api/admin/words/books/g5s1-en-1").json()["words"][0]["id"]
        r = cli.post(f"/api/admin/words/{wid}/focus")
        assert r.status_code == 200, r.text
        assert r.json()["due_at"] == wordmod.tomorrow()
        c = db.connect()
        row = c.execute(
            "SELECT interval_idx, due_at FROM word_progress WHERE kid_id=? AND word_id=?",
            (kid, wid),
        ).fetchone()
        c.close()
        assert row["interval_idx"] == 0
        assert cli.get("/api/admin/words/problem-words").json() == []


def _enable(cli, **extra):
    assert cli.post("/api/admin/cursor", json={"subject_id": "英语", "task_id": "g5s1-en-1-1"}).status_code == 200
    body = {"enabled": True, "current_book": "g5s1-en-1", "new_per_day": 5, "max_due": 10,
            "base_sunshine": 3, "perfect_sunshine": 2}
    body.update(extra)
    r = cli.put("/api/admin/words/config", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _words(cli):
    return cli.get("/api/admin/words/books/g5s1-en-1").json()["words"]


def _spell(cli, sid, item, text=None, phase="spell", attempt_no=1):
    return cli.post(
        f"/api/words/session/{sid}/spell",
        json={"word_id": item["word_id"], "text": item["word"] if text is None else text,
              "phase": phase, "attempt_no": attempt_no},
    )


def test_session_stable_and_start():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws1", "wordpass", "练家")
        _enable(cli, new_per_day=3)
        a = cli.get("/api/words/today").json()
        assert a["enabled"] is True and a["session"] is None and a["finished"] is False
        s1 = cli.post("/api/words/session/start")
        assert s1.status_code == 200, s1.text
        sess = s1.json()["session"]
        assert sess["state"] == "active" and len(sess["items"]) == 3
        assert sess["counts"]["new"] == 3 and sess["counts"]["due"] == 0
        ids = [x["word_id"] for x in sess["items"]]
        assert ids == sorted(set(ids))
        s2 = cli.post("/api/words/session/start").json()
        t2 = cli.get("/api/words/today").json()
        assert s2["session"]["id"] == sess["id"] == t2["session"]["id"]
        assert [x["word_id"] for x in s2["session"]["items"]] == ids
        c = db.connect()
        seen = c.execute(
            "SELECT COUNT(*) FROM word_progress WHERE kid_id=? AND first_seen_at IS NOT NULL AND first_seen_at!=''",
            (kid,),
        ).fetchone()[0]
        c.close()
        assert seen == 0


def test_due_cap_prefers_review():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws2", "wordpass", "到期家")
        _enable(cli, new_per_day=10, max_due=15)
        words = _words(cli)[:12]
        c = db.connect()
        now, today = db.now(), db.today()
        for w in words:
            c.execute(
                "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
                "last_result,streak_right,correct_count,wrong_count) "
                "VALUES(?,?,0,?,?,?, 'right',1,1,0)",
                (kid, w["id"], today, now, now),
            )
        c.commit()
        c.close()
        sess = cli.post("/api/words/session/start").json()["session"]
        assert len(sess["items"]) == 10
        assert sess["counts"]["due"] == 10 and sess["counts"]["new"] == 0
        assert cli.get("/api/words/today").json()["backlog_due"] == 2


def test_spell_srs_retry_and_normalize():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws3", "wordpass", "判家")
        _enable(cli, new_per_day=2)
        words = _words(cli)
        first, second = words[0], words[1]
        c = db.connect()
        now, today = db.now(), db.today()
        c.execute(
            "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
            "last_result,streak_right,correct_count,wrong_count) "
            "VALUES(?,?,3,?,?,?, 'right',2,2,0)",
            (kid, first["id"], today, now, now),
        )
        c.commit()
        c.close()
        sess = cli.post("/api/words/session/start").json()["session"]
        due_item = next(x for x in sess["items"] if x["word_id"] == first["id"])
        new_item = next(x for x in sess["items"] if x["source"] == "new")
        sid = sess["id"]
        r = _spell(cli, sid, due_item, text="nope")
        assert r.status_code == 200, r.text
        assert r.json()["result"] == "wrong" and r.json()["progress"]["interval_idx"] == 0
        assert r.json()["progress"]["due_at"] == wordmod.tomorrow()
        replay = _spell(cli, sid, due_item, text="nope")
        assert replay.json()["replay"] is True and replay.json()["result"] == "wrong"
        r2 = _spell(cli, sid, due_item, text=due_item["word"], phase="retry")
        assert r2.status_code == 200
        c = db.connect()
        p = c.execute("SELECT interval_idx, wrong_count, correct_count FROM word_progress WHERE kid_id=? AND word_id=?",
                      (kid, first["id"])).fetchone()
        c.close()
        assert p["interval_idx"] == 0 and p["wrong_count"] == 1 and p["correct_count"] == 2
        pad = "  " + new_item["word"].upper() + "  "
        r3 = _spell(cli, sid, new_item, text=pad)
        assert r3.status_code == 200 and r3.json()["result"] == "right"
        assert r3.json()["progress"]["interval_idx"] == 0
        assert r3.json()["progress"]["due_at"] == wordmod.tomorrow()
        replay2 = _spell(cli, sid, new_item, text=new_item["word"] + "x")
        assert replay2.status_code == 200 and replay2.json()["replay"] is True
        assert replay2.json()["result"] == "right"
        extra = _spell(cli, sid, new_item, text="x", attempt_no=2)
        assert extra.status_code == 409


def test_complete_reward_idempotent_and_snapshot():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws4", "wordpass", "奖家")
        _enable(cli, new_per_day=2, base_sunshine=3, perfect_sunshine=2)
        before = cli.get("/api/overview").json()["earned"]
        sess = cli.post("/api/words/session/start").json()["session"]
        sid = sess["id"]
        assert cli.post(f"/api/words/session/{sid}/complete").status_code == 409
        assert cli.put("/api/admin/words/config", json={"base_sunshine": 0, "perfect_sunshine": 0}).status_code == 200
        for it in sess["items"]:
            assert _spell(cli, sid, it).status_code == 200
        r = cli.post(f"/api/words/session/{sid}/complete")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["finished"] is True and body["session"]["state"] == "completed"
        assert body["session"]["reward"]["base"] == 3 and body["session"]["reward"]["perfect"] == 2
        after = cli.get("/api/overview").json()["earned"]
        assert after == before + 5
        r2 = cli.post(f"/api/words/session/{sid}/complete")
        assert r2.status_code == 200
        assert cli.get("/api/overview").json()["earned"] == after
        c = db.connect()
        n = c.execute(
            "SELECT reason, COUNT(*) n FROM ledger WHERE kid_id=? AND reason IN ('word_daily','word_perfect') "
            "GROUP BY reason", (kid,)
        ).fetchall()
        wp = c.execute("SELECT COUNT(*) FROM weak_points").fetchone()[0]
        c.close()
        assert {r["reason"]: r["n"] for r in n} == {"word_daily": 1, "word_perfect": 1}
        assert wp == 0


def test_abandon_does_not_swallow_new_and_isolation():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        kid_a = _parent(a, "alicews", "alice888", "A练")
        _parent(b, "bobws", "bob88888", "B练")
        _enable(a, new_per_day=2)
        sess = a.post("/api/words/session/start").json()["session"]
        sid = sess["id"]
        assert b.post(f"/api/words/session/{sid}/spell",
                      json={"word_id": sess["items"][0]["word_id"], "text": "x"}).status_code == 404
        y = (__import__("datetime").date.today() - __import__("datetime").timedelta(days=1)).isoformat()
        c = db.connect()
        c.execute("UPDATE word_sessions SET study_date=? WHERE id=?", (y, sid))
        c.commit()
        n1 = c.execute(
            "SELECT COUNT(*) FROM word_progress WHERE kid_id=? AND first_seen_at IS NOT NULL AND first_seen_at!=''",
            (kid_a,),
        ).fetchone()[0]
        c.close()
        assert n1 == 0
        again = a.post("/api/words/session/start").json()["session"]
        assert again["id"] != sid
        assert {x["word_id"] for x in again["items"]} == {x["word_id"] for x in sess["items"]}


def test_admin_stats_tts_and_problem_words():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "wst", "wordpass", "统家")
        empty = cli.get("/api/admin/words/stats").json()
        assert len(empty["days"]) == 7
        assert empty["completed_sessions"] == 0
        assert empty["first_try_rate"] is None
        r = cli.put("/api/admin/words/config", json={"tts": False, "tts_autoplay": True, "tts_lang": "en-US"})
        assert r.status_code == 200, r.text
        cfg = cli.get("/api/admin/words/config").json()
        assert cfg["tts"] is False and cfg["tts_autoplay"] is True and cfg["tts_lang"] == "en-US"
        u1 = next(b for b in cfg["books"] if b["id"] == "g5s1-en-1")
        assert u1["source_ver"] == "words-g5s1-en-v2"
        assert u1["source_unit"] == "Unit 1 Good habits"
        _enable(cli, new_per_day=2)
        sess = cli.post("/api/words/session/start").json()["session"]
        sid = sess["id"]
        for it in sess["items"]:
            assert _spell(cli, sid, it).status_code == 200
        assert cli.post(f"/api/words/session/{sid}/complete").status_code == 200
        st = cli.get("/api/admin/words/stats").json()
        assert st["completed_sessions"] == 1
        assert st["first_try_rate"] == 100
        done = [d for d in st["days"] if d["completed"]]
        assert len(done) == 1 and done[0]["rate"] == 100
        wid = sess["items"][0]["word_id"]
        c = db.connect()
        c.execute("UPDATE word_progress SET wrong_count=2 WHERE kid_id=? AND word_id=?", (kid, wid))
        c.commit()
        c.close()
        probs = cli.get("/api/admin/words/problem-words").json()
        assert any(p["word_id"] == wid and p["wrong_count"] >= 2 for p in probs)
        books = cli.get("/api/admin/words/config").json()["books"]
        u1 = next(b for b in books if b["id"] == "g5s1-en-1")
        assert u1["problem_count"] >= 1


def test_admin_words_need_kid():
    db.init_db()
    with TestClient(main.app) as cli:
        r = cli.post("/api/auth/register", json={"account": "nokidw", "pin": "wordpass", "family_name": "空家"})
        assert r.status_code == 200, r.text
        r = cli.get("/api/admin/words/stats")
        assert r.status_code == 400
        r = cli.get("/api/admin/words/config")
        assert r.status_code == 400
