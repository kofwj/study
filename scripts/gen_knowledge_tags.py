# -*- coding: utf-8 -*-
"""考点标签：科目字典 + 单元映射。

五上五科与 1–4 年级上册 = 人工精标（HAND）；其余学期只保留自动标签作内部占位，家长端不把它们当作可点选考点。
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

# 1–4 年级上册精标：依据 catalog.json 章节名，写成可复练动作。
# 入学教育 / 数学游戏分享 / 期末复习不进 HAND（家长端不显示自动占位）。
CN1_TAGS = [
    {"id": "cn1-jmwht", "subject_id": "语文", "kind": "单元考点", "name": "认读金木水火土"},
    {"id": "cn1-kemsz", "subject_id": "语文", "kind": "单元考点", "name": "认读口耳目手足"},
    {"id": "cn1-rycs", "subject_id": "语文", "kind": "单元考点", "name": "认读日月山川"},
    {"id": "cn1-iuu", "subject_id": "语文", "kind": "单元考点", "name": "认读 i u ü"},
    {"id": "cn1-bpmf", "subject_id": "语文", "kind": "单元考点", "name": "认读 b p m f"},
    {"id": "cn1-dtnl", "subject_id": "语文", "kind": "单元考点", "name": "认读 d t n l"},
    {"id": "cn1-jqx", "subject_id": "语文", "kind": "单元考点", "name": "认读 j q x"},
    {"id": "cn1-zcs", "subject_id": "语文", "kind": "单元考点", "name": "认读 z c s"},
    {"id": "cn1-zhch", "subject_id": "语文", "kind": "单元考点", "name": "认读翘舌音 zh ch sh r"},
    {"id": "cn1-fym", "subject_id": "语文", "kind": "单元考点", "name": "认读复韵母 o ou iu ie"},
    {"id": "cn1-qby", "subject_id": "语文", "kind": "单元考点", "name": "认读前鼻韵母 n en in"},
    {"id": "cn1-hby", "subject_id": "语文", "kind": "单元考点", "name": "认读后鼻韵母 ng eng ing ong"},
    {"id": "cn1-jn", "subject_id": "语文", "kind": "单元考点", "name": "朗读《江南》"},
    {"id": "cn1-xdh", "subject_id": "语文", "kind": "单元考点", "name": "讲清雪地里的小画家"},
    {"id": "cn1-sj", "subject_id": "语文", "kind": "单元考点", "name": "按顺序说四季"},
    {"id": "cn1-rym", "subject_id": "语文", "kind": "单元考点", "name": "会认会写「日月明」"},
    {"id": "cn1-sbb", "subject_id": "语文", "kind": "单元考点", "name": "认读小书包里的物品"},
    {"id": "cn1-sgq", "subject_id": "语文", "kind": "单元考点", "name": "认读并说出升国旗"},
    {"id": "cn1-yz", "subject_id": "语文", "kind": "单元考点", "name": "讲清影子是怎么来的"},
    {"id": "cn1-ljb", "subject_id": "语文", "kind": "单元考点", "name": "说出两件宝是什么"},
    {"id": "cn1-wy", "subject_id": "语文", "kind": "单元考点", "name": "讲清乌鸦喝水"},
    {"id": "cn1-yd", "subject_id": "语文", "kind": "单元考点", "name": "讲清雨点儿去了哪里"},
]
MA1_TAGS = [
    {"id": "ma1-05r", "subject_id": "数学", "kind": "单元考点", "name": "认读 0～5"},
    {"id": "ma1-05j", "subject_id": "数学", "kind": "单元考点", "name": "5 以内加减"},
    {"id": "ma1-69r", "subject_id": "数学", "kind": "单元考点", "name": "认读 6～9"},
    {"id": "ma1-69j", "subject_id": "数学", "kind": "单元考点", "name": "9 以内加减"},
    {"id": "ma1-lft", "subject_id": "数学", "kind": "单元考点", "name": "分清长方体和正方体"},
    {"id": "ma1-pmx", "subject_id": "数学", "kind": "单元考点", "name": "认识常见平面图形"},
    {"id": "ma1-10r", "subject_id": "数学", "kind": "单元考点", "name": "认识 10"},
    {"id": "ma1-10j", "subject_id": "数学", "kind": "单元考点", "name": "10 的加减"},
    {"id": "ma1-1119", "subject_id": "数学", "kind": "单元考点", "name": "认识 11～19"},
    {"id": "ma1-sj", "subject_id": "数学", "kind": "单元考点", "name": "十几加减一位数"},
]
KX1_TAGS = [
    {"id": "kx1-gc", "subject_id": "科学", "kind": "单元考点", "name": "说出什么是科学观察"},
    {"id": "kx1-bz", "subject_id": "科学", "kind": "单元考点", "name": "按步骤做一次观察"},
    {"id": "kx1-gg", "subject_id": "科学", "kind": "单元考点", "name": "用眼耳鼻手分别观察"},
    {"id": "kx1-bj", "subject_id": "科学", "kind": "单元考点", "name": "比较不同感官发现的不同"},
    {"id": "kx1-tw", "subject_id": "科学", "kind": "单元考点", "name": "根据观察提出一个问题"},
    {"id": "kx1-yz", "subject_id": "科学", "kind": "单元考点", "name": "用简单办法验证想法"},
    {"id": "kx1-zp", "subject_id": "科学", "kind": "单元考点", "name": "用材料做一个小作品"},
    {"id": "kx1-wt", "subject_id": "科学", "kind": "单元考点", "name": "说出作品解决什么问题"},
]
DF1_TAGS = [
    {"id": "df1-xxs", "subject_id": "道法", "kind": "单元考点", "name": "说出小学生该怎么做"},
    {"id": "df1-xyr", "subject_id": "道法", "kind": "单元考点", "name": "认识校园里的人"},
    {"id": "df1-gz", "subject_id": "道法", "kind": "单元考点", "name": "说出校园生活的规则"},
    {"id": "df1-zl", "subject_id": "道法", "kind": "单元考点", "name": "自己整理书包和课桌"},
    {"id": "df1-xg", "subject_id": "道法", "kind": "单元考点", "name": "说出一项好习惯并做到"},
    {"id": "df1-zs", "subject_id": "道法", "kind": "单元考点", "name": "按时作息不熬夜"},
    {"id": "df1-wm", "subject_id": "道法", "kind": "单元考点", "name": "用礼貌用语打招呼"},
    {"id": "df1-pd", "subject_id": "道法", "kind": "单元考点", "name": "排队不插队"},
]
CN2_TAGS = [
    {"id": "cn2-wssm", "subject_id": "语文", "kind": "单元考点", "name": "讲清「我是什么」里的水"},
    {"id": "cn2-zwmm", "subject_id": "语文", "kind": "单元考点", "name": "讲清植物妈妈怎么传播种子"},
    {"id": "cn2-szg", "subject_id": "语文", "kind": "单元考点", "name": "认读树木名称"},
    {"id": "cn2-psg", "subject_id": "语文", "kind": "单元考点", "name": "有节奏地朗读拍手歌"},
    {"id": "cn2-tjs", "subject_id": "语文", "kind": "单元考点", "name": "按季节说农事"},
    {"id": "cn2-wpm", "subject_id": "语文", "kind": "单元考点", "name": "讲清去外婆家"},
    {"id": "cn2-sxx", "subject_id": "语文", "kind": "单元考点", "name": "讲清数星星的孩子"},
    {"id": "cn2-lspb", "subject_id": "语文", "kind": "单元考点", "name": "朗读《望庐山瀑布》"},
    {"id": "cn2-hsqs", "subject_id": "语文", "kind": "单元考点", "name": "抓住特点说黄山奇石"},
    {"id": "cn2-ryt", "subject_id": "语文", "kind": "单元考点", "name": "介绍日月潭或葡萄沟"},
    {"id": "cn2-hnb", "subject_id": "语文", "kind": "单元考点", "name": "讲清寒号鸟的教训"},
    {"id": "cn2-hl", "subject_id": "语文", "kind": "单元考点", "name": "讲清我要的是葫芦"},
    {"id": "cn2-zdbd", "subject_id": "语文", "kind": "单元考点", "name": "讲清朱德的扁担"},
    {"id": "cn2-psj", "subject_id": "语文", "kind": "单元考点", "name": "讲清难忘的泼水节"},
    {"id": "cn2-clg", "subject_id": "语文", "kind": "单元考点", "name": "朗读《敕勒歌》"},
    {"id": "cn2-wzna", "subject_id": "语文", "kind": "单元考点", "name": "讲清雾在哪里"},
    {"id": "cn2-xhz", "subject_id": "语文", "kind": "单元考点", "name": "讲清雪孩子"},
    {"id": "cn2-zcfz", "subject_id": "语文", "kind": "单元考点", "name": "讲清纸船和风筝"},
    {"id": "cn2-klxh", "subject_id": "语文", "kind": "单元考点", "name": "讲清快乐的小河"},
]
MA2_TAGS = [
    {"id": "ma2-16k", "subject_id": "数学", "kind": "单元考点", "name": "背出 1～6 的乘法口诀"},
    {"id": "ma2-16c", "subject_id": "数学", "kind": "单元考点", "name": "用口诀算乘法"},
    {"id": "ma2-16ch", "subject_id": "数学", "kind": "单元考点", "name": "用口诀算除法"},
    {"id": "ma2-cht", "subject_id": "数学", "kind": "单元考点", "name": "看图列出除法算式"},
    {"id": "ma2-79k", "subject_id": "数学", "kind": "单元考点", "name": "背出 7～9 的乘法口诀"},
    {"id": "ma2-79cc", "subject_id": "数学", "kind": "单元考点", "name": "用 7～9 口诀算乘除"},
    {"id": "ma2-3w", "subject_id": "数学", "kind": "单元考点", "name": "读写三位数"},
    {"id": "ma2-3b", "subject_id": "数学", "kind": "单元考点", "name": "比较三位数的大小"},
    {"id": "ma2-jj", "subject_id": "数学", "kind": "单元考点", "name": "两位数加减两位数"},
    {"id": "ma2-jw", "subject_id": "数学", "kind": "单元考点", "name": "进位退位时对位"},
    {"id": "ma2-ysc", "subject_id": "数学", "kind": "单元考点", "name": "有余数的除法"},
    {"id": "ma2-ysx", "subject_id": "数学", "kind": "单元考点", "name": "余数要比除数小"},
]
KX2_TAGS = [
    {"id": "kx2-cl", "subject_id": "科学", "kind": "单元考点", "name": "说出常见物品用什么材料"},
    {"id": "kx2-yx", "subject_id": "科学", "kind": "单元考点", "name": "比较材料的软硬轻重"},
    {"id": "kx2-ct", "subject_id": "科学", "kind": "单元考点", "name": "找出能被磁铁吸住的东西"},
    {"id": "kx2-ld", "subject_id": "科学", "kind": "单元考点", "name": "观察磁铁两端有什么不同"},
    {"id": "kx2-yl", "subject_id": "科学", "kind": "单元考点", "name": "用力改变物体的运动"},
    {"id": "kx2-dx", "subject_id": "科学", "kind": "单元考点", "name": "比较用力大小带来的效果"},
    {"id": "kx2-gj", "subject_id": "科学", "kind": "单元考点", "name": "认识常见工具"},
    {"id": "kx2-xz", "subject_id": "科学", "kind": "单元考点", "name": "选对工具做一件事"},
]
DF2_TAGS = [
    {"id": "df2-jr", "subject_id": "道法", "kind": "单元考点", "name": "说出节假日怎么过得有意义"},
    {"id": "df2-aq", "subject_id": "道法", "kind": "单元考点", "name": "过节时注意安全"},
    {"id": "df2-bj", "subject_id": "道法", "kind": "单元考点", "name": "为班级做一件事"},
    {"id": "df2-fg", "subject_id": "道法", "kind": "单元考点", "name": "和同学分工合作"},
    {"id": "df2-jx", "subject_id": "道法", "kind": "单元考点", "name": "介绍家乡一处风景或特产"},
    {"id": "df2-hj", "subject_id": "道法", "kind": "单元考点", "name": "爱护家乡环境"},
    {"id": "df2-gq", "subject_id": "道法", "kind": "单元考点", "name": "认识国旗国歌"},
    {"id": "df2-ag", "subject_id": "道法", "kind": "单元考点", "name": "说出爱国的一件小事"},
]
CN3_TAGS = [
    {"id": "cn3-hxx", "subject_id": "语文", "kind": "单元考点", "name": "感受《花的学校》的想象"},
    {"id": "cn3-bd", "subject_id": "语文", "kind": "单元考点", "name": "不懂的地方能提问"},
    {"id": "cn3-qt", "subject_id": "语文", "kind": "单元考点", "name": "抓住秋天特点朗读"},
    {"id": "cn3-sx", "subject_id": "语文", "kind": "单元考点", "name": "按顺序写秋天"},
    {"id": "cn3-jg", "subject_id": "语文", "kind": "单元考点", "name": "讲清犟龟为什么不放弃"},
    {"id": "cn3-xgx", "subject_id": "语文", "kind": "单元考点", "name": "创造性复述小狗学叫"},
    {"id": "cn3-ndl", "subject_id": "语文", "kind": "单元考点", "name": "讲清在牛肚子里旅行"},
    {"id": "cn3-nla", "subject_id": "语文", "kind": "单元考点", "name": "抓住特点说一块奶酪"},
    {"id": "cn3-jsd", "subject_id": "语文", "kind": "单元考点", "name": "观察草地前后有什么变化"},
    {"id": "cn3-jw", "subject_id": "语文", "kind": "单元考点", "name": "按顺序写一处景物"},
    {"id": "cn3-hbc", "subject_id": "语文", "kind": "单元考点", "name": "抓住特点介绍海滨小城"},
    {"id": "cn3-xal", "subject_id": "语文", "kind": "单元考点", "name": "按顺序介绍小兴安岭"},
    {"id": "cn3-dzr", "subject_id": "语文", "kind": "单元考点", "name": "找出大自然的声音"},
    {"id": "cn3-dsh", "subject_id": "语文", "kind": "单元考点", "name": "从生活中发现可写的事物"},
    {"id": "cn3-zq", "subject_id": "语文", "kind": "单元考点", "name": "讲清一定要争气"},
    {"id": "cn3-sst", "subject_id": "语文", "kind": "单元考点", "name": "讲清手术台就是阵地"},
]
MA3_TAGS = [
    {"id": "ma3-hh", "subject_id": "数学", "kind": "单元考点", "name": "先乘除后加减"},
    {"id": "ma3-kh", "subject_id": "数学", "kind": "单元考点", "name": "带括号的混合运算"},
    {"id": "ma3-c1", "subject_id": "数学", "kind": "单元考点", "name": "两、三位数乘一位数"},
    {"id": "ma3-cwt", "subject_id": "数学", "kind": "单元考点", "name": "用乘法解决问题"},
    {"id": "ma3-sj", "subject_id": "数学", "kind": "单元考点", "name": "收集整理数据"},
    {"id": "ma3-tjb", "subject_id": "数学", "kind": "单元考点", "name": "读懂简单统计表"},
    {"id": "ma3-mm", "subject_id": "数学", "kind": "单元考点", "name": "毫米、分米、千米换算"},
    {"id": "ma3-dw", "subject_id": "数学", "kind": "单元考点", "name": "选择合适的长度单位"},
    {"id": "ma3-py", "subject_id": "数学", "kind": "单元考点", "name": "按方向平移"},
    {"id": "ma3-dc", "subject_id": "数学", "kind": "单元考点", "name": "判断轴对称图形"},
    {"id": "ma3-ch1", "subject_id": "数学", "kind": "单元考点", "name": "两、三位数除以一位数"},
    {"id": "ma3-ys", "subject_id": "数学", "kind": "单元考点", "name": "有余数的除法"},
    {"id": "ma3-xdt", "subject_id": "数学", "kind": "单元考点", "name": "用线段图分析数量关系"},
    {"id": "ma3-lb", "subject_id": "数学", "kind": "单元考点", "name": "两步解决问题"},
    {"id": "ma3-st", "subject_id": "数学", "kind": "单元考点", "name": "根据视图摆小正方体"},
    {"id": "ma3-gc", "subject_id": "数学", "kind": "单元考点", "name": "从不同方向观察物体"},
]
EN3_TAGS = [
    {"id": "en3-hi", "subject_id": "英语", "kind": "单元考点", "name": "用 Hello 打招呼"},
    {"id": "en3-abcd", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 A B C D"},
    {"id": "en3-name", "subject_id": "英语", "kind": "单元考点", "name": "用 What's your name 问姓名"},
    {"id": "en3-efg", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 E F G"},
    {"id": "en3-areu", "subject_id": "英语", "kind": "单元考点", "name": "用 Are you 确认是谁"},
    {"id": "en3-hijk", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 H I J K"},
    {"id": "en3-this", "subject_id": "英语", "kind": "单元考点", "name": "用 This is 介绍朋友"},
    {"id": "en3-lmn", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 L M N"},
    {"id": "en3-who", "subject_id": "英语", "kind": "单元考点", "name": "用 Who's she/he 介绍家人"},
    {"id": "en3-opq", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 O P Q"},
    {"id": "en3-ishe", "subject_id": "英语", "kind": "单元考点", "name": "用 Is he/she 询问家人"},
    {"id": "en3-rst", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 R S T"},
    {"id": "en3-hbd", "subject_id": "英语", "kind": "单元考点", "name": "说生日祝福 Happy Birthday"},
    {"id": "en3-uvw", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 U V W"},
    {"id": "en3-ican", "subject_id": "英语", "kind": "单元考点", "name": "用 I can 说能为家人做什么"},
    {"id": "en3-xyz", "subject_id": "英语", "kind": "单元考点", "name": "认读字母 X Y Z"},
]
KX3_TAGS = [
    {"id": "kx3-tr", "subject_id": "科学", "kind": "单元考点", "name": "观察土壤里有什么"},
    {"id": "kx3-bjt", "subject_id": "科学", "kind": "单元考点", "name": "比较不同土壤"},
    {"id": "kx3-gt", "subject_id": "科学", "kind": "单元考点", "name": "分清固体和液体"},
    {"id": "kx3-zt", "subject_id": "科学", "kind": "单元考点", "name": "观察物质状态变化"},
    {"id": "kx3-st", "subject_id": "科学", "kind": "单元考点", "name": "说出地球上的水体"},
    {"id": "kx3-jy", "subject_id": "科学", "kind": "单元考点", "name": "说出节约用水的做法"},
    {"id": "kx3-kq", "subject_id": "科学", "kind": "单元考点", "name": "用实验证明空气存在"},
    {"id": "kx3-kj", "subject_id": "科学", "kind": "单元考点", "name": "说出空气占空间"},
    {"id": "kx3-cl", "subject_id": "科学", "kind": "单元考点", "name": "比较不同材料"},
    {"id": "kx3-yb", "subject_id": "科学", "kind": "单元考点", "name": "说出材料怎么变得更好用"},
]
DF3_TAGS = [
    {"id": "df3-sj", "subject_id": "道法", "kind": "单元考点", "name": "自己安排学习时间"},
    {"id": "df3-kn", "subject_id": "道法", "kind": "单元考点", "name": "遇到困难先自己想办法"},
    {"id": "df3-gc", "subject_id": "道法", "kind": "单元考点", "name": "用观察或实验了解科学"},
    {"id": "df3-bx", "subject_id": "道法", "kind": "单元考点", "name": "不信没有根据的说法"},
    {"id": "df3-yd", "subject_id": "道法", "kind": "单元考点", "name": "为集体遵守约定"},
    {"id": "df3-hz", "subject_id": "道法", "kind": "单元考点", "name": "和同学一起完成一件事"},
    {"id": "df3-gg", "subject_id": "道法", "kind": "单元考点", "name": "公共场合不大声喧哗"},
    {"id": "df3-ss", "subject_id": "道法", "kind": "单元考点", "name": "爱护公共设施"},
]
CN4_TAGS = [
    {"id": "cn4-gc", "subject_id": "语文", "kind": "单元考点", "name": "抓住特点说观潮"},
    {"id": "cn4-fx", "subject_id": "语文", "kind": "单元考点", "name": "体会《繁星》的想象"},
    {"id": "cn4-wd", "subject_id": "语文", "kind": "单元考点", "name": "讲清五粒豆各自的选择"},
    {"id": "cn4-tj", "subject_id": "语文", "kind": "单元考点", "name": "讲清田忌赛马的策略"},
    {"id": "cn4-psj", "subject_id": "语文", "kind": "单元考点", "name": "观察爬山虎的脚"},
    {"id": "cn4-gcrj", "subject_id": "语文", "kind": "单元考点", "name": "按顺序写观察日记"},
    {"id": "cn4-pg", "subject_id": "语文", "kind": "单元考点", "name": "讲清盘古开天地"},
    {"id": "cn4-jw", "subject_id": "语文", "kind": "单元考点", "name": "讲清精卫填海或普罗米修斯"},
    {"id": "cn4-mq", "subject_id": "语文", "kind": "单元考点", "name": "抓住动作神态写麻雀"},
    {"id": "cn4-qs", "subject_id": "语文", "kind": "单元考点", "name": "把一件事写清楚"},
    {"id": "cn4-cc", "subject_id": "语文", "kind": "单元考点", "name": "按游览顺序介绍长城或颐和园"},
    {"id": "cn4-jjy", "subject_id": "语文", "kind": "单元考点", "name": "当小小讲解员介绍一处景点"},
    {"id": "cn4-nhe", "subject_id": "语文", "kind": "单元考点", "name": "讲清牛和鹅前后态度的变化"},
    {"id": "cn4-gs", "subject_id": "语文", "kind": "单元考点", "name": "把心里的感受写具体"},
    {"id": "cn4-jq", "subject_id": "语文", "kind": "单元考点", "name": "讲清为中华之崛起而读书"},
    {"id": "cn4-xx", "subject_id": "语文", "kind": "单元考点", "name": "用书信表达想法"},
]
MA4_TAGS = [
    {"id": "ma4-ch2", "subject_id": "数学", "kind": "单元考点", "name": "两、三位数除以两位数"},
    {"id": "ma4-sw", "subject_id": "数学", "kind": "单元考点", "name": "商是两位数的除法"},
    {"id": "ma4-zc", "subject_id": "数学", "kind": "单元考点", "name": "长方形、正方形周长"},
    {"id": "ma4-mj", "subject_id": "数学", "kind": "单元考点", "name": "长方形、正方形面积"},
    {"id": "ma4-csl", "subject_id": "数学", "kind": "单元考点", "name": "用乘法数量关系解决问题"},
    {"id": "ma4-bei", "subject_id": "数学", "kind": "单元考点", "name": "画图分析倍的关系"},
    {"id": "ma4-hh", "subject_id": "数学", "kind": "单元考点", "name": "四则混合运算的顺序"},
    {"id": "ma4-cl", "subject_id": "数学", "kind": "单元考点", "name": "用两步策略解决问题"},
    {"id": "ma4-ds", "subject_id": "数学", "kind": "单元考点", "name": "读写多位数"},
    {"id": "ma4-bj", "subject_id": "数学", "kind": "单元考点", "name": "比较多位数的大小"},
    {"id": "ma4-jj", "subject_id": "数学", "kind": "单元考点", "name": "大数加减"},
    {"id": "ma4-c1", "subject_id": "数学", "kind": "单元考点", "name": "大数乘一位数或整十"},
]
EN4_TAGS = [
    {"id": "en4-km", "subject_id": "英语", "kind": "单元考点", "name": "说出学校科目"},
    {"id": "en4-sub", "subject_id": "英语", "kind": "单元考点", "name": "用 What subject 提问"},
    {"id": "en4-day", "subject_id": "英语", "kind": "单元考点", "name": "按时间说一天安排"},
    {"id": "en4-clk", "subject_id": "英语", "kind": "单元考点", "name": "用 o'clock 说整点"},
    {"id": "en4-wk", "subject_id": "英语", "kind": "单元考点", "name": "说一周各天做什么"},
    {"id": "en4-wd", "subject_id": "英语", "kind": "单元考点", "name": "用星期几提问和回答"},
    {"id": "en4-sp", "subject_id": "英语", "kind": "单元考点", "name": "说出喜欢的运动"},
    {"id": "en4-like", "subject_id": "英语", "kind": "单元考点", "name": "用 I like 表达爱好"},
    {"id": "en4-toy", "subject_id": "英语", "kind": "单元考点", "name": "比较不同玩具"},
    {"id": "en4-myt", "subject_id": "英语", "kind": "单元考点", "name": "介绍自己的玩具"},
    {"id": "en4-wt", "subject_id": "英语", "kind": "单元考点", "name": "用英语说天气"},
    {"id": "en4-wth", "subject_id": "英语", "kind": "单元考点", "name": "用 What's the weather 提问"},
    {"id": "en4-ss", "subject_id": "英语", "kind": "单元考点", "name": "说出四季特点"},
    {"id": "en4-act", "subject_id": "英语", "kind": "单元考点", "name": "说出季节里做什么"},
    {"id": "en4-wear", "subject_id": "英语", "kind": "单元考点", "name": "说出穿着"},
    {"id": "en4-clth", "subject_id": "英语", "kind": "单元考点", "name": "按天气选衣服"},
]
KX4_TAGS = [
    {"id": "kx4-fl", "subject_id": "科学", "kind": "单元考点", "name": "给动物分类"},
    {"id": "kx4-tz", "subject_id": "科学", "kind": "单元考点", "name": "观察一种动物的特征"},
    {"id": "kx4-yd", "subject_id": "科学", "kind": "单元考点", "name": "描述物体怎么运动"},
    {"id": "kx4-km", "subject_id": "科学", "kind": "单元考点", "name": "比较运动的快慢和方向"},
    {"id": "kx4-dl", "subject_id": "科学", "kind": "单元考点", "name": "连接简单电路让灯亮"},
    {"id": "kx4-gz", "subject_id": "科学", "kind": "单元考点", "name": "找出电路为什么不通"},
    {"id": "kx4-yy", "subject_id": "科学", "kind": "单元考点", "name": "解释影子是怎么来的"},
    {"id": "kx4-dx", "subject_id": "科学", "kind": "单元考点", "name": "改变影子的大小和方向"},
    {"id": "kx4-jb", "subject_id": "科学", "kind": "单元考点", "name": "找出磁铁的北极和南极"},
    {"id": "kx4-gt", "subject_id": "科学", "kind": "单元考点", "name": "磁铁隔着东西也能吸铁"},
]
DF4_TAGS = [
    {"id": "df4-gy", "subject_id": "道法", "kind": "单元考点", "name": "为班级定一条公约并遵守"},
    {"id": "df4-gb", "subject_id": "道法", "kind": "单元考点", "name": "说出班干部该负的责任"},
    {"id": "df4-tc", "subject_id": "道法", "kind": "单元考点", "name": "说出自己的兴趣特长"},
    {"id": "df4-mb", "subject_id": "道法", "kind": "单元考点", "name": "给自己定一个小目标"},
    {"id": "df4-zj", "subject_id": "道法", "kind": "单元考点", "name": "分辨网上信息真假"},
    {"id": "df4-ys", "subject_id": "道法", "kind": "单元考点", "name": "保护个人隐私"},
    {"id": "df4-xf", "subject_id": "道法", "kind": "单元考点", "name": "理性消费不攀比"},
    {"id": "df4-gw", "subject_id": "道法", "kind": "单元考点", "name": "文明购物"},
]
HAND14 = {
    "g1s1-cn-2": ["cn1-jmwht", "cn1-kemsz", "cn1-rycs"],
    "g1s1-cn-3": ["cn1-iuu", "cn1-bpmf", "cn1-dtnl"],
    "g1s1-cn-4": ["cn1-jqx", "cn1-zcs", "cn1-zhch"],
    "g1s1-cn-5": ["cn1-fym", "cn1-qby", "cn1-hby"],
    "g1s1-cn-6": ["cn1-jn", "cn1-xdh", "cn1-sj"],
    "g1s1-cn-7": ["cn1-rym", "cn1-sbb", "cn1-sgq"],
    "g1s1-cn-8": ["cn1-yz", "cn1-ljb"],
    "g1s1-cn-9": ["cn1-wy", "cn1-yd"],
    "g1s1-ma-2": ["ma1-05r", "ma1-05j"],
    "g1s1-ma-3": ["ma1-69r", "ma1-69j"],
    "g1s1-ma-4": ["ma1-lft", "ma1-pmx"],
    "g1s1-ma-5": ["ma1-10r", "ma1-10j"],
    "g1s1-ma-6": ["ma1-1119", "ma1-sj"],
    "g1s1-kx-1": ["kx1-gc", "kx1-bz"],
    "g1s1-kx-2": ["kx1-gg", "kx1-bj"],
    "g1s1-kx-3": ["kx1-tw", "kx1-yz"],
    "g1s1-kx-4": ["kx1-zp", "kx1-wt"],
    "g1s1-df-1": ["df1-xxs", "df1-xyr"],
    "g1s1-df-2": ["df1-gz", "df1-zl"],
    "g1s1-df-3": ["df1-xg", "df1-zs"],
    "g1s1-df-4": ["df1-wm", "df1-pd"],
    "g2s1-cn-1": ["cn2-wssm", "cn2-zwmm"],
    "g2s1-cn-2": ["cn2-szg", "cn2-psg", "cn2-tjs"],
    "g2s1-cn-3": ["cn2-wpm", "cn2-sxx"],
    "g2s1-cn-4": ["cn2-lspb", "cn2-hsqs", "cn2-ryt"],
    "g2s1-cn-5": ["cn2-hnb", "cn2-hl"],
    "g2s1-cn-6": ["cn2-zdbd", "cn2-psj"],
    "g2s1-cn-7": ["cn2-clg", "cn2-wzna", "cn2-xhz"],
    "g2s1-cn-8": ["cn2-zcfz", "cn2-klxh"],
    "g2s1-ma-2": ["ma2-16k", "ma2-16c"],
    "g2s1-ma-3": ["ma2-16ch", "ma2-cht"],
    "g2s1-ma-4": ["ma2-79k", "ma2-79cc"],
    "g2s1-ma-5": ["ma2-3w", "ma2-3b"],
    "g2s1-ma-6": ["ma2-jj", "ma2-jw"],
    "g2s1-ma-7": ["ma2-ysc", "ma2-ysx"],
    "g2s1-kx-1": ["kx2-cl", "kx2-yx"],
    "g2s1-kx-2": ["kx2-ct", "kx2-ld"],
    "g2s1-kx-3": ["kx2-yl", "kx2-dx"],
    "g2s1-kx-4": ["kx2-gj", "kx2-xz"],
    "g2s1-df-1": ["df2-jr", "df2-aq"],
    "g2s1-df-2": ["df2-bj", "df2-fg"],
    "g2s1-df-3": ["df2-jx", "df2-hj"],
    "g2s1-df-4": ["df2-gq", "df2-ag"],
    "g3s1-cn-1": ["cn3-hxx", "cn3-bd"],
    "g3s1-cn-2": ["cn3-qt", "cn3-sx"],
    "g3s1-cn-3": ["cn3-jg", "cn3-xgx"],
    "g3s1-cn-4": ["cn3-ndl", "cn3-nla"],
    "g3s1-cn-5": ["cn3-jsd", "cn3-jw"],
    "g3s1-cn-6": ["cn3-hbc", "cn3-xal"],
    "g3s1-cn-7": ["cn3-dzr", "cn3-dsh"],
    "g3s1-cn-8": ["cn3-zq", "cn3-sst"],
    "g3s1-ma-2": ["ma3-hh", "ma3-kh"],
    "g3s1-ma-3": ["ma3-c1", "ma3-cwt"],
    "g3s1-ma-4": ["ma3-sj", "ma3-tjb"],
    "g3s1-ma-5": ["ma3-mm", "ma3-dw"],
    "g3s1-ma-6": ["ma3-py", "ma3-dc"],
    "g3s1-ma-7": ["ma3-ch1", "ma3-ys"],
    "g3s1-ma-8": ["ma3-xdt", "ma3-lb"],
    "g3s1-ma-9": ["ma3-st", "ma3-gc"],
    "g3s1-en-1": ["en3-hi", "en3-abcd"],
    "g3s1-en-2": ["en3-name", "en3-efg"],
    "g3s1-en-3": ["en3-areu", "en3-hijk"],
    "g3s1-en-4": ["en3-this", "en3-lmn"],
    "g3s1-en-5": ["en3-who", "en3-opq"],
    "g3s1-en-6": ["en3-ishe", "en3-rst"],
    "g3s1-en-7": ["en3-hbd", "en3-uvw"],
    "g3s1-en-8": ["en3-ican", "en3-xyz"],
    "g3s1-kx-1": ["kx3-tr", "kx3-bjt"],
    "g3s1-kx-2": ["kx3-gt", "kx3-zt"],
    "g3s1-kx-3": ["kx3-st", "kx3-jy"],
    "g3s1-kx-4": ["kx3-kq", "kx3-kj"],
    "g3s1-kx-5": ["kx3-cl", "kx3-yb"],
    "g3s1-df-1": ["df3-sj", "df3-kn"],
    "g3s1-df-2": ["df3-gc", "df3-bx"],
    "g3s1-df-3": ["df3-yd", "df3-hz"],
    "g3s1-df-4": ["df3-gg", "df3-ss"],
    "g4s1-cn-1": ["cn4-gc", "cn4-fx"],
    "g4s1-cn-2": ["cn4-wd", "cn4-tj"],
    "g4s1-cn-3": ["cn4-psj", "cn4-gcrj"],
    "g4s1-cn-4": ["cn4-pg", "cn4-jw"],
    "g4s1-cn-5": ["cn4-mq", "cn4-qs"],
    "g4s1-cn-6": ["cn4-cc", "cn4-jjy"],
    "g4s1-cn-7": ["cn4-nhe", "cn4-gs"],
    "g4s1-cn-8": ["cn4-jq", "cn4-xx"],
    "g4s1-ma-1": ["ma4-ch2", "ma4-sw"],
    "g4s1-ma-2": ["ma4-zc", "ma4-mj"],
    "g4s1-ma-3": ["ma4-csl", "ma4-bei"],
    "g4s1-ma-4": ["ma4-hh", "ma4-cl"],
    "g4s1-ma-5": ["ma4-ds", "ma4-bj"],
    "g4s1-ma-6": ["ma4-jj", "ma4-c1"],
    "g4s1-en-1": ["en4-km", "en4-sub"],
    "g4s1-en-2": ["en4-day", "en4-clk"],
    "g4s1-en-3": ["en4-wk", "en4-wd"],
    "g4s1-en-4": ["en4-sp", "en4-like"],
    "g4s1-en-5": ["en4-toy", "en4-myt"],
    "g4s1-en-6": ["en4-wt", "en4-wth"],
    "g4s1-en-7": ["en4-ss", "en4-act"],
    "g4s1-en-8": ["en4-wear", "en4-clth"],
    "g4s1-kx-1": ["kx4-fl", "kx4-tz"],
    "g4s1-kx-2": ["kx4-yd", "kx4-km"],
    "g4s1-kx-3": ["kx4-dl", "kx4-gz"],
    "g4s1-kx-4": ["kx4-yy", "kx4-dx"],
    "g4s1-kx-5": ["kx4-jb", "kx4-gt"],
    "g4s1-df-1": ["df4-gy", "df4-gb"],
    "g4s1-df-2": ["df4-tc", "df4-mb"],
    "g4s1-df-3": ["df4-zj", "df4-ys"],
    "g4s1-df-4": ["df4-xf", "df4-gw"],
}

TAGS += CN1_TAGS + MA1_TAGS + KX1_TAGS + DF1_TAGS + CN2_TAGS + MA2_TAGS + KX2_TAGS + DF2_TAGS + CN3_TAGS + MA3_TAGS + EN3_TAGS + KX3_TAGS + DF3_TAGS + CN4_TAGS + MA4_TAGS + EN4_TAGS + KX4_TAGS + DF4_TAGS

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
HAND.update(HAND14)

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
        if unit["id"] in HAND:
            return True
        return unit["subject"] in core_subjects or (
            unit["id"].startswith("g5s1-") and unit["subject"] in g5_extra_subjects)
    for t in SEED["tasks"]:
        if t["subject"] in core_subjects or t["unit_id"] in HAND or t["unit_id"].startswith(("g5s1-kx-", "g5s1-df-")):
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
            "note": "科目级字典 + 单元映射。五上五科与 1–4 年级上册为人工精标，其余自动生成。",
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
