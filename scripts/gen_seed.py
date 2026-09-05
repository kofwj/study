# -*- coding: utf-8 -*-
"""catalog.json → 多学期 seed 结构（terms[] + units + tasks）。

只自动转换「结构」——单元名、任务标题来自目录（可靠）；
每课的 action（做什么/怎么做）只能按关键词给默认值、标记 auto:true，
精确到每课的「怎么做」仍需人工过一遍（同当年实物核对五上）。

输出：
  data/tasks.seed.multi.json   多学期结构化数据
  data/tasks_review_multi.md   人工核对表（重点看 action 默认的条目）
"""
import json
import re
from pathlib import Path

import gen_tasks  # 复用 HINT / SUN / DAILY_TASKS / SUBJECTS

DATA = Path(__file__).parent.parent / "data"
CATALOG = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))

HINT = gen_tasks.HINT
SUN = gen_tasks.SUN
SUBJECTS = gen_tasks.SUBJECTS
DAILY = gen_tasks.DAILY_TASKS

SUBJ_ID = {"语文": "cn", "数学": "ma", "英语": "en", "科学": "kx", "道法": "df"}
GRADE_CN = "一二三四五六"


def term_id(grade: int, term: str) -> str:
    # 跟现有五上手工 id 对齐：g5s1=五年级上，g5x2=五年级下
    return f"g{grade}{'s1' if term == '上' else 'x2'}"


# ---------------- 各科：单元切分 + 动作规则 ----------------

def cn_split(chapters):
    units, cur = [], None
    for line in chapters:
        if "单元" in line:
            cur = {"name": line, "items": []}
            units.append(cur)
        elif cur is None:
            cur = {"name": "入学教育", "items": [line]}
            units.append(cur)
        else:
            cur["items"].append(line)
    return units


def cn_action(t):
    if "习作" in t: return "习作"
    if "口语交际" in t: return "口语"
    if "语文园地" in t: return "复习"
    if "快乐读书吧" in t: return "读书"
    if "古诗" in t or "诗词" in t or "背诵" in t: return "背诵"
    if re.match(r"^\d+\s*\*", t): return "略读"
    return "阅读"


def ma_split(chapters):
    units, cur, prep = [], None, []  # prep = 开篇「数学游戏分享」等无编号项
    for line in chapters:
        if re.match(r"^[一二三四五六七八九十]+ ", line):
            cur = {"name": line, "items": []}
            units.append(cur)
        elif line.startswith("期末"):
            units.append({"name": line, "items": []})
            cur = None
        elif cur is None:
            prep.append(line)
        else:
            cur["items"].append(line)
    if prep:
        units.insert(0, {"name": "数学游戏分享", "items": prep})
    return units


def ma_unit_tasks(name, items):
    """数学：1 单元 → 预习/练习/复习（+实践 per ☆），同手工五上 MA 约定。"""
    if "期末" in name or (not items and "复习" in name):
        return [("复习", "期末总复习")]
    out = [("预习", f"预习「{name}」"),
           ("练习", f"完成「{name}」课后练习"),
           ("复习", f"复习「{name}」")]
    for it in items:
        if it.startswith("☆") or "实践" in it:
            out.append(("实践", f"综合实践：{it.lstrip('☆ ')}"))
    return out


def en_split(chapters):
    units, cur = [], None
    for line in chapters:
        if re.match(r"^(Unit|Module)\s*\d+", line):
            cur = {"name": line, "items": []}
            units.append(cur)
        elif cur is None:
            cur = {"name": "开篇", "items": [line]}
            units.append(cur)
        else:
            cur["items"].append(line)
    return units


def en_action(t):
    if "Project" in t: return "项目"
    if "Word list" in t: return "单词"
    if "Letters" in t: return "拼读"
    if "Big question" in t: return "语法"
    if "Learning tips" in t: return "复习"
    return "跟读"


def kx_df_split(chapters):
    units, cur = [], None
    for line in chapters:
        if "单元" in line:
            cur = {"name": line, "items": []}
            units.append(cur)
        elif cur is None:
            cur = {"name": "开篇", "items": [line]}
            units.append(cur)
        else:
            cur["items"].append(line)
    return units


SPLIT = {"语文": cn_split, "数学": ma_split, "英语": en_split,
         "科学": kx_df_split, "道法": kx_df_split}
ACTION = {"语文": cn_action, "英语": en_action,
          "科学": lambda t: "实践", "道法": lambda t: "阅读"}
DEFAULT_ACTION = {"语文": "阅读", "数学": "练习", "英语": "跟读",
                  "科学": "实践", "道法": "阅读"}


def _task(subject, uid, i, action, title):
    return {"id": f"{uid}-{i}", "subject": subject, "unit_id": uid,
            "action": action, "title": title, "detail": HINT.get(action, ""),
            "sunshine": SUN, "sort": i, "auto": True}


def build_book(book):
    subject, term, grade = book["subject"], book["term"], book["grade"]
    tid = term_id(grade, term)
    subj_id = SUBJ_ID[subject]
    units_grouped = SPLIT[subject](book["chapters"])
    units, tasks = [], []
    for seq, g in enumerate(units_grouped, 1):
        uid = f"{tid}-{subj_id}-{seq}"
        units.append({"id": uid, "subject": subject, "term_id": tid,
                      "seq": seq, "name": g["name"]})
        if subject == "数学":
            for i, (action, title) in enumerate(ma_unit_tasks(g["name"], g["items"]), 1):
                tasks.append(_task(subject, uid, i, action, title))
        else:
            afn = ACTION[subject]
            for i, title in enumerate(g["items"], 1):
                tasks.append(_task(subject, uid, i, afn(title), title))
    return units, tasks


def main():
    units, tasks = [], []
    for book in CATALOG["books"]:
        u, t = build_book(book)
        units.extend(u)
        tasks.extend(t)
    # 兜底：任何没生成任务的单元补一条，避免空单元
    have = {t["unit_id"] for t in tasks}
    for u in units:
        if u["id"] not in have:
            tasks.append(_task(u["subject"], u["id"], 1,
                               DEFAULT_ACTION[u["subject"]], f"完成「{u['name']}」"))
    # 五上语数英用手工实物核对版覆盖自动生成，保留 g5s1-* id（完成记录不断）
    hand = json.loads((DATA / "tasks.seed.json").read_text(encoding="utf-8"))
    hand_subj = {"语文", "数学", "英语"}
    units = [u for u in units if not (u["term_id"] == "g5s1" and u["subject"] in hand_subj)]
    keep = {u["id"] for u in units}
    tasks = [t for t in tasks if t["unit_id"] in keep]
    units.extend(hand["units"])
    tasks.extend(hand["tasks"])

    term_ids = sorted({term_id(b["grade"], b["term"]) for b in CATALOG["books"]})
    terms = []
    for t in term_ids:
        m = re.match(r"g(\d+)([sx])", t)
        g, sx = int(m.group(1)), m.group(2)
        terms.append({"id": t, "label": f"{GRADE_CN[g-1]}年级{'上' if sx=='s' else '下'}",
                      "grade": f"{GRADE_CN[g-1]}年级", "term": "上" if sx == "s" else "下",
                      "version": "江苏南通"})

    seed = {"curriculum_ver": "2026-multi-v1", "subjects": SUBJECTS,
            "terms": terms, "units": units, "tasks": tasks, "daily_tasks": DAILY}
    (DATA / "tasks.seed.multi.json").write_text(
        json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")

    # 人工核对表
    lines = ["# 多学期任务卡 · 人工核对表", "",
             "> 结构自动生成；`action` 全部为默认猜测（auto），重点核对每课 action/怎么做。", ""]
    umap = {u["id"]: u for u in units}
    for tid in term_ids:
        lines.append(f"## {next(t['label'] for t in terms if t['id']==tid)}（{tid}）")
        by_subj = {}
        for t in tasks:
            if umap[t["unit_id"]]["term_id"] == tid:
                by_subj.setdefault(t["subject"], []).append(t)
        for subj in ["语文", "数学", "英语", "科学", "道法"]:
            if subj not in by_subj:
                continue
            lines.append(f"### {subj}（{len(by_subj[subj])} 卡）")
            lines.append("| 单元 | 动作 | 标题 |")
            lines.append("|---|---|---|")
            for t in by_subj[subj]:
                lines.append(f"| {umap[t['unit_id']]['name']} | {t['action']} | {t['title']} |")
            lines.append("")
    (DATA / "tasks_review_multi.md").write_text("\n".join(lines), encoding="utf-8")

    from collections import Counter
    print(f"terms={len(terms)} units={len(units)} tasks={len(tasks)}")
    print(dict(Counter(t["subject"] for t in tasks)))
    print(f"已写 {DATA/'tasks.seed.multi.json'} 和 {DATA/'tasks_review_multi.md'}")


if __name__ == "__main__":
    main()