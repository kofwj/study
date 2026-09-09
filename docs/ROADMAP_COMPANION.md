# 主屏伙伴计划书（养成 1.5 · 第 ① 刀）

> 状态：**已实现（v0.2.16）。**  
> 目标：孩子打开「今天」，主屏上有一只会长大的阳光精灵；阶段只读 `earned()` 与 `streak()`，**不写 ledger、不发阳光、不掉级。**  
> 对照：Habitica 宠物 / ClassDojo 小怪物 / 多邻国猫头鹰——主屏有活物，而不是只改等级六个字。  
> 总图见 [ROADMAP_GAMEIFICATION.md](ROADMAP_GAMEIFICATION.md) §3.3；抽卡图鉴仍是阶段二，本刀不做。

## 0. 结论

| 问题 | 决定 |
|---|---|
| 养什么 | 每娃一只「阳光芽」，四阶段：蛋 → 芽 → 苗 → 花 |
| 阶段怎么算 | 只读累计阳光 `earned()`，阈值写死在代码里，与 10 档等级分开 |
| 连击干什么 | 不改阶段；满 7/14/30 天给花环光晕（只读 `streak()`） |
| 存什么 | 只用现有 `kid_settings`：名字、上次看过的阶段。**不新建表、不新迁移**（当前尾号已是 `029_words`） |
| 放哪 | 「今天」标题左侧，替代字母头像；点开改名 + 看下一阶段还差多少 |
| 进化仪式 | 阶段比 `companion_stage_seen` 高时全屏庆祝一次，然后写回 seen |
| 老数据 | 已有很多阳光的孩子第一次打开直接停在对应阶段，**静默写入 seen，不弹进化**（避免「上线当天突然开花」） |

## 1. 为什么这一刀够用

当前顶栏是余额、连击、等级名、成就、宝箱，全是数字。孩子无法指着屏幕说「这是我的」。

本刀只做三件事：

1. 主屏有一只精灵，阶段随累计阳光变。
2. 孩子能起名（1–8 字）。
3. 跨越阶段时庆祝一次。

不做：抽卡、图鉴、对战、上传涂色、今日三格、宝箱改外观。那些仍按总路线图排期。

## 2. 阶段表（与等级解耦）

等级仍是 10 档（0/50/150/…/5000，`backend/db.py` `RANKS`）。精灵只有 4 段，避免「等级变了精灵也变、两套名字打架」。

| `stage` | 名字 | 累计阳光 `earned` | 约等于 | 主屏样子（CSS/emoji，不引图库） |
|---|---|---:|---|---|
| `egg` | 阳光蛋 | 0 | 刚开始 | ⚪ 蛋 |
| `sprout` | 阳光芽 | ≥ 50 | 过「阳光小苗」附近 | 🌱 |
| `leaf` | 阳光苗 | ≥ 350 | 过「阳光达人」 | 🌿 |
| `bloom` | 阳光花 | ≥ 1200 | 过「阳光学霸」 | 🌼 |

进度条：到下一阶段还差 `next_need - earned` 阳光。已是 `bloom` 则 100%，文案「开完花了，继续攒阳光也不会掉」。

**连击光晕（不改 stage）：**

| streak | 光晕 |
|---:|---|
| 0–6 | 无 |
| ≥ 7 | 细橙环 |
| ≥ 14 | 橙环 + 小火花 |
| ≥ 30 | 金环 |

断连击只摘光晕，**不缩小阶段**（与消费不掉级同一哲学）。

阈值写在 `backend/main.py` 常量 `COMPANION_STAGES`，不进数据库、家长不可改（和成就稀有度一样）。

## 3. 数据：只加 kid_settings 键

已有 `kid_settings(kid_id, key, value)`（`backend/db.py`）。本刀新增：

| key | 含义 | 默认 |
|---|---|---|
| `companion_name` | 孩子起的名 | 空 → 展示「阳光芽」 |
| `companion_stage_seen` | 已经看过庆祝的阶段 id | 空 → 第一次 GET 时写成当前 stage，不庆祝 |

不存 stage 本身：每次用 `earned()` 现算，取消任务导致 earned 回落时精灵外观可以退回上一阶段（只读映射），但 **不弹「退化」动画**，避免惩罚感。`companion_stage_seen` 只升不降。

读写走现有 `get_kid_setting` / `set_kid_setting`，按 kid 隔离。SQLite 无 RLS；PG 路径仍经 `get_conn()` + `apply_scope`。

## 4. API

不单独开资源表。挂在孩子已有接口上，少一次请求。

### 4.1 `GET /api/tasks` 增加 `companion`

现有已返回 `level.earned`、`streak`（`backend/main.py` `tasks()`）。增加：

```json
"companion": {
  "stage": "sprout",
  "stage_name": "阳光芽",
  "name": "小芽",
  "earned": 80,
  "next_stage": "leaf",
  "next_stage_name": "阳光苗",
  "next_need": 350,
  "progress": 10.0,
  "aura": null,
  "evolve": false
}
```

`aura` 为 `null` / `"week"` / `"fortnight"` / `"month"`，由 streak 映射。

`evolve`：当前 `stage` 的序号 **大于** `companion_stage_seen` 时为 `true`。首次无 seen 时服务端 **当场写成当前 stage** 且 `evolve=false`（老用户静默对齐）。

计算函数（示意，须走测试）：

```python
COMPANION_STAGES = [
    ("egg", "阳光蛋", 0),
    ("sprout", "阳光芽", 50),
    ("leaf", "阳光苗", 350),
    ("bloom", "阳光花", 1200),
]

def companion_info(c, kid=None):
    kid = kid or kid_id()
    e = earned(c, kid)
    s = streak(c, kid)
    # 选不超过 e 的最高档
    ...
```

### 4.2 `POST /api/companion/name`

```json
{ "name": "小芽" }
```

- 登录孩子；`strip` 后 1–8 字，禁止空。
- 写入 `companion_name`。
- 400：「给它起个 1 到 8 个字的名字」。
- 返回更新后的 `companion` 对象。

### 4.3 `POST /api/companion/ack-evolve`

进化庆祝关闭时调用。把 `companion_stage_seen` 写成**当前** stage。幂等。不发阳光。

前端若漏调：下次 `GET /api/tasks` 仍 `evolve=true`，会再弹一次（与成就 `seen=0` 同一保守策略）。

家长端本刀不加页面。

## 5. 孩子端 UI（`frontend/src/App.vue`）

### 5.1 放哪

现有顶栏左侧是彩色字母头像（`avatar` + `avatarLetter`）。**字母头像改为精灵**，仍占同一位置，不新占一行（避免挤掉今日任务）。

```text
[ 🌱 ]  9月9日 星期二
        乐乐
        小芽 · 阳光芽
        再 270 阳光到阳光苗
```

- 精灵圈直径与现头像一致（约 40–48px）。
- 副文案一行：有自定义名则 `小芽 · 阳光芽`，否则只 `阳光芽`。
- 「再 N 阳光到阳光苗」字号小于名字；`bloom` 不显示再得。
- 点精灵：打开小卡（不要全屏商店那种大遮罩）。

小卡：

- 大精灵 + 光晕
- 下一阶段进度条（复用 `.next-bar`）
- 改名：一个输入 + 「保存」，调 `POST /api/companion/name`
- 关闭

### 5.2 进化庆祝

复用现有 `.celebrate`（升级已有 2.8s 撒花）。`companion.evolve===true` 时：

1. 全屏：蛋破开 / 芽变苗 等 CSS，标题「长大了」，名字 + 新 `stage_name`
2. 关闭或 2.8s 后调 `ack-evolve`
3. 与等级升级同时发生时：**先精灵进化，再等级**（精灵是新主视觉）；不要两层叠在一起

断连击、earned 因取消回落：**不庆祝、不播缩小动画**。

### 5.3 样子（禁止第三方 IP）

纯 CSS + 现有 Lucide / 已有 rank 图标语义，**不引入角色图、不画奥特曼/帕鲁/豌豆**。

建议：圆形底（蛋灰 / 芽绿 / 苗深绿 / 花暖黄）+ 中央 emoji 或 `Sprout`/`Leaf`/`Flower` 图标。光晕用 `box-shadow`。Android WebView 若 emoji 不一致，以 Lucide 图标为准。

### 5.4 `frontend/src/api.js`

```js
companionName: (name) => j('/api/companion/name', { method: 'POST', ...body({ name }) }),
ackCompanionEvolve: () => j('/api/companion/ack-evolve', { method: 'POST' }),
```

`refresh()` 已拉 `api.tasks()`，不必加新并行请求。

## 6. 铁律

1. 任何 companion 接口 **不得** `insert_ledger`。
2. 取消任务、扣分、兑换：阶段只随 `earned()` 变；扣分不进 earned，精灵不缩小；兑换不进 earned，同样不缩。
3. 不改 `RANKS`、不改成就、不改宝箱期望值。
4. 不新增 npm/pip 依赖。
5. 多娃：每 kid 自己的 settings，孩子端不展示其他娃的精灵。

## 7. 测试（`backend/test_kids.py` 或新 `test_companion.py`）

| 用例 | 断言 |
|---|---|
| earned=0 | stage=`egg`，`evolve=false`，seen 被写成 egg |
| earned=50 新号 | 第一次 GET：stage=`sprout`，seen 对齐，`evolve=false` |
| seen=egg 且 earned 已到 50 | `evolve=true`；ack 后 false |
| 改名 1–8 字 | 读回一致 |
| 空名 / 9 字 | 400 |
| 家庭 B 读不到家庭 A 的名字 | 隔离 |
| ack 不产生 ledger 行 | COUNT 不变 |
| streak=7 | `aura=week`，stage 仍只由 earned 决定 |

前端手测：375px 顶栏不挤爆；进化与升级不同时叠两层；改名后刷新仍在。

```bash
cd backend && python3 -m pytest -q
npm --prefix frontend run build
```

## 8. 涉及文件

- `backend/main.py`：`COMPANION_STAGES`、`companion_info`、tasks 字段、两个 POST
- `frontend/src/api.js`：两个方法
- `frontend/src/App.vue`：头像位、小卡、进化庆祝
- `backend/test_companion.py`（新）或扩 `test_kids.py`
- **不改** `backend/db.py` 迁移表

工期：**0.5–1 天**（纯展示 + 两个小接口）。

## 9. 明确不做（本刀）

- 抽卡、星尘、涂色上传、多只精灵
- 今日三格（养成 1.5 的 ②）
- 宝箱改掉外观（③）
- 精灵饥饿/死亡/喂食（制造焦虑，不适合家庭学习）
- 家长替孩子改名以外的养成数值

## 10. 和阶段二抽卡怎么接

本刀的「一只主屏芽」以后可以是图鉴里的**展示位**：抽到的贴纸只改光晕/颜色，不换这只芽的物种。阶段阈值继续只读 earned。抽卡消耗阳光走 ledger `gacha`，不影响本刀的 seen/name。
