# -*- coding: utf-8 -*-
"""考点标签：科目字典 + 单元映射。

五上五科 = 人工精标（HAND）；其余年级只保留自动标签作内部占位，家长端不把它们当作可点选考点。
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

# 五上精标：依据 2026 秋电子课本的单元、Grammar/Sounds/Project 结构整理。
# 标签写成家长可以勾选、孩子可以复练的项目，不直接照搬笼统的学科术语。
CN5_TAGS = [
    {"id": "cn5-jw", "subject_id": "语文", "kind": "单元考点", "name": "借助事物体会感情"},
    {"id": "cn5-gj", "subject_id": "语文", "kind": "单元考点", "name": "从关键语句体会感情"},
    {"id": "cn5-gk", "subject_id": "语文", "kind": "单元考点", "name": "概括主要内容"},
    {"id": "cn5-xxw", "subject_id": "语文", "kind": "单元考点", "name": "写心爱之物（写清特点）"},
    {"id": "cn5-ysd", "subject_id": "语文", "kind": "单元考点", "name": "带着问题快速阅读"},
    {"id": "cn5-rw", "subject_id": "语文", "kind": "单元考点", "name": "抓住特点写人物"},
    {"id": "cn5-mj", "subject_id": "语文", "kind": "单元考点", "name": "讲清民间故事"},
    {"id": "cn5-fs", "subject_id": "语文", "kind": "单元考点", "name": "创造性复述故事"},
    {"id": "cn5-gsx", "subject_id": "语文", "kind": "单元考点", "name": "故事新编（保留主线）"},
    {"id": "cn5-zl", "subject_id": "语文", "kind": "单元考点", "name": "结合资料体会爱国情感"},
    {"id": "cn5-tg", "subject_id": "语文", "kind": "单元考点", "name": "列提纲写想象作文"},
    {"id": "cn5-sm", "subject_id": "语文", "kind": "单元考点", "name": "辨认说明方法"},
    {"id": "cn5-smw", "subject_id": "语文", "kind": "单元考点", "name": "用说明方法介绍事物"},
    {"id": "cn5-xj", "subject_id": "语文", "kind": "单元考点", "name": "从场景细节体会父母之爱"},
    {"id": "cn5-bd", "subject_id": "语文", "kind": "单元考点", "name": "写信表达真情实感"},
    {"id": "cn5-dj", "subject_id": "语文", "kind": "单元考点", "name": "体会静态和动态描写"},
    {"id": "cn5-sx", "subject_id": "语文", "kind": "单元考点", "name": "按顺序描写景物"},
    {"id": "cn5-xl", "subject_id": "语文", "kind": "单元考点", "name": "梳理信息把握要点"},
    {"id": "cn5-fd", "subject_id": "语文", "kind": "单元考点", "name": "推荐一本书说明理由"},
]

MA5_TAGS = [
    {"id": "ma5-py", "subject_id": "数学", "kind": "单元考点", "name": "按方向和距离平移"},
    {"id": "ma5-xz", "subject_id": "数学", "kind": "单元考点", "name": "按中心和角度旋转"},
    {"id": "ma5-dc", "subject_id": "数学", "kind": "单元考点", "name": "补全轴对称图形"},
    {"id": "ma5-fbtj", "subject_id": "数学", "kind": "单元考点", "name": "读填复式统计表"},
    {"id": "ma5-fbtu", "subject_id": "数学", "kind": "单元考点", "name": "读画复式条形统计图"},
    {"id": "ma5-fbfx", "subject_id": "数学", "kind": "单元考点", "name": "从图表比较数据"},
    {"id": "ma5-md", "subject_id": "数学", "kind": "单元考点", "name": "面积单位换算"},
    {"id": "ma5-px", "subject_id": "数学", "kind": "单元考点", "name": "平行四边形面积"},
    {"id": "ma5-sjx", "subject_id": "数学", "kind": "单元考点", "name": "三角形面积"},
    {"id": "ma5-tx", "subject_id": "数学", "kind": "单元考点", "name": "梯形面积"},
    {"id": "ma5-zhmj", "subject_id": "数学", "kind": "单元考点", "name": "组合图形面积"},
    {"id": "ma5-xsc", "subject_id": "数学", "kind": "单元考点", "name": "小数乘法（确定小数位数）"},
    {"id": "ma5-xsch", "subject_id": "数学", "kind": "单元考点", "name": "小数除法（确定商的小数点）"},
    {"id": "ma5-xy", "subject_id": "数学", "kind": "单元考点", "name": "用小数乘除解决问题"},
    {"id": "ma5-kn", "subject_id": "数学", "kind": "单元考点", "name": "用一定、可能、不可能描述"},
    {"id": "ma5-kndx", "subject_id": "数学", "kind": "单元考点", "name": "判断可能性大小"},
    {"id": "ma5-ys", "subject_id": "数学", "kind": "单元考点", "name": "找因数和倍数"},
    {"id": "ma5-bstz", "subject_id": "数学", "kind": "单元考点", "name": "2、3、5的倍数特征"},
    {"id": "ma5-zh", "subject_id": "数学", "kind": "单元考点", "name": "判断质数和合数"},
    {"id": "ma5-jou", "subject_id": "数学", "kind": "单元考点", "name": "判断奇数和偶数"},
    {"id": "ma5-zm", "subject_id": "数学", "kind": "单元考点", "name": "用字母表示数量关系"},
    {"id": "ma5-zmsz", "subject_id": "数学", "kind": "单元考点", "name": "化简含字母的式子"},
    {"id": "ma5-drc", "subject_id": "数学", "kind": "单元考点", "name": "代入字母求值"},
    {"id": "ma5-gc", "subject_id": "数学", "kind": "单元考点", "name": "从不同方向观察物体"},
    {"id": "ma5-st", "subject_id": "数学", "kind": "单元考点", "name": "根据视图摆小正方体"},
]

EN5_TAGS = [
    {"id": "en5-u1", "subject_id": "英语", "kind": "单元考点", "name": "三单动词变化"},
    {"id": "en5-u1phon", "subject_id": "英语", "kind": "单元考点", "name": "bl 拼读"},
    {"id": "en5-u1hab", "subject_id": "英语", "kind": "单元考点", "name": "用英语说日常习惯"},
    {"id": "en5-u2", "subject_id": "英语", "kind": "单元考点", "name": "表达感受"},
    {"id": "en5-u2phon", "subject_id": "英语", "kind": "单元考点", "name": "cl 拼读"},
    {"id": "en5-u2gram", "subject_id": "英语", "kind": "单元考点", "name": "Does he/she like ...?"},
    {"id": "en5-u3", "subject_id": "英语", "kind": "单元考点", "name": "用 like doing 谈爱好"},
    {"id": "en5-u3phon", "subject_id": "英语", "kind": "单元考点", "name": "br 拼读"},
    {"id": "en5-u3gram", "subject_id": "英语", "kind": "单元考点", "name": "What does he/she like doing?"},
    {"id": "en5-u4", "subject_id": "英语", "kind": "单元考点", "name": "用英语说安全规则"},
    {"id": "en5-u4phon", "subject_id": "英语", "kind": "单元考点", "name": "gr 拼读"},
    {"id": "en5-u4gram", "subject_id": "英语", "kind": "单元考点", "name": "should / shouldn't 提建议"},
    {"id": "en5-u5", "subject_id": "英语", "kind": "单元考点", "name": "用英语说周末活动"},
    {"id": "en5-u5phon", "subject_id": "英语", "kind": "单元考点", "name": "tr 拼读"},
    {"id": "en5-u5gram", "subject_id": "英语", "kind": "单元考点", "name": "频率副词说周末活动"},
    {"id": "en5-u6", "subject_id": "英语", "kind": "单元考点", "name": "用英语谈相处"},
    {"id": "en5-u6phon", "subject_id": "英语", "kind": "单元考点", "name": "dr 拼读"},
    {"id": "en5-u6gram", "subject_id": "英语", "kind": "单元考点", "name": "Why don't ...? 提建议"},
    {"id": "en5-u7", "subject_id": "英语", "kind": "单元考点", "name": "用英语购物"},
    {"id": "en5-u7phon", "subject_id": "英语", "kind": "单元考点", "name": "st / sk / sp 拼读"},
    {"id": "en5-u7gram", "subject_id": "英语", "kind": "单元考点", "name": "How much is/are ...? 问价"},
    {"id": "en5-u8", "subject_id": "英语", "kind": "单元考点", "name": "用英语谈节日"},
    {"id": "en5-u8phon", "subject_id": "英语", "kind": "单元考点", "name": "ing 拼读"},
    {"id": "en5-u8gram", "subject_id": "英语", "kind": "单元考点", "name": "in / on / at 说时间"},
    {"id": "en5-pjt", "subject_id": "英语", "kind": "单元考点", "name": "完成综合项目"},
    {"id": "en5-p1", "subject_id": "英语", "kind": "单元考点", "name": "完成 A happy life 海报"},
    {"id": "en5-p2", "subject_id": "英语", "kind": "单元考点", "name": "完成邀请卡"},
]
KX5_TAGS = [
    {"id": "kx5-cb", "subject_id": "科学", "kind": "单元考点", "name": "用实验判断光的传播"},
    {"id": "kx5-fs", "subject_id": "科学", "kind": "单元考点", "name": "用镜子改变光的方向"},
    {"id": "kx5-qg", "subject_id": "科学", "kind": "单元考点", "name": "解释潜望镜和万花筒"},
    {"id": "kx5-sg", "subject_id": "科学", "kind": "单元考点", "name": "用实验分解或合成七色光"},
    {"id": "kx5-rd", "subject_id": "科学", "kind": "单元考点", "name": "用实验判断热传导"},
    {"id": "kx5-dl", "subject_id": "科学", "kind": "单元考点", "name": "用水观察热对流"},
    {"id": "kx5-fs2", "subject_id": "科学", "kind": "单元考点", "name": "举例说明热辐射"},
    {"id": "kx5-cl", "subject_id": "科学", "kind": "单元考点", "name": "比较材料传热本领"},
    {"id": "kx5-tl", "subject_id": "科学", "kind": "单元考点", "name": "用实验认识弹力"},
    {"id": "kx5-ml", "subject_id": "科学", "kind": "单元考点", "name": "比较摩擦力大小"},
    {"id": "kx5-fl", "subject_id": "科学", "kind": "单元考点", "name": "用实验认识浮力"},
    {"id": "kx5-yd", "subject_id": "科学", "kind": "单元考点", "name": "解释力对运动的影响"},
    {"id": "kx5-gg", "subject_id": "科学", "kind": "单元考点", "name": "用杠杆省力撬重物"},
    {"id": "kx5-lz", "subject_id": "科学", "kind": "单元考点", "name": "解释轮轴和螺丝的作用"},
    {"id": "kx5-dl2", "subject_id": "科学", "kind": "单元考点", "name": "用滑轮改变用力方向"},
    {"id": "kx5-xp", "subject_id": "科学", "kind": "单元考点", "name": "比较斜坡的省力效果"},
    {"id": "kx5-sw", "subject_id": "科学", "kind": "单元考点", "name": "从生物结构找到仿生启示"},
    {"id": "kx5-dk", "subject_id": "科学", "kind": "单元考点", "name": "解释蛋壳与薄壳结构"},
    {"id": "kx5-sz", "subject_id": "科学", "kind": "单元考点", "name": "解释海豚与声呐"},
    {"id": "kx5-fs3", "subject_id": "科学", "kind": "单元考点", "name": "设计一个仿生方案"},
]

DF5_TAGS = [
    {"id": "df5-dj", "subject_id": "道法", "kind": "单元考点", "name": "说清中国共产党成立的意义"},
    {"id": "df5-gm", "subject_id": "道法", "kind": "单元考点", "name": "讲清中国革命道路"},
    {"id": "df5-kz", "subject_id": "道法", "kind": "单元考点", "name": "用史实说明抗战中流砥柱"},
    {"id": "df5-js", "subject_id": "道法", "kind": "单元考点", "name": "按时间线讲清解放战争"},
    {"id": "df5-jg", "subject_id": "道法", "kind": "单元考点", "name": "说清新中国成立的意义"},
    {"id": "df5-rm", "subject_id": "道法", "kind": "单元考点", "name": "举例说明人民当家作主"},
    {"id": "df5-she", "subject_id": "道法", "kind": "单元考点", "name": "用事实说明社会主义建设"},
    {"id": "df5-gg", "subject_id": "道法", "kind": "单元考点", "name": "说清改革开放带来的变化"},
    {"id": "df5-gli", "subject_id": "道法", "kind": "单元考点", "name": "用数据或事例说明综合国力"},
    {"id": "df5-ty", "subject_id": "道法", "kind": "单元考点", "name": "说清祖国统一进展"},
    {"id": "df5-xd", "subject_id": "道法", "kind": "单元考点", "name": "说清新时代的历史方位"},
    {"id": "df5-cj", "subject_id": "道法", "kind": "单元考点", "name": "列举新时代历史性成就"},
    {"id": "df5-zr", "subject_id": "道法", "kind": "单元考点", "name": "说出新时代少年的行动"},
]
TAGS += CN5_TAGS + MA5_TAGS + EN5_TAGS + KX5_TAGS + DF5_TAGS

# 五上/五下语数英精标。五上按 2026 秋教材逐单元配置；五下保留原映射。
# 五上考点区只放“本单元特有的难点”。
# 字词、背诵、词汇、跟读等重复基础练习由下方教材任务卡检查，
# 不再每个单元都列成可点选薄弱点，避免家长面对一页重复项目。
HAND = {
    "g5s1-cn-1": ["cn5-jw", "cn5-xxw"],
    "g5s1-cn-2": ["cn5-ysd", "cn5-rw"],
    "g5s1-cn-3": ["cn5-mj", "cn5-fs", "cn5-gsx"],
    "g5s1-cn-4": ["cn5-zl", "cn5-tg"],
    "g5s1-cn-5": ["cn5-sm", "cn5-smw"],
    "g5s1-cn-6": ["cn5-xj", "cn5-bd"],
    "g5s1-cn-7": ["cn5-dj", "cn5-sx"],
    "g5s1-cn-8": ["cn5-xl", "cn5-fd"],
    "g5s1-ma-1": ["ma5-py", "ma5-xz", "ma5-dc"],
    "g5s1-ma-2": ["ma5-fbtj", "ma5-fbtu", "ma5-fbfx"],
    "g5s1-ma-3": ["ma5-md", "ma5-px", "ma5-sjx", "ma5-tx", "ma5-zhmj"],
    "g5s1-ma-4": ["ma5-xsc", "ma5-xsch", "ma5-xy"],
    "g5s1-ma-5": ["ma5-kn", "ma5-kndx"],
    "g5s1-ma-6": ["ma5-ys", "ma5-bstz", "ma5-zh", "ma5-jou"],
    "g5s1-ma-7": ["ma5-zm", "ma5-zmsz", "ma5-drc"],
    "g5s1-ma-8": ["ma5-gc", "ma5-st"],
    "g5s1-en-1": ["en5-u1phon", "en5-u1", "en5-u1hab"],
    "g5s1-en-2": ["en5-u2phon", "en5-u2gram", "en5-u2"],
    "g5s1-en-3": ["en5-u3phon", "en5-u3gram", "en5-u3"],
    "g5s1-en-4": ["en5-u4phon", "en5-u4gram", "en5-u4"],
    "g5s1-en-5": ["en5-u5phon", "en5-u5gram", "en5-u5"],
    "g5s1-en-6": ["en5-u6phon", "en5-u6gram", "en5-u6"],
    "g5s1-en-7": ["en5-u7phon", "en5-u7gram", "en5-u7"],
    "g5s1-en-8": ["en5-u8phon", "en5-u8gram", "en5-u8"],
    "g5s1-en-9": ["en5-p1"],
    "g5s1-en-10": ["en5-p2"],
    "g5s1-kx-1": ["kx5-cb", "kx5-fs", "kx5-qg", "kx5-sg"],
    "g5s1-kx-2": ["kx5-rd", "kx5-dl", "kx5-fs2", "kx5-cl"],
    "g5s1-kx-3": ["kx5-tl", "kx5-ml", "kx5-fl", "kx5-yd"],
    "g5s1-kx-4": ["kx5-gg", "kx5-lz", "kx5-dl2", "kx5-xp"],
    "g5s1-kx-5": ["kx5-sw", "kx5-dk", "kx5-sz", "kx5-fs3"],
    "g5s1-df-1": ["df5-dj", "df5-gm", "df5-kz", "df5-js"],
    "g5s1-df-2": ["df5-jg", "df5-rm", "df5-she"],
    "g5s1-df-3": ["df5-gg", "df5-gli", "df5-ty"],
    "g5s1-df-4": ["df5-xd", "df5-cj", "df5-zr"],
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
    core_subjects = ("语文", "数学", "英语")
    g5_extra_subjects = ("科学", "道法")
    def has_tags(unit):
        return unit["subject"] in core_subjects or (
            unit["id"].startswith("g5s1-") and unit["subject"] in g5_extra_subjects)
    for t in SEED["tasks"]:
        if t["subject"] in core_subjects or t["unit_id"].startswith(("g5s1-kx-", "g5s1-df-")):
            by_unit[t["unit_id"]].append(t)
    unit_tags = []
    for u in SEED["units"]:
        if not has_tags(u):
            continue
        uid = u["id"]
        if uid in HAND:
            tags, auto = HAND[uid], False
        else:
            tags, auto = auto_tags(u, by_unit.get(uid, [])), True
        unit_tags.append({"unit_id": uid, "tag_ids": tags, "auto": auto})
    out = {
        "_meta": {
            "note": "科目级字典 + 单元映射。五上语数英科学道法和五下语数英为人工精标，其余自动生成。",
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
