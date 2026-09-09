# 游戏化更新计划书

> 基线：v0.2.0（2026-09-08）。本文回答三个问题：成长系统怎么升级、能不能用奥特曼 / 幻兽帕鲁 / 植物大战僵尸的形象做抽卡、英语单词每日背默怎么接进来。所有设计不违反既有铁律（见 §1.4），不引入新的第三方依赖。

## 0. 结论速览

| 问题 | 结论 | 对应章节 |
|---|---|---|
| 等级和成就太简单，怎么养成化？ | 不动等级和 ledger，加三层：伙伴养成（视觉资产）+ 成就段位（稀有度/进度感）+ 惊喜时刻（抽卡感）| §3 |
| 奥特曼/帕鲁/PvZ 人物能用阳光抽吗？ | **不能直接用**。形象是受版权和商标保护的第三方 IP；换成自创「阳光精灵」体系，孩子自己涂色上传，抽卡照做 | §4 |
| 英语每天背+默写怎么做？ | 新增 words（词库）+ word_progress（档位内存活）两张表，默写判定进孩子端动线，ledger 照旧唯一真相 | §5 |
| 先做哪个？ | 阶段一：成就升级（纯内部增强）；阶段二：阳光精灵抽卡；阶段三：单词模块 | §6 |

## 1. 现状盘点（与代码逐条对得上）

### 1.1 阳光账本

- 入账：`insert_ledger`（`backend/main.py:96`）统一写 `ledger` 表，reason 有 `task` / `daily` / `box` / `milestone` / `family_goal` / `redeem` / `penalty` / `penalty_cancel` / `test`。
- 累计获得 `earned()`（`backend/main.py:262-265`）：`reason NOT IN ('redeem','penalty','penalty_cancel')` —— 消费与扣分都不掉级。
- 余额 `balance()`：全 ledger SUM，兑换走审批两步（`POST /api/redeem` 批准扣款，`backend/main.py:1754` 附近；`POST /api/redeem/{id}/deliver` 兑现，`:1781`）。
- 防重：`completions` 表 `ON CONFLICT DO NOTHING`（`backend/main.py:909` 附近）；盲盒发放用 `kid_settings.box_opened` 游标防重复（`backend/main.py:700-718`）；里程碑用 `milestone_{n}` 标记一次性发放（`maybe_milestone`，`backend/main.py:616-625`）。

### 1.2 等级

- `RANKS` 10 档（0/50/150/350/700/1200/2000/3000/4000/5000，`backend/db.py:41-54`），家庭级可改（`/api/admin/ranks`，`backend/main.py:2091-2125`）。
- `level_info()`（`backend/main.py:283-310`）每次实时算，无等级状态表 —— 这意味着**升级时刻目前没有任何「仪式」**：前端拿到新 level 字符串，最多换个名字。

### 1.3 成就与盲盒（孩子端）

- 20 个成就全部是**纯数值计数**：完成第 N 张卡、坚持 N 天、累计 N 阳光（`ACHIEVEMENTS`，`backend/main.py:630-651`）。`GET /api/achievements`（`backend/main.py:654-694`）实时算 `current >= target`，没有发放记录、没有时间戳、没有稀有度、没有展示态差异 —— 20 个徽章拿到即终点。
- 连击宝箱：`BOX_INTERVAL=3`，每坚持 3 天开一个，随机 +3~+10 阳光（`backend/main.py:700-718`）。期望值约每天 +2，防通胀设计良好，但**只有数值奖励，没有收集物**。

### 1.4 复习队列（weak_points）

- 表：`weak_points(kid_id, unit_id, tag_id, note, status, interval_idx, review_due_at, ...)`（`backend/db.py:699-703`）。
- 档位：`WEAKPOINT_INTERVALS = [1,3,7,14,30]`（`backend/main.py:1877`），`interval_idx` 0-4，pass 升档 / fail 降档 / done 归档（`admin_wp_judge`，`backend/main.py:2050-2081`）。
- 铁律：**复习队列由家长诊断驱动**（家长点亮薄弱考点 `PUT /api/admin/weak-points`，`backend/main.py:1949-1993`），孩子端只看到到期复习项（`GET /api/review-due`，`backend/main.py:2027`）。

### 1.5 系统铁律（新功能必须全部遵守）

1. `ledger` 是阳光唯一真相；所有发放走 `insert_ledger`。
2. 余额不能为负（现有 `redeem` 已有余额校验）。
3. 消费不掉级（`earned()` 的 reason 白名单机制保持）。
4. 复习队列仍是家长诊断驱动，孩子端的单词默写判定**不自动改 weak_points**（见 §5.4 的折中）。
5. 一次性奖励必须防重发（学习 `box_opened` / `milestone_{n}` 的游标模式）。
6. 课程任务只读；新表都挂 `family_id` / `kid_id` 并纳入 RLS（SQLite 单库现状下先字段对齐，PG 模式补 GUC —— `apply_scope`，`backend/db.py:202`）。

## 2. 调研：同类项目怎么做的

> 说明：小红书站内有登录墙，以下「小红书玩法」均为公开二手来源（搜狐/头条转载、模板站说明），已注明；其余为开源项目与维基条目。检索路径：DuckDuckGo `小红书 儿童 打卡 积分 系统 自制`、Sogou `家庭 积分银行 孩子 奖励 制度`、`小红书 任务 打卡 程序 自制 开发` 等，2026-09-09 抓取。

### 2.1 小红书系：手工积分卡 / 奖励卡（二手来源）

来源：搜狐号「玩子今天玩什么」《手工积分卡丨手工奖励卡丨助攻娃养成好习惯~》 https://www.sohu.com/a/742232759_121856877 （作者自述「看到小红书上有些宝妈想要资源」—— 即小红书同款玩法的公开转载）。

机制拆解：
- 涂色积分卡：完成一次任务涂一颗星，整张 20 颗涂满**解锁一次抽奖励卡**。
- 分值积分卡：按任务难度设 1/2/3 分，满 20 分抽一次。
- 奖励卡是「券」体系：糖果券、奶茶券、电影券、野餐券、**免唠叨券、免家务券、一日主人券、万能券**。
- 心理依据（原文）：积极强化 + 抽盲盒的随机惊喜「孩子别提有多喜欢了」。

对本项目的启发：**「积分攒满 → 抽一张券」是家长圈验证过的最强动线**，且奖励卡内容=家庭特权而非商品，几乎零成本。我们已有 rewards 商店（审批兑换），缺的正是「抽」的动作和「券」的形态。

### 2.2 小红书系：家庭积分银行 / 自律表（二手来源）

来源：搜狐《寒假儿童自律新法：用家庭积分激发孩子的内在动力》 https://www.sohu.com/a/855682289_121956424 （Sogou 检索「家庭 积分银行 孩子 奖励 制度」首条，为头条号文章转载）。

机制拆解（原文「六步法」）：
1. 家长与孩子**共同制定**行为标准（参与感）；
2. 挖掘内心需求，物质+精神双轨奖励；
3. 前两周坚持期重点陪跑，及时反馈；
4. **兑现要有仪式感**：小庆祝、颁奖时刻；
5. 定期回顾积分本，调整标准；
6. 奖励从物质逐渐过渡到精神（家庭活动优先权、亲子时间）。

对本项目的启发：仪式感（第 4 步）正是我们升级等级时缺失的；「共同制定」（第 1 步）对应家长端已有的自定义任务，可加「和孩子一起选精灵/起名」的仪式。

### 2.3 Habitica（RPG 任务管理，开源）

来源：Wikipedia: Habitica https://en.wikipedia.org/wiki/Habitica ；官网 https://habitica.com 。

- 机制：RPG 化任务管理 —— 完成现实任务得经验+金币，升级回血；负向习惯掉血；长期习惯会随坚持「变绿」，荒废「变红」。装备、宠物、头像驱动收集欲。
- 验证点：任务=数值+视觉资产双反馈；正向行为的视觉状态变化（绿→红）被大量用户认可。
- 启发：**升级要有可视资产**（装备/宠物/伙伴），等级名只是文本。伙伴的「成长阶段」可以直接复用现有 streak 数据。

### 2.4 ClassDojo（课堂行为积分，全球教师使用）

来源：Wikipedia: ClassDojo https://en.wikipedia.org/wiki/ClassDojo 。

- 机制：教师即时加减分（Dojo Points），怪物头像（每生一个可定制小怪物）作为身份资产；家校共享流。
- 启发：**每个孩子一个专属拟人形象**是低龄段被反复验证的粘性来源；我们多娃场景下，精灵=孩子身份卡。

### 2.5 KidPoints（开源，家庭积分系统，中文）

来源：GitHub https://github.com/cwjcw/KidPoints （描述：儿童行为激励系统，支持触摸屏打卡、微信小程序查看、家长后台管理，全栈 Python，低成本部署）。

- 与本项目定位最接近的国内开源参照。启发：触摸屏一键打卡、家长后台、低成本自部署 —— 我们已全部具备，说明方向对；其未做的成就/收集层正是我们的机会。

### 2.6 eastondev 习惯积分表（在线模板工具）

来源：https://eastondev.com/habit-tracker/zh/ （站点 meta：22+ 打卡表模板、80+ 预设习惯、19 个系列化培养计划，面向 3-12 岁）。

- 机制：打印导向的习惯表+系列化计划（刷牙系列、阅读系列…）。
- 启发：**系列化/主题化**的成套任务比散任务更有「集齐」冲动 —— 对应「精灵图鉴按主题分系列」。

### 2.7 抽卡合规基线（为 §4 定规矩）

- 中国文化部 2016 年 12 月公告：2017 年 5 月起网络游戏出版运营者须公示虚拟物品「抽取概率」（Wikipedia: Loot box § China https://en.wikipedia.org/wiki/Loot_box ）。
- 2019 年 11 月起，国家新闻出版署要求：不得向 8 周岁以下用户付费抽卡；8-16 岁单次/每月消费受限（同上条目引 GAPP 通知）。
- 本项目**阳光不可充值购买**，孩子侧无任何真实货币入口，天然规避付费抽卡监管；但「概率对家长透明」仍应做（家长端展示概率表），既是合规习惯也是家长信任基础。

## 2. 调研：同类项目怎么做的

> 说明：小红书站内有登录墙，以下「小红书玩法」均为公开二手来源（搜狐/头条转载、模板站说明），已注明；其余为开源项目与维基条目。检索路径：DuckDuckGo `小红书 儿童 打卡 积分 系统 自制`、Sogou `家庭 积分银行 孩子 奖励 制度`、`小红书 任务 打卡 程序 自制 开发` 等，2026-09-09 抓取。

### 2.1 小红书系：手工积分卡 / 奖励卡（二手来源）

来源：搜狐号「玩子今天玩什么」《手工积分卡丨手工奖励卡丨助攻娃养成好习惯~》 https://www.sohu.com/a/742232759_121856877 （作者自述「看到小红书上有些宝妈想要资源」—— 即小红书同款玩法的公开转载）。

机制拆解：
- 涂色积分卡：完成一次任务涂一颗星，整张 20 颗涂满**解锁一次抽奖励卡**。
- 分值积分卡：按任务难度设 1/2/3 分，满 20 分抽一次。
- 奖励卡是「券」体系：糖果券、奶茶券、电影券、野餐券、**免唠叨券、免家务券、一日主人券、万能券**。
- 心理依据（原文）：积极强化 + 抽盲盒的随机惊喜「孩子别提有多喜欢了」。

对本项目的启发：**「积分攒满 → 抽一张券」是家长圈验证过的最强动线**，且奖励卡内容=家庭特权而非商品，几乎零成本。我们已有 rewards 商店（审批兑换），缺的正是「抽」的动作和「券」的形态。

### 2.2 小红书系：家庭积分银行 / 自律表（二手来源）

来源：搜狐《寒假儿童自律新法：用家庭积分激发孩子的内在动力》 https://www.sohu.com/a/855682289_121956424 （Sogou 检索「家庭 积分银行 孩子 奖励 制度」首条，为头条号文章转载）。

机制拆解（原文「六步法」）：
1. 家长与孩子**共同制定**行为标准（参与感）；
2. 挖掘内心需求，物质+精神双轨奖励；
3. 前两周坚持期重点陪跑，及时反馈；
4. **兑现要有仪式感**：小庆祝、颁奖时刻；
5. 定期回顾积分本，调整标准；
6. 奖励从物质逐渐过渡到精神（家庭活动优先权、亲子时间）。

对本项目的启发：仪式感（第 4 步）正是我们升级等级时缺失的；「共同制定」（第 1 步）对应家长端已有的自定义任务，可加「和孩子一起选精灵/起名」的仪式。

### 2.3 Habitica（RPG 任务管理，开源）

来源：Wikipedia: Habitica https://en.wikipedia.org/wiki/Habitica ；官网 https://habitica.com 。

- 机制：RPG 化任务管理 —— 完成现实任务得经验+金币，升级回血；负向习惯掉血；长期习惯会随坚持「变绿」，荒废「变红」。装备、宠物、头像驱动收集欲。
- 验证点：任务=数值+视觉资产双反馈；正向行为的视觉状态变化（绿→红）被大量用户认可。
- 启发：**升级要有可视资产**（装备/宠物/伙伴），等级名只是文本。伙伴的「成长阶段」可以直接复用现有 streak 数据。

### 2.4 ClassDojo（课堂行为积分，全球教师使用）

来源：Wikipedia: ClassDojo https://en.wikipedia.org/wiki/ClassDojo 。

- 机制：教师即时加减分（Dojo Points），怪物头像（每生一个可定制小怪物）作为身份资产；家校共享流。
- 启发：**每个孩子一个专属拟人形象**是低龄段被反复验证的粘性来源；我们多娃场景下，精灵=孩子身份卡。

### 2.5 KidPoints（开源，家庭积分系统，中文）

来源：GitHub https://github.com/cwjcw/KidPoints （描述：儿童行为激励系统，支持触摸屏打卡、微信小程序查看、家长后台管理，全栈 Python，低成本部署）。

- 与本项目定位最接近的国内开源参照。启发：触摸屏一键打卡、家长后台、低成本自部署 —— 我们已全部具备，说明方向对；其未做的成就/收集层正是我们的机会。

### 2.6 eastondev 习惯积分表（在线模板工具）

来源：https://eastondev.com/habit-tracker/zh/ （站点 meta：22+ 打卡表模板、80+ 预设习惯、19 个系列化培养计划，面向 3-12 岁）。

- 机制：打印导向的习惯表+系列化计划（刷牙系列、阅读系列…）。
- 启发：**系列化/主题化**的成套任务比散任务更有「集齐」冲动 —— 对应我们的「精灵图鉴按主题分系列」。

### 2.7 抽卡合规基线（为 §4 定规矩）

- 中国文化部 2016 年 12 月公告：2017 年 5 月起网络游戏出版运营者须公示虚拟物品「抽取概率」（Wikipedia: Loot box § China https://en.wikipedia.org/wiki/Loot_box ）。
- 2019 年 11 月起，国家新闻出版署要求：不得向 8 周岁以下用户付费抽卡；8-16 岁单次/每月消费受限（同上条目引 GAPP 通知）。
- 本项目**阳光不可充值购买**，孩子侧无任何真实货币入口，天然规避付费抽卡监管；但「概率对家长透明」仍应做（家长端展示概率表），既是合规习惯也是家长信任基础。

## 3. 方向一：养成系统升级（不碰 ledger 与等级规则）

### 3.1 设计原则

1. 数值层（阳光/等级）不动 —— ledger、earned、balance、RANKS 全部保持现状，`level_info()` 不改。
2. 新增的都是「视觉资产层」和「进度仪式层」：徽章稀有度、伙伴养成、升级时刻动效。
3. 家长可见、可控、可关闭（参照 `penalty_enabled` 的开关模式，`families` 表加列 + 迁移）。

### 3.2 成就段位与稀有度（阶段一）

#### 3.2.1 问题诊断：现有成就的三个痛点

当前 20 个成就（`backend/main.py:630-651`）存在以下问题：

1. **无差异感**：`first`（第一张卡）和 `sun5000`（累计 5000 阳光）视觉上除了图标不同，没有任何「这个更厉害」的区分 —— 孩子拿到后无法感知自己跨越了里程碑还是只是日常完成。
2. **终点即终点**：拿到徽章后无后续（`current >= target` 立即终止计数），没有「继续努力」的动力 —— `sun500 → sun2000 → sun5000` 三个是独立徽章，孩子不知道这是同一条成长线的三段。
3. **无惊喜时刻**：实时计算（`GET /api/achievements` 每次算一遍），没有「获得时刻」的记录 —— 孩子看到进度从 499/500 变成 500/500，最多前端换个勾，没有庆祝动画、没有「新」角标、刷新页面后也不知道这是刚拿的还是上周拿的。

Habitica 的徽章有颜色边框区分稀有度，ClassDojo 的成就有「刚获得」的闪烁提示，小红书家长圈的涂色积分卡有「涂满一张」的仪式感 —— 我们当前三者都缺。

#### 3.2.2 设计方案：四档稀有度 + 段位链 + 获得时刻

##### （1）数据模型（迁移 `028_achievement_earned`）

```sql
-- 发放记录：拿到徽章的时刻 + 是否已看
CREATE TABLE achievement_earned (
  kid_id TEXT NOT NULL,
  ach_id TEXT NOT NULL,
  earned_at TEXT NOT NULL,       -- ISO 8601 时间戳（孩子端展示「3 天前获得」）
  seen INTEGER NOT NULL DEFAULT 0, -- 0=未看过「新徽章」动画，1=已看
  PRIMARY KEY (kid_id, ach_id)
);
CREATE INDEX idx_ae_kid_seen ON achievement_earned(kid_id, seen); -- 快速查「有几个新徽章」

-- 稀有度、tier、series 等静态属性直接写在 ACHIEVEMENTS 定义里（Python list），不入库
```

防重机制：`INSERT OR IGNORE` —— 达标时后端写一次，重复调用无副作用（学习 `completions` 表的 `ON CONFLICT DO NOTHING` 模式）。

##### （2）升级 ACHIEVEMENTS 定义（`backend/main.py:630-651`）

每个成就增加三个新字段：

```python
ACHIEVEMENTS = [
    {
        "id": "first", "icon": "sprout", 
        "name": "初来乍到", "desc": "完成第 1 张任务卡", 
        "target": 1,
        "rarity": "bronze",  # 新增：bronze/silver/gold/legend
        "series": "milestone",  # 新增：同系列成就归类展示（里程碑/学科/坚持/阳光）
        "tier": None  # 新增：段位链 ID（None=独立徽章）
    },
    # ... 现有 20 个改造 ...
    {
        "id": "sun500", "icon": "coins",
        "name": "阳光新手", "desc": "累计获得 500 阳光",
        "target": 500,
        "rarity": "silver",
        "series": "wealth",
        "tier": "sun"  # 与 sun2000/sun5000 同属「阳光段位」
    },
    {
        "id": "sun2000", "icon": "gem",
        "name": "阳光大师", "desc": "累计获得 2000 阳光",
        "target": 2000,
        "rarity": "gold",
        "series": "wealth",
        "tier": "sun"
    },
    {
        "id": "sun5000", "icon": "crown",
        "name": "阳光传说", "desc": "累计获得 5000 阳光",
        "target": 5000,
        "rarity": "legend",
        "series": "wealth",
        "tier": "sun"
    },
    # ... 新增徽章见 3.2.3 ...
]
```

**稀有度分配原则**（让孩子「一眼看出难度」）：
- **bronze（青铜，60%）**：日常可得（`first`、`cn10`、`streak7`、`shop1`、`box5` 等 12 个）
- **silver（白银，25%）**：需要一定积累（`all100`、`daily30`、`streak14`、`sun500` 等 5 个）
- **gold（黄金，12%）**：中期挑战（`streak30`、`sun2000`、`custom10` 等 2 个）
- **legend（传说，3%）**：长期目标（`sun5000`，后续加「全年全勤 365 天」等 1 个）

**段位链（tier）**设计：
- 同 tier 的徽章显示在同一条「段位轨道」上（视觉上是 3 格横向进度条，而非 3 个散落的圆形徽章）。
- 当前有 3 条天然段位链：
  - `sun`（阳光）：500 → 2000 → 5000
  - `streak`（坚持）：7 → 14 → 30 天
  - `subject`（学科）：cn10/ma10/en10 → 各 50 → 各 100（新增后两档）
- 其余徽章 `tier=None`，独立展示。

##### （3）后端 API 改动（`backend/main.py`）

**A. 修改 `GET /api/achievements` 返回结构**（`main.py:654-694`）

现有逻辑：
```python
def achievements():
    # ... 实时计算 current ...
    return [{"id": a["id"], "name": a["name"], ..., "current": c, "unlocked": c >= a["target"]}]
```

改为：
```python
def achievements():
    kid = get_kid()
    # 1. 查询已获得记录（一次查完，避免循环查询）
    earned_map = {}  # {ach_id: {"earned_at": "2026-09-09T10:23:00", "seen": 0}}
    rows = db.execute(
        "SELECT ach_id, earned_at, seen FROM achievement_earned WHERE kid_id=?", 
        (kid,)
    ).fetchall()
    for r in rows:
        earned_map[r[0]] = {"earned_at": r[1], "seen": r[2]}
    
    # 2. 遍历 ACHIEVEMENTS，计算 current + 判断是否首次达标
    result = []
    for ach in ACHIEVEMENTS:
        current = _calc_ach_current(kid, ach)  # 抽出现有计算逻辑为子函数
        unlocked = current >= ach["target"]
        
        # 首次达标且未记录 -> 写入 achievement_earned（幂等）
        if unlocked and ach["id"] not in earned_map:
            now = datetime.utcnow().isoformat()
            db.execute(
                "INSERT OR IGNORE INTO achievement_earned (kid_id, ach_id, earned_at, seen) VALUES (?,?,?,0)",
                (kid, ach["id"], now)
            )
            db.commit()
            earned_map[ach["id"]] = {"earned_at": now, "seen": 0}
        
        # 3. 组装返回（新增字段：rarity、series、tier、earned_at、seen、chain_progress）
        item = {
            "id": ach["id"],
            "name": ach["name"],
            "desc": ach["desc"],
            "icon": ach["icon"],
            "target": ach["target"],
            "current": current,
            "unlocked": unlocked,
            # --- 新增 ---
            "rarity": ach["rarity"],
            "series": ach["series"],
            "tier": ach.get("tier"),
            "earned_at": earned_map.get(ach["id"], {}).get("earned_at"),  # None 表示未获得
            "seen": earned_map.get(ach["id"], {}).get("seen", 1),  # 默认 1 避免前端误判
        }
        
        # 段位进度：同 tier 中拿了几个/总共几个（前端显示「2/3 段」）
        if ach.get("tier"):
            tier_achs = [a for a in ACHIEVEMENTS if a.get("tier") == ach["tier"]]
            tier_unlocked = sum(1 for a in tier_achs if a["id"] in earned_map)
            item["chain_progress"] = f"{tier_unlocked}/{len(tier_achs)}"
        else:
            item["chain_progress"] = None
        
        result.append(item)
    
    return result
```

**B. 新增 `POST /api/achievements/{ach_id}/mark-seen`**

孩子端点开「新徽章」弹窗后调用，将 `seen` 置 1（幂等）：

```python
@app.post("/api/achievements/{ach_id}/mark-seen")
def mark_achievement_seen(ach_id: str):
    kid = get_kid()
    db.execute(
        "UPDATE achievement_earned SET seen=1 WHERE kid_id=? AND ach_id=?",
        (kid, ach_id)
    )
    db.commit()
    return {"ok": True}
```

##### （4）前端展示改造（`frontend/src/App.vue`）

**A. 成就墙布局**（现有「成就」tab，约 `App.vue:1200` 附近）

改为分系列折叠展示（学习手风琴，复用现有 `details` 标签）：

```vue
<section v-if="view==='achievements'">
  <h2>成就墙 <span v-if="newAchCount>0" class="badge">{{ newAchCount }} 个新</span></h2>
  
  <!-- 按 series 分组 -->
  <details v-for="(achs, series) in achBySeries" :key="series" open>
    <summary>{{ seriesName[series] }} ({{ achs.filter(a=>a.unlocked).length }}/{{ achs.length }})</summary>
    
    <!-- 段位链：横向 3 格 -->
    <div v-for="tier in uniqueTiers(achs)" :key="tier" class="tier-track">
      <div v-for="ach in achs.filter(a=>a.tier===tier)" :key="ach.id" 
           :class="['ach-badge', ach.rarity, {unlocked: ach.unlocked, new: !ach.seen}]"
           @click="openAchDetail(ach)">
        <icon :name="ach.icon" />
        <span class="ach-name">{{ ach.name }}</span>
        <span v-if="!ach.seen" class="new-dot">NEW</span>
      </div>
      <span class="tier-progress">{{ achs.find(a=>a.tier===tier).chain_progress }}</span>
    </div>
    
    <!-- 独立徽章：平铺 -->
    <div class="ach-grid">
      <div v-for="ach in achs.filter(a=>!a.tier)" :key="ach.id"
           :class="['ach-badge', ach.rarity, {unlocked: ach.unlocked, new: !ach.seen}]"
           @click="openAchDetail(ach)">
        <icon :name="ach.icon" />
        <span>{{ ach.name }}</span>
        <progress :value="ach.current" :max="ach.target"></progress>
        <span v-if="!ach.seen" class="new-dot">NEW</span>
      </div>
    </div>
  </details>
</section>
```

**B. 稀有度配色**（新增 CSS，复用现有颜色变量）

```css
.ach-badge.bronze { border: 2px solid var(--surface-3); }
.ach-badge.silver { border: 2px solid #c0c0c0; box-shadow: 0 0 8px rgba(192,192,192,0.5); }
.ach-badge.gold   { border: 2px solid var(--warm); box-shadow: 0 0 12px rgba(255,193,7,0.6); }
.ach-badge.legend { 
  border: 2px solid #9c27b0; 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 0 16px rgba(156,39,176,0.8);
  animation: glow 2s ease-in-out infinite;
}
@keyframes glow {
  0%, 100% { box-shadow: 0 0 16px rgba(156,39,176,0.8); }
  50% { box-shadow: 0 0 24px rgba(156,39,176,1); }
}

.ach-badge.new .new-dot {
  position: absolute; top: -5px; right: -5px;
  background: var(--warn); color: white;
  padding: 2px 6px; border-radius: 8px; font-size: 0.7em;
  animation: pulse 1s ease-in-out infinite;
}
```

**C. 获得时刻弹窗**（点开徽章 or 首次解锁）

```vue
<div v-if="achModal" class="modal" @click.self="closeAchModal">
  <div :class="['ach-detail', achModal.rarity]">
    <icon :name="achModal.icon" size="64" />
    <h3>{{ achModal.name }}</h3>
    <p>{{ achModal.desc }}</p>
    <p class="rarity-label">{{ rarityLabel[achModal.rarity] }}</p>
    <p v-if="achModal.earned_at" class="earned-time">{{ timeAgo(achModal.earned_at) }} 获得</p>
    <button @click="closeAchModal">关闭</button>
  </div>
</div>
```

首次解锁时（`!seen`），自动弹窗 + 播放撒花动画（纯 CSS `confetti` keyframe，参考现有 transitions），关闭时调 `mark-seen`。

##### （5）新增徽章（利用现有数据，无需新表）

| id | name | desc | target | rarity | series | tier | 数据来源 |
|---|---|---|---|---|---|---|---|
| early_bird | 早鸟 | 连续 7 天早 8 点前完成每日任务 | 7 | silver | habit | None | `completions` JOIN `checkins` WHERE `hour(completed_at) < 8` |
| review_pro | 复习达人 | 本周复习判定 pass ≥ 5 次 | 5 | bronze | study | None | `weak_points` WHERE `status='pass'` 本周计数 |
| word_debut | 单词首秀 | 第一次完成每日背默 | 1 | bronze | study | None | `word_daily` 存在记录（§5 联动）|
| perfect_week | 满分一周 | 连续 7 天每日任务全打卡 | 7 | gold | habit | None | `checkins` 连续 7 天 `completed=all` |
| streak60 | 坚持两月 | 连续坚持 60 天 | 60 | legend | habit | streak | 与现有 7/14/30 组成四段链 |

新增后总计 **25 个成就**（bronze 14、silver 6、gold 3、legend 2），稀有度分布符合金字塔。

#### 3.2.3 实施检查清单

- [ ] 迁移 `028_achievement_earned.sql` 通过（`python3 backend/db.py` 无报错）
- [ ] ACHIEVEMENTS 定义增加 rarity/series/tier 三字段（20 个现有 + 5 个新增）
- [ ] `GET /api/achievements` 返回新增字段（earned_at、seen、chain_progress）
- [ ] `POST /api/achievements/{id}/mark-seen` 端点实现
- [ ] 前端成就墙改为系列折叠 + 段位轨道布局
- [ ] 稀有度 CSS 四档配色（bronze/silver/gold/legend）
- [ ] 「新徽章」角标与弹窗动画
- [ ] **测试用例**（`backend/test_kids.py`）：
  - `test_achievement_earned_idempotent()`：重复达标不重复写记录
  - `test_achievement_seen_toggle()`：seen 置 1 幂等
  - `test_achievement_chain_progress()`：段位链进度计算正确（sun 1/3 → 2/3 → 3/3）
  - `test_new_achievements_query()`：`seen=0` 过滤返回正确数量
- [ ] **防回退断言**：`earned()` 计算不受新表影响、现有 24 个测试全绿

#### 3.2.4 为什么这样设计（决策依据）

1. **为什么不用数值分（1 分/5 分/10 分）表示难度？** —— 儿童对「青铜/白银/黄金/传说」的认知来自卡牌游戏与等级勋章（学校奖状也有铜银金），颜色+光效比数字更直观。
2. **为什么 tier 只做 3 条链？** —— 避免「全是段位」的疲劳感；大多数成就仍是独立里程碑（符合现实：不是所有目标都有进阶版）。
3. **为什么 earned_at 存 ISO 时间而非时间戳？** —— 前端展示「3 天前」需要日期运算，ISO 字符串可直接 `new Date()` 解析，且人眼可读（调试友好）。
4. **为什么 seen 默认 0 而非 1？** —— 新徽章必须明确「看过」才消角标，防止网络中断导致的「一直有角标」bug（保守策略：宁可重复提示，不可遗漏）。
5. **为什么不把 rarity 存数据库？** —— 稀有度是设计决策而非用户数据（家长不能改某个徽章的稀有度），写在代码里版本管理更清晰，且减少一张配置表。

### 3.3 伙伴养成「阳光精灵」（阶段二，见 §4）

等级之外的第二条成长线：精灵有阶段（蛋 → 幼年 → 成年），阶段由**累计 earned** 阈值驱动（只读，不发阳光，天然不破坏铁律），进化时刻做全屏庆祝。

### 3.4 升级仪式（小改动，大感知）

`level_info()` 返回的 `level` 变化时（前端对比上次 level_id），孩子端播放「升级时刻」：当前等级图标 → 新等级图标 + 撒阳光粒子（纯 CSS keyframes，几十行）。数据不动，纯前端。

## 4. 方向二：抽卡——IP 风险与替代方案

### 4.1 直接用奥特曼 / 幻兽帕鲁 / 植物大战僵尸？——不可以

三个 IP 的权利状态（公开资料，2026-09-09 查证）：

| IP | 权利方 | 关键事实 | 来源 |
|---|---|---|---|
| 奥特曼 | 圆谷制作（Tsuburaya Productions） | 长期在全球积极维权：2006 年曾就奥特曼形象著作权把争议方诉至法院，案件进入中国，北京法院为此成立「奥特曼著作权研究组」；系列在中国由权利方持续授权管理 | https://en.wikipedia.org/wiki/Ultraman |
| 幻兽帕鲁 | Pocketpair（被告）/ 任天堂·宝可梦公司（原告） | 2024-09-18 任天堂与宝可梦公司在东京地方法院对 Pocketpair 提起**专利侵权**诉讼（指其「在虚拟场地捕捉生物」机制），索赔并申请禁令；Pocketpair 随后修改了游戏内类似机制 | https://en.wikipedia.org/wiki/Palworld |
| 植物大战僵尸 | 宝开（PopCap）/ EA | 2009 年宝开发行、后被 EA 收购扩展为系列（漫画、网剧等） | https://en.wikipedia.org/wiki/Plants_vs._Zombies |

结论：
1. **形象直接入库 = 必须删除项。** 哪怕自用，APK 已通过 GitHub Releases 公开分发（README 记载），公开分发显著放大侵权风险；任天堂对「机制相似」都起诉，对形象相似的维权强度只会更高。
2. 「致敬风格」（自绘一张银红色超人、豌豆射手造型的原创角色）同样有**实质性相似**风险，且孩子端无法区分「我们画得像」和「我们获得了授权」，长期形成错误示范。
3. 本项目对外可传播（FAMILY.md 写明给其他家庭用），任何侵权素材都会把整个仓库置于下架风险。

### 4.2 替代方案：「阳光精灵」自创 IP 体系

设计要点（孩子感兴趣的「收集+进化+对战感」全部保留，IP 归零）：

1. **让孩子成为创作者**：精灵底稿由本项目提供 12 个自创线稿主题（元素系：日光/水滴/绿叶/岩石…），孩子**自己涂色**（平板画板或纸绘拍照上传），命名、写一句「技能描述」。这一步直接借力孩子对奥特曼/帕鲁的热爱 —— 他们爱的不是某个商标，是「我有一只很酷的、我说了算的怪物」。上传图存静态目录（前端 `public/uploads/`），后端只存路径与元数据（`families`/`kids` 维度隔离）。
2. **抽卡获得的是「蛋」**：单抽 30 阳光 / 十连 270 阳光（9 折），消耗走 ledger 新 reason `gacha`（负 delta，**加入 earned() 白名单排除项**，与 redeem 同等待遇 → 消费不掉级，天然合规铁律 3）。
3. **概率家长透明**：普通 70% / 稀有 25% / 传说 5%，家长端「抽卡设置」页明示并**可调**；孩子端也展示（合规习惯从第一版养成）。保底：30 抽内必出稀有以上（pity 计数器存 kid_settings，复用 `box_opened` 模式）。
4. **重复转化**：抽到重复精灵自动转「星尘」，星尘可给已有精灵升星（1→3 星），把「抽歪了」的挫败感转成进度感 —— 这是儿童 gacha 与成人 gacha 最大的差异点（儿童产品要减少挫败）。
5. **精灵不参与任何对战数值**：没有属性克制、没有胜负，避免「为赢而抽」的赌博化心理；精灵只提供：图鉴收集、进化视觉、成就联动（集齐某系列 3 只 → 徽章）。学习任务与精灵强度**零挂钩**，防止「不学习就打不过」的负反馈。
6. 进化消耗 earned 阈值而非阳光余额（不可「氪」进度）。

数据模型（迁移 `029_sprites`，全部 family_id 隔离）：

```sql
CREATE TABLE sprite_defs (          -- 12 主题底稿，全局只读种子
  id TEXT PRIMARY KEY, series TEXT NOT NULL,  -- 系列：element/plant/tech...
  name TEXT NOT NULL, base_art TEXT NOT NULL  -- 线稿路径
);
CREATE TABLE kid_sprites (          -- 孩子的收藏实例
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id TEXT NOT NULL, family_id TEXT NOT NULL,
  def_id TEXT NOT NULL,
  nickname TEXT DEFAULT '',          -- 孩子命名
  art_url TEXT DEFAULT '',           -- 涂色上传路径（空=用底稿）
  stars INTEGER NOT NULL DEFAULT 1,  -- 1-3
  hatched INTEGER NOT NULL DEFAULT 0, -- 蛋/已孵化
  dust_source INTEGER DEFAULT 0,     -- 重复转化的星尘来源
  obtained_at TEXT NOT NULL
);
CREATE TABLE gacha_draws (           -- 每次抽取留痕（概率可审计）
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id TEXT NOT NULL, family_id TEXT NOT NULL,
  cost INTEGER NOT NULL, pity INTEGER NOT NULL,  -- 抽时的保底计数
  result_def_id TEXT NOT NULL, created_at TEXT NOT NULL
);
```

API（后端 3 个端点，家长端 1 个）：

| 端点 | 说明 |
|---|---|
| `GET /api/sprites` | 图鉴：全 defs + 我的收藏（kid_sprites JOIN）+ 星尘余额 + 当前 pity |
| `POST /api/gacha` | body `{ count: 1\|10 }`：校验余额 → 写 gacha_draws + kid_sprites（重复转星尘）→ `insert_ledger(-cost, 'gacha', ref=gacha-{id})` → 返回开蛋动画所需数据 |
| `POST /api/sprites/{id}/customize` | 改名/传涂色图（图片走现有上传通道白名单，仅 png/jpg ≤2MB）|
| `GET/PUT /api/admin/gacha-config` | 家长：概率、价格、保底、总开关（默认关，参照 penalty_enabled 模式）|

防通胀核算：单抽 30 阳光 ≈ 5 张任务卡或 3 天正常产出。十连 270 需约 2 周积累，且每月十连上限 2 次（kid_settings 计数），杜绝「攒一个月阳光一天抽完」的空虚感。

## 5. 方向三：英语单词每日背 + 默写

### 5.1 数据模型（迁移 `030_words`）

```sql
CREATE TABLE word_books (           -- 词书：教材单元词表 / 家长自建
  id TEXT PRIMARY KEY, family_id TEXT,  -- NULL=系统内置（译林五上按 Unit）
  name TEXT NOT NULL, unit_id TEXT       -- 对齐既有 units 表的教材单元
);
CREATE TABLE words (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id TEXT NOT NULL,
  word TEXT NOT NULL, cn TEXT NOT NULL,   -- 释义
  ipa TEXT DEFAULT '',                    -- 音标（可选）
  sort INTEGER DEFAULT 0,
  UNIQUE(book_id, word)
);
CREATE TABLE word_progress (         -- 每娃每词的 SRS 状态
  kid_id TEXT NOT NULL, word_id TEXT NOT NULL,
  interval_idx INTEGER NOT NULL DEFAULT 0,  -- 复用 1/3/7/14/30 五档（见下）
  rep INTEGER NOT NULL DEFAULT 0,           -- 连续答对次数（SM-2 的 n）
  due TEXT,                                 -- 到期日 YYYY-MM-DD
  wrong_count INTEGER DEFAULT 0,            -- 默错次数
  last_result TEXT DEFAULT '',               -- last 记录见/默
  PRIMARY KEY (kid_id, word_id)
);
CREATE TABLE word_daily (            -- 每日背默记录（防重+统计）
  kid_id TEXT NOT NULL, date TEXT NOT NULL,
  new_count INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0,
  dict_right INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0, -- 认读对/默写错
  PRIMARY KEY (kid_id, date)
);
```

**SRS 算法选型：固定五档 Leitner，不引入 SM-2/FSRS 依赖。** 理由：
- `WEAKPOINT_INTERVALS = [1,3,7,14,30]`（`backend/main.py:1877`）就是 Leitner 盒子变体，孩子端已有此心智模型（复习轮次），两套间隔系统会让家长困惑；
- SM-2（EF 初始 2.5、`I←round(I×EF)`，Wikipedia: SuperMemo https://en.wikipedia.org/wiki/SuperMemo）对儿童场景收益有限：儿童词表量小（一学期约 150 词）、判断粒度粗（对/错二元），EF 浮点调参是过度工程；
- FSRS（开源 https://github.com/open-spaced-repetition/py-fsrs ）需训练个人参数，家庭单娃数据量不支持。
- 升级路径留好：`word_progress` 的 `rep` 字段就是为将来换 SM-2 预留的连续答对计数，不需要现在用。

每日调度（服务端算，前端零逻辑）：
- 新词 = `due IS NULL` 且未在 `word_daily` 出现过，按 `sort` 取家长设定的 `new_per_day`（默认 5，译林 5A 约 150 词 ÷ 一学期 ≈ 每天自然消化）；
- 复习 = `due <= today`；
- 参照百词斩「选词典 → 定计划 → 每日打卡」动线（Wikipedia: 百词斩 https://zh.wikipedia.org/wiki/百词斩 ：选词典、定每日量、PK）与主流 SRS 产品的「新学+复习混排」惯例。

### 5.2 API 设计

| 端点 | 谁用 | 说明 |
|---|---|---|
| `GET /api/words/today` | 孩子 | `{ new: [...], review: [...] }`：当日队列（新词+到期复习），含中文释义、音标 |
| `POST /api/words/study` | 孩子 | body `{ word_id, known: bool }`：背认环节「认识/不认识」，不判定，只推进队列（known=false 立即再次出现）|
| `POST /api/words/spell` | 孩子 | body `{ word_id, text: "a-p-p-l-e" }`：默写判定。对 → `interval_idx+1`（封顶 4）、`due=INTERVALS[idx]`、`rep+1`；错 → 归零 `interval_idx=0`、`due=明天`、`wrong_count+1`、**写 ledger（见 5.3）** |
| `POST /api/words/done` | 孩子 | 结束今日背默：写 `word_daily`，发一次「今日背默完成」阳光（见 5.3）|
| `GET /api/admin/word-config` | 家长 | 每日新词数、每日默写词数、背默阳光、开关 |
| `PUT /api/admin/word-config` | 家长 | 同上修改（家庭级，families 表列 or settings）|
| `GET /api/admin/words?book=` | 家长 | 词表管理：看/加/删/导入 |
| `POST /api/admin/words/import` | 家长 | body `{ book_id, text }`：粘贴 `word<TAB>中文` 每行一条，或 CSV；上限 500 行/次 |

默写输入：孩子端按现有移动优先样式做逐字母输入框（参照 App.vue 现有表单风格，无新依赖）；对三年级以上可用键盘直接输入。防作弊不在本期（家长在旁是产品基本假设，与现有任务打卡一致）。

### 5.3 阳光规则衔接（不破坏 ledger 铁律）

1. **每日背默完成**：`POST /api/words/done` 首次调用发固定 X 阳光（默认 3，家长可调 0-10），ledger reason=`word_daily`，ref=`wd-{kid}-{date}` —— **日期做 ref 的一部分天然防重**（比 box 的游标更简单），同日二次调用返回已有结果不发。
2. **默写全对奖励**：当日 `review+new` 全部 `last_result='right'` 额外 +2（ref=`wd-perfect-{kid}-{date}`，同样幂等）。
3. **不发/不扣**：不认识、默错**不扣分**（扣分=penalty 域，家长专属），错词只是明天再见 —— 与「扣分默认关」的产品哲学一致。
4. `word_daily` 是正收入，不需要进 `earned()` 排除名单（如果 §4 已实施 gacha，同一迁移里把 `gacha` 加入排除）。

### 5.4 与复习队列（weak_points）的关系 —— 分开但可见

关键决策：**单词默错不自动写 weak_points**。理由：
- weak_points 的 tag 体系挂教材单元知识点（`knowledge_tags`），单词粒度不同；
- 铁律 4：诊断权在家长 —— 自动把 20 个默错词塞进复习队列会打破「家长决定练什么」；
- 单词自身有 SRS 档位，再进复习队列 = 双重排期，孩子端混乱。

替代（家长仍一眼看到问题词）：
- `GET /api/admin/weak-points` 返回**不变**；
- 家长端「英语」页加一块「高频错词」：`word_progress WHERE wrong_count>=2` 按次数倒序，家长可一键「重点盯」（把该词 `interval_idx` 重置 0、`due=明天`，孩子端明天必见）—— 操作权仍在家长；
- 周报（`/api/admin/weekly`）的 `insight` 增加一种类型 `word_stuck`：「本周乐乐默错了 8 个词，其中 3 个重复错」—— 复用现有 `build_insights()` 的排序框架（`backend/main.py:541-598`）。

## 6. 分阶段实施计划

### 阶段一：成就升级（P0，1-2 天，纯内部增强）

- 目标：徽章有稀有度、段位链、获得时刻；不动任何数值规则。
- 涉及文件：`backend/db.py`（迁移 028）、`backend/main.py`（ACHIEVEMENTS 定义 + /api/achievements）、`frontend/src/App.vue`（成就墙 UI、新徽章动画）、`backend/test_kids.py`（新增用例）。
- 验收：`cd backend && python3 -m pytest -q` 全绿（含新增：earned 记录幂等、seen 置 1、稀有度字段存在）；`npm --prefix frontend run build` 成功。
- 防回退：现有 24 个测试必须一个不红（特别是 test_task_rules 的取消冲正、test_weak_points 的 judge 档位）。

### 阶段二：阳光精灵 + 抽卡（P1，3-5 天）

- 目标：自创精灵体系上线：图鉴、抽卡（阳光消耗）、涂色上传、保底。
- 涉及文件：`backend/db.py`（迁移 029 + sprite_defs 种子）、`backend/main.py`（4 个端点 + ledger reason `gacha` + earned 排除）、`frontend/src/App.vue`（图鉴页、开蛋动画）、`frontend/src/Admin.vue`（gacha-config）、`backend/test_kids.py`/新 `test_gacha.py`。
- 验收：pytest 全绿（重点用例：余额不足 409、十连=10 条 draw 记录、pity 到 30 强制稀有、重复转星尘、gacha 不掉级 earned 断言、关闭开关后 403）；build 成功；手测上传涂色图（>2MB 拒绝）。
- 防回退：`earned()` 的 reason 排除名单改动必须带上回归断言「抽卡后 earned 不变、balance 减少」。

### 阶段三：单词背默（P1.5，3-4 天）

- 目标：译林 5A 词表导入（data/ 新增 `words.5a.json`，走 scripts 生成脚本模式，与 tasks.seed 同套路）；孩子端今日背默动线；家长配置与错词视图。
- 涉及文件：`data/words.5a.json`（新）、`scripts/gen_words.py`（新，参照 gen_seed.py）、`backend/db.py`（迁移 030 + 种子）、`backend/main.py`（端点见 §5.2）、`frontend/src/App.vue`（背/默 UI）、`frontend/src/Admin.vue`（config + 词表管理 + 高频错词）、`backend/test_words.py`（新）。
- 验收：pytest 全绿（新增：同日 done 幂等不重发、spell 对/错档位变化、due 计算跨月正确、跨家庭隔离）；build 成功；真实词表 spot check（Unit 1 前 10 词顺序与教材一致 —— 人工核对一次）。
- 防回退：weak_points 相关测试原样通过（证明没动诊断流）；ledger 新 reason 回归（word_daily 幂等）。

### 阶段四（可选，P2）：联动与打磨

- 抽卡与成就联动（集齐系列徽章）、周报 `word_stuck` 洞察、精灵进化动画、错词「重点盯」。
- 验收同上模式，不设硬期限。

## 7. 不做清单（本期明确不做）

- 精灵对战、属性克制、排行（多娃 PK 在 PLAN.md 支线 B 已明确禁止）。
- 任何第三方 IP 素材（奥特曼/帕鲁/PvZ/宝可梦……），包括「画得很像」的致敬形象。
- 真实货币充值、广告、任何外部付费入口（阳光永远只能学习获得）。
- SM-2 / FSRS 动态间隔（保留 rep 字段作为升级路径，不现在做）。
- 单词自动进 weak_points 复习队列（诊断权留给家长，见 §5.4）。
- 引入任何新的第三方依赖（前端动画纯 CSS；后端全部标准库 + 现有 FastAPI）。

## 8. 检索与来源清单

| # | 来源 | 用途 |
|---|---|---|
| 1 | https://www.sohu.com/a/742232759_121856877 搜狐「玩子今天玩什么」 | 小红书系手工积分卡/奖励券玩法（二手） |
| 2 | https://www.sohu.com/a/855682289_121956424 搜狐《寒假儿童自律新法》 | 家庭积分六步法、仪式感（二手，Sogou 检索） |
| 3 | https://en.wikipedia.org/wiki/Habitica | RPG 任务管理、装备/宠物收集 |
| 4 | https://en.wikipedia.org/wiki/ClassDojo | 课堂积分、专属怪物头像 |
| 5 | https://github.com/cwjcw/KidPoints | 国内开源家庭积分系统参照 |
| 6 | https://eastondev.com/habit-tracker/zh/ | 打卡表模板、系列化习惯计划 |
| 7 | https://en.wikipedia.org/wiki/Loot_box （§China） | 抽卡概率公示规定、未成年人限制 |
| 8 | https://en.wikipedia.org/wiki/Palworld | 任天堂诉 Pocketpair 专利案（2024-09） |
| 9 | https://en.wikipedia.org/wiki/Ultraman | 圆谷维权史、在华诉讼 |
| 10 | https://en.wikipedia.org/wiki/Plants_vs._Zombies | PvZ 权利归属（PopCap/EA） |
| 11 | https://en.wikipedia.org/wiki/SuperMemo | SM-2 公式与参数 |
| 12 | https://en.wikipedia.org/wiki/Leitner_system | 五档盒子间隔原理 |
| 13 | https://github.com/open-spaced-repetition/py-fsrs | FSRS 开源实现（论证为何不用） |
| 14 | https://zh.wikipedia.org/wiki/百词斩 | 选词典定计划每日量动线 |

> 检索执行记录：DuckDuckGo（`小红书 孩子 打卡 积分 系统 自制` 等词，命中 #1/#5/#6）→ DDG 限流后切 Sogou（`家庭 积分银行 孩子 奖励 制度` 命中 #2）→ 维基百科与 GitHub API 直接抓取（#3/#4/#7-14）。小红书站内笔记未直接抓取（登录墙 + 版权边界），全部采用注明「二手来源」的公开转载。
