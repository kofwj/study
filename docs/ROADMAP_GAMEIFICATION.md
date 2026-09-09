# 游戏化更新计划书

> 基线：v0.2.0（2026-09-08）。本文回答三个问题：成长系统怎么升级、能不能用奥特曼 / 幻兽帕鲁 / 植物大战僵尸的形象做抽卡、英语单词每日背默怎么接进来。所有设计不违反既有铁律（见 §1.4），不引入新的第三方依赖。

## 0. 结论速览

| 问题 | 结论 | 对应章节 |
|---|---|---|
| 等级和成就太简单，怎么养成化？ | 不动等级和 ledger，加三层：伙伴养成（视觉资产）+ 成就段位（稀有度/进度感）+ 惊喜时刻（抽卡感）| §3 |
| 奥特曼/帕鲁/PvZ 人物能用阳光抽吗？ | **不能直接用**。形象是受版权和商标保护的第三方 IP；换成自创「阳光精灵」体系，孩子自己涂色上传，抽卡照做 | §4 |
| 英语每天背+默写怎么做？ | 新增教材词书、单词进度、每日 session 与答题审计四层数据；默写由服务端判定，ledger 仍是唯一阳光真相 | §5 |
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
4. 复习队列仍是家长诊断驱动，孩子端的单词默写判定**不自动改 weak_points**（见 §5.7.1）。
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
| word_debut | 单词首秀 | 第一次完成每日背默 | 1 | bronze | study | None | `word_sessions` 存在 `state='completed'` 记录（§5 联动）|
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

> **状态：规划中，尚未实现。** 当前 `backend/main.py`、`backend/db.py`、`frontend/src/api.js`、`frontend/src/App.vue` 和 `frontend/src/Admin.vue` 尚无单词 session、词书、进度表或单词 API；本章是实施规格，不是现有功能说明。

### 5.1 先定边界：这是「教材词汇练习」，不是另一个背词 App

本模块的目标是把当前「听读并会写 Unit N 重点词汇」的教材任务（例如 `g5s1-en-1` 的现有任务卡）拆成每天 5-10 分钟、能追踪效果的练习闭环；不是复制百词斩、扇贝或 Anki。

**MVP 只做五件事：**

1. 家长选定当前教材词书，孩子每天完成「到期复习 → 少量新词 → 默写」。
2. 系统按对/错安排下一次复习；不会因为一天没做而扣阳光、归零或堆积无限任务。
3. 一天完成一个完整 session 才发一次阳光；每个词的错题与成长对家长可见。
4. 词书、单词、进度均按家庭和孩子隔离；不影响既有 `tasks`、`weak_points`、`completions` 的行为。
5. 看词页展示音标，并提供朗读按钮（见 §5.6.3）。默写页不朗读、不显示完整英文。

**MVP 明确不做：**语音识别/跟读打分、AI 出题、拼写联想、跨设备离线冲突处理、词根词缀、排行榜和自动推送。不从百词斩、教材配套音频、有道等第三方抓取或转存读音文件；不接入云端 TTS API，避免新依赖和隐私出网。朗读只用设备自带的 `speechSynthesis`（Web Speech API）。

### 5.2 孩子实际要走的流程

入口放在现有孩子端「今天」的三段流程里：

```text
到期复习（已有 weak_points）
  → 每日打卡（已有）
  → 今日单词（新增，英语词书启用时显示）
  → 本课下一步（已有教材任务）
```

不替换英语单元任务卡。单元任务代表「这个 Unit 的词汇要求是否完成」，单词 session 是把大任务拆成每日练习；两者可独立完成，家长仍可以按学校实际情况勾选单元任务。

#### 5.2.1 单次 session 的状态机

| 阶段 | 孩子看到什么 | 孩子操作 | 服务端变化 | 是否发阳光 |
|---|---|---|---|---|
| 0. 开始 | `今天复习 4 个 · 新学 5 个` | 点「开始」 | 创建或恢复当天 `word_sessions` | 否 |
| 1. 看词 | 英文、音标、中文、朗读按钮、例句（若有） | 点「听读音」/「去默写」/「再看一次」 | 只记 session 内的学习状态；「再看一次」排到本 session 末尾 | 否 |
| 2. 默写 | 给中文/例句留空，显示字母数（如 `_ _ _ _ _`）；**不显示英文、不朗读** | 输入单词后点「检查」 | 写 `word_attempts`；正确升档，错误归到明天并进入本 session 的纠错卡 | 否 |
| 3. 纠错 | 错词显示正确拼写、音标、朗读按钮 | 点「听读音」/「再写一次」 | 第二次写对只完成本次学习体验，**不额外升档** | 否 |
| 4. 完成 | `今天背默完成：正确 8 / 10` | 点「收下阳光」 | 原子地完结 session，按规则写 1-2 条 ledger | 是，最多一次基础奖+一次全对奖 |

**关键体验规则：**

- 每天默认最多 **10 个待默写词**：先到期复习，剩余名额才放新词。孩子今天有 10 个到期词时，不再塞新词。
- 错词当天只强制重写 **一次**。第二次仍错也允许完成，排到明天重新开始，避免把「每天 10 分钟」变成挫败式加班。
- 重新打开页面或网络中断，`GET /api/words/today` 必须恢复同一个未结束 session 和已答题状态，不能重新抽词。
- 每个 session 的题目顺序由服务端固定保存，前端只渲染，避免刷新后题目变化、重复刷奖励或家长无法复核。

#### 5.2.2 单词范围和教材解锁

词书不使用泛用「小学 1500 词」直接灌入。系统词书按教材单元建立：现有五上译林英语单元已经稳定为 `g5s1-en-1` 至 `g5s1-en-10`（Unit 1-8 + Project 1-2，见 `data/tasks.seed.json:136-204`）。

第一期词书结构：

| 词书 ID | 名称 | 映射单元 | 上线策略 |
|---|---|---|---|
| `g5s1-en-1` | Unit 1 Good habits | `g5s1-en-1` | 先做人工核对的 20-30 个核心词，作为试点 |
| `g5s1-en-2` … `g5s1-en-8` | Unit 2-8 | 对应 unit | Unit 1 试运行 2 周后逐个补充 |
| `g5s1-en-p1` / `g5s1-en-p2` | Project 1/2 回顾词 | `g5s1-en-9/10` | 只收录复习价值高的词，不机械复制全书 |
| `family-{uuid}` | 家长自建词书 | `unit_id=NULL` | 家长粘贴导入，默认不跟教材游标锁定 |

教材词书由家长为每个孩子选定一个「当前新词词书」；到期复习会覆盖该孩子已经开始过的旧词书，避免换到 Unit 2 后遗忘 Unit 1。

课程游标锁开启时，服务端须先把 `cursor_英语` 的**任务 ID** JOIN 到 `tasks.unit_id`，再取 `units.seq` 比较，只有 `word_books.unit_id` 序号不晚于该单元的系统词书可以被选为新词词书。不得把 cursor 值当作 unit ID 比较。没有英语 cursor 时，系统词书下拉为空，家长可先在「已学到」设置英语进度，或临时关闭游标锁后选择词书；不隐式给孩子开启未来单元。家庭自建词书不受游标限制。**系统词书只允许代码/seed 更新，家长不可改写；家庭词书才允许增删改。**

### 5.3 数据模型（迁移 `030_words`）

> 当前已落库的迁移尾号是 `028_achievement_earned`。本路线图按阶段二先落 `029_sprites`、阶段三再落 `030_words` 的顺序编号；若产品优先级调整为先做单词，必须将单词迁移统一改为 `029_words`，并将抽卡顺延，不能在 `MIGRATIONS` 中出现重复 id。

#### 5.3.1 表设计

```sql
-- 词书。系统词书 family_id=''、is_system=1；家庭词书绑定 family_id。
-- word_books 的 family_id 主要用于 SQLite 显式过滤与 PG 的家庭 RLS。
CREATE TABLE word_books (
  id TEXT PRIMARY KEY,
  family_id TEXT NOT NULL DEFAULT '',
  term_id TEXT NOT NULL DEFAULT '',
  unit_id TEXT,                         -- NULL=家庭自由词书
  name TEXT NOT NULL,
  is_system INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  sort INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX ix_word_books_family ON word_books(family_id, term_id, enabled, sort);

-- 词条。word_norm 用于大小写和空格归一后的去重；accept_json 保存可接受拼写（如 colour/color）。
-- `id` 类型按 backend/db.py 的 pk 兼容分支生成：SQLite 为 AUTOINCREMENT，PostgreSQL 为 identity。
CREATE TABLE words (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id TEXT NOT NULL,
  word TEXT NOT NULL,
  word_norm TEXT NOT NULL,
  cn TEXT NOT NULL,
  ipa TEXT NOT NULL DEFAULT '',
  example_en TEXT NOT NULL DEFAULT '',
  example_cn TEXT NOT NULL DEFAULT '',
  accept_json TEXT NOT NULL DEFAULT '[]',
  sort INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(book_id, word_norm)
);
CREATE INDEX ix_words_book_sort ON words(book_id, active, sort, id);

-- 每个孩子、每个词的长期间隔复习状态。只有拼写判定会更新它。
CREATE TABLE word_progress (
  kid_id TEXT NOT NULL,
  word_id INTEGER NOT NULL,
  interval_idx INTEGER NOT NULL DEFAULT 0, -- 0..4 对应 1/3/7/14/30 天
  due_at TEXT,                            -- NULL=从未通过拼写，尚未进入复习周期
  first_seen_at TEXT,
  last_seen_at TEXT,
  last_result TEXT NOT NULL DEFAULT '',   -- right/wrong
  streak_right INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0,
  wrong_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (kid_id, word_id)
);
CREATE INDEX ix_word_progress_due ON word_progress(kid_id, due_at, interval_idx);

-- 某个孩子某一天只存在一个 session；state=active/completed/abandoned。
-- task_json 只保存出题快照（word_id/source/order），不保存可由 words JOIN 得到的释义。
-- base/perfect 奖励在创建时快照，家长改配置不会篡改当天奖励。
CREATE TABLE word_sessions (
  id TEXT PRIMARY KEY,
  kid_id TEXT NOT NULL,
  family_id TEXT NOT NULL,
  study_date TEXT NOT NULL,
  book_ids_json TEXT NOT NULL,
  task_json TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'active',
  started_at TEXT NOT NULL,
  completed_at TEXT,
  base_sunshine INTEGER NOT NULL DEFAULT 0,
  perfect_sunshine INTEGER NOT NULL DEFAULT 0,
  UNIQUE (kid_id, study_date)
);
CREATE INDEX ix_word_sessions_kid_state ON word_sessions(kid_id, study_date, state);
CREATE INDEX ix_word_sessions_family_date ON word_sessions(family_id, study_date);

-- task_json 中每个 item 的当前状态单独保存，便于恢复、并发幂等和统计。
-- SQLite 使用 INTEGER PRIMARY KEY AUTOINCREMENT；PostgreSQL 迁移沿用 db.py 的 identity 类型。
CREATE TABLE word_session_items (
  -- `id` 同样按 SQLite/PG 的现有 identity 兼容分支生成。
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  kid_id TEXT NOT NULL,
  family_id TEXT NOT NULL,
  word_id INTEGER NOT NULL,
  source TEXT NOT NULL,                    -- due/new
  item_order INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'study',    -- study/spell/retry/done
  first_result TEXT,                       -- right/wrong；首轮判定后固定
  retry_used INTEGER NOT NULL DEFAULT 0,
  answered_at TEXT,
  UNIQUE(session_id, word_id)
);
CREATE INDEX ix_word_session_items_current ON word_session_items(session_id, state, item_order);

-- 每次「检查拼写」保留审计记录：不存孩子输入原文，避免把无必要数据长期留库；只存结果和次数。
CREATE TABLE word_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  kid_id TEXT NOT NULL,
  family_id TEXT NOT NULL,
  word_id INTEGER NOT NULL,
  phase TEXT NOT NULL,                    -- spell/retry
  result TEXT NOT NULL,                   -- right/wrong
  attempt_no INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(session_id, word_id, phase, attempt_no)
);
CREATE INDEX ix_word_attempts_session ON word_attempts(session_id, word_id);

-- 单词奖励防重：现有 ledger.ref_id 无唯一约束（backend/db.py insert_ledger 无条件 INSERT）。
-- SQLite 与 PostgreSQL 都支持部分唯一索引。reason 不同，同一 session 可以有基础奖和全对奖各一条。
CREATE UNIQUE INDEX ux_ledger_word_reward
  ON ledger(kid_id, reason, ref_id)
  WHERE reason IN ('word_daily', 'word_perfect');
```

**为什么需要 session、items 与 attempts，而不只用旧方案的 `word_daily` 表：**

- `word_progress` 管长期记忆，不知道「今天抽了哪些题」；`word_sessions.task_json` 固化题单，`word_session_items` 保存题目状态，二者共同解决刷新、重试、当日统计和奖励防重。
- 当前 `ledger.ref_id` **没有全表唯一约束**（`backend/db.py:971-973`）；不能仅靠 `wd-{kid}-{date}` 字符串承诺防重。最终防线是：`word_sessions(kid_id, study_date)` 唯一、`state='active'→completed` 的条件更新，以及上面的 `ux_ledger_word_reward`。结束 session 与写 ledger 必须在同一个事务里完成。
- `word_attempts` 能让家长看见错题趋势，但不需要保存每一次输入的原始文本，减少儿童数据保存范围。
- `first_seen_at` **只在该词第一次进入 spell 判定时写入**。创建 session 或只看词不写；若 session 被标为 `abandoned` 且该新词从未 spell，保持 `first_seen_at IS NULL`，明天仍可作为新词候选。不能在导入词表或 start session 时写 first_seen，否则中途退出会把新词永久吞掉。

#### 5.3.2 家庭配置：不新增 families 列

沿用已有 `kid_settings`（每娃、每 key 一行）和家庭 `settings` 方式，不往 `families` 持续加大量特性列。

| key | 作用 | 默认值 | 归属 |
|---|---|---:|---|
| `words_enabled` | 是否显示单词模块 | `0`（显式开启） | kid_settings |
| `words_new_per_day` | 每日最多新词 | `5`，范围 1-10 | kid_settings |
| `words_max_due` | 每日最多到期词 | `10`，范围 5-15 | kid_settings |
| `words_base_sunshine` | 完成 session 的基础阳光 | `3`，范围 0-10 | kid_settings |
| `words_perfect_sunshine` | 首轮全部拼对的额外阳光 | `2`，范围 0-5 | kid_settings |
| `words_unlock_by_cursor` | 是否受英语课程游标约束 | `1` | kid_settings |
| `words_current_book` | 当前新词词书 ID | 空=尚未选定 | kid_settings |
| `words_tts` | 是否显示朗读按钮 | `1` | kid_settings |
| `words_tts_autoplay` | 看词页是否自动朗读一次 | `0`（默认不自动播，避免吵） | kid_settings |
| `words_tts_lang` | 朗读语言标签 | `en-GB`（译林偏英式；可选 `en-US`） | kid_settings |

这样多孩子可以用不同节奏：一个孩子每天 3 个新词，另一个每天 8 个；家长也可以把某个孩子临时关闭，不影响全家。家长端批量设置可作为后续便利功能，不纳入 MVP。

**不要复用全局 `progress_lock`。** 当前进度锁走 `settings` 表（`get_setting` / `set_setting`），多家庭部署下不是家庭隔离字段。单词词书锁只用 `kid_settings.words_unlock_by_cursor`。

#### 5.3.3 RLS 与家庭隔离

所有业务查询必须走 `get_conn()` → `apply_scope(family_id, kid_id)`。PostgreSQL 运行时必须是 `DATABASE_APP_URL` 的非超级用户，否则 RLS 可被绕过。SQLite 没有 RLS，每条 SQL 仍须显式带 `kid_id` / `family_id` 条件。

| 表 | PG RLS | SQLite 显式条件 |
|---|---|---|
| `word_books` | `is_system=1 OR family_id = current_setting('app.family_id', true)` | 同上 |
| `words` | 不单独 RLS；只能 JOIN 可访问的 `word_books` | 同左，禁止按 `word_id` 裸查 |
| `word_progress` | `kid_id = current_setting('app.kid_id', true)` | `kid_id=?` |
| `word_sessions` | 同上 | 同上 |
| `word_session_items` | 同上（表上冗余 `kid_id`，不依赖 JOIN 才能隔离） | 同上 |
| `word_attempts` | 同上 | 同上 |

写入家庭词书的接口先 `require_parent()`，且不能修改 `is_system=1` 的行。不能相信客户端传入的 `kid_id` 或 `family_id`。

### 5.4 调度与间隔重复规则

#### 5.4.1 算法选择

使用现有薄弱点相同的固定五档间隔：

```python
WORD_INTERVALS = [1, 3, 7, 14, 30]  # 与 WEAKPOINT_INTERVALS 分开常量，但初值一致
```

选择固定五档 Leitner 变体，不上 SM-2/FSRS：

- `WEAKPOINT_INTERVALS = [1,3,7,14,30]` 已在 `backend/main.py:2025` 附近实际使用，家长已经理解「过关后隔更久再练」。
- 本产品一学期英语词汇量相对有限，儿童判断是「拼对/没拼对」二元结果；SM-2 的 ease factor（初值 2.5）和 FSRS 的个体参数在此数据量下是过度工程。
- `streak_right`、`correct_count` 已保留，将来证据足够时可以迁移到 SM-2；**不能**在没有迁移计划时悄悄改变已有孩子的复习日期。

#### 5.4.2 建 session 时的选词算法

服务端在事务内执行，所有日期用 `db.today()`，禁止相信前端时间：

```text
1. 如果今天已有 `active` 或 `completed` session：直接返回它的 `task_json` 与 `word_session_items`；不能重新选词。若存在前一天遗留的 `active` session，第一次请求今天时将其标为 `abandoned`，不发奖励；其未完成词按原 due_at 规则进入今天候选。
2. 读取启用且可见的词书：系统词书需满足课程游标；家庭词书恒可见。
3. 先取 due_at <= today 的到期词，按 due_at ASC、interval_idx ASC、word_id ASC；最多 words_max_due 个。
4. 剩余名额 = max(0, min(words_max_due, 10) - 到期词数)。新词只从 `words_current_book` 中取：
   `word_progress` 不存在或 `first_seen_at IS NULL` 的 active 词，按 words.sort、words.id。
   数量 = min(剩余名额, words_new_per_day)。到期复习可跨该孩子已经开始过的旧词书。
5. 无到期词且无新词：返回 finished=true，不创建 session，也不发阳光。
6. `INSERT ... ON CONFLICT (kid_id, study_date) DO NOTHING` 创建 session；冲突则重读已有行。
   成功插入后再写 `task_json` 与 `word_session_items(state='study')`。此时**不写** `first_seen_at`。
```

这里的 `10` 是孩子端单次 session 总上限；`words_max_due` 是独立上限。若 due 词很多，系统不会「消失」它们：后面的会继续留在明天，且家长端显示「还有 N 个到期词」。第一版不做逾期惩罚，也不对堆积词批量降档。

#### 5.4.3 拼写判定与进度变化

统一归一化函数（后端唯一实现，前端不得自行判对错）：

```python
def normalize_word(raw: str) -> str:
    # 去首尾空格，连续空格压成一个；统一 Unicode apostrophe，转小写。
    return " ".join((raw or "").strip().replace("’", "'").lower().split())
```

判定规则：`normalize_word(input)` 等于 `word_norm` 或 `accept_json` 中任一归一形式即正确。不能做模糊匹配、编辑距离自动放过或自动改错；孩子需要知道拼写是否准确，遇到教材存在英美变体时由系统词书显式列在 `accept_json`。

| 本次结果 | `interval_idx` | `due_at` | `streak_right` | 其它 |
|---|---|---|---:|---|
| 从未成功过的词首轮拼对 | `0` | 明天（`WORD_INTERVALS[0]=1`） | `1` | `correct_count +1`；儿童新词第二天必须再见一次 |
| 已有档位的词首轮拼对 | `min(old + 1, 4)` | `today + WORD_INTERVALS[new_idx]` | `+1` | `correct_count +1` |
| 首轮拼错 | `0` | 明天 | `0` | `wrong_count +1`；当天加入一次 retry |
| retry 拼对 | 不变 | 不变 | 不变 | 仅改善当日体验，不刷复习档位 |
| retry 再错 | 不变 | 不变 | 不变 | 允许结束；明天仍是最低档复习 |

与薄弱点不同：考点第一次「过关」发生时，今天已经练过，所以 weak_points 的 pass 会跳到 3 天。新单词第一次拼对仍安排明天再见，避免「刚学会就一周后再见」。后续成功才按 3/7/14/30 拉长。

注意：**默写错误绝不写 ledger。** ledger 只在完成整个 session 时写奖励；错题是学习诊断，不是惩罚。

### 5.5 API 合约与幂等规则

所有孩子 API 都由登录态取 `kid_id()`；前端 API 封装会自动附带 `selected_kid`，服务端仍必须按当前 scope 校验。

#### 5.5.1 孩子端 API

| 端点 | 请求 | 返回 / 关键约束 |
|---|---|---|
| `GET /api/words/today` | 无 | 返回 `{enabled, finished, backlog_due, session, config}`。若有 session，返回固定 `items[]`，每项含 `word_id, word, cn, ipa, example_en, source, state`；不得返回其他家庭词。 |
| `POST /api/words/session/start` | `{}` | 幂等创建或恢复当天 session，返回与 `today` 相同结构。无题可做时 `{finished:true}`。 |
| `POST /api/words/session/{id}/study` | `{word_id, action:"known"\|"again"}` | 仅更新 session 中当前学习状态；`again` 将词移到 session 末尾。word 不属于 session 返回 403/404。 |
| `POST /api/words/session/{id}/spell` | `{word_id, text, phase:"spell"\|"retry", attempt_no}` | 服务端归一化后判分。相同 `(session, word, phase, attempt_no)` 重放时返回第一次结果，不重复更新 progress。 |
| `POST /api/words/session/{id}/complete` | `{}` | 只允许该 session 全部完成后调用；同事务将 state 改为 completed、写基础奖励和可能的全对奖励；重复调用返回既有 `reward`，不再写 ledger。 |

示例：`GET /api/words/today` 返回：

```json
{
  "enabled": true,
  "finished": false,
  "backlog_due": 3,
  "config": {"new_per_day": 5, "max_due": 10, "base_sunshine": 3, "perfect_sunshine": 2},
  "session": {
    "id": "ws-7d3e...",
    "study_date": "2026-09-09",
    "state": "active",
    "counts": {"due": 3, "new": 5, "answered": 2, "correct_first_try": 2},
    "items": [
      {"word_id": 41, "word": "always", "cn": "总是", "ipa": "/ˈɔːlweɪz/", "source": "due", "state": "spell"}
    ]
  }
}
```

#### 5.5.2 家长端 API

| 端点 | 权限 | 说明 |
|---|---|---|
| `GET /api/admin/words/config` | parent | 当前 selected kid 的配置 + 可见词书摘要 |
| `PUT /api/admin/words/config` | parent | 校验范围后写 kid_settings；未知字段 400，禁止把 `words_enabled` 以外字段写成字符串垃圾值 |
| `GET /api/admin/words/books` | parent | 系统词书 + 当前家庭词书；返回每本总词数、已学/到期/高频错词数 |
| `POST /api/admin/words/books` | parent | 建家庭词书：`{name}`，名称 1-30 字 |
| `PUT/DELETE /api/admin/words/books/{id}` | parent | 只能改/删本家庭的非系统词书；若已有 progress，删除走 `active=0` 软删除而不是物理删除 |
| `POST /api/admin/words/books/{id}/import` | parent | 粘贴 TSV/CSV，最多 500 行；逐行返回 `{line, error}`，不因一行坏数据吞掉其他合法行 |
| `GET /api/admin/words/problem-words` | parent | 当前孩子 `wrong_count >= 2` 的词，含最近错日、下次到期、关联词书/单元 |
| `POST /api/admin/words/{word_id}/focus` | parent | 强制明天复习：重置 `interval_idx=0`、`due_at=tomorrow`；不扣分、不发阳光 |

导入格式（家长端直接展示示例）：

```text
always	总是	/ˈɔːlweɪz/
usually	通常	/ˈjuːʒuəli/
get up	起床
```

- 第 1 列单词必填，最多 60 字符；第 2 列中文释义必填，最多 120 字符；第 3 列音标可选。
- CSV 解析使用 Python `csv` 标准库；TSV 用明确的制表符分列。禁止用 `split(',')` 处理 CSV。
- 系统教材词书来自新增 `data/words.seed.multi.json` + `scripts/gen_words.py`，同 `data/tasks.seed.multi.json` 的数据驱动思路一致；每个词书需注明来源页码/词表位置，人工复核后再入库。

#### 5.5.3 奖励事务伪代码

`POST /complete` 的现有模式已在 completion 写入后立即记 ledger（`backend/main.py:900` 附近）。单词必须采用相同事务，但奖励防重依赖 session 主键和 state，而非 ledger ref：

```python
# 伪代码：c 已是 get_conn()，受 kid scope 限制
row = c.execute(
    "SELECT * FROM word_sessions WHERE id=? AND kid_id=?", (sid, kid_id())
).fetchone()
if not row: raise HTTPException(404, "没找到今天的单词练习")
if row["state"] == "completed":
    return _completed_word_session_payload(c, row)  # 幂等返回，零新增流水
if not _all_items_finished(row):
    raise HTTPException(409, "还有单词没有完成")

# 同一事务：先 CAS 更新。rowcount=0 代表并发请求已经完成，重读已有结果。
updated = c.execute(
    "UPDATE word_sessions SET state='completed', completed_at=? "
    "WHERE id=? AND kid_id=? AND state='active'", (db.now(), sid, kid_id())
).rowcount
if not updated:
    return _completed_word_session_payload(c, row)

# 奖励金额用 session 创建时快照的 base/perfect，不读最新 kid_settings。
# ref 用 session id；部分唯一索引 ux_ledger_word_reward 是第二道防线。
insert_ledger(c, db.today(), row["base_sunshine"], "word_daily", f"word-{sid}", "今日单词背默")
if _first_try_all_right(sid):
    insert_ledger(c, db.today(), row["perfect_sunshine"], "word_perfect", f"word-perfect-{sid}", "单词默写全对")
c.commit()
```

SQLite 和 PostgreSQL 的 `rowcount` / `RETURNING` 差异要按现有 `db.insert()` 兼容层处理；这里表达的是原子条件更新语义，不能照抄为未经测试的代码。若 `insert_ledger` 撞上 `ux_ledger_word_reward`，视为已经发过奖，重读 payload 返回，不得再改 SRS。两种奖励都计入 `earned()`（不进排除名单），测试须断言 earned 增加 `base + perfect`。

### 5.6 前端与家长端交互规格

#### 5.6.1 孩子端（`frontend/src/App.vue`）

**入口：**

- 仅 `words_enabled=1` 且当天有题时，`今日推荐` 的「每日打卡」和「本课下一步」之间插入「今日单词」 section；优先级低于既有到期复习，高于可延后的本课任务。
- 侧边栏英语 tab 下加一张紧凑的「今日单词」卡，不另加一级主导航，避免孩子在任务、单词和图鉴之间反复跳转。
- 若今天已完成，卡片显示 `今日背默完成 · 正确 8/10`，可点开回顾但不可再领阳光。

**交互细节：**

1. 看词页一次只出现 1 个词：英文最大，下一行音标（`ipa` 为空则显示「暂无音标」），再下一行中文；右侧或英文旁一个喇叭按钮「听读音」。另有「再看一次」与「去默写」。
2. 默写页显示中文和字母槽（不预填首字母），不显示完整英文、不显示音标、不提供朗读；input 属性见 §5.9.3。到期词可「忘了，看一眼」。
3. 对：槽变绿，英文音标淡入后自动下一题；错：琥珀提示 + 正确答案 + 听读音，「再写一次」不计分。没有红叉、扣分、失败音效。
4. 每题都有 `当前 3/8`，但没有倒计时；完成页显示今天学了/复习了多少、首轮正确数和获得阳光。
5. 无词可做时显示「这一单元的词都练过了」，不创建空 session、不出现可点击的领阳光按钮。
6. 访问性：按钮最小触控区域 44px；不能只依赖颜色表达对错；键盘 Enter 交题，Esc 不丢弃输入。喇叭按钮须有文字或 `aria-label="听读音"`，不能只靠图标。

**Vue 状态建议：**

```js
const wordToday = ref({ enabled: false, finished: false, session: null })
const wordDialog = reactive({ open: false, itemIndex: 0, phase: 'study', input: '', busy: false })

const wordRemaining = computed(() =>
  (wordToday.value.session?.items || []).filter(x => x.state !== 'done').length
)
```

不要把出题顺序、间隔计算、是否全对等规则放在 computed 中；前端只显示服务端返回的 session 状态。新的 `api.words.*` 方法按 `frontend/src/api.js` 现有 `j()` 封装新增，自动继承 cookie、错误消息和 `selected_kid` 参数处理。看词/默写每一屏的布局、按钮、输入和中断恢复见 **§5.9.3**。

#### 5.6.3 音标与读音

**音标（必须有展示位，允许缺数据）：**

- 系统词书 seed 的 `ipa` 用教材/课标常见的国际音标，人工核对后入库；家庭导入第 3 列为可选音标。
- 孩子端看词页、纠错页、完成回顾都显示 `ipa`；空字符串显示「暂无音标」，不编造。
- 音标是静态文本，不参与判分。拼写仍只比 `word_norm` / `accept_json`。
- 字体：优先系统已有的 Unicode 音标；不要为音标引入新 webfont 依赖。Android WebView 上若个别符号缺字，允许回退到普通衬线，但不能因此隐藏整行。

**读音（设备 TTS，不存音频文件）：**

```js
function speakWord(word, lang) {
  if (typeof speechSynthesis === 'undefined') return false
  speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(word)
  u.lang = lang || 'en-GB'
  u.rate = 0.85
  speechSynthesis.speak(u)
  return true
}
```

- 朗读的是**英文单词本身**（`words.word`），不是音标字符串。音标给孩子看，TTS 给孩子听。
- `words_tts=0` 时隐藏喇叭，音标仍显示。
- `words_tts_autoplay=1` 时，看词页进入后自动朗读一次；默写页即使开了自动播也**禁止**朗读。
- 连续点喇叭：先 `cancel()` 再播，避免叠音。
- `speechSynthesis` 不存在或没有英语 voice 时：喇叭仍可点，toast「这台设备暂时不能朗读，先看音标」；不影响完成 session 和发阳光。
- Android WebView 手测必做：有的壳需要用户手势后才能出声，因此默认不自动播。
- 后续若要「更像教材原声」，只能：家长自己录音上传（需新的存储与审核，不在 MVP），或采购有授权的词级音频。禁止爬取第三方读音。

#### 5.6.2 家长端（`frontend/src/Admin.vue`）

在「学习」组新增一个「英语单词」页面，而不是塞进「每日任务」：

1. **今日概览**：新词/复习/首轮正确/未完成/积压到期词，默认显示当前顶栏孩子。
2. **开关与节奏**：开关、当前新词词书、每天新词数、每日到期上限、基础/全对阳光、是否按教材游标锁词书、朗读开关、看词页自动朗读、英式/美式。朗读相关即时生效；词数和阳光只影响**明天新建的 session**。
3. **词书管理**：系统词书只读显示单元/词数/来源版本；家庭词书可创建、导入、编辑、软删除。
4. **高频错词**：错误两次以上列出单词、释义、错几次、下次复习；只有「明天重点练」按钮，不提供删进度或扣分。
5. **周趋势**：第一期只展示近 7 日「完成 session 数 / 首轮拼写正确率」，不做排名或连续挑战海报。

### 5.7 与既有系统的关系

#### 5.7.1 与 weak_points 分开，但可见

关键决策：**单词默错不自动写 `weak_points`**。

- `weak_points` 的 tag 体系是教材单元知识点（`knowledge_tags`），且由家长诊断、家长判定 pass/fail/done；单词的 SRS 是孩子自练的细粒度数据，混合会损害现有诊断闭环。
- 单词错一次并不等于「薄弱考点」，自动塞入 20 个单词会让孩子端的「到期复习」爆炸，且造成两个互相竞争的到期日。
- 家长可在高频错词页点击「明天重点练」，而不是强行改 `weak_points`。若家长确认某单元整体词汇薄弱，仍可在现有考点页点亮该 unit 的英语词汇相关 tag。

周报可在阶段四加一个低优先级 `word_stuck` insight：本周错误词数/重复错误词数达到家庭阈值时才显示，排序应低于现有到期复习与低分单元；第一期不要为它加推送。

#### 5.7.2 与阳光/等级/成就的关系

1. 单词 session 只在完成时记一笔 `reason='word_daily'` 正流水，首轮全对时可再记一笔 `reason='word_perfect'` 正流水。两者是劳动奖励，应计入 `earned()`，因此会推动等级；`word_daily` 是流水 reason，不是单独的统计表。
2. MVP 不提供孩子端「取消单词完成」。扣分（`penalty`）只能动阳光余额，**不能**当作 session 回滚：它不会改 SRS、不会改 attempts、也不会生成单词审计。家长录错词或误操作时，第一期只允许改家庭词书内容和「明天重点练」；完整 `word_cancel`（反向流水 + 恢复受影响 `word_progress` + 写 correction 审计）放到阶段四，不能 DELETE ledger。
3. 成就模块只读取汇总结果，不反向控制单词：可新增 `word_debut`（完成首个 session）与 `word30`（完成 30 个 session），但不因拿不到徽章改变单词内容或奖励。
4. 单词阳光不用于抽卡概率、保底或「错得多就少给」等机制，保持学习与随机消费解耦。

### 5.8 验收测试矩阵（新建 `backend/test_words.py`）

| 用例 | 操作 | 断言 |
|---|---|---|
| 系统词书只读 | 家长 PUT/DELETE 系统书/词 | 403；家庭书可改 |
| 家庭隔离 | 家庭 A 取家庭 B 的 book/word/session id | 404 或空，不泄露名称/释义 |
| 当日 session 稳定 | 连续两次 `GET /today`、刷新后 start | 同一个 session id、同一 task_json、无重复词 |
| 上限调度 | 12 个 due + 10 个新词 | session 最多 10，due 优先，新词为 0 |
| 新词首次拼对 | 从未成功过的词首轮拼对 | idx=0、due=明天、correct_count+1、写入 first_seen_at |
| 已有档位升档 | 已是 idx 0 的词再次首轮拼对 | idx=1、due=3 天后、correct_count+1 |
| 错误降档 | idx 3 首轮拼错 | idx=0、due=明天、wrong_count+1、当天仅一个 retry |
| retry 不刷进度 | retry 拼对/错 | interval、correct_count、wrong_count 不二次变化 |
| 输入归一 | ` Always ` / `always` | 正确；未登记变体不模糊放过 |
| 完成幂等 | 并发/连续两次 complete | 仅一笔 `word_daily`、最多一笔 `word_perfect`，余额只增加一次 |
| 未答完禁止领奖 | 还有任意 item 未 done 调 complete | 409、无 ledger |
| 配置快照 | session 开始后家长改阳光 | 当日仍使用 session 的 base/perfect 值，明天才生效 |
| 游标锁 | 英语 cursor 为 Unit 1 的任务 ID | JOIN tasks.unit_id 后 Unit 2 系统词书不可选为新词书；关闭锁后可选 |
| 放弃不吞新词 | 创建含新词的 session 后跨日 abandoned | 未 spell 的新词 first_seen_at 仍为空，可再次入选 |
| 既有复习不变 | 跑完整 word 流程 | `test_weak_points.py` 仍全绿，`weak_points` 行数不变 |
| 账本/等级 | 完成带全对 session | ledger 两条正确 reason/ref；`earned()`、balance、level 计算正确 |

执行命令：

```bash
cd backend && python3 -m pytest -q
npm --prefix frontend run build
```

上线前手测：手机宽度、Android WebView、中文输入法/英文键盘、断网后重开、跨日时区边界（以服务器 `db.today()` 为准）。

### 5.9 实施顺序（将原估时拆细）

#### 5.9.1 数据与只读词书（0.5-1 天）

迁移、RLS、系统 Unit 1 试点词书 seed、家长词书导入；先无孩子端入口，用 API/TestClient 验证隔离。

#### 5.9.2 session 与 SRS（1-1.5 天）

选词、固定 task_json、拼写判定、间隔更新、完成事务、`test_words.py` 覆盖幂等。

#### 5.9.3 孩子端看词/默写页（1 天，本小节是逐屏规格）

目标：一个全屏遮罩（复用现有 `mask` + `shop-modal` 节奏，不要新开路由），一次只练当前 item。前端只渲染 `word_session_items.state`，不自己改 SRS。关闭遮罩 = 暂停，不放弃 session、不发阳光。

**A. 前端相位（只存在于遮罩内）**

| `item.state`（服务端） | 遮罩 `phase` | 孩子看到 |
|---|---|---|
| `study` | `look` | 看词页 |
| `spell` | `spell` | 默写页 |
| `retry` | `retry` | 纠错后再写一次 |
| `done` | 自动跳到下一个未 done 的 item；全 done 则 `done` 完成页 | |

打开遮罩时：取 `items` 里第一个 `state !== 'done'`。新词（`source=new`）从 `look` 开始；到期词（`source=due`）**跳过看词，直接 `spell`**（复习就是默写）。到期词提供次要操作「忘了，看一眼」，看完 2 秒自动回到默写，**不改 SRS**。

按钮文案统一（覆盖 §5.2.1 里「我记住了」的旧说法）：

| 屏 | 主按钮 | 次按钮 | 禁止 |
|---|---|---|---|
| 看词 | 去默写 | 听读音；再看一次（把本题排到队尾，调 `study action=again`） | 跳过、领取阳光 |
| 默写 | 检查 | 无。到期词额外「忘了，看一眼」 | 听读音、显示英文/音标 |
| 纠错 | 再写一次 | 听读音 | 改首轮对错、领阳光 |
| 完成 | 收下阳光 | 关闭（已完成时关闭=回顾，不再领） | 再练一遍刷奖 |

`busy=true` 期间所有按钮 disabled，防止双击两次 `spell`。

**B. 看词页布局（手机宽优先，平板居中最大 420px）**

```text
┌─────────────────────────┐
│ 今日单词        3 / 8   │  ← 已完成+当前 / 总数；新词标「新学」，到期标「复习」
│ ████░░░░                │  ← 细进度条，已 done 比例
│                         │
│         always          │  ← 英文 32–40px，加粗
│      /ˈɔːlweɪz/         │  ← 音标 16px；空则「暂无音标」
│         总是            │  ← 中文 18px
│                         │
│   [ 🔊 听读音 ]         │  ← ≥44px；words_tts=0 时隐藏
│                         │
│  I always get up early. │  ← 例句可选，两行截断
│                         │
│ [再看一次]  [去默写]    │  ← 次按钮幽灵样式，主按钮实心
└─────────────────────────┘
```

- 点「去默写」：`POST .../study {word_id, action:"known"}`，成功后本地把该 item 的 state 设为服务端返回值（应为 `spell`），`phase='spell'`，清空 `input`。
- 点「再看一次」：`action:"again"`，用返回的 items 顺序重排，留在当前词的下一题看词页。
- 自动朗读只在 `words_tts_autoplay=1` 且本 item 本轮第一次进入 look 时播一次；从默写返回看一眼不自动播。

**C. 默写页布局**

```text
┌─────────────────────────┐
│ 今日单词        3 / 8   │
│                         │
│         总是            │  ← 只给中文，字号 28px
│                         │
│    _ _ _ _ _ _          │  ← 字母槽，个数 = 去掉空格后的字母数
│                         │
│  [ always________ ]     │  ← 实际是一个 input，placeholder 空
│                         │
│        [ 检查 ]         │
│   忘了，看一眼          │  ← 仅 source=due 显示
└─────────────────────────┘
```

字母槽规则：

- 单词 `always` → 6 个槽 `_ _ _ _ _ _`，**不预填首字母**（五年级默写；看词页已经看过）。
- 短语 `get up` → `_ _ _  _ _`，空格位置留空白缺口，input 允许输入空格。
- 连字符 `good-bye`（若有）→ 槽里保留 `-`，孩子不必输入连字符；判分仍走服务端 `normalize_word`。
- 槽只是视觉提示，真正提交的是 input 字符串。

input 属性：`type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false" enterkeyhint="done"`。Enter 等于点「检查」。打开本页时 focus；Android WebView 不强制调起全屏键盘。

「忘了，看一眼」：本地切回 look 2 秒（可用 `peekUntil` 时间戳），然后强制回到 spell，input 不清空。不调 study again，不改 interval。每题最多看一眼 **2 次**，第三次 toast「先写一写，写错了会看到答案」。

点「检查」：trim 后若空，toast「先写一写」不发请求。否则 `POST .../spell {word_id, text, phase:"spell", attempt_no:1}`。

**D. 对 / 错反馈（仍在默写遮罩内，不新开层）**

- **对：**槽变绿，英文与音标淡入 0.8s，然后自动下一题。不弹「真棒」大窗，不放音效。`busy` 直到下一项渲染完。
- **错：**槽变琥珀（不要刺眼红叉）。展示：你写了 `alway` · 正确 `always` · 音标 · 听读音。主按钮「再写一次」。**不扣阳光、不震动、不音效。**
- 自动下一题间隔固定 800ms，不跟随语速。

**E. 纠错页（phase=retry）**

与默写页相同，但：

- 顶部小字「再写一次，不计分」；
- 字母槽可预填**首字母**作为台阶（仅 retry）；
- 提交 `phase:"retry", attempt_no:1`；
- 写对：绿勾后下一题，不升档；
- 再写错：显示答案，主按钮变成「下一题」（把本题标 done），明天最低档再见。

**F. 完成页**

```text
今日背默完成
复习 3 · 新学 5
首轮正确 7 / 8
+3 阳光
（全对时再显示 +2 全对）
[收下阳光]
```

点「收下阳光」才调 `complete`。已 completed 再进遮罩只展示回顾，按钮改「关闭」。阳光数字以接口返回为准，前端不算。

**G. 中断、关闭、恢复**

- 遮罩点灰色蒙层或系统返回：关闭遮罩，session 仍 `active`。再点「今日单词」从第一个未 done 继续。
- 刷新 / 杀进程：`GET /today` 带回 items.state，按 A 的规则选 phase。
- 断网：检查失败 toast 现有 `e.message`，input 保留；不要本地假装判对。
- 完成页之前没有任何「领取」入口。

**H. 短语与输入边界**

| 输入 | 结果 |
|---|---|
| `Always` / ` always ` | 服务端归一后正确 |
| `get  up`（多空格） | 正确 |
| `getup`（丢空格） | 错误，纠错时展示 `get up` |
| 中文、数字 | 错误 |
| 超 60 字 | 前端截断到 60 再提交 |

**I. 手测清单（本屏必过）**

- 375px 宽：英文不溢出、两个主按钮不换行挤压到 <44px。
- Android WebView：喇叭需先有点击；默写页不可出声。
- 中文输入法切英文后 Enter 能提交。
- 到期词默认不出现看词页；新词必须先看词才能默写。
- 连续点「检查」只产生一次 spell。

#### 5.9.4 家长端配置与诊断（0.5-1 天）

配置、词书管理、高频错词、周趋势摘要。

#### 5.9.5 教材扩充与观察（持续）

Unit 1 运行两周，人工核对错词和每天耗时后再扩 Unit 2；每新增一单元都做教材词表 spot check，不批量从未核对网页抓词。

这使阶段三的合理投入从原先笼统的 3-4 天调整为 **4-5 天开发 + 两周 Unit 1 试运行观察**。

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

### 阶段三：单词背默（P1.5，4-5 天开发 + 两周观察）

- 目标：按 `data/words.seed.multi.json` 导入经人工核对的译林 5A Unit 1 试点词表；实现 §5 的 session 背默闭环，再逐步扩充其他 Unit。
- 涉及文件：`data/words.seed.multi.json`（新）、`scripts/gen_words.py`（新，参照 `scripts/gen_seed.py`）、`backend/db.py`（迁移 030，SQLite/PG schema + RLS）、`backend/main.py`（§5.5 端点）、`frontend/src/api.js`、`frontend/src/App.vue`（今日背默 UI）、`frontend/src/Admin.vue`（配置/词书/错词视图）、`backend/test_words.py`（新）。
- 验收：`cd backend && python3 -m pytest -q` 全绿（session 幂等、spell 档位、跨月 due、跨家庭隔离、奖励事务）；`npm --prefix frontend run build` 成功；Unit 1 词表逐条人工 spot check。
- 防回退：`test_weak_points.py`、`test_task_rules.py` 原样通过；快照验证 ledger 总额、完成记录和 weak_points 行数不因创建/放弃 session 改变；`word_daily`/`word_perfect` 奖励同一 session 只能各写一次。

### 阶段四（可选，P2）：联动与打磨

- 抽卡与成就联动（集齐系列徽章）、周报 `word_stuck` 洞察、精灵进化动画、错词「重点盯」。
- 验收同上模式，不设硬期限。

## 7. 不做清单（本期明确不做）

- 精灵对战、属性克制、排行（多娃 PK 在 PLAN.md 支线 B 已明确禁止）。
- 任何第三方 IP 素材（奥特曼/帕鲁/PvZ/宝可梦……），包括「画得很像」的致敬形象。
- 真实货币充值、广告、任何外部付费入口（阳光永远只能学习获得）。
- SM-2 / FSRS 动态间隔（保留 `streak_right` / `correct_count` 作为升级路径，不现在做）。
- 单词自动进 weak_points 复习队列（诊断权留给家长，见 §5.7.1）。
- 用家长扣分回滚已完成的单词 session。
- 引入任何新的第三方依赖（前端动画纯 CSS；朗读用浏览器 `speechSynthesis`；后端全部标准库 + 现有 FastAPI）。
- 从第三方 App、教材配套光盘或网页抓取、转存单词读音文件。

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
