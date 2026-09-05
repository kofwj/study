# -*- coding: utf-8 -*-
"""P1 登录自检。python3 test_auth.py"""
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


def main_fn():
    db.init_db()
    c = db.connect()
    assert not db.get_setting(c, "admin_pin")
    assert c.execute("SELECT account FROM users WHERE id=?", (db.DEFAULT_PARENT,)).fetchone()[0] == "parent"
    pin_hash = c.execute("SELECT pin_hash FROM users WHERE id=?", (db.DEFAULT_PARENT,)).fetchone()[0]
    assert pin_hash.startswith("pbkdf2$")
    assert db.verify_pin("8888", pin_hash)
    c.close()

    with TestClient(main.app) as cli:
        r = cli.get("/api/tasks")
        assert r.status_code == 401, r.text
        r = cli.post("/api/auth/login", json={"account": "parent", "pin": "0000"})
        assert r.status_code == 401
        r = cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "parent"
        assert "pid" in r.cookies
        r = cli.get("/api/tasks")
        assert r.status_code == 200, r.text
        r = cli.post("/api/admin/pin", json={"pin": "4321"})
        assert r.status_code == 400
        r = cli.post("/api/admin/pin", json={"pin": "parent88"})
        assert r.status_code == 200, r.text
        r = cli.post("/api/auth/logout")
        assert r.status_code == 200
        r = cli.get("/api/tasks")
        assert r.status_code == 401
        r = cli.post("/api/auth/login", json={"account": "parent", "pin": "8888"})
        assert r.status_code == 401
        r = cli.post("/api/auth/login", json={"account": "parent", "pin": "parent88"})
        assert r.status_code == 200
        r = cli.post("/api/auth/login", json={"account": "lele", "pin": "8888"})
        assert r.status_code == 200, r.text
        r = cli.get("/api/admin/weekly")
        assert r.status_code == 403
    print("auth ok")


if __name__ == "__main__":
    main_fn()
