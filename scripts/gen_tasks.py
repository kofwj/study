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

# 标题已经说明了复习目标时，提示必须告诉孩子“做什么算完成”。
# 先按标题匹配，其他年级/旧任务继续使用动作级默认提示。
def detail_for(action, title):
    if title.startswith("字词："):
        return "读课文，圈出生字词；会读、会写，并能说出重点词语的意思。"
    if title.startswith("关键语句："):
        return "找出 2~3 处关键语句，读给家长听，并说清它表达了什么感情。"
    if title.startswith("快速阅读：") or title.startswith("带着问题读："):
        return "先看问题，再连续读完；不逐字回读，读后用 2~3 句话说出答案和主要内容。"
    if title.startswith("讲清故事："):
        return "按起因、经过、结果讲一遍，人物和关键情节不能漏。"
    if title.startswith("创造性复述："):
        return "先列出故事主线，再加入人物语言或动作，完整讲给家长听。"
    if title.startswith("阅读略读") or title.startswith("略读"):
        return "快速读完，先说主要内容，再说一个你印象最深的情节。"
    if title.startswith("按起因、经过、结果"):
        return "不看课文讲一遍，家长能听懂故事顺序和结局。"
    if title.startswith("故事新编："):
        return "保留原故事人物和主线，加入合理变化；写完读一遍并修改。"
    if title.startswith("背诵："):
        return "先理解诗句或文章意思，再脱稿背给家长听，错处回看后重背。"
    if title.startswith("结合资料体会感情："):
        return "先读资料和课文，再说出人物/文字表达的感情，最后脱稿背诵。"
    if title.startswith("找一找：") or title.startswith("找说明方法："):
        return "圈出举例子、列数字、作比较等说明方法，并说出它说明了什么。"
    if title.startswith("整理信息："):
        return "用表格或提纲整理 3 个要点，再用自己的话说清主要内容。"
    if title.startswith("用说明方法介绍"):
        return "选一个熟悉的事物，至少用两种说明方法介绍，写完检查内容是否准确。"
    if title.startswith("场景细节："):
        return "圈出动作、语言或场景细节，说说这些细节怎样表现父母之爱。"
    if title.startswith("结合生活事例"):
        return "先讲一个真实事例，再说自己的感受或看法，不能只说‘很好’。"
    if title.startswith("写信："):
        return "写清一件具体的事和自己的感受，格式完整，写完读给家长听。"
    if title.startswith("静态描写："):
        return "找出描写景物形态、颜色和位置的句子，说说景物静态的特点。"
    if title.startswith("动态描写："):
        return "找出景物变化、声音或动作的句子，说说画面是怎样动起来的。"
    if title.startswith("摘抄描写景物"):
        return "摘抄 3~5 句，并标出是在写静态还是动态；注明课文出处。"
    if title.startswith("按顺序写："):
        return "确定观察顺序，按顺序写出景物特点，至少加入两处具体描写。"
    if title.startswith("课外阅读："):
        return "读完后说清人物、主要情节和自己的收获。"
    if title.startswith("推荐一本书："):
        return "写清书名、主要内容和推荐理由，至少举一个具体理由。"
    if title.startswith("在方格图中"):
        return "标出一个对应点，按指定方向数格子平移；检查形状、大小是否改变。"
    if title.startswith("按中心和角度"):
        return "找准旋转中心和方向，按指定角度旋转；检查对应点是否正确。"
    if title.startswith("补全轴对称"):
        return "先找对称轴，再数对应格子补全；检查两边到对称轴距离是否相等。"
    if title.startswith("读填复式统计表"):
        return "补全表格，再说出两组数据的相同点和不同点。"
    if title.startswith("读画复式条形"):
        return "看清图例和刻度，按数据画两组柱子，并检查高度是否对应。"
    if title.startswith("根据图表"):
        return "从图表找出数据，至少说出一个比较结论，并说明依据。"
    if title.startswith("面积单位换算"):
        return "先判断单位大小，再按进率换算；写完检查单位是否正确。"
    if title.startswith("算平行四边形"):
        return "先找底和对应的高，再选择公式计算，最后写上面积单位。"
    if title.startswith("算组合图形"):
        return "把图形分成已会计算的图形，分别算面积后合并，并检查单位。"
    if title.startswith("小数乘法"):
        return "先按整数乘法计算，再数因数小数位确定积的小数点，最后估算检查。"
    if title.startswith("小数乘除口算"):
        return "限时完成，错题写出计算过程，说明小数点为什么这样移动。"
    if title.startswith("小数除法"):
        return "先判断商的大致大小，再正确定位小数点，最后用乘法或估算检查。"
    if title.startswith("用小数乘除"):
        return "先找数量关系和单位，再列式计算，最后检查答案和单位是否合理。"
    if title.startswith("用一定、可能"):
        return "对每个事件选择‘一定、可能或不可能’，并用题目条件说出理由。"
    if title.startswith("判断可能性大小"):
        return "比较各种结果出现的机会，用‘大/小’或数据说明判断依据。"
    if title.startswith("用可能性解释"):
        return "先判断可能性，再用生活中的条件解释为什么。"
    if title.startswith("找因数和倍数"):
        return "用乘法算式找全因数和倍数，并说清谁是谁的因数或倍数。"
    if title.startswith("用 2、3、5"):
        return "不逐个试除，先看个位或各位数字和，再说明判断理由。"
    if title.startswith("判断质数"):
        return "分别判断质数、合数、奇数和偶数，注意 2 是偶数也是质数。"
    if title.startswith("用字母表示"):
        return "先找数量关系，再用字母写式子；说清每个字母表示什么。"
    if title.startswith("化简含字母"):
        return "先合并同类项，再把给出的数代入；注意运算顺序和单位。"
    if title.startswith("用含字母式子"):
        return "读懂题意列出含字母的式子，化简或代入后写完整答句。"
    if title.startswith("从不同方向"):
        return "分别从前、侧、上面观察，记录每个方向看到的形状和小正方体数量。"
    if title.startswith("根据视图"):
        return "根据每个方向看到的图形摆小正方体，再从三个方向检查是否一致。"
    if title.startswith("画出物体"):
        return "先确定观察方向和轮廓，再按小正方体位置画图，最后和实物对照。"
    if title.startswith("听读并会写"):
        return "先听音跟读，再遮住中文说英文、遮住英文写中文；错词订正后再读写一次。"
    if title.startswith("练习拼读"):
        return "先读字母组合发音，再拼读本单元单词；每个词读三遍并让家长抽查。"
    if title.startswith("跟读"):
        return "跟音频逐句读，注意重音和语调；最后不看音频完整读一遍。"
    if title.startswith("三单练习") or title.startswith("练习 Does") or title.startswith("练习 What"):
        return "先读例句，再替换人物或活动造 3 句；检查主语、动词形式和问答是否匹配。"
    if title.startswith("练习 should") or title.startswith("练习 Why"):
        return "用本单元句型提出 3 条建议，并正确使用动词原形。"
    if title.startswith("练习 always"):
        return "用 5 个频率副词各说或写一句周末活动，注意位置和句意。"
    if title.startswith("练习 How much"):
        return "分别练习单数和复数问价，能问、能听懂并能用完整句子回答。"
    if title.startswith("练习 in / on"):
        return "用 in、on、at 各造句，分别表示月份、日期/星期和具体时刻。"
    if title.startswith("完成 Wrap-up"):
        return "准备 3 句以上完整英语表达，脱稿说给家长听，发音和句型都要清楚。"
    if title.startswith("完成 Project"):
        return "按课本要求完成作品，检查英文内容和书写，再展示并用英语介绍。"
    return HINT.get(action, "")

DAILY_TASKS = [
    {"id": "cn-read", "subject": "语文", "name": "课外阅读 20 分钟",
     "sunshine": SUN, "frequency": "daily",
     "note": "连续阅读 20 分钟，读完说出主要内容或一个收获",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "cn-pen", "subject": "语文", "name": "练字一页",
     "sunshine": SUN, "frequency": "daily",
     "note": "练字一页，注意姿势、笔画和整洁，写完让家长看一眼",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "cn-diary", "subject": "语文", "name": "小练笔/日记",
     "sunshine": SUN, "frequency": "daily",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "note": "写一篇不少于 250 字的小练笔或日记，写完读一遍并改错",
     "metrics": []},
    {"id": "ma-calc", "subject": "数学", "name": "每日口算",
     "sunshine": SUN, "frequency": "daily",
     "note": "完成一组口算，记录用时和正确率；错题订正后再看一遍",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "time", "label": "用时", "unit": "分钟", "direction": "lower_better", "note": "从第一题做到最后一题计时"},
         {"id": "acc", "label": "正确率", "unit": "%", "direction": "higher_better", "note": "正确题数 ÷ 总题数 × 100%"},
     ]},
    {"id": "en-phonics", "subject": "英语", "name": "自然拼读学习",
     "sunshine": SUN, "frequency": "daily",
     "note": "听音读本单元词汇，圈出不会读的词，再拼读给家长听",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "pe-jump-rope", "subject": "体育", "name": "跳绳打卡",
     "sunshine": SUN, "frequency": "daily",
     "note": "先热身，再记录 100 下用时和 1 分钟跳绳个数；量力完成",
     "bonus_rule": {"type": "personal_best", "per_metric": 3,
                   "note": "破个人纪录才叠加（首日只记基线，防囤分）"},
     "metrics": [
         {"id": "t100", "label": "100下用时", "unit": "秒", "direction": "lower_better", "note": "从第 1 下开始计时，到第 100 下停止"},
         {"id": "n1m", "label": "1分钟跳多少个", "unit": "个", "direction": "higher_better", "note": "连续跳 1 分钟，记录完成的个数"},
     ]},
    {"id": "pe-situp", "subject": "体育", "name": "1分钟仰卧起坐",
     "sunshine": SUN, "frequency": "daily",
     "note": "先热身，在动作规范的前提下记录 1 分钟次数；不舒服就停止",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "cnt", "label": "1分钟做多少个", "unit": "个", "direction": "higher_better", "note": "只记录动作完整的次数"},
     ]},
    {"id": "pe-bend", "subject": "体育", "name": "坐位体前屈",
     "sunshine": SUN, "frequency": "daily",
     "note": "先热身，坐稳后向前伸展，记录手指超过脚尖的距离；不要用力硬压",
     "bonus_rule": {"type": "personal_best", "per_metric": 3, "note": "破个人纪录才叠加"},
     "metrics": [
         {"id": "cm", "label": "手指过脚尖多远", "unit": "厘米", "direction": "higher_better", "note": "以最远位置为准，脚尖前为正数"},
     ]},
    {"id": "pe-eye", "subject": "体育", "name": "做一遍眼保健操",
     "sunshine": SUN, "frequency": "daily",
     "note": "按完整节拍认真做一遍，保持手部清洁，结束后看远处放松",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": ""},
     "metrics": []},
    {"id": "go-play", "subject": "围棋", "name": "围棋对弈",
     "sunshine": SUN, "frequency": "daily",
     "note": "完成至少一局对弈，记录赢和输各几局，并说出一处复盘发现",
     "bonus_rule": {"type": "personal_best", "per_metric": 0, "note": "记胜负，不发破纪录阳光"},
     "metrics": [
         {"id": "win", "label": "赢了几局", "unit": "局", "direction": "higher_better", "note": "记录今天赢下的完整对局数"},
         {"id": "lose", "label": "输了几局", "unit": "局", "direction": "higher_better", "note": "记录今天输掉的完整对局数"},
     ]},
]

# 语文：单元名 + 具体课文任务（2026 部编六三制实物目录）
CN = [
    ("第1单元 桂花雨·落花生", [
        ("通读", "字词：通读《桂花雨》，圈出生字词"),
        ("通读", "关键语句：读《桂花雨》和《落花生》，说说感情"),
        ("听写", "生字词默写一遍"),
        ("朗读", "有感情地朗读《桂花雨》"),
        ("略读", "阅读略读课文《珍珠鸟》"),
        ("口语", "说清楚：我建议的班级公约"),
        ("习作", "写清楚：我的心爱之物有什么特点"),
    ]),
    ("第2单元 冀中的地道战·将相和", [
        ("通读", "字词：通读《冀中的地道战》和《将相和》"),
        ("阅读", "快速阅读：带着问题读本单元课文"),
        ("阅读", "带着问题读：什么比猎豹的速度更快"),
        ("阅读", "带着问题读：“诺曼底号”遇难记"),
        ("听写", "生字词默写一遍"),
        ("习作", "习作：“漫画”老师"),
    ]),
    ("第3单元 民间故事", [
        ("阅读", "讲清故事：阅读《猎人海力布》"),
        ("阅读", "创造性复述：讲《牛郎织女》的故事"),
        ("略读", "阅读略读《牛郎织女（二）》"),
        ("口语", "按起因、经过、结果讲清民间故事"),
        ("习作", "故事新编：保留主线，加入合理想象"),
        ("读书", "快乐读书吧：从前有座山"),
    ]),
    ("第4单元 爱国情怀", [
        ("背诵", "背诵：古诗三首（示儿 / 题临安邸 / 己亥杂诗）"),
        ("背诵", "结合资料体会感情：背诵《少年中国说》节选"),
        ("阅读", "阅读《圆明园的毁灭》"),
        ("略读", "阅读略读《梅兰芳蓄须明志》"),
        ("习作", "列提纲写：二十年后的家乡"),
    ]),
    ("第5单元 说明文", [
        ("阅读", "找一找：《太阳》用了哪些说明方法"),
        ("阅读", "整理信息：说清《金字塔》的主要内容"),
        ("例文", "找说明方法：鲸和风向袋怎么介绍事物"),
        ("习作", "用说明方法介绍一种事物"),
    ]),
    ("第6单元 父母之爱", [
        ("朗读", "场景细节：朗读《慈母情深》，体会父母之爱"),
        ("阅读", "阅读《父爱之舟》"),
        ("阅读", "阅读《航天员写给孩子的信》"),
        ("口语", "结合生活事例说说父母之爱"),
        ("习作", "写信：把想对父母说的话写清楚"),
    ]),
    ("第7单元 四时景物", [
        ("背诵", "背诵：古诗三首（山居秋暝 / 枫桥夜泊 / 早春呈水部张十八员外）"),
        ("阅读", "静态描写：读《第一场雪》和《白鹭》"),
        ("阅读", "动态描写：找出景物变化和动感句子"),
        ("摘抄", "摘抄描写景物的句子并注明出处"),
        ("习作", "按顺序写：我最喜爱的季节"),
    ]),
    ("第8单元 读书明智", [
        ("阅读", "梳理信息：读《古人谈读书》和《忆读书》"),
        ("阅读", "梳理信息：说清一本书讲了什么"),
        ("略读", "略读《走遍天下书为侣》，说说读书方法"),
        ("阅读", "课外阅读：说清故事内容和读书收获"),
        ("习作", "推荐一本书：写清内容和推荐理由"),
    ]),
]

# 数学：苏教 2026 秋教材。每张卡直接对应“任务与考点”里的可复练项目。
MA = [
    ("第1单元 图形的运动", [
        ("练习", "在方格图中按方向和距离平移"),
        ("练习", "按中心和角度旋转图形"),
        ("练习", "补全轴对称图形"),
        ("实践", "综合实践：图案的还原"),
    ]),
    ("第2单元 统计表和条形统计图（二）", [
        ("练习", "读填复式统计表"),
        ("练习", "读画复式条形统计图"),
        ("实践", "综合实践：绿色出行"),
        ("复习", "根据图表比较数据"),
    ]),
    ("第3单元 多边形的面积", [
        ("练习", "面积单位换算"),
        ("练习", "算平行四边形、三角形和梯形面积"),
        ("练习", "算组合图形面积"),
        ("实践", "综合实践：农田收入调查"),
    ]),
    ("第4单元 小数乘法和除法（一）", [
        ("练习", "小数乘法：确定积的小数位数"),
        ("口算", "小数乘除口算 20 题"),
        ("练习", "小数除法：确定商的小数点"),
        ("复习", "用小数乘除解决问题"),
    ]),
    ("第5单元 可能性", [
        ("练习", "用一定、可能、不可能描述"),
        ("练习", "判断可能性大小"),
        ("复习", "用可能性解释生活问题"),
    ]),
    ("第6单元 因数与倍数", [
        ("练习", "找因数和倍数"),
        ("练习", "用 2、3、5 的倍数特征判断"),
        ("复习", "判断质数、合数、奇数和偶数"),
    ]),
    ("第7单元 用字母表示数量关系（一）", [
        ("练习", "用字母表示数量关系"),
        ("练习", "化简含字母的式子并代入求值"),
        ("实践", "综合实践：钉子板上的多边形"),
        ("复习", "用含字母式子解决问题"),
    ]),
    ("第8单元 观察物体（三）", [
        ("练习", "从不同方向观察物体"),
        ("练习", "根据视图摆小正方体"),
        ("复习", "画出物体从不同方向看到的图形"),
    ]),
]

# 英语：译林 2026 实物目录
EN = [
    ("Unit 1 Good habits", [
        ("单词", "听读并会写 Unit 1 重点词汇（Word list）"),
        ("拼读", "练习拼读 bl（blackboard）"),
        ("跟读", "跟读 Story time"),
        ("语法", "三单练习：He/She does (not) …"),
        ("任务", "完成 Wrap-up：Talk about habits"),
    ]),
    ("Unit 2 I feel good", [
        ("单词", "听读并会写 Unit 2 重点词汇（Word list）"),
        ("拼读", "练习拼读 cl（climbing）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 Does he/she like …?"),
        ("任务", "完成 Wrap-up：Give advice"),
    ]),
    ("Unit 3 Hobbies", [
        ("单词", "听读并会写 Unit 3 重点词汇（Word list）"),
        ("拼读", "练习拼读 br（brother）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 What does he/she like doing?"),
        ("任务", "完成 Wrap-up：Talk about hobbies"),
    ]),
    ("Unit 4 Safety first", [
        ("单词", "听读并会写 Unit 4 重点词汇（Word list）"),
        ("拼读", "练习拼读 gr（great）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 should / shouldn't"),
        ("任务", "完成 Wrap-up：Give a speech about safety"),
    ]),
    ("Unit 5 At weekends", [
        ("单词", "听读并会写 Unit 5 重点词汇（Word list）"),
        ("拼读", "练习拼读 tr（travel）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 always/usually/often/sometimes/never"),
        ("任务", "完成 Wrap-up：Talk about your weekends"),
    ]),
    ("Unit 6 Getting along with others", [
        ("单词", "听读并会写 Unit 6 重点词汇（Word list）"),
        ("拼读", "练习拼读 dr（children）"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 Why don't …?"),
        ("任务", "完成 Wrap-up：Put on a play"),
    ]),
    ("Unit 7 Shopping smart", [
        ("单词", "听读并会写 Unit 7 重点词汇（Word list）"),
        ("拼读", "练习拼读 st/sk/sp"),
        ("跟读", "跟读 Story time"),
        ("语法", "练习 How much is/are …?"),
        ("任务", "完成 Wrap-up：Make a shopping plan"),
    ]),
    ("Unit 8 We love festivals", [
        ("单词", "听读并会写 Unit 8 重点词汇（Word list）"),
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

# 五上科学、道法：依据 2026 秋电子教材目录，把自动生成的泛化卡改成可完成的动作。
# gen_seed.py 只覆盖对应 g5s1 任务，保留原任务 ID 和单元内顺序。
G5_EXTRA = {
    "科学": [
        [("实验", "光的传播：用实验说明光沿直线传播", "用纸板或遮挡物设计小实验，观察并说出光的传播路线。"),
         ("实验", "光的反射：用镜子改变光的方向", "用镜子把光照到指定位置，画出入射和反射的大致方向。"),
         ("制作", "潜望镜与万花筒：画图解释光路", "观察或制作一个装置，画出光线经过镜子的路线并说清作用。"),
         ("实验", "七色光：观察白光分解后的颜色", "用三棱镜、光盘或其他安全方法观察七色光，并按顺序说出看到的颜色。")],
        [("实验", "热传导：比较不同材料传热快慢", "用相同条件比较两种材料，记录哪种先变热，并说出判断依据。"),
         ("实验", "热对流：观察水受热后的流动", "安全加热并观察水的流动，用箭头画出热水和冷水的运动方向。"),
         ("观察", "热辐射：找出生活中的热辐射", "找出太阳、火或暖气等例子，说清热是怎样传到物体上的。"),
         ("实践", "材料的传热本领：做一次保温比较", "选两种材料包住同样的温水，定时比较温度变化，记录结果并下结论。")],
        [("实验", "弹力：观察物体形变后的弹力", "让橡皮筋、弹簧等发生形变，观察它怎样恢复，并举一个弹力的用途。"),
         ("实验", "摩擦力：比较不同表面的摩擦大小", "让同一物体在不同表面运动，比较用力大小并记录影响摩擦力的条件。"),
         ("实验", "浮力：观察物体在水中的浮沉", "把不同物体放入水中，记录浮沉现象，并说出水对物体有向上的力。"),
         ("实验", "力与运动：观察力怎样改变运动", "对物体施加不同方向或大小的力，记录运动快慢、方向或状态的变化。")],
        [("实验", "撬重物的窍门：找出杠杆的三个点", "用尺或木条撬物体，标出支点、用力点和阻力点，说说怎样更省力。"),
         ("观察", "拧螺丝的学问：认识轮轴的作用", "比较直接拧和用螺丝刀拧的差别，说清轮和轴怎样帮助用力。"),
         ("实验", "升旗的方法：观察滑轮怎样工作", "观察升旗装置，指出滑轮的位置和作用，并说清它是否改变用力方向。"),
         ("实验", "斜坡的启示：比较斜坡的省力效果", "用不同坡度把同一物体移到相同高度，记录用力大小并比较结果。")],
        [("观察", "生物的启示：从结构找到仿生想法", "观察一种生物的外形或功能，写下它给生活用品带来的一个设计启示。"),
         ("实验", "蛋壳与薄壳结构：比较形状的承重能力", "比较平面和拱形/薄壳结构的承重效果，记录现象并说出原因。"),
         ("解释", "海豚与声呐：用回声解释探测", "查阅或根据课文画出声波往返路线，说清声呐怎样发现目标。"),
         ("设计", "我们来仿生：完成一个仿生方案", "从生物特点、模仿对象、解决问题和制作方法四项写出方案，并画草图。"),
         ("探究", "专项学习：像科学家一样完成探究", "提出一个可研究的问题，写出猜想、步骤、记录和结论。"),
         ("复盘", "课后评价：说清这学期的科学发现", "选一个实验或设计，说清现象、结论和一次改进，不只说‘学会了’。")],
    ],
    "道法": [
        [("时间线", "开天辟地的大事变：说清中国共产党成立的意义", "按时间、地点、事件和意义四项整理，再用自己的话讲给家长听。"),
         ("讲述", "探索中国革命道路：讲清革命道路的探索", "用时间线说出重要探索和转折，至少讲出两件具体史实。"),
         ("举例", "抗日战争的中流砥柱：用史实说明作用", "列出两件抗战史实，说明中国共产党为什么是抗日战争的中流砥柱。"),
         ("时间线", "夺取胜利的解放战争：按顺序讲清过程", "按时间线整理重要战役或事件，说清解放战争走向胜利的过程。")],
        [("讲述", "中国人民站起来了：说清新中国成立的意义", "结合课文和一件史实，说清新中国成立后人民生活和国家地位的变化。"),
         ("举例", "人民当家作主：举例说明人民参与国家治理", "说出一个人民当家作主的制度或生活例子，并解释它怎样发挥作用。"),
         ("比较", "社会主义好：用事实说明建设成就", "从课文中找两项建设成就，说清成就、事实和你的感受。")],
        [("比较", "改革开放展宏图：说清前后变化", "找一项改革开放前后的生活变化，用具体事例说明变化从哪里来。"),
         ("整理", "综合国力日益提升：用数据或事例说明实力", "从课文找三条数据或事例，分成经济、科技、生活等方面并说出结论。"),
         ("时间线", "祖国统一大业不断推进：整理统一进展", "按时间顺序整理课文中的重要进展，说清它们与祖国统一的关系。")],
        [("讲述", "走进新时代：说清新时代的历史方位", "用三句话说清新时代是什么、从哪里开始以及和少年有什么关系。"),
         ("举例", "历史性成就：列举新时代的成就", "从经济、科技、民生或生态中各找例子，至少列举三项并说出依据。"),
         ("行动", "开启新征程：说出少年的行动", "结合自己的学习和生活，写下并说出一项现在就能做到的行动。")],
    ],
}


def pack(subj, seq, name, items):
    # 任务/单元 id 带学期前缀，确保跨学期不撞旧 completion（五上=g5s1）
    uid = f"{TERM['id']}-{SUBJ_ID[subj]}-{seq}"
    unit = {"id": uid, "subject": subj, "term_id": TERM["id"], "seq": seq, "name": name}
    tasks = []
    for i, item in enumerate(items, 1):
        action, title = item[:2]
        detail = item[2] if len(item) > 2 else detail_for(action, title)
        tasks.append({
            "id": f"{uid}-{i}", "subject": subj, "unit_id": uid,
            "action": action, "title": title, "detail": detail,
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
        json.dump({"term": TERM, "subjects": SUBJECTS, "curriculum_ver": "2026-g5s1-v11",
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
