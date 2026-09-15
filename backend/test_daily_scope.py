# -*- coding: utf-8 -*-
"""每日任务「只对某个孩子显示」：kid_id NULL=全家，否则只有那个孩子看得到。

覆盖：
  1. 孩子端 /api/tasks 只返回给自己或全家的每日任务；
  2. 孩子不能通过 /api/complete 完成「只给别的孩子」的任务（404），也不能靠它刷阳光；
  3. 家长端额外拿到 daily_all（全家任务），否则家长在另一个孩子的页签下会以为任务丢了；
  4. 「全勤」只数这个孩子看得到的每日任务 —— 曾经按全家所有任务计数，
     家长给弟弟加一个定向任务，乐乐的全勤就永远差一个。
"""
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


def _setup(cli):
    r = cli.post("/api/auth/register",
                 json={"account": "dsc", "pin": "dailyscope", "family_name": "定向家"})
    assert r.status_code == 200, r.text
    lele = cli.post("/api/admin/kids",
                    json={"name": "乐乐", "account": "dsclele", "pin": "111222"}).json()["id"]
    didi = cli.post("/api/admin/kids",
                    json={"name": "弟弟", "account": "dscdidi", "pin": "333444"}).json()["id"]
    return lele, didi


def _add_daily(cli, name, kid_id=None):
    r = cli.post("/api/admin/daily",
                 json={"subject_id": "体育", "name": name, "sunshine": 5, "kid_id": kid_id})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_daily_scope_filters_kid_side():
    db.init_db()
    with TestClient(main.app) as cli:
        lele, didi = _setup(cli)
        whole = _add_daily(cli, "全家跳绳")
        for_didi = _add_daily(cli, "弟弟拍球", didi)
        for_lele = _add_daily(cli, "乐乐跑步", lele)

        t_lele = cli.get("/api/tasks?selected_kid=" + lele).json()
        t_didi = cli.get("/api/tasks?selected_kid=" + didi).json()
        ids_lele = {d["id"] for d in t_lele["daily"]}
        ids_didi = {d["id"] for d in t_didi["daily"]}

        # 全家的两边都有；定向的只有本人有
        assert whole in ids_lele and whole in ids_didi
        assert for_lele in ids_lele and for_lele not in ids_didi
        assert for_didi in ids_didi and for_didi not in ids_lele

        # 家长端拿到全家任务，带孩子维度信息，这样在谁的页签下都能改
        rows = {d["id"]: d for d in t_lele["daily_all"]}
        assert {whole, for_lele, for_didi} <= set(rows)
        assert rows[for_didi]["kid_id"] == didi
        assert rows[for_lele]["kid_id"] == lele
        assert rows[whole]["kid_id"] in (None, "")

        # 孩子端不该拿到全量视图（否则会看到别的孩子的任务名）
        kid = TestClient(main.app)
        assert kid.post("/api/auth/login", json={"account": "dsclele", "pin": "111222"}).status_code == 200
        assert "daily_all" not in kid.get("/api/tasks").json()


def test_kid_cannot_complete_other_kids_daily():
    db.init_db()
    with TestClient(main.app) as cli:
        lele, didi = _setup(cli)
        for_didi = _add_daily(cli, "弟弟拍球", didi)
        for_lele = _add_daily(cli, "乐乐跑步", lele)

        kid = TestClient(main.app)
        r = kid.post("/api/auth/login", json={"account": "dsclele", "pin": "111222"})
        assert r.status_code == 200, r.text
        assert kid.post("/api/checkin").status_code == 200

        # 自己的能打勾
        assert kid.post("/api/complete", json={"task_id": for_lele}).status_code == 200
        # 别人的打不了，也拿不到阳光
        r = kid.post("/api/complete", json={"task_id": for_didi})
        assert r.status_code == 404, r.text

        # 弟弟那项没被误打上勾
        other = cli.get("/api/tasks?selected_kid=" + didi).json()
        assert not next(d for d in other["daily"] if d["id"] == for_didi)["done_today"]


def test_scope_rejects_other_family_kid():
    """「只给某个孩子」只能指向本家庭的孩子，跨家庭的一律当全家，不写脏数据。"""
    db.init_db()
    with TestClient(main.app) as cli:
        _lele, didi = _setup(cli)
        other = TestClient(main.app)
        assert other.post("/api/auth/register",
                          json={"account": "dsc2", "pin": "dailyscope2",
                                "family_name": "别家"}).status_code == 200
        outsider = other.post("/api/admin/kids",
                              json={"name": "外人", "account": "dscout", "pin": "555666"}).json()["id"]

        did = _add_daily(cli, "指向外人的任务", outsider)
        c = db.connect(admin=True)
        row = c.execute("SELECT kid_id FROM daily_tasks WHERE id=?", (did,)).fetchone()
        assert not row["kid_id"], "跨家庭的 kid_id 不该被写进去"
        # 本家两个孩子都还能看到它（等价于「全家」）
        for kid in (didi,):
            ids = {d["id"] for d in cli.get("/api/tasks?selected_kid=" + kid).json()["daily"]}
            assert did in ids


def test_perfect_week_counts_only_visible_daily():
    """全勤的分母只算这个孩子看得到的每日任务。"""
    db.init_db()
    with TestClient(main.app) as cli:
        lele, didi = _setup(cli)
        # 清掉系统内置每日任务，让「全勤」可判定（否则还要把系统那几项也做了）
        c = db.connect(admin=True)
        c.execute("DELETE FROM daily_tasks WHERE family_id IS NULL")
        c.commit()

        whole = _add_daily(cli, "全家跳绳")
        _for_didi = _add_daily(cli, "弟弟拍球", didi)

        kid = TestClient(main.app)
        assert kid.post("/api/auth/login", json={"account": "dsclele", "pin": "111222"}).status_code == 200
        assert kid.post("/api/checkin").status_code == 200
        # 乐乐只做自己看得到的那一项
        assert kid.post("/api/complete", json={"task_id": whole}).status_code == 200

        c = db.connect()
        # 反向验证：如果按「全家所有每日任务」当分母，这里会是 2，乐乐永远拿不到全勤
        assert c.execute("SELECT COUNT(*) FROM daily_tasks").fetchone()[0] == 2
        cur = main._ach_currents(c, lele)
        assert cur["perfect_week"] == 1, "乐乐做完自己看得到的全部每日任务，就该算全勤"
