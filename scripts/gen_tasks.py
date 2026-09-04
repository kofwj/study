# -*- coding: utf-8 -*-
"""按 2026 秋新教材目录生成任务卡（语文/数学/英语已实物核对）。"""
import json, os
from collections import Counter

TERM = {"id": "g5s1", "label": "五年级上", "grade": "五年级", "term": "上",
        "version": "江苏南通 · 2026秋新教材"}
SUN = 5
SUBJECTS = ["语文", "数学", "英语", "科学", "道法", "体育", "音美", "综合", "围棋"]

# 动作类型 → 「怎么做」提示（卡片展开展示）
HINT = {
    "通读": "读一遍，铅笔圈出生字词，查字典标注读音和意思",
    "朗读": "有感情地朗读，注意停顿和重音",
    "略读": "快速浏览知道大意，能说出课文讲了什么",
    "阅读": "读一遍圈出生字，能复述主要内容",
    "听写": "看一遍后合书默写，错字订正三遍",
    "背诵": "先熟读三遍再试背，能完整背出才算过关",
    "口语": "先列个提纲，再对家人完整说一遍",
    "习作": "先列提纲（写什么、分几段），写完读一遍改错",
    "例文": "读两遍，圈出写得好的句子",
    "读书": "读一个故事，能复述大概内容",
    "摘抄": "抄 3-5 个喜欢的句子，注明出处",
    "预习": "看课本例题，不懂的地方标问号，课上重点听",
    "练习": "独立完成不翻答案，做完自己对照检查一遍",
    "口算": "限时做，错题标记出来重算",
    "实践": "动手做，做完拍个照或记下结果",
    "复习": "翻本单元笔记和错题，能复述学了什么",
    "单词": "遮中文背英文、遮英文写中文，错词反复过",
    "拼读": "按发音规则拼读每个词，读三遍",
    "跟读": "跟音频逐句模仿语音语调，读两遍以上",
    "语法": "先看例句再做练习，错题弄懂为什么",
    "任务": "用英语完成，能用本单元句型说 3 句以上",
    "项目": "按课本 Project 要求完成，完成后展示给家长",
}

DAILY_TASKS = [
    {"id": "pe-jump-rope", "subject": "体育", "name": "跳绳打卡",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 3,
                   "note": "破个人纪录才叠加（首日只记基线，防囤分）"},
     "metrics": [
         {"id": "t100", "label": "100下用时", "unit": "秒", "direction": "lower_better"},
         {"id": "n1m", "label": "1分钟跳多少个", "unit": "个", "direction": "higher_better"},
     ]},
    {"id": "pe-situp", "subject": "体育", "name": "1分钟仰卧起坐",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "cnt", "label": "1分钟做多少个", "unit": "个", "direction": "higher_better"},
     ]},
    {"id": "pe-bend", "subject": "体育", "name": "坐位体前屈",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "cm", "label": "手指过脚尖多远", "unit": "厘米", "direction": "higher_better"},
     ]},
    {"id": "pe-eye", "subject": "体育", "name": "做一遍眼保健操",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "cn-read", "subject": "语文", "name": "课外阅读 20 分钟",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "cn-pen", "subject": "语文", "name": "练字一页",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "ma-calc", "subject": "数学", "name": "每日口算",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "time", "label": "用时", "unit": "分钟", "direction": "lower_better"},
         {"id": "acc", "label": "正确率", "unit": "%", "direction": "higher_better"},
     ]},
    {"id": "en-phonics", "subject": "英语", "name": "自然拼读学习",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "go-play", "subject": "围棋", "name": "围棋对弈",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": "记胜负，不发破纪录阳光"},
     "metrics": [
         {"id": "win", "label": "赢了几局", "unit": "局", "direction": "higher_better"},
         {"id": "lose", "label": "输了几局", "unit": "局", "direction": "higher_better"},
     ]},
]

# 语文：单元名 + 具体课文任务（2026 部编六三制实物目录）
CN = [
    ("第1单元 桂花雨·落花生", [
        ("通读", "通读《桂花雨》，圈出生字词"),
        ("通读", "通读《落花生》，圈出生字词"),
        ("听写", "生字词默写一遍"),
        ("朗读", "有感情地朗读《桂花雨》"),
        ("略读", "阅读略读课文《珍珠鸟》"),
        ("口语", "口语交际：制定班级公约"),
        ("习作", "习作：我的心爱之物"),
    ]),
    ("第2单元 冀中的地道战·将相和", [
        ("通读", "通读《冀中的地道战》"),
        ("通读", "通读《将相和》"),
        ("阅读", "阅读《什么比猎豹的速度更快》"),
        ("阅读", "阅读《“诺曼底号”遇难记》"),
        ("听写", "生字词默写一遍"),
        ("习作", "习作：“漫画”老师"),
    ]),
    ("第3单元 民间故事", [
        ("阅读", "阅读《猎人海力布》"),
        ("阅读", "阅读《牛郎织女（一）》"),
        ("略读", "阅读略读《牛郎织女（二）》"),
        ("口语", "口语交际：讲民间故事"),
        ("习作", "习作：故事新编"),
        ("读书", "快乐读书吧：从前有座山"),
    ]),
    ("第4单元 爱国情怀", [
        ("背诵", "背诵古诗三首（示儿 / 题临安邸 / 己亥杂诗）"),
        ("背诵", "背诵《少年中国说》节选"),
        ("阅读", "阅读《圆明园的毁灭》"),
        ("略读", "阅读略读《梅兰芳蓄须明志》"),
        ("习作", "习作：二十年后的家乡"),
    ]),
    ("第5单元 说明文", [
        ("阅读", "阅读《太阳》并做笔记"),
        ("阅读", "阅读《金字塔》"),
        ("例文", "阅读习作例文《鲸》《风向袋的制作》"),
        ("习作", "习作：介绍一种事物"),
    ]),
    ("第6单元 父母之爱", [
        ("朗读", "有感情地朗读《慈母情深》"),
        ("阅读", "阅读《父爱之舟》"),
        ("阅读", "阅读《航天员写给孩子的信》"),
        ("口语", "口语交际：父母之爱"),
        ("习作", "习作：我想对您说"),
    ]),
    ("第7单元 四时景物", [
        ("背诵", "背诵古诗三首（山居秋暝 / 枫桥夜泊 / 早春呈水部张十八员外）"),
        ("阅读", "阅读《第一场雪》"),
        ("阅读", "阅读《白鹭》"),
        ("摘抄", "摘抄描写景物的句子"),
        ("习作", "习作：我最喜爱的季节"),
    ]),
    ("第8单元 读书明智", [
        ("阅读", "阅读《古人谈读书》"),
        ("阅读", "阅读《忆读书》并做笔记"),
        ("略读", "阅读略读《走遍天下书为侣》"),
        ("阅读", "完成一次课外阅读打卡"),
        ("习作", "习作：推荐一本书"),
    ]),
]

# 数学：苏教 2026 实物目录
MA = [
    ("第1单元 图形的运动", [
        ("预习", "预习平移、旋转、轴对称"),
        ("练习", "完成课后练习"),
        ("实践", "综合实践：图案的还原"),
        ("复习", "单元复习"),
    ]),
    ("第2单元 统计表和条形统计图（二）", [
        ("预习", "预习复式统计表和条形统计图"),
        ("练习", "完成课后练习"),
        ("实践", "综合实践：绿色出行"),
        ("复习", "单元复习"),
    ]),
    ("第3单元 多边形的面积", [
        ("预习", "预习平行四边形、三角形、梯形面积"),
        ("练习", "完成课后练习"),
        ("实践", "综合实践：农田收入调查"),
        ("复习", "单元复习"),
    ]),
    ("第4单元 小数乘法和除法（一）", [
        ("预习", "预习小数乘整数、小数乘小数"),
        ("口算", "口算 20 题"),
        ("练习", "完成课后练习"),
        ("复习", "单元复习"),
    ]),
    ("第5单元 可能性", [
        ("预习", "预习可能性"),
        ("练习", "完成课后练习"),
        ("复习", "单元复习"),
    ]),
    ("第6单元 因数与倍数", [
        ("预习", "预习因数、倍数、质数与合数"),
        ("练习", "完成课后练习"),
        ("复习", "单元复习"),
    ]),
    ("第7单元 用字母表示数量关系（一）", [
        ("预习", "预习用字母表示数"),
        ("练习", "完成课后练习"),
        ("实践", "综合实践：钉子板上的多边形"),
        ("复习", "单元复习"),
    ]),
    ("第8单元 观察物体（三）", [
        ("预习", "预习从不同方向观察物体"),
        ("练习", "完成课后练习"),
        ("复习", "单元复习"),
    ]),
]

# 英语：译林 2026 实物目录
EN = [
    ("Unit 1 Good habits", [
        ("单词", "背 Unit 1 词汇（Word list）"),
        ("拼读", "练习拼读 bl（blackboard）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 He/She does (not) …"),
        ("任务", "完成 Wrap-up：Talk about habits"),
    ]),
    ("Unit 2 I feel good", [
        ("单词", "背 Unit 2 词汇（Word list）"),
        ("拼读", "练习拼读 cl（climbing）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 Does he/she like …?"),
        ("任务", "完成 Wrap-up：Give advice"),
    ]),
    ("Unit 3 Hobbies", [
        ("单词", "背 Unit 3 词汇（Word list）"),
        ("拼读", "练习拼读 br（brother）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 What does he/she like doing?"),
        ("任务", "完成 Wrap-up：Talk about hobbies"),
    ]),
    ("Unit 4 Safety first", [
        ("单词", "背 Unit 4 词汇（Word list）"),
        ("拼读", "练习拼读 gr（great）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 should / shouldn't"),
        ("任务", "完成 Wrap-up：Give a speech about safety"),
    ]),
    ("Unit 5 At weekends", [
        ("单词", "背 Unit 5 词汇（Word list）"),
        ("拼读", "练习拼读 tr（travel）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 always/usually/often/sometimes/never"),
        ("任务", "完成 Wrap-up：Talk about your weekends"),
    ]),
    ("Unit 6 Getting along with others", [
        ("单词", "背 Unit 6 词汇（Word list）"),
        ("拼读", "练习拼读 dr（children）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 Why don't …?"),
        ("任务", "完成 Wrap-up：Put on a play"),
    ]),
    ("Unit 7 Shopping smart", [
        ("单词", "背 Unit 7 词汇（Word list）"),
        ("拼读", "练习拼读 st/sk/sp"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 How much is/are …?"),
        ("任务", "完成 Wrap-up：Make a shopping plan"),
    ]),
    ("Unit 8 We love festivals", [
        ("单词", "背 Unit 8 词汇（Word list）"),
        ("拼读", "练习拼读 ing（morning）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 in / on / at"),
        ("任务", "完成 Wrap-up：Talk about your favourite festival"),
    ]),
    ("Project 1 A happy life poster", [
        ("项目", "完成 Project 1：A happy life poster"),
    ]),
    ("Project 2 An invitation card", [
        ("项目", "完成 Project 2：An invitation card"),
    ]),
]

SUBJ_ID = {"语文": "cn", "数学": "ma", "英语": "en"}


def pack(subj, seq, name, items):
    # 任务/单元 id 带学期前缀，确保跨学期不撞旧 completion（五上=g5s1）
    uid = f"{TERM['id']}-{SUBJ_ID[subj]}-{seq}"
    unit = {"id": uid, "subject": subj, "term_id": TERM["id"], "seq": seq, "name": name}
    tasks = []
    for i, (action, title) in enumerate(items, 1):
        tasks.append({
            "id": f"{uid}-{i}", "subject": subj, "unit_id": uid,
            "action": action, "title": title, "detail": HINT.get(action, ""),
            "sunshine": SUN, "sort": i,
        })
    return unit, tasks


def build():
    units, tasks = [], []
    for i, (name, items) in enumerate(CN, 1):
        u, ts = pack("语文", i, name, items)
        units.append(u); tasks.extend(ts)
    for i, (name, items) in enumerate(MA, 1):
        u, ts = pack("数学", i, name, items)
        units.append(u); tasks.extend(ts)
    for i, (name, items) in enumerate(EN, 1):
        u, ts = pack("英语", i, name, items)
        units.append(u); tasks.extend(ts)
    return units, tasks


def main():
    units, tasks = build()
    os.makedirs("data", exist_ok=True)
    with open("data/tasks.seed.json", "w", encoding="utf-8") as f:
        json.dump({"term": TERM, "subjects": SUBJECTS, "curriculum_ver": "2026-g5s1-v6",
                   "units": units, "tasks": tasks, "daily_tasks": DAILY_TASKS},
                  f, ensure_ascii=False, indent=2)
    lines = ["# 2026 新教材任务卡", "",
             f"> {TERM['label']} · {TERM['version']} · {len(tasks)} 张系统卡", ""]
    umap = {u["id"]: u for u in units}
    by = {}
    for t in tasks:
        by.setdefault(t["subject"], []).append(t)
    for subj in ["语文", "数学", "英语"]:
        lines.append(f"## {subj}（{len(by[subj])} 卡）")
        lines.append("| 单元 | 动作 | 标题 | 怎么做 |")
        lines.append("|---|---|---|---|")
        for t in by[subj]:
            lines.append(f"| {umap[t['unit_id']]['name']} | {t['action']} | {t['title']} | {t['detail']} |")
        lines.append("")
    with open("data/tasks_review.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"units={len(units)} tasks={len(tasks)}", dict(Counter(t["subject"] for t in tasks)))


if __name__ == "__main__":
    main()
