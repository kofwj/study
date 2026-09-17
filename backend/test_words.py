# -*- coding: utf-8 -*-
"""单词模块 5.9.1：Unit 1 词表、迁移、家长词书 API。"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
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
        expected_ids = {
            f"{term}-en-{unit}"
            for term in ("g3s1", "g3x2", "g4s1", "g4x2", "g5s1")
            for unit in range(1, 11 if term == "g5s1" else 9)
        }
        assert sys_ids == expected_ids
        u1 = next(b for b in books if b["id"] == "g5s1-en-1")
        assert u1["is_system"] == 1
        assert u1["word_count"] == 20
        u8 = next(b for b in books if b["id"] == "g5s1-en-8")
        assert u8["name"] == "Unit 8 We love festivals" and u8["word_count"] == 18
        detail = cli.get("/api/admin/words/books/g5s1-en-8").json()
        by_word = {w["word"]: w for w in detail["words"]}
        assert {"page", "entry_type", "core"} <= set(by_word["May"])
        assert by_word["May"]["entry_type"] == "专名" and by_word["May"]["active"] == 0
        assert by_word["Spring Festival"]["entry_type"] == "节日名" and by_word["Spring Festival"]["active"] == 0
        assert by_word["China"]["entry_type"] == "专名" and by_word["China"]["active"] == 0
        project = cli.get("/api/admin/words/books/g5s1-en-9").json()["words"]
        assert len(project) == 16 and all(w["page"] is None and w["entry_type"] == "项目词汇" for w in project)
        family = cli.get("/api/admin/words/books/g3s1-en-5").json()["words"]
        mum = next(w for w in family if w["word"] == "mum")
        assert "mom" in mum["accept_json"] and mum["word"] == "mum"
        assert all("（" not in w["word"] for w in family)
        detail = cli.get("/api/admin/words/books/g5s1-en-1").json()
        words = [w["word"] for w in detail["words"] if w["active"]]
        assert words[0] == "habit"
        assert "carefully" in words and "do exercise" in words and "always" not in words
        u5 = cli.get("/api/admin/words/books/g5s1-en-5").json()
        assert "always" in {w["word"] for w in u5["words"] if w["active"]}
        assert cli.put("/api/admin/words/books/g5s1-en-1", json={"name": "改"}).status_code == 403
        assert cli.delete("/api/admin/words/books/g5s1-en-1").status_code == 403
        assert cli.post("/api/admin/words/books/g5s1-en-1/import", json={"text": "hi\t嗨"}).status_code == 403
        today = cli.get("/api/words/today?selected_kid=" + kid).json()
        assert today["enabled"] is False and today["session"] is None
        c = db.connect()
        migs = {r[0] for r in c.execute("SELECT id FROM schema_migrations").fetchall()}
        assert "039_word_metadata" in migs
        assert "029_words" in migs


def test_metadata_filter_keeps_noncore_extensions():
    db.init_db()
    with TestClient(main.app) as cli:
        _parent(cli, "wmeta", "wordpass", "元数据家")
        assert cli.post("/api/admin/cursor", json={"subject_id": "英语", "task_id": "g5s1-en-8-1"}).status_code == 200
        r = cli.put("/api/admin/words/config", json={
            "enabled": True, "current_book": "g5s1-en-8", "new_per_day": 10, "max_due": 10,
        })
        assert r.status_code == 200, r.text
        sess = cli.post("/api/words/session/start").json()["session"]
        assert sess and sess["items"]
        assert all(x["entry_type"] not in {"专名", "节日名", "课程名", "社团名", "菜名"} for x in sess["items"])
        assert any(not x["core"] for x in sess["items"])
        assert {"page", "entry_type", "core"} <= set(sess["items"][0])


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
    body = {"enabled": True, "current_book": "g5s1-en-1", "new_per_day": 5, "max_due": 10}
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
        # v0.3.55：/word/ 的「再练一遍」用 attempt_no>1 的 spell 轮，允许再判；
        # 同一轮（attempt_no=1）重复提交仍走缓存、不重判
        extra = _spell(cli, sid, new_item, text=new_item["word"], attempt_no=2)
        assert extra.status_code == 200 and extra.json()["result"] == "right"
        same_round = _spell(cli, sid, new_item, text="x")
        assert same_round.status_code == 200 and same_round.json()["replay"] is True
        assert same_round.json()["result"] == "right"



def test_spell_judge_requires_apostrophe_but_not_sentence_punctuation():
    """v0.3.66 口径：**字母和撇号都算数**，空格/句末标点不算。
    撇号是单词的一部分（let's / It's / o'clock）—— 漏敲要判错，弯撇号 ’ 要算对。"""
    def row(word, accept=()):
        return {"word_norm": wordmod.normalize_word(word),
                "accept_json": wordmod.accept_json_of({"accept": list(accept)})}

    it = row("It's your turn.")
    # 对：敲了撇号（直的弯的、大小写、空格、末尾句号都不计较）
    for said in ["It's your turn.", "it's your turn", "IT'SYOURTURN", "it's your turn.",
                 "It\u2019s your turn.", "  it's   your turn.  "]:
        assert wordmod._spell_ok(said, it) is True, said
    # 错：漏了撇号（这才是练它的意义）
    for wrong in ["its your turn", "itsyourturn", "Its your turn.", "Itsyourturn."]:
        assert wordmod._spell_ok(wrong, it) is False, wrong
    # 错：真错了的地方照样错
    for wrong in ["", "   ", "...", "it's your tur", "it's your turnn", "it's whose turn"]:
        assert wordmod._spell_ok(wrong, it) is False, wrong

    # 句末标点仍然免敲
    period = row("Good morning.")
    assert wordmod._spell_ok("good morning", period) is True
    assert wordmod._spell_ok("goodmorning.", period) is True
    assert wordmod._spell_ok("good evening", period) is False

    # 撇号居中：o'clock
    oclock = row("o'clock")
    assert wordmod._spell_ok("o'clock", oclock) is True
    assert wordmod._spell_ok("o\u2019clock", oclock) is True
    assert wordmod._spell_ok("oclock", oclock) is False

    # accept 里的其它写法同口径：也要带撇号
    both = row("don't", ["do not"])
    assert wordmod._spell_ok("don't", both) is True
    assert wordmod._spell_ok("dont", both) is False
    assert wordmod._spell_ok("do not", both) is True     # accept 里那条本来就靠空格分隔，免敲


def test_apostrophe_round_trip_through_the_api():
    """整条链路：带撇号的词当到期词，孩子**敲了撇号**判对、**漏敲**判错。"""
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws9", "wordpass", "撇号家")
        _enable(cli, new_per_day=10)
        c = db.connect()
        row = c.execute("SELECT id, word FROM words WHERE word LIKE 'It''s%'").fetchone()
        assert row, "词库里应该有带撇号的句型"
        c.execute(
            "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
            "last_result,streak_right,correct_count,wrong_count) VALUES(?,?,1,?,?,?, 'wrong',0,1,1)",
            (kid, row["id"], db.today(), db.now(), db.now()),
        )
        c.commit()
        c.close()
        sess = cli.post("/api/words/session/start").json()["session"]
        sid, items = sess["id"], sess["items"]
        target = next((x for x in items if x["word_id"] == row["id"]), None)
        assert target, [x["word"] for x in items]
        assert not target["word"].isalpha()          # 库里这条确实带标点/撇号
        # 敲「字母 + 撇号」（句末标点和空格免敲）→ 判对
        said = "".join(ch for ch in target["word"] if ch.isascii() and (ch.isalpha() or ch == "'"))
        assert "'" in said, said
        r = _spell(cli, sid, target, text=said)
        assert r.status_code == 200 and r.json()["result"] == "right", (target["word"], said, r.text)
        # 同一份答案漏掉撇号 → 判分必须为假
        assert wordmod._spell_ok(said.replace("'", ""), {
            "word_norm": target["word"].lower(), "accept_json": "[]"}) is False
        # 这一局其余的词也一样：敲「字母 + 撇号」一律判对
        for it in items:
            if it["word_id"] == row["id"]:
                continue
            typed = "".join(ch for ch in it["word"] if ch.isascii() and (ch.isalpha() or ch == "'"))
            r = _spell(cli, sid, it, text=typed)
            assert r.status_code == 200 and r.json()["result"] == "right", (it["word"], typed, r.text)

def test_complete_reward_idempotent_and_snapshot():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "ws4", "wordpass", "奖家")
        _enable(cli, new_per_day=2)
        before = cli.get("/api/overview").json()["earned"]
        sess = cli.post("/api/words/session/start").json()["session"]
        sid = sess["id"]
        assert cli.post(f"/api/words/session/{sid}/complete").status_code == 409
        for it in sess["items"]:
            assert _spell(cli, sid, it).status_code == 200
        r = cli.post(f"/api/words/session/{sid}/complete")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["finished"] is True and body["session"]["state"] == "completed"
        # v0.3.53：单词流程不再发阳光（英语阳光改由独立页 /word/ 按当天最好成绩结算）
        assert body["session"]["reward"]["base"] == 0 and body["session"]["reward"]["perfect"] == 0
        after = cli.get("/api/overview").json()["earned"]
        assert after == before
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
        assert {r["reason"]: r["n"] for r in n} == {}
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
        assert u1["source_ver"] == "words-g3-g5-en-v1"
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

def test_scope_review_books_filters_and_preserves_current_behavior():
    db.init_db()
    with TestClient(main.app) as cli:
        kid = _parent(cli, "scopew", "wordpass", "范围家")
        family = cli.post("/api/admin/words/books", json={"name": "家庭词"}).json()["id"]
        assert cli.post("/api/admin/cursor", json={
            "subject_id": "英语", "task_id": "g5s1-en-1-1"
        }).status_code == 200
        cfg = cli.put("/api/admin/words/config", json={
            "enabled": True, "review_mode": "scope",
            "review_books": ["g3s1-en-2", "not-a-book", family, "g3s1-en-1", "g3s1-en-2"],
            "current_book": "g3s1-en-1", "new_per_day": 10, "max_due": 10,
        })
        assert cfg.status_code == 200, cfg.text
        body = cfg.json()
        assert body["review_mode"] == "scope"
        assert body["review_books"] == ["g3s1-en-2", "g3s1-en-1"]

        c = db.connect()
        chosen = c.execute("SELECT id FROM words WHERE book_id='g3s1-en-1' AND active=1 LIMIT 1").fetchone()[0]
        outside = c.execute("SELECT id FROM words WHERE book_id='g5s1-en-1' AND active=1 LIMIT 1").fetchone()[0]
        now, today = db.now(), db.today()
        for wid in (chosen, outside):
            c.execute(
                "INSERT INTO word_progress(kid_id,word_id,interval_idx,due_at,first_seen_at,last_seen_at,"
                "last_result,streak_right,correct_count,wrong_count) VALUES(?,?,0,?,?,?, 'right',1,1,0)",
                (kid, wid, today, now, now),
            )
        c.commit()
        c.close()

        sess = cli.post("/api/words/session/start").json()["session"]
        assert sess and sess["counts"]["due"] == 1
        c = db.connect()
        books = {r["book_id"] for r in c.execute(
            "SELECT DISTINCT w.book_id FROM word_session_items i JOIN words w ON w.id=i.word_id "
            "WHERE i.session_id=?", (sess["id"],)
        ).fetchall()}
        c.close()
        assert books <= {"g3s1-en-1", "g3s1-en-2"}
        assert all(x["entry_type"] not in wordmod.NON_PRACTICE_ENTRY_TYPES for x in sess["items"])
        yday = (__import__("datetime").date.today() - __import__("datetime").timedelta(days=1)).isoformat()
        c = db.connect()
        c.execute("UPDATE word_sessions SET study_date=?, state='abandoned' WHERE id=?", (yday, sess["id"]))
        c.commit()
        c.close()
        r = cli.put("/api/admin/words/config", json={
            "review_mode": "current", "current_book": "g5s1-en-1"
        })
        assert r.status_code == 200, r.text
        assert r.json()["review_mode"] == "current"
        old = cli.post("/api/words/session/start").json()["session"]
        c = db.connect()
        old_books = {r["book_id"] for r in c.execute(
            "SELECT DISTINCT w.book_id FROM word_session_items i JOIN words w ON w.id=i.word_id "
            "WHERE i.session_id=?", (old["id"],)
        ).fetchall()}
        c.close()
        assert "g5s1-en-1" in old_books


def test_english_sentences_pure():
    """两句人话的所有分支（纯函数、不碰库）：没练 / 差几个 / 达标 / 目标关掉 / 英语关掉。"""
    zero = {"wrote": 0, "rounds": 0, "best_score": 0, "sunshine": 0, "sunshine_limit": 10,
            "goal": 10, "goal_done": False, "finished": False}
    seven = dict(zero, wrote=7, best_score=70, sunshine=2)
    done = dict(seven, wrote=20, goal_done=True)
    assert wordmod.today_sentence(False, seven) == "英语单词没开"
    assert wordmod.today_sentence(True, zero) == "今天还没练"
    assert wordmod.today_sentence(True, seven) == "今天写了 7 词（目标 10，还差 3 词） · 最好一轮 70 分 · 阳光 2/10"
    assert wordmod.today_sentence(True, done) == "今天写了 20 词（目标 10，已达标） · 最好一轮 70 分 · 阳光 2/10"
    assert wordmod.today_sentence(True, dict(done, goal=0, goal_done=False)) == "今天写了 20 个词 · 最好一轮 70 分 · 阳光 2/10"

    none = {"days": 0, "words": 0, "rate": None}
    four = {"days": 4, "words": 58, "rate": 78}
    assert wordmod.week_sentence(True, none, zero) == "这周还没练过英语；今天还没练"
    assert wordmod.week_sentence(True, four, seven) == "这周练了 4 天，首轮正确率 78%；今天写了 7/10 词"
    assert wordmod.week_sentence(True, four, done) == "这周练了 4 天，首轮正确率 78%；今天写了 20/10 词（达标）"
    assert wordmod.week_sentence(True, four, dict(done, goal=0, goal_done=False)) == "这周练了 4 天，首轮正确率 78%；今天写了 20 个词"
    assert wordmod.week_sentence(True, {"days": 2, "words": 12, "rate": None}, zero) == "这周练了 2 天；今天还没练"
    assert wordmod.week_sentence(False, four, done) == "英语单词没开"


def test_admin_words_stats_today_and_money_match():
    """P4-a：家长端「今天」的数字要和 /word/ 那一局完全一致（写了 20 词 / 对 14 个 / 阳光 8）。"""
    db.init_db()
    real_now = os.environ.get("SUNSHINE_NOW")
    os.environ["SUNSHINE_NOW"] = "2026-09-16T12:00:00"     # 固定时间：落在打卡时间窗内、due 也稳定
    try:
        with TestClient(main.app) as cli:
            _parent(cli, "w8", "wordpass", "统计家")
            _enable(cli, new_per_day=10, max_due=15, game_size=20, daily_goal=10)

            s = cli.get("/api/admin/words/stats").json()
            assert s["today"]["wrote"] == 0 and s["today"]["rounds"] == 0 and s["today"]["best_score"] == 0
            assert s["today"]["goal"] == 10 and s["today"]["goal_done"] is False and s["today"]["finished"] is False
            assert s["today_sentence"] == "今天还没练"
            assert s["today_source"] == "今天还没开局（下一局按「新词词书」取词）", s["today_source"]
            assert s["week_sentence"] == "这周还没练过英语；今天还没练"
            assert s["week"]["days"] == 0 and s["week"]["rate"] is None

            sess = cli.post("/api/words/game/start").json()["session"]
            sid, items = sess["id"], sess["items"]
            assert len(items) == 20
            for i, it in enumerate(items):
                r = _spell(cli, sid, it, text=(it["word"] if i < 14 else "zzz"))
                assert r.status_code == 200, r.text
            b = cli.post("/api/words/game/settle", json={"session_id": sid}).json()
            assert b["round"]["score"] == 70 and b["today"]["granted"] == 8, b

            s = cli.get("/api/admin/words/stats").json()
            t = s["today"]
            assert (t["wrote"], t["rounds"], t["best_score"], t["sunshine"], t["sunshine_limit"]) == (20, 1, 70, 8, 10), t
            assert t["goal_done"] is True and t["finished"] is True
            assert s["today_sentence"] == "今天写了 20 词（目标 10，已达标） · 最好一轮 70 分 · 阳光 8/10"
            assert s["week"] == {"days": 1, "words": 20, "rate": 70}
            assert s["week_sentence"] == "这周练了 1 天，首轮正确率 70%；今天写了 20/10 词（达标）"
            # 孩子端「今天」也带目标环（P4-b 的入口卡靠它算「今天写了 7/10」）
            kid_today = cli.get("/api/words/today").json()
            assert kid_today["goal"] == {"scored_words": 20, "goal": 10, "goal_done": True}, kid_today["goal"]

            # 目标关掉：句子不再提目标
            assert cli.put("/api/admin/words/config", json={"daily_goal": 0}).status_code == 200
            s = cli.get("/api/admin/words/stats").json()
            assert s["today"]["books"] and s["today"]["books"][0]["n"] == 20, s["today"]["books"]
            assert s["today_source"].startswith("这批词来自：") and "新词：" in s["today_source"], s["today_source"]
            assert s["today"]["goal"] == 0
            assert s["today_sentence"] == "今天写了 20 个词 · 最好一轮 70 分 · 阳光 8/10"

            # 英语关掉：两句都写「英语单词没开」，数字照样读得出来（页面不空白）
            assert cli.put("/api/admin/words/config", json={"enabled": False}).status_code == 200
            s = cli.get("/api/admin/words/stats").json()
            assert s["today_sentence"] == "英语单词没开" and s["week_sentence"] == "英语单词没开"
            assert s["today"]["wrote"] == 20

            # 别的家看不到这一家的数字
            with TestClient(main.app) as cli2:
                _parent(cli2, "w5", "wordpass", "另一家")
                _enable(cli2)
                s2 = cli2.get("/api/admin/words/stats").json()
                assert s2["today"]["wrote"] == 0 and s2["today"]["sunshine"] == 0
                assert s2["today_sentence"] == "今天还没练"
    finally:
        if real_now is None:
            os.environ.pop("SUNSHINE_NOW", None)
        else:
            os.environ["SUNSHINE_NOW"] = real_now


def test_source_sentence_variants():
    """「这批词来自：X · 新词：Y」的几种情况（纯函数，不碰库）。"""
    books = [{"id": "g3s1-en-1", "name": "三年级上 Unit 1", "n": 12},
             {"id": "g5s1-en-1", "name": "五年级上 Unit 1", "n": 8}]
    nb_none = {"id": "", "name": "", "blocked": False, "mode": "current"}
    nb_ok = {"id": "g5s1-en-1", "name": "五年级上 Unit 1", "blocked": False, "mode": "current"}
    nb_blocked = {"id": "g5s1-en-1", "name": "五年级上 Unit 1", "blocked": True, "mode": "current"}
    nb_scope = {"id": "g5s1-en-1", "name": "五年级上 Unit 1", "blocked": False, "mode": "scope"}
    assert wordmod.source_sentence(False, books, nb_ok, True) == ""
    assert wordmod.source_sentence(True, [], nb_ok, False) == "今天还没开局（下一局按「新词词书」取词）"
    got = wordmod.source_sentence(True, books, nb_none, True)
    assert got == "这批词来自：三年级上 Unit 1（12 个）、五年级上 Unit 1（8 个） · 新词：还没选词书 → 不会出新词", got
    assert "被词书锁挡住" in wordmod.source_sentence(True, books, nb_blocked, True)
    assert wordmod.source_sentence(True, books, nb_ok, True).endswith("新词：五年级上 Unit 1")
    assert "（自定义范围）" in wordmod.source_sentence(True, books, nb_scope, True)
    assert wordmod.source_sentence(True, [], nb_ok, True).startswith("这批词来自：没取到词")


def test_admin_weekly_has_english_line():
    """总览页「本周英语」：/api/admin/weekly 的每个孩子带一句（顺带钉住字段形状）。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _parent(cli, "w7", "wordpass", "周报家")
        _enable(cli, daily_goal=10)
        w = cli.get("/api/admin/weekly").json()
        kids = w.get("kids") or []
        assert kids, w
        note = kids[0]["words"]
        assert note["days"] == 0 and note["words"] == 0 and note["rate"] is None, note
        assert note["goal"] == 10 and note["goal_done"] is False and note["today_wrote"] == 0, note
        assert note["sentence"] == "这周还没练过英语；今天还没练", note
