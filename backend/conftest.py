# -*- coding: utf-8 -*-
"""pytest 隔离：每个用例独立临时库，连接时再读 SUNSHINE_DB。"""
import pytest


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_APP_URL", raising=False)
    monkeypatch.setenv("SUNSHINE_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
