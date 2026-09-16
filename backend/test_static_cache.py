# -*- coding: utf-8 -*-
"""静态资源 gzip + 缓存头。python3 -m pytest -q test_static_cache.py"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ.pop("DATABASE_APP_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / f"{Path(__file__).stem}.db")
os.environ["SECRET_KEY"] = "test-secret"

import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


def test_static_cache_control_table():
    assert main.static_cache_control("/api/health") is None
    assert main.static_cache_control("/api/tasks") is None
    assert main.static_cache_control("/") == "no-cache"
    assert main.static_cache_control("/index.html") == "no-cache"
    assert main.static_cache_control("/word/") == "no-cache"
    assert main.static_cache_control("/word/index.html") == "no-cache"
    assert main.static_cache_control("/sw.js") == "no-cache"
    assert main.static_cache_control("/assets/main-abc.js") == main.CACHE_IMMUTABLE
    assert main.static_cache_control("/sprites/foo.webp") == main.CACHE_IMMUTABLE
    assert main.static_cache_control("/sounds/coin.mp3") == main.CACHE_IMMUTABLE
    assert main.static_cache_control("/manifest.webmanifest") is None


def test_gzip_and_cache_headers_on_real_files():
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if not (dist / "index.html").exists():
        return
    db.init_db()
    assets = dist / "assets"
    js = next(assets.glob("main-*.js"), None)
    assert js is not None
    with TestClient(main.app) as cli:
        html = cli.get("/")
        assert html.status_code == 200
        assert html.headers.get("cache-control") == "no-cache"

        sw = cli.get("/sw.js")
        assert sw.status_code == 200
        assert sw.headers.get("cache-control") == "no-cache"

        js_r = cli.get("/assets/" + js.name, headers={"Accept-Encoding": "gzip"})
        assert js_r.status_code == 200
        assert js_r.headers.get("cache-control") == main.CACHE_IMMUTABLE
        assert js_r.headers.get("content-encoding") == "gzip"
        raw = getattr(js_r, "num_bytes_downloaded", 0)
        assert raw == 0 or raw < js.stat().st_size

        health = cli.get("/api/health", headers={"Accept-Encoding": "gzip"})
        assert health.status_code == 200
        assert health.json()["ok"] is True
        assert "max-age=31536000" not in (health.headers.get("cache-control") or "")
