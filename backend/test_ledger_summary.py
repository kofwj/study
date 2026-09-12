# -*- coding: utf-8 -*-
"""阳光周聚合端点 /api/ledger/summary：自然周边界、口径分类、多娃隔离。"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SUNSHINE_NOW"] = "2026-09-09 12:00:00"  # 周三

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


def seed(c, kid, date, delta, reason, ref, account="pocket", note="测试"):
    db.insert_ledger(c, date, delta, reason, ref, note, kid, account)


def test_ledger_summary():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/register", json={"account": "sumparent", "pin": "parent123", "family_name": "聚合家"}).status_code == 200
        r = cli.post("/api/admin/kids", json={"name": "甲", "account": "sumkid", "pin": "111222", "term_id": "g5s1"})
        kid = r.json()["id"]
        assert cli.post("/api/auth/login", json={"account": "sumkid", "pin": "111222"}).status_code == 200

        c = db.connect(admin=True)
        # 本周（09-07 周一 ~ 09-13 周日）
        seed(c, kid, "2026-09-08", 5, "task", "s1")                 # 周二 课文 +5
        seed(c, kid, "2026-09-09", 3, "daily", "s2")                # 周三 打卡 +3
        seed(c, kid, "2026-09-09", -3, "cancel", "s2-cancel")       # 周三 冲正 -3
        seed(c, kid, "2026-09-09", -20, "bank_deposit", "s3-pocket")  # 口袋转出（生产符号）
        seed(c, kid, "2026-09-09", 20, "bank_deposit", "s3-bank", account="bank")  # 银行侧不重复计
        seed(c, kid, "2026-09-09", 1, "bank_interest", "s3-int", account="bank")  # 利息算攒到
        seed(c, kid, "2026-09-09", -10, "redeem", "s4")             # 周三 兑换 -10
        seed(c, kid, "2026-09-07", 2, "milestone", "s5")            # 周一 连击 +2（box 途径）
        seed(c, kid, "2026-09-13", 4, "word_perfect", "s6")         # 周日 单词全对 +4
        seed(c, kid, "2026-09-09", 50, "task", "s-bank", account="bank")  # 其它银行流水不计入

        seed(c, kid, "2026-09-09", -5, "penalty", "pen1", note="作业拖拉")  # 约定不进柱
        # 上周
        seed(c, kid, "2026-09-02", 7, "task", "p1")
        c.commit()
        c.close()

        # 别的娃的流水不计入（先切回家长会话）
        assert cli.post("/api/auth/login", json={"account": "sumparent", "pin": "parent123"}).status_code == 200
        r2 = cli.post("/api/admin/kids", json={"name": "乙", "account": "sumkid2", "pin": "111222", "term_id": "g5s1"})
        kid2 = r2.json()["id"]
        c = db.connect(admin=True)
        seed(c, kid2, "2026-09-09", 99, "task", "other-kid")
        c.commit()
        c.close()

        assert cli.post("/api/auth/login", json={"account": "sumkid", "pin": "111222"}).status_code == 200
        r = cli.get("/api/ledger/summary")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["today"] == "2026-09-09"
        assert d["week_start"] == "2026-09-07"
        assert len(d["days"]) == 7
        assert d["days"][0]["date"] == "2026-09-07" and d["days"][6]["date"] == "2026-09-13"

        tue = d["days"][1]
        assert tue["earn"] == 5 and tue["by_reason"]["task"] == 5
        wed = d["days"][2]
        # 20 存银行 + 1 利息 + 3 打卡 - 3 冲正 = 21；兑换 10；约定不进 earn/spend
        assert wed["earn"] == 21 and wed["spend"] == 10
        assert wed["by_reason"]["daily"] == 3 and wed["by_reason"]["bank"] == 21
        mon = d["days"][0]
        assert mon["earn"] == 2 and mon["by_reason"]["box"] == 2
        sun = d["days"][6]
        assert sun["earn"] == 4 and sun["by_reason"]["word"] == 4
        # 周内未来天（周四~周六）为 0
        assert all(d["days"][i]["earn"] == 0 for i in (3, 4, 5))
        assert d["week_in"] == 32 and d["week_out"] == 10

        assert d["prev_week"][2]["earn"] == 7
        assert d["penalty_today"]["n"] == 5 and d["penalty_today"]["count"] == 1
        assert d["penalty_today"]["reason"] == "作业拖拉"

        # 撤回约定后 penalty_today 清空
        c = db.connect(admin=True)
        seed(c, kid, "2026-09-09", 5, "penalty_cancel", "pen1", note="撤回扣分")
        c.commit()
        c.close()
        d = cli.get("/api/ledger/summary").json()
        assert d["penalty_today"] is None
        assert d["week_in"] == 32


        # 上一周
        r = cli.get("/api/ledger/summary?offset=1")
        d = r.json()
        assert d["week_start"] == "2026-08-31"
        assert d["days"][2]["earn"] == 7 and d["week_in"] == 7

        # 多娃隔离：乙只见自己的 99，看不到甲的流水
        assert cli.post("/api/auth/login", json={"account": "sumkid2", "pin": "111222"}).status_code == 200
        d2 = cli.get("/api/ledger/summary").json()
        assert d2["week_in"] == 99
        assert d2["penalty_today"] is None

        # 未登录 401
        assert cli.post("/api/auth/logout").status_code == 200
        assert cli.get("/api/ledger/summary").status_code == 401


def test_summary_offset_clamped():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        assert cli.get("/api/ledger/summary?offset=-5").status_code == 200
        assert cli.get("/api/ledger/summary?offset=999").status_code == 200

