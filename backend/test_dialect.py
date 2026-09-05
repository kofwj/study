# -*- coding: utf-8 -*-
"""方言自检：ON CONFLICT DO NOTHING RETURNING / upsert。python3 test_dialect.py"""
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
os.environ["SUNSHINE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")

import db  # noqa: E402


def main():
    assert db._pg_query("SELECT * FROM t WHERE a=? AND b='?'") == "SELECT * FROM t WHERE a=%s AND b='?'"
    assert db._pg_query("SELECT 'it''s' WHERE x=?") == "SELECT 'it''s' WHERE x=%s"
    assert db._pg_query("SELECT to_char(x,'%Y') WHERE a=?") == "SELECT to_char(x,'%%Y') WHERE a=%s"
    db.init_db()
    c = db.connect()
    i1 = db.insert(c, "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?) ON CONFLICT DO NOTHING;",
                   ("2099-01-01", 0, db.now(), db.DEFAULT_KID))
    assert i1 is not None
    i2 = db.insert(c, "INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
                   ("2099-01-01", 0, db.now(), db.DEFAULT_KID))
    assert i2 is None
    cid = db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                    "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                    ("t-unit", "2099-01-01", "completed", 5, None, "unit", db.now(), db.DEFAULT_KID))
    assert cid is not None
    assert db.insert(c, "INSERT INTO completions(task_id,date,status,sunshine,metrics,kind,created_at,kid_id) "
                     "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                     ("t-unit", "2099-01-02", "completed", 5, None, "unit", db.now(), db.DEFAULT_KID)) is None
    db.set_setting(c, "k", "1")
    db.set_setting(c, "k", "2")
    assert db.get_setting(c, "k") == "2"
    c.commit()
    c.close()
    db.init_db()  # 二次 init 幂等
    c = db.connect()
    n = c.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    assert n >= 8
    assert db.get_setting(c, "k") == "2"
    migs = {r[0] for r in c.execute("SELECT id FROM schema_migrations").fetchall()}
    assert {"001_identity", "002_kid_id"} <= migs
    assert c.execute("SELECT 1 FROM users WHERE id=?", (db.DEFAULT_KID,)).fetchone()
    assert c.execute("SELECT kid_id FROM checkins LIMIT 1").fetchone()[0] == db.DEFAULT_KID
    fp = db.fingerprints(c)
    assert fp["checkins"] >= 1 and fp["completions"] >= 1
    c.close()
    print("ok", i1, "subjects", n, "migs", sorted(migs))


if __name__ == "__main__":
    main()
