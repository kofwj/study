# -*- coding: utf-8 -*-
"""打卡窗口：每天 7:00–21:00（上海时间）。"""
import os
from datetime import datetime

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SECRET_KEY"] = "prod-secret"
os.environ["SUNSHINE_FORCE_CHECKIN_WINDOW"] = "1"

import db  # noqa: E402
import main  # noqa: E402


def _at(h, m=0):
    return datetime(2026, 9, 11, h, m, tzinfo=db.TZ)


def test_window_hours():
    os.environ["SUNSHINE_FORCE_CHECKIN_WINDOW"] = "1"
    early = main.checkin_window(_at(6, 59))
    assert early["open"] is False and "太早" in early["hint"]
    open7 = main.checkin_window(_at(7, 0))
    assert open7["open"] is True and open7["hint"] == ""
    open20 = main.checkin_window(_at(20, 59))
    assert open20["open"] is True
    closed = main.checkin_window(_at(21, 0))
    assert closed["open"] is False and "打烊" in closed["hint"]


def test_tests_skip_window_by_default():
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ.pop("SUNSHINE_FORCE_CHECKIN_WINDOW", None)
    late = main.checkin_window(_at(22, 0))
    assert late["open"] is True


def test_api_rejects_after_hours():
    import tempfile
    from pathlib import Path
    from fastapi.testclient import TestClient
    os.environ["SECRET_KEY"] = "prod-secret"
    os.environ["SUNSHINE_FORCE_CHECKIN_WINDOW"] = "1"
    os.environ["SUNSHINE_NOW"] = "2026-09-11T22:10:00"
    os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "w.db")
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        r = cli.post("/api/checkin")
        assert r.status_code == 403
        assert "打烊" in r.json()["detail"]
        daily = cli.get("/api/tasks").json()["daily"][0]["id"]
        r = cli.post("/api/complete", json={"task_id": daily})
        assert r.status_code == 403
        r = cli.post("/api/words/session/start")
        assert r.status_code == 403


if __name__ == "__main__":
    test_window_hours()
    test_tests_skip_window_by_default()
    test_api_rejects_after_hours()
    print("checkin window ok")
