# -*- coding: utf-8 -*-
"""五上课程数据回归：单元、任务、考点映射。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = json.loads((ROOT / "data" / "tasks.seed.multi.json").read_text(encoding="utf-8"))
TAGS = json.loads((ROOT / "data" / "knowledge_tags.json").read_text(encoding="utf-8"))


def _g5_units():
    return [u for u in SEED["units"] if str(u.get("id", "")).startswith("g5s1-")]


def _g5_tasks():
    return [t for t in SEED["tasks"] if str(t.get("id", "")).startswith("g5s1-")]


def _g5_maps():
    return [x for x in TAGS["unit_tags"] if str(x.get("unit_id", "")).startswith("g5s1-")]


def test_g5s1_unit_and_task_counts():
    units = _g5_units()
    tasks = _g5_tasks()
    assert len(units) == 35, len(units)
    assert len(tasks) == 149, len(tasks)
    assert len({u["id"] for u in units}) == 35
    assert len({t["id"] for t in tasks}) == 149


def test_g5s1_task_ids_stable():
    tasks = _g5_tasks()
    ids = [t["id"] for t in tasks]
    assert all(i.startswith("g5s1-") for i in ids)
    assert len(ids) == len(set(ids))
    assert "g5s1-cn-1-1" in ids
    assert all(t.get("unit_id") for t in tasks)


def test_g5s1_unique_review_tags():
    maps = _g5_maps()
    unit_ids = {u["id"] for u in _g5_units()}
    mapped = {x["unit_id"] for x in maps}
    assert unit_ids == mapped
    assert all(x.get("tag_ids") for x in maps)
    flat = []
    for x in maps:
        flat.extend(x.get("tag_ids") or [])
    assert len(flat) == 101, len(flat)
    assert len(set(flat)) == 101
    assert not any(x.get("auto") for x in maps)


def test_g1_to_g4_s1_hand_tags():
    """1–4 年级上册有可点选单元考点，不是「字词/阅读理解」那种自动占位。"""
    generic = {"cn-zi", "cn-read", "cn-skim", "ma-calc", "ma-idea", "en-word", "en-listen"}
    by = {x["unit_id"]: x for x in TAGS["unit_tags"]}
    names = {t["id"]: t["name"] for t in TAGS["tags"]}
    expect = {
        "g1s1-cn-2": 3, "g1s1-ma-2": 2, "g1s1-kx-1": 2, "g1s1-df-1": 2,
        "g2s1-cn-1": 2, "g2s1-ma-2": 2, "g3s1-en-1": 2, "g4s1-ma-1": 2,
        "g4s1-cn-1": 2, "g4s1-en-1": 2, "g4s1-kx-3": 2, "g4s1-df-4": 2,
        "g1s1-en-1": 2, "g2s1-en-1": 2,
    }
    units = {u["id"]: u["name"] for u in SEED["units"]}
    assert "Liu Tao" in units["g1s1-en-1"]
    assert "aunt" in units["g2s1-en-1"]
    for uid, n in expect.items():
        row = by[uid]
        assert not row.get("auto"), uid
        assert len(row["tag_ids"]) == n, (uid, row)
        assert not (set(row["tag_ids"]) & generic), uid
        assert all(names.get(i) for i in row["tag_ids"]), uid
    # 入学教育 / 期末复习仍可以是自动占位，家长端不会当考点勾选
    assert by["g1s1-cn-1"].get("auto")
    assert by["g4s1-ma-7"].get("auto")
    g14 = [x for x in TAGS["unit_tags"] if not x.get("auto") and x["unit_id"][:4] in ("g1s1", "g2s1", "g3s1", "g4s1")]
    assert len(g14) == 123, len(g14)
