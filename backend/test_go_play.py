# -*- coding: utf-8 -*-
"""围棋对弈：赢 0 局不给阳光，赢 1 局才给。python3 test_go_play.py"""
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


def test_go_play_needs_a_win():
    db.init_db()
    with TestClient(main.app) as cli:
        assert cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"}).status_code == 200
        before = cli.get("/api/overview").json()["earned"]

        empty = cli.post("/api/complete", json={"task_id": "go-play", "metrics": {}})
        assert empty.status_code == 200, empty.text
        assert empty.json()["delta"] == 0
        assert cli.get("/api/overview").json()["earned"] == before
        daily = next(x for x in cli.get("/api/tasks").json()["daily"] if x["id"] == "go-play")
        assert daily["done_today"]

        assert cli.post("/api/cancel", json={"task_id": "go-play"}).status_code == 200
        lose = cli.post("/api/complete", json={"task_id": "go-play", "metrics": {"win": 0, "lose": 2}})
        assert lose.status_code == 200, lose.text
        assert lose.json()["delta"] == 0
        assert cli.get("/api/overview").json()["earned"] == before

        assert cli.post("/api/cancel", json={"task_id": "go-play"}).status_code == 200
        win = cli.post("/api/complete", json={"task_id": "go-play", "metrics": {"win": 1, "lose": 1}})
        assert win.status_code == 200, win.text
        assert win.json()["delta"] == 5
        assert cli.get("/api/overview").json()["earned"] == before + 5


if __name__ == "__main__":
    test_go_play_needs_a_win()
    print("go_play ok")
