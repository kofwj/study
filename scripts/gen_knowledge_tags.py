# -*- coding: utf-8 -*-
"""考点标签：科目字典 + 单元映射。

五上/五下语数英 = 人工精标（HAND）；其余年级按课文 action / 单元名自动标 auto:true。
输出 data/knowledge_tags.json
"""
import json
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
SEED = json.loads((DATA / "tasks.seed.multi.json").read_text(encoding="utf-8"))

TAGS = [
    {"id": "cn-zi", "subject_id": "语文", "kind": "基础", "name": "字词"},
    {"id": "cn-recite", "subject_id": "语文", "kind": "基础", "name": "背诵"},
    {"id": "cn-poem", "subject_id": "语文", "kind": "基础", "name": "古诗"},
    {"id": "cn-read", "subject_id": "语文", "kind": "阅读", "name": "阅读理解"},
    {"id": "cn-skim", "subject_id": "语文", "kind": "阅读", "name": "略读"},
    {"id": "cn-write", "subject_id": "语文", "kind": "表达", "name": "习作"},
    {"id": "cn-oral", "subject_id": "语文", "kind": "表达", "name": "口语"},
    {"id": "cn-copy", "subject_id": "语文", "kind": "表达", "name": "摘抄"},
    {"id": "ma-oral", "subject_id": "数学", "kind": "计算", "name": "口算"},
    {"id": "ma-calc", "subject_id": "数学", "kind": "计算", "name": "计算"},
    {"id": "ma-word", "subject_id": "数学", "kind": "应用", "name": "应用题"},
    {"id": "ma-shape", "subject_id": "数学", "kind": "空间", "name": "图形"},
    {"id": "ma-stat", "subject_id": "数学", "kind": "数据", "name": "统计"},
    {"id": "ma-idea", "subject_id": "数学", "kind": "概念", "name": "概念"},
    {"id": "en-word", "subject_id": "英语", "kind": "基础", "name": "词汇"},
    {"id": "en-sent", "subject_id": "英语", "kind": "基础", "name": "句型"},
    {"id": "en-phon", "subject_id": "英语", "kind": "基础", "name": "拼读"},
    {"id": "en-listen", "subject_id": "英语", "kind": "听说", "name": "听力跟读"},
    {"id": "en-gram", "subject_id": "英语", "kind": "基础", "name": "语法"},
    {"id": "en-task", "subject_id": "英语", "kind": "运用", "name": "口语任务"},
]

# 五上语文精标（统编语文要素提炼，替换泛化大类）
CN5_TAGS = [
    {"id": "cn5-jw", "subject_id": "语文", "kind": "单元考点", "name": "借物抒情"},
    {"id": "cn5-gj", "subject_id": "语文", "kind": "单元考点", "name": "抓关键语句体会感情"},
    {"id": "cn5-gk", "subject_id": "语文", "kind": "单元考点", "name": "概括主要内容"},
    {"id": "cn5-ysd", "subject_id": "语文", "kind": "单元考点", "name": "提高阅读速度"},
    {"id": "cn5-rw", "subject_id": "语文", "kind": "单元考点", "name": "结合事例写人物"},
    {"id": "cn5-mj", "subject_id": "语文", "kind": "单元考点", "name": "民间故事特点"},
    {"id": "cn5-fs", "subject_id": "语文", "kind": "单元考点", "name": "创造性复述"},
    {"id": "cn5-zl", "subject_id": "语文", "kind": "单元考点", "name": "结合资料体会感情"},
    {"id": "cn5-tg", "subject_id": "语文", "kind": "单元考点", "name": "列提纲分段落"},
    {"id": "cn5-sm", "subject_id": "语文", "kind": "单元考点", "name": "了解说明方法"},
    {"id": "cn5-smw", "subject_id": "语文", "kind": "单元考点", "name": "用说明方法介绍事物"},
    {"id": "cn5-xj", "subject_id": "语文", "kind": "单元考点", "name": "体会场景细节描写"},
    {"id": "cn5-bd", "subject_id": "语文", "kind": "单元考点", "name": "表达自己看法"},
    {"id": "cn5-dj", "subject_id": "语文", "kind": "单元考点", "name": "体会静态动态描写"},
    {"id": "cn5-sx", "subject_id": "语文", "kind": "单元考点", "name": "按顺序写景"},
    {"id": "cn5-xl", "subject_id": "语文", "kind": "单元考点", "name": "梳理信息把握要点"},
    {"id": "cn5-fd", "subject_id": "语文", "kind": "单元考点", "name": "分段表述突出重点"},
]
TAGS += CN5_TAGS

# 五上数学精标（苏教版新版单元知识点）
MA5_TAGS = [
    {"id": "ma5-py", "subject_id": "数学", "kind": "单元考点", "name": "平移"},
    {"id": "ma5-xz", "subject_id": "数学", "kind": "单元考点", "name": "旋转"},
    {"id": "ma5-dc", "subject_id": "数学", "kind": "单元考点", "name": "轴对称"},
    {"id": "ma5-fbtj", "subject_id": "数学", "kind": "单元考点", "name": "复式统计表"},
    {"id": "ma5-fbtu", "subject_id": "数学", "kind": "单元考点", "name": "复式条形统计图"},
    {"id": "ma5-px", "subject_id": "数学", "kind": "单元考点", "name": "平行四边形面积"},
    {"id": "ma5-sjx", "subject_id": "数学", "kind": "单元考点", "name": "三角形面积"},
    {"id": "ma5-tx", "subject_id": "数学", "kind": "单元考点", "name": "梯形面积"},
    {"id": "ma5-xsc", "subject_id": "数学", "kind": "单元考点", "name": "小数乘法"},
    {"id": "ma5-xsch", "subject_id": "数学", "kind": "单元考点", "name": "小数除法"},
    {"id": "ma5-kn", "subject_id": "数学", "kind": "单元考点", "name": "确定与不确定事件"},
    {"id": "ma5-kndx", "subject_id": "数学", "kind": "单元考点", "name": "可能性大小"},
    {"id": "ma5-ys", "subject_id": "数学", "kind": "单元考点", "name": "因数与倍数"},
    {"id": "ma5-bstz", "subject_id": "数学", "kind": "单元考点", "name": "2、3、5的倍数特征"},
    {"id": "ma5-zh", "subject_id": "数学", "kind": "单元考点", "name": "质数与合数"},
    {"id": "ma5-zm", "subject_id": "数学", "kind": "单元考点", "name": "用字母表示数"},
    {"id": "ma5-zmsz", "subject_id": "数学", "kind": "单元考点", "name": "含字母式子的化简"},
    {"id": "ma5-gc", "subject_id": "数学", "kind": "单元考点", "name": "从不同方向观察"},
    {"id": "ma5-st", "subject_id": "数学", "kind": "单元考点", "name": "三视图与空间想象"},
]

# 五上英语精标（译林新版：单元话题 + 已确认核心语法）
EN5_TAGS = [
    {"id": "en5-u1", "subject_id": "英语", "kind": "单元考点", "name": "一般现在时·三单"},
    {"id": "en5-u1hab", "subject_id": "英语", "kind": "单元考点", "name": "谈日常习惯"},
    {"id": "en5-u2", "subject_id": "英语", "kind": "单元考点", "name": "表达感受"},
    {"id": "en5-u3", "subject_id": "英语", "kind": "单元考点", "name": "like doing 谈爱好"},
    {"id": "en5-u4", "subject_id": "英语", "kind": "单元考点", "name": "谈安全规则"},
    {"id": "en5-u5", "subject_id": "英语", "kind": "单元考点", "name": "谈周末活动"},
    {"id": "en5-u6", "subject_id": "英语", "kind": "单元考点", "name": "谈与人相处"},
    {"id": "en5-u7", "subject_id": "英语", "kind": "单元考点", "name": "购物用语"},
    {"id": "en5-u8", "subject_id": "英语", "kind": "单元考点", "name": "谈节日"},
    {"id": "en5-pjt", "subject_id": "英语", "kind": "单元考点", "name": "综合运用"},
]
TAGS += MA5_TAGS
TAGS += EN5_TAGS

# 五上/五下语数英精标（对照现有手工任务卡）
HAND = {
    "g5s1-cn-1": ["cn5-jw", "cn5-gj", "cn5-gk"],
    "g5s1-cn-2": ["cn5-ysd", "cn5-rw"],
    "g5s1-cn-3": ["cn5-mj", "cn5-fs"],
    "g5s1-cn-4": ["cn5-zl", "cn5-tg"],
    "g5s1-cn-5": ["cn5-sm", "cn5-smw"],
    "g5s1-cn-6": ["cn5-xj", "cn5-bd"],
    "g5s1-cn-7": ["cn5-dj", "cn5-sx"],
    "g5s1-cn-8": ["cn5-xl", "cn5-fd"],
    "g5s1-ma-1": ["ma5-py", "ma5-xz", "ma5-dc"],
    "g5s1-ma-2": ["ma5-fbtj", "ma5-fbtu"],
    "g5s1-ma-3": ["ma5-px", "ma5-sjx", "ma5-tx"],
    "g5s1-ma-4": ["ma5-xsc", "ma5-xsch"],
    "g5s1-ma-5": ["ma5-kn", "ma5-kndx"],
    "g5s1-ma-6": ["ma5-ys", "ma5-bstz", "ma5-zh"],
    "g5s1-ma-7": ["ma5-zm", "ma5-zmsz"],
    "g5s1-ma-8": ["ma5-gc", "ma5-st"],
    "g5s1-en-1": ["en5-u1", "en5-u1hab"],
    "g5s1-en-2": ["en5-u2"],
    "g5s1-en-3": ["en5-u3"],
    "g5s1-en-4": ["en5-u4"],
    "g5s1-en-5": ["en5-u5"],
    "g5s1-en-6": ["en5-u6"],
    "g5s1-en-7": ["en5-u7"],
    "g5s1-en-8": ["en5-u8"],
    "g5s1-en-9": ["en5-pjt"],
    "g5s1-en-10": ["en5-pjt"],
    "g5x2-cn-1": ["cn-poem", "cn-recite", "cn-read", "cn-oral", "cn-write"],
    "g5x2-cn-2": ["cn-read", "cn-oral", "cn-write"],
    "g5x2-cn-3": ["cn-zi", "cn-read"],
    "g5x2-cn-4": ["cn-poem", "cn-recite", "cn-read", "cn-write"],
    "g5x2-cn-5": ["cn-read", "cn-write"],
    "g5x2-cn-6": ["cn-read", "cn-write"],
    "g5x2-cn-7": ["cn-read", "cn-oral", "cn-write"],
    "g5x2-cn-8": ["cn-read", "cn-oral", "cn-write"],
    "g5x2-ma-1": ["ma-idea", "ma-calc", "ma-word"],
    "g5x2-ma-2": ["ma-stat"],
    "g5x2-ma-3": ["ma-idea"],
    "g5x2-ma-4": ["ma-idea"],
    "g5x2-ma-5": ["ma-calc"],
    "g5x2-ma-6": ["ma-shape", "ma-calc"],
    "g5x2-ma-7": ["ma-word"],
    "g5x2-ma-8": ["ma-idea", "ma-calc", "ma-word", "ma-shape", "ma-stat"],
    "g5x2-en-1": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-2": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-3": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-4": ["en-task"],
    "g5x2-en-5": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-6": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-7": ["en-word", "en-listen", "en-sent"],
    "g5x2-en-8": ["en-word", "en-task"],
}

CN_ACTION = {
    "通读": ["cn-zi", "cn-read"], "听写": ["cn-zi"], "朗读": ["cn-read"],
    "背诵": ["cn-recite"], "略读": ["cn-skim"], "阅读": ["cn-read"],
    "口语": ["cn-oral"], "习作": ["cn-write"], "例文": ["cn-write"],
    "读书": ["cn-read"], "摘抄": ["cn-copy"], "复习": ["cn-zi", "cn-read"],
}
EN_ACTION = {
    "单词": ["en-word"], "拼读": ["en-phon"], "跟读": ["en-listen"],
    "语法": ["en-gram"], "任务": ["en-task"], "项目": ["en-task"], "复习": ["en-word"],
}


def ma_from_name(name):
    if any(k in name for k in ("统计", "折线", "条形")): return ["ma-stat"]
    if any(k in name for k in ("图形", "圆", "面积", "观察", "平移", "对称", "角", "体积")): return ["ma-shape"]
    if any(k in name for k in ("口算",)): return ["ma-oral"]
    if any(k in name for k in ("方程", "分数", "小数", "乘", "除", "加", "减")): return ["ma-calc"]
    if any(k in name for k in ("解决问题", "应用")): return ["ma-word"]
    return ["ma-idea"]


def auto_tags(unit, tasks):
    subj = unit["subject"]
    name = unit["name"]
    acts = list(dict.fromkeys(t["action"] for t in tasks))
    out = []
    if subj == "语文":
        if "古诗" in name or any("古诗" in t["title"] for t in tasks):
            out += ["cn-poem", "cn-recite"]
        for a in acts:
            out += CN_ACTION.get(a, [])
    elif subj == "数学":
        out += ma_from_name(name)
        if any(t["action"] == "口算" for t in tasks):
            out += ["ma-oral"]
        if any(k in name for k in ("解决问题", "策略")):
            out += ["ma-word"]
    elif subj == "英语":
        for a in acts:
            out += EN_ACTION.get(a, [])
        if "Unit" in name:
            out += ["en-word", "en-listen"]
    # unique keep order
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq


def main():
    by_unit = defaultdict(list)
    for t in SEED["tasks"]:
        if t["subject"] in ("语文", "数学", "英语"):
            by_unit[t["unit_id"]].append(t)
    unit_tags = []
    for u in SEED["units"]:
        if u["subject"] not in ("语文", "数学", "英语"):
            continue
        uid = u["id"]
        if uid in HAND:
            tags, auto = HAND[uid], False
        else:
            tags, auto = auto_tags(u, by_unit.get(uid, [])), True
        unit_tags.append({"unit_id": uid, "tag_ids": tags, "auto": auto})
    out = {
        "_meta": {
            "note": "科目级字典 + 单元映射。g5s1/g5x2 语数英 auto=false 精标，其余 auto=true。",
            "hand_units": sorted(HAND),
        },
        "tags": TAGS,
        "unit_tags": unit_tags,
    }
    dest = DATA / "knowledge_tags.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    n_hand = sum(1 for x in unit_tags if not x["auto"])
    n_auto = sum(1 for x in unit_tags if x["auto"])
    empty = [x["unit_id"] for x in unit_tags if not x["tag_ids"]]
    assert not empty, empty
    print("knowledge_tags", dest, "hand", n_hand, "auto", n_auto)


if __name__ == "__main__":
    main()
