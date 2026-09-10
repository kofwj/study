# -*- coding: utf-8 -*-
"""P3 多家庭隔离。python3 test_family.py"""
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


def test_family():
    db.init_db()
    with TestClient(main.app) as a, TestClient(main.app) as b:
        r = a.post("/api/auth/register", json={"account": "alice", "pin": "alice888", "family_name": "A家"})
        assert r.status_code == 200, r.text
        r = a.post("/api/admin/kids", json={"name": "阿乐", "account": "ale", "pin": "111222"})
        assert r.status_code == 200, r.text
        r = a.post("/api/admin/rewards", json={"name": "A家奖", "price": 3, "category": "测"})
        assert r.status_code == 200, r.text
        names_a = {x["name"] for x in a.get("/api/rewards").json()}
        assert "A家奖" in names_a

        r = b.post("/api/auth/register", json={"account": "bob", "pin": "bob88888", "family_name": "B家"})
        assert r.status_code == 200, r.text
        r = b.post("/api/admin/kids", json={"name": "波波", "account": "bobo", "pin": "222333"})
        assert r.status_code == 200
        names_b = {x["name"] for x in b.get("/api/rewards").json()}
        assert "A家奖" not in names_b
        rid_a = next(x["id"] for x in a.get("/api/rewards").json() if x["name"] == "A家奖")
        assert a.post("/api/rewards/redeem", json={"reward_id": rid_a}).status_code == 200
        pend = next(x for x in a.get("/api/admin/redemptions").json() if x["status"] == "pending")
        assert b.post(f"/api/admin/redemptions/{pend['id']}/approve").status_code == 404
        assert b.post(f"/api/admin/redemptions/{pend['id']}/reject").status_code == 404
        r = a.post("/api/admin/daily", json={"subject_id": "体育", "name": "A家跳绳", "sunshine": 3})
        assert r.status_code == 200, r.text
        a_daily = {d["name"] for d in a.get("/api/tasks").json()["daily"]}
        b_daily = {d["name"] for d in b.get("/api/tasks").json()["daily"]}
        assert "A家跳绳" in a_daily and "A家跳绳" not in b_daily
        kids_b = b.get("/api/admin/kids").json()
        assert all(k["account"] != "ale" for k in kids_b)

        code = a.post("/api/admin/invite").json()["code"]
        r = b.post("/api/auth/join", json={"account": "carol", "pin": "carol888", "code": code, "name": "卡卡"})
        assert r.status_code == 200, r.text
        # carol 进了 A 家，应看到 A 家奖
        with TestClient(main.app) as c:
            r = c.post("/api/auth/login", json={"account": "carol", "pin": "carol888"})
            assert r.status_code == 200
            names_c = {x["name"] for x in c.get("/api/rewards").json()}
            assert "A家奖" in names_c
        members = a.get("/api/admin/members").json()
        carol = next(m for m in members if m["account"] == "carol")
        me = a.get("/api/auth/me").json()
        assert me["id"] and me.get("parent_role") == "owner"
        # 成员不能删人、不能转让、不能删孩子
        with TestClient(main.app) as c:
            assert c.post("/api/auth/login", json={"account": "carol", "pin": "carol888"}).status_code == 200
            assert c.get("/api/auth/me").json()["parent_role"] == "member"
            assert c.delete("/api/admin/members/" + me["id"]).status_code == 403
            assert c.post("/api/admin/transfer-owner", json={"new_owner_id": me["id"]}).status_code == 403
            kid_id = a.get("/api/admin/kids").json()[0]["id"]
            assert c.delete("/api/admin/kids/" + kid_id).status_code == 403
        # 创建者把权限交给成员
        r = a.post("/api/admin/transfer-owner", json={"new_owner_id": carol["id"]})
        assert r.status_code == 200, r.text
        assert a.get("/api/auth/me").json()["parent_role"] == "member"
        with TestClient(main.app) as c:
            assert c.post("/api/auth/login", json={"account": "carol", "pin": "carol888"}).status_code == 200
            assert c.get("/api/auth/me").json()["parent_role"] == "owner"
            # 交回去
            assert c.post("/api/admin/transfer-owner", json={"new_owner_id": me["id"]}).status_code == 200
        assert a.get("/api/auth/me").json()["parent_role"] == "owner"
        mid = carol["id"]
        assert a.delete("/api/admin/members/" + mid).status_code == 200
        with TestClient(main.app) as c2:
            r = c2.post("/api/auth/login", json={"account": "carol", "pin": "3333"})
            assert r.status_code == 401
        # 邀请码保护：开=一次性，用一次作废
        assert a.put("/api/admin/family/invite_protect", json={"enabled": True}).status_code == 200
        code1 = a.post("/api/admin/invite").json()["code"]
        assert b.post("/api/auth/join", json={"account": "dave", "pin": "dave8888", "code": code1, "name": "戴夫"}).status_code == 200
        assert b.post("/api/auth/join", json={"account": "erin", "pin": "erin8888", "code": code1, "name": "二用"}).status_code != 200
        ivs = {x["code"]: x for x in a.get("/api/admin/invites").json()}
        assert ivs[code1]["used_count"] == 1 and ivs[code1]["used_by"] == "戴夫"
        print("family ok")


def test_penalty_switch_and_ledger():
    db.init_db()
    with TestClient(main.app) as cli, TestClient(main.app) as other, TestClient(main.app) as kidc:
        assert cli.post("/api/auth/register", json={"account": "pena", "pin": "penalty8", "family_name": "扣分家"}).status_code == 200
        fam = cli.get("/api/admin/family").json()
        assert fam.get("penalty_enabled") in (0, False)
        kid = cli.post("/api/admin/kids", json={"name": "甲", "account": "jia3", "pin": "111222"}).json()["id"]
        q = "?selected_kid=" + kid
        assert cli.post("/api/admin/penalty" + q, json={"amount": 5, "reason": "磨蹭"}).status_code == 403
        assert cli.put("/api/admin/family/penalty", json={"enabled": True}).status_code == 200
        c = db.connect()
        db.insert_ledger(c, db.today(), 20, "task", "seed-pen", "测试余额", kid)
        c.commit(); c.close()
        ov = cli.get("/api/overview" + q).json()
        earned0, bal0, level0 = ov["earned"], ov["balance"], ov["level"]
        assert earned0 == 20 and bal0 == 20
        r = cli.post("/api/admin/penalty" + q, json={"amount": 5, "reason": "磨蹭"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delta"] == -5 and body["balance"] == bal0 - 5
        assert body["earned"] == earned0 - 5
        assert body["earned_before"] == earned0
        assert cli.post("/api/admin/penalty" + q, json={"amount": body["balance"] + 1, "reason": "磨蹭"}).status_code == 400
        assert cli.post("/api/admin/penalty" + q, json={"amount": 1, "reason": "其他"}).status_code == 400
        lid = body["id"]
        c1 = cli.post(f"/api/admin/penalty/{lid}/cancel" + q)
        assert c1.status_code == 200, c1.text
        assert c1.json()["balance"] == bal0 and c1.json()["earned"] == earned0
        assert cli.post(f"/api/admin/penalty/{lid}/cancel" + q).status_code == 409
        r2 = cli.post("/api/admin/penalty" + q, json={"amount": 8, "reason": "没礼貌"})
        assert r2.status_code == 200
        assert cli.post(f"/api/admin/penalty/{r2.json()['id']}/cancel" + q).status_code == 200
        wk = cli.get("/api/admin/weekly" + q).json()
        assert wk["penalty_net"] == 0
        r3 = cli.post("/api/admin/penalty" + q, json={"amount": 3, "reason": "其他", "note": "约定没做到"})
        assert r3.status_code == 200, r3.text
        wk2 = cli.get("/api/admin/weekly" + q).json()
        assert wk2["penalty_net"] == -3 and wk2["penalty_count"] >= 1
        ov2 = cli.get("/api/overview" + q).json()
        assert ov2["earned"] == earned0 - 3 and ov2["balance"] == bal0 - 3
        assert ov2["level"] == level0
        got = cli.get("/api/admin/penalty" + q).json()
        rows = got["items"] if isinstance(got, dict) else got
        assert any(x["id"] == r3.json()["id"] and not x["cancelled"] for x in rows)
        sm = got["summary"]
        assert sm["net"] == -3 and sm["count"] == 1 and sm["amount"] == 3
        other_row = next(x for x in sm["by_reason"] if x["reason"] == "其他")
        assert other_row["count"] == 1 and other_row["amount"] == 3
        assert all(x["count"] == 0 for x in sm["by_reason"] if x["reason"] != "其他")
        assert other.post("/api/auth/register", json={"account": "penb", "pin": "penalty9", "family_name": "别家"}).status_code == 200
        assert other.post("/api/admin/penalty", json={"amount": 1, "reason": "磨蹭"}).status_code == 403
        assert kidc.post("/api/auth/login", json={"account": "jia3", "pin": "111222"}).status_code == 200
        assert kidc.post("/api/admin/penalty", json={"amount": 1, "reason": "磨蹭"}).status_code == 403
        led = kidc.get("/api/ledger?limit=5").json()
        assert any(x["reason"] == "penalty" and x["delta"] == -3 for x in led)


def test_penalty_concurrent_sqlite():
    """测试SQLite并发扣分的IMMEDIATE事务保护"""
    db.init_db()
    with TestClient(main.app) as cli1, TestClient(main.app) as cli2:
        # 创建家庭和孩子
        assert cli1.post("/api/auth/register", json={"account": "concurrent", "pin": "test1234", "family_name": "并发家"}).status_code == 200
        kid = cli1.post("/api/admin/kids", json={"name": "测试", "account": "test1", "pin": "111222"}).json()["id"]
        q = "?selected_kid=" + kid
        
        # 开启扣分
        assert cli1.put("/api/admin/family/penalty", json={"enabled": True}).status_code == 200
        
        # 给孩子初始余额10阳光
        c = db.connect()
        db.insert_ledger(c, db.today(), 10, "task", "init-concurrent", "初始余额", kid)
        c.commit()
        c.close()
        
        # 验证余额
        ov = cli1.get("/api/overview" + q).json()
        assert ov["balance"] == 10
        
        # cli2用同一家长账号登录（模拟并发）
        assert cli2.post("/api/auth/login", json={"account": "concurrent", "pin": "test1234"}).status_code == 200
        
        # 同时扣分：cli1扣6，cli2扣6
        # 由于IMMEDIATE事务，至少有一个会失败或者总余额不会为负
        import concurrent.futures
        
        def penalty_request(client, amount):
            try:
                r = client.post("/api/admin/penalty" + q, json={"amount": amount, "reason": "磨蹭"})
                return r.status_code, r.json() if r.status_code == 200 else r.text
            except Exception as e:
                return 500, str(e)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(penalty_request, cli1, 6)
            future2 = executor.submit(penalty_request, cli2, 6)
            
            result1 = future1.result()
            result2 = future2.result()
        
        # 验证结果：至少有一个成功，余额不为负
        final_balance = cli1.get("/api/overview" + q).json()["balance"]
        
        success_count = sum(1 for r in [result1, result2] if r[0] == 200)
        
        # 两种合理结果：
        # 1. 两个都成功但有序执行：10-6-6=-2不可能，所以第二个会失败
        # 2. 一个成功一个失败：余额=4或4
        
        if success_count == 2:
            # 如果两个都成功，余额应该是负数，这不应该发生
            assert False, f"Both succeeded but balance is {final_balance}, should not be negative!"
        elif success_count == 1:
            # 一个成功，余额应该是4
            assert final_balance == 4, f"One succeeded, balance should be 4, got {final_balance}"
        else:
            # 两个都失败也不对
            assert False, f"Both failed: {result1}, {result2}"


def test_register_recover_and_kid_cap():
    db.init_db()
    with TestClient(main.app) as cli:
        r = cli.post("/api/auth/register", json={"account": "reca", "pin": "reca8888", "family_name": "找回家", "name": "阿爸"})
        assert r.status_code == 200, r.text
        code = r.json()["recovery_code"]
        assert len(code) == 10
        c = db.connect(admin=True)
        names = {r[0] for r in c.execute("SELECT name FROM rewards").fetchall()}
        c.close()
        assert "看动画30分钟" in names
        assert cli.get("/api/admin/kids").json() == []
        for i in range(5):
            rr = cli.post("/api/admin/kids", json={"name": "娃%d" % i, "account": "kidcap%d" % i, "pin": "111222"})
            assert rr.status_code == 200, rr.text
        r6 = cli.post("/api/admin/kids", json={"name": "老六", "account": "kidcap6", "pin": "111222"})
        assert r6.status_code == 400

        other = TestClient(main.app)
        assert other.post("/api/auth/login", json={"account": "reca", "pin": "reca8888"}).status_code == 200
        bad = cli.post("/api/auth/recover", json={"account": "reca", "code": "WRONGCODE1", "pin": "newpin888"})
        assert bad.status_code == 400
        ok = cli.post("/api/auth/recover", json={"account": "reca", "code": code, "pin": "newpin888"})
        assert ok.status_code == 200, ok.text
        assert other.get("/api/admin/kids").status_code == 401
        assert cli.post("/api/auth/login", json={"account": "reca", "pin": "reca8888"}).status_code == 401
        assert cli.post("/api/auth/login", json={"account": "reca", "pin": "newpin888"}).status_code == 200
        again = cli.post("/api/auth/recover", json={"account": "reca", "code": code, "pin": "other888"})
        assert again.status_code == 400


def test_register_daily_limit_persists():
    db.init_db()
    with TestClient(main.app) as cli:
        for i in range(3):
            r = cli.post("/api/auth/register", json={"account": "lim%d" % i, "pin": "limit888", "family_name": "限%d" % i})
            assert r.status_code == 200, r.text
        r = cli.post("/api/auth/register", json={"account": "lim3", "pin": "limit888", "family_name": "限3"})
        assert r.status_code == 429
    with TestClient(main.app) as cli2:
        r = cli2.post("/api/auth/register", json={"account": "lim4", "pin": "limit888", "family_name": "限4"})
        assert r.status_code == 429


def test_join_guess_rate_limit():
    db.init_db()
    with TestClient(main.app) as a:
        assert a.post("/api/auth/register", json={"account": "joina", "pin": "join8888", "family_name": "加家"}).status_code == 200
        for i in range(main.RATE_MAX):
            r = a.post("/api/auth/join", json={"account": "guess%d" % i, "pin": "guess888", "code": "DEADCODE", "name": "猜"})
            assert r.status_code == 404, r.text
        r = a.post("/api/auth/join", json={"account": "guessx", "pin": "guess888", "code": "DEADCODE", "name": "猜"})
        assert r.status_code == 429


if __name__ == "__main__":
    test_family()
    test_penalty_switch_and_ledger()
    test_penalty_concurrent_sqlite()
    test_register_recover_and_kid_cap()
    test_register_daily_limit_persists()
    test_join_guess_rate_limit()
