# -*- coding: utf-8 -*-
"""生成三科任务卡草稿（按单元 + 固定动作，方案3）。

下学期只改 UNITS 里的单元名，重跑本脚本即可再生任务卡。
"""
import json, os

TERM = {"id": "g5s1", "label": "五年级上", "grade": "五年级", "term": "上",
        "version": "江苏南通 · 2026秋新教材"}
SUN = 5  # 默认每卡阳光

SUBJECTS = ["语文", "数学", "英语", "科学", "道法", "体育", "音美", "综合"]

# 每日循环任务（无单元，每天出现）。metrics 为要记录的数字维度。
DAILY_TASKS = [
    {"id": "pe-jump-rope", "subject": "体育", "name": "跳绳打卡",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 3,
                   "note": "破个人纪录才叠加（首日只记基线，防囤分）"},
     "metrics": [
         {"id": "t100", "label": "100下用时", "unit": "秒", "direction": "lower_better", "note": "跳完100下用时（秒）"},
         {"id": "n1m", "label": "1分钟跳多少个", "unit": "个", "direction": "higher_better", "note": "1分钟最多跳多少个"},
     ]},
]

# 动作模板：code -> (标签, 标题模板)
ACTIONS = {
    "语文": [
        ("read",    "朗读课文", "朗读本单元课文"),
        ("dict",    "生字听写", "听写/默写本单元生字词"),
        ("recite",  "背诵默写", "背诵默写本单元要求篇目"),
        ("exer",    "课后练习", "完成本单元练习（同步练习册）"),
        ("review",  "单元复习", "复习本单元重点并整理错题"),
    ],
    "数学": [
        ("preview", "预习例题", "预习本单元例题，圈出疑问"),
        ("mental",  "口算天天练", "口算 20 题"),
        ("exer",    "课后练习", "完成本单元课后练习"),
        ("review",  "单元复习", "整理本单元知识点与公式"),
    ],
    "英语": [
        ("words",   "背单词",   "背本单元词汇（Word list）"),
        ("phonics", "拼读练习", "练习 Sounds in focus 拼读"),
        ("read",    "跟读课文", "跟读 Story time，模仿语音语调"),
        ("grammar", "语法练习", "掌握并练习 Grammar time 句型"),
        ("wrapup",  "Wrap-up 任务", "完成 Wrap-up time 任务"),
    ],
}

# 单元 -> (名称, 综合实践名 or None)
MATH_UNITS = [
    ("图形的运动", "图案的还原"),
    ("统计表和条形统计图（二）", "绿色出行"),
    ("多边形的面积", "农田收入调查"),
    ("小数乘法和除法（一）", None),
    ("可能性", None),
    ("因数与倍数", None),
    ("用字母表示数量关系（一）", "钉子板上的多边形"),
    ("观察物体（三）", None),
]
CN_UNITS = ["第一单元", "第二单元", "第三单元", "第四单元",
            "第五单元", "第六单元", "第七单元", "第八单元"]
EN_UNITS = ["Good habits", "I feel good", "Hobbies", "Safety first",
            "At weekends", "Getting along with others", "Shopping smart",
            "We love festivals"]

SUBJ_ID = {"语文": "cn", "数学": "ma", "英语": "en"}

def build():
    units, tasks = [], []
    def add_unit(subj, name, seq):
        uid = f"{SUBJ_ID[subj]}-{seq}"
        units.append({"id": uid, "subject": subj, "term_id": TERM["id"],
                      "seq": seq, "name": name})
        return uid
    def add_tasks(subj, uid, seq, extra_practice=None):
        for i, (code, label, title) in enumerate(ACTIONS[subj]):
            tasks.append({
                "id": f"{uid}-{code}", "subject": subj, "unit_id": uid,
                "action": label, "title": title, "sunshine": SUN,
                "sort": i + 1,
            })
        if extra_practice:
            tasks.append({
                "id": f"{uid}-practice", "subject": subj, "unit_id": uid,
                "action": "综合实践", "title": f"完成综合实践「{extra_practice}」",
                "sunshine": SUN, "sort": 99,
            })
    # 语文
    for i, name in enumerate(CN_UNITS, 1):
        add_tasks("语文", add_unit("语文", name, i), i)
    # 数学
    for i, (name, prac) in enumerate(MATH_UNITS, 1):
        add_tasks("数学", add_unit("数学", name, i), i, prac)
    # 英语
    for i, name in enumerate(EN_UNITS, 1):
        add_tasks("英语", add_unit("英语", name, i), i)
    # 英语 Project
    for j, name in enumerate(["A happy life poster", "An invitation card"], 1):
        uid = f"en-p{j}"
        units.append({"id": uid, "subject": "英语", "term_id": TERM["id"],
                      "seq": 8 + j, "name": f"Project {j}：{name}"})
        tasks.append({"id": f"{uid}-project", "subject": "英语", "unit_id": uid,
                      "action": "项目任务", "title": f"完成 Project：{name}",
                      "sunshine": SUN, "sort": 1})
    return units, tasks

def main():
    units, tasks = build()
    os.makedirs("data", exist_ok=True)
    with open("data/tasks.seed.json", "w", encoding="utf-8") as f:
        json.dump({"term": TERM, "subjects": SUBJECTS,
                   "units": units, "tasks": tasks, "daily_tasks": DAILY_TASKS},
                  f, ensure_ascii=False, indent=2)

    # 过目用 markdown
    lines = ["# 任务卡草稿（方案3：单元 + 固定动作）", "",
             f"> 学期：**{TERM['label']}** · {TERM['version']} · 每卡默认 {SUN} 阳光",
             f"> 单元卡合计：**{len(tasks)}** 张（{len(units)} 个单元/项目）",
             f"> 每日卡：**{len(DAILY_TASKS)}** 张（体育跳绳等）", ""]
    by_subj = {}
    unit_map = {u["id"]: u for u in units}
    for t in tasks:
        by_subj.setdefault(t["subject"], []).append(t)
    for subj in ["语文", "数学", "英语"]:
        lines.append(f"## {subj}（{len(by_subj[subj])} 卡）")
        lines.append("")
        lines.append("| 单元 | 动作 | 标题 | 阳光 |")
        lines.append("|---|---|---|---|")
        for t in by_subj[subj]:
            lines.append(f"| {unit_map[t['unit_id']]['name']} | {t['action']} | {t['title']} | {t['sunshine']} |")
        lines.append("")
    if DAILY_TASKS:
        lines.append("## 体育（每日循环）")
        lines.append("")
        lines.append("| 任务 | 频率 | 记录维度 | 阳光 |")
        lines.append("|---|---|---|---|")
        for t in DAILY_TASKS:
            dims = " · ".join(
                f"{m['label']}({m['unit']}，越{'多' if m['direction']=='higher_better' else '少'}越好)"
                for m in t["metrics"])
            lines.append(f"| {t['name']} | 每天 | {dims} | {t['sunshine']} |")
        br = DAILY_TASKS[0].get("bonus_rule")
        if br:
            lines.append("")
            lines.append(f"> 破纪录叠加：每破一个维度个人纪录 +{br['per_metric']} 阳光（首日只记基线，防囤分）。")
        lines.append("")
    with open("data/tasks_review.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 控制台摘要
    from collections import Counter
    c = Counter(t["subject"] for t in tasks)
    print(f"units={len(units)} tasks={len(tasks)}", dict(c), f"daily={len(DAILY_TASKS)}")
    print("wrote -> data/tasks_review.md, data/tasks.seed.json")

if __name__ == "__main__":
    main()