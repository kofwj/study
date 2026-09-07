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
