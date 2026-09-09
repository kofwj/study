# 养成 1.5 · 第 ② 刀今日三格 · 第 ③ 刀宝箱外观与成就打断

> 状态：**规划中，尚未实现。** 相对初稿补了与现码对齐的口径、UI 挂点和坑。  
> ① 主屏伙伴已实现（v0.2.16，见 [ROADMAP_COMPANION.md](ROADMAP_COMPANION.md)）。  
> 不写 ledger 以外的阳光规则；不引入第三方 IP；不新增 npm/pip 依赖；**不新建表**（迁移尾号仍 `029_words`）。  
> 本两刀继续只用 `kid_settings`。

## 0. 两刀分别解决什么

| 刀 | 孩子今天能看见 | 学谁 | 不学谁 |
|---|---|---|---|
| ② 今日三格 | 复习 / 打卡 / 学习各一环，关满精灵闪一下 | 苹果健身圆环：今天关环 | 学期 KPI、把今日清单清空、累计 5000 阳光 |
| ③A 宝箱外观 | 开箱掉颜色/贴纸；重复变星尘升星 | 小红书抽券、Habitica 掉装备 | 付费抽卡、稀有度、排行榜 |
| ③B 成就打断 | 打完卡当时弹出新徽章 | 游戏掉装备打断 | 登录弹历史 NEW |

① 解决「主屏有活物」。没有 ②，活物仍和今日任务脱节；没有 ③A，宝箱仍是阳光换阳光；没有 ③B，徽章仍要自己点墙。

**实施顺序：③B → ② → ③A**（③B 全是现成数据；③A 改掉落期望，单独回归）。不要和阶段二抽卡同一 PR。

---

# ② 今日三格

## 2.1 产品规则（学圆环，不学 KPI）

三条环，**每条今日关一格即可**，不是把今日清单清空。`todayRemaining`（「今天还有 N 项」）继续数剩余件数；圆环是另一套「今日目标开/关」。两行可以并存。

| 环 | id | 何时算关上 | 今日完全没有这类事时 |
|---|---|---|---|
| 复习 | `review` | `_due_queue` 长度为 0 | **视为已关**，文案「今日没有到期」。空队列不是失败。`applicable` 恒为 true |
| 打卡 | `daily` | 今日 ≥ 1 条 `kind=daily` 且 `status=completed`（未被 cancel 的 ledger 对冲） | 家里没配每日任务：`applicable=false`，分母变小 |
| 学习 | `study` | 今日 ≥ 1 张单元卡完成 **或** 今日单词 session `state=completed` | 单词未开 **且** 本课下一步为空 **且** 今日也没完成过单元卡：`applicable=false` |

单词**并进学习环**，不单独开第四环。签到（`/api/checkin`）**不是**打卡环——打卡环只看 `daily_tasks`。

关满（所有 `applicable` 的环都 `on`）且今天还没谢过幕：

- 一句 **「今天长了一点」**；有自定义名则 `小芽今天长了一点`
- 顶栏精灵 CSS 闪 1.2s（`transform`/`filter`，**不要改 `box-shadow`**，以免盖掉连击光晕）
- 不进化、不发阳光、不写 ledger
- `kid_settings.rings_all_ack = YYYY-MM-DD`（`db.today()`），同一天只闪一次
- 取消任务导致环重新打开：不播「缩小」；ack 日期仍在则今天不再闪

不关环、不扣分、不进「今天怎么做」惩罚。明天 0 点（`db.today()`）自然重置。

## 2.2 为什么复习环可以「空=已关」

孩子不能自己把 `weak_points` 判掉（诊断权在家长，`admin_wp_judge`）。若「有到期才算关环」，没到期的日子永远缺一环，圆环就变成学期待办。健身圆环是「今日目标」；没到期复习 = 今日目标为 0 = 环是满的。

有到期时：环空心琥珀，文案「复习还差告诉家长」。家长 judge 完队列空了，环关上。点环滚到 `#sec-review`。

## 2.3 不要用前端剩余条数当关环口径

现码陷阱：

| 现码 | 含义 | 不能当环 |
|---|---|---|
| `reviewDue.length` | 到期件数 | 件数>0 只说明未关；**0 才是关**。对 |
| `dailyTodo` | **还没打**的每日 | 关环看「今天已完成 ≥1」，不是 `dailyTodo.length===0` |
| `studyNext` | 每科当前一张未做单元卡 | 关环看「今天做成了 ≥1 张或单词 session」，不是把 `studyNext` 清空 |
| `todayRemaining` | 复习+未打卡+学习下一步+未完单词 | KPI 心态，禁止当 `all` |

例：家里 4 条每日，完成跳绳 1 条 → 打卡环关上，`dailyTodo` 仍有 3。这就是「一格即可」。

## 2.4 服务端计算（优先，挂在 `GET /api/tasks`）

`rings_info(c, kid)` 与 `companion_info` 并列。`GET /api/tasks` 已会 `c.commit()`（伙伴首次静默写 seen）；**本函数只读，禁止在 GET 里写 `rings_all_ack`**，否则刷新看不见闪。

```json
"rings": {
  "date": "2026-09-09",
  "review": { "on": true,  "applicable": true,  "due": 0, "label": "今日没有到期" },
  "daily":  { "on": true,  "applicable": true,  "done": 2, "label": "打卡 2" },
  "study":  { "on": false, "applicable": true,  "done": 0, "label": "还差 1 格学习" },
  "closed": 2,
  "need": 3,
  "all": false,
  "flash": false
}
```

- `applicable=false`：不进 `need`，前端不画这环
- `closed` = applicable 且 on 的条数
- `need` = applicable 条数（复习恒计入，故 need ≥ 1）
- `all` = `need > 0 && closed == need`
- `flash` = `all && rings_all_ack != today`

`POST /api/rings/ack`：把 `rings_all_ack` 写成 `db.today()`。幂等。无 ledger。未关满也允许写（防前端误调；测试不断言必须 all）。

### 2.4.1 SQL / 复用（必须与现接口同口径）

**复习**（与 `GET /api/review-due` 相同）：

```python
due = _due_queue(c, kid)          # open + review_due_at <= db.today()
review.on = len(due) == 0
review.due = len(due)
```

**打卡**：

```python
# 配置：与 tasks() 同一条
# SELECT * FROM daily_tasks WHERE family_id IS NULL OR family_id=?
applicable = len(dts) > 0
done = COUNT completions
        WHERE kid_id=? AND date=today AND kind='daily' AND status='completed'
        AND NOT EXISTS (SELECT 1 FROM ledger WHERE reason='cancel' AND ref_id='cmp-'||completions.id)
on = done >= 1
```

取消打卡走现有 `cancel` → 环会重新打开。

**学习**：

```python
unit_done = COUNT completions
            WHERE kid_id=? AND date=today AND kind='unit' AND status='completed'
            AND 同样排除 cancel 对冲
word_done = 0
if db._has_table(c, "word_sessions"):
    word_done = EXISTS word_sessions
                WHERE kid_id=? AND study_date=today AND state='completed'
study.on = unit_done >= 1 or word_done

# applicable
words_on = kid_settings.words_enabled == "1"     # words.CFG_ENABLED，缺省 "0"
has_next = 存在一张当前学期（+ custom）单元任务：not done、not past、not locked
           # 口径对齐前端 studyNext / locked_task_ids / is_past
study.applicable = words_on or has_next or unit_done >= 1
```

`words_enabled=0` 且课程全部 past/done/locked、今日也没完成单元卡 → 学习环不出现。已全部学完的老用户不会永远缺一环。

单词 session `abandoned`（跨日作废）**不算**关环。

## 2.5 UI（`frontend/src/App.vue`）

挂在「今天」标题下、现有 `.today-summary` **左侧**（或取代其右侧空白），不要新开一页，不要塞进顶栏（顶栏已被伙伴+药丸占满）。

```text
  (橙)  (蓝)  (绿)     今天还有 4 项
   复习  打卡  学习     复习 2 · 打卡 3 · …
```

- 环直径 36–44px，SVG `circle` 或 CSS `conic-gradient` 二选一；未关浅底+缺口，已关实心。颜色用现有 `--accent` / `--brand` / `--ok`，不要新色板
- `need=2` 时只画两环，不要画一个永远空的假环
- 点环：`scrollIntoView` 到 `#sec-review` / `#sec-daily` / `#sec-study`（给现有 section 补 id；单词在英语每日区，学习环滚到本课下一步，没有则滚到单词卡）
- 关满文案出现在环右侧，**不挡任务卡**、不是全屏遮罩
- 375px：三环优先，文案可藏（`rings.all` 时用 toast「今天长了一点」兜底）

精灵闪：`.avatar.companion.pulse` 1.2s。`overflow: hidden` 的头像圈不要靠 box-shadow 做闪。播完（`animationend` 或 1.2s timer）调 `api.ackRings()`。若当时有全屏遮罩（进化/徽章/升级/开箱），**等遮罩都关掉再闪**，避免孩子看不见。

## 2.6 与庆祝队列

同时只显示一层全屏。闪环不是全屏，排在最后：

1. 精灵进化（① 已做，`companionEvolve`）
2. 新徽章（③B）
3. 等级升级（已做，`pendingLevelUp` / `celebrate`）
4. 开箱结果（用户点的，开着时也不闪）
5. 三格关满闪（本刀）

## 2.7 测试 `backend/test_rings.py`（学 `test_companion.py` 的 TestClient 套路）

| 用例 | 断言 |
|---|---|
| 新号，无到期、无每日、无单元可做、单词关 | review on，daily/study 不适用，need=1，all=true，flash=true |
| 有 2 条到期 | review.on=false，all=false |
| 4 条每日，完成 1 条 | daily.on=true（一格即可） |
| 仅单词 session 完成、无单元卡 | study.on=true |
| 仅完成 1 张单元卡、单词关 | study.on=true |
| 课程全部完成且单词关、今日无单元完成 | study.applicable=false |
| 同一天两次 GET all | 只有 ack 前 flash=true；ack 后 false |
| GET 不写 ack | 连拉两次 flash 仍 true |
| ack 无 ledger | COUNT 不变 |
| 跨日 | 昨天 ack 不影响今天 flash |
| 完成后再 cancel 每日 | daily.on 变 false；ack 仍在则 flash 仍 false |

工期：**0.5 天**。

---

# ③B 成就打断打卡（先做）

## 3.7 现在的问题

`achievement_earned.seen=0` 已有，`pickUnseenAch()` 已按传说>金>银>铜排序，但：

1. **只在 `openAch()` 里调用**——打完卡 `refresh()` 不弹。
2. **`.ach-pop` 写在 `v-if="achOpen"` 墙里面**（`App.vue` 约 1300–1348 行）。不打开整面墙就无法显示弹层。这是本刀最大的结构改动。

孩子看不到「刚刚得到」。角标只是顶栏一个数字。

## 3.8 规则

写完成成功之后，若有**本回合新徽章**，立刻弹现有 `ach-pop` 样式，**不打开成就墙**（`achOpen` 保持 false）。关掉后再刷新孩子对任务列表的感知——视觉上庆祝盖住列表；数据可以先拉。

写入路径（`refresh({ fromAction: true })`）：

| 调用点 | fromAction |
|---|---|
| `onMounted` 登录 | **否**（历史 NEW 只留顶栏角标） |
| Admin `@switched` 切娃 | 否 |
| `toggleTask` 完成 | 是 |
| `toggleTask` / `cancelDaily` 取消 | **否**（不弹「徽章收回」） |
| `submitDaily` | 是 |
| `checkin` | 是（连击类徽章） |
| `wordCollect` → `wordsComplete` | 是 |
| `openBox` 成功 | 是，但等开箱遮罩关掉再弹徽章 |
| `redeem` | 否 |

判定（登录已拉过成就列表之后）：

```text
prevUnseen = 刷新前 achNew 的 id 集合
刷新后 newHit = achNew 且 id 不在 prevUnseen
按传说>金>银>铜排序，弹第一个
关掉 → mark-seen → 再弹下一个 newHit
```

不要用 `earned_at` 墙钟对时（客户端/服务器时钟会偏）。id 集合足够：成就只插入一次，不会「再解锁」。

`complete` 接口可额外返回 `new_achievements: []` 以免再拉；**非必须**，因 `refresh` 已 `api.achievements()`。若加字段，前端仍以 refresh 后的列表为准，避免两套口径。

取消打卡 **不弹**「徽章收回」。徽章行不删（现 `_sync_achievement_earned` 只插入不删除）——取消导致计数回落时墙会显示未点亮，但已 seen 的记录可留。本刀不改这套。

## 3.9 前端结构

把 `.ach-pop` 从成就墙 `mask` 里**搬出来**，与 `companionEvolve` / `.celebrate` 同级。墙内点徽章详情仍用同一组件。

庆祝队列接到现有 `pendingLevelUp`：

```text
closeCompanionEvolve
  → 若 pendingNewAch：弹徽章（先于升级）
  → 否则若 pendingLevelUp：showLevelCelebrate
closeAchModal（打断模式）
  → 下一枚 newHit 或升级
升级 2.8s 结束
  → tryPulseRings()     # ② 的闪
```

`openBox`：先显示开箱遮罩；`refresh({ fromAction: true })` 把 newHit 推进队列，**开箱遮罩关闭后**再进入队列（避免箱和徽章叠两层）。

登录第一次 `refresh()` 不传 fromAction：老未读每天不会吓一跳。

## 3.10 测试 / 手测

自动化难画 Vue 遮罩，后端不新增接口也可。手测清单：

- 完成第 1 张卡：不点成就墙也弹出「初来乍到」；关掉 `seen=1`，顶栏角标 -1
- 登录有历史 NEW：只角标，不弹
- 一次完成同时进化+徽章+升级：先进化，再徽章，再升级，不叠两层
- 取消刚打的卡：不弹
- 开箱触发 `box5`：先看箱，关掉后再看徽章

工期：**0.5 天**。

---

# ③A 连击宝箱改外观

## 3.1 现在的问题

`open_box`（`backend/main.py`）：每连击 3 天一箱，`random.randint(3, 10)` 阳光，`reason=box`。遮罩只显示 `+N`。伙伴外观不变。

`BOX_INTERVAL=3`、`kid_settings.box_opened` 游标、`box5` 按 opened 计数——**都不改**。

## 3.2 掉落（仍 3 天一箱）

一次开箱 **必出 1 个外观** + **少量阳光**：

| 项 | 规则 |
|---|---|
| 阳光 | `randint(1, 3)`，仍 `insert_ledger(..., 'box', f'box-{n}')`。比现在 3–10 低，把惊喜让给外观 |
| 外观池 | 8 色 + 8 贴纸 = 16，全是 CSS class，无角色图、无第三方剪影 |
| 未拥有 | 在未拥有集合里均匀随机 1 件，写入 owned，**自动装备**该件 |
| 已拥有（重复） | 不进 owned，`dust += 3`，**不改**当前装备 |
| 池子用尽 | 阳光 1–3 + 尘 3；`item` 仍给一个池内 id 方便动画「变成星尘」，`duplicate=true` |
| 升星 | `while dust >= 12 and stars < 3: dust -= 12; stars += 1`。满 3 星后尘继续加，不再升 |
| 装备 | `POST /api/companion/equip { tint?, sticker? }`，必须已 owned 且在白名单 |

色（底色，覆盖 `stage-*` 的 background，**不改图标**）：  
`tint-sun` `tint-sky` `tint-leaf` `tint-grape` `tint-rose` `tint-sand` `tint-mint` `tint-night`

贴纸（圆圈**外**角 12px 小标，CSS 伪元素或 span）：  
`dot-star` `dot-leaf` `dot-drop` `dot-spark` `dot-moon` `dot-heart` `dot-cloud` `dot-seed`

贴纸**不是**帕鲁/奥特曼/植物剪影。星（dust 升上来的 1–3）用 `★` 小点，和贴纸不是同一层。

## 3.3 只加 kid_settings

key = `companion_bag`，JSON：

```json
{
  "owned": ["tint-sun", "dot-star"],
  "tint": "tint-sun",
  "sticker": "dot-star",
  "dust": 3,
  "stars": 0
}
```

非法 class、未知键丢弃。解析失败当空袋。读写经 `get_kid_setting` / `set_kid_setting`。

`companion_info` 增加：`tint` `sticker` `stars` `dust` `owned`（小卡换装需要 owned；顶栏只用前四个）。

尘/星**不写 ledger**（不是阳光）。`earned()` / 指纹口径不变。

## 3.4 `POST /api/open_box` 返回

```json
{
  "delta": 2,
  "item": "tint-sky",
  "kind": "tint",
  "duplicate": false,
  "dust": 0,
  "dust_gain": 0,
  "stars": 0,
  "companion": { },
  "streak": 9,
  "level": { }
}
```

重复时 `duplicate=true`，`dust_gain=3`。无箱仍 409，settings 不动。

前端开箱遮罩：先 `+N 阳光`，再展示色块/贴纸；重复则色块碎成「星尘 +3」，若刚好升星再给 1 个 ★。`boxResult` 从数字改成整个响应对象。

## 3.5 CSS 坑（头像现在会裁贴纸）

`.avatar { overflow: hidden }`（`App.vue` 约 1445 行）。贴纸/星星必须做在**包裹层**：

```html
<span class="avatar-wrap" :class="[companion.tint, companion.sticker ? 'has-sticker' : '']">
  <button class="avatar companion" :class="['stage-…', companion.tint, companion.aura && 'aura-'+…]">
  <i v-if="companion.sticker" class="companion-dot" :class="companion.sticker" />
  <i v-if="companion.stars" class="companion-stars">★ × n</i>
</span>
```

- `tint-*` 写在 `stage-*` **之后**，只改 `background`
- 光晕仍打在 `.avatar` 上
- 小卡 `.companion-big` 同样吃 tint/sticker
- 换装区：两行 chip（色 / 贴纸），点已拥有的调用 equip；未拥有灰掉不可点

## 3.6 防通胀与保底

- 阳光期望从约每天 +2（3–10 的均值 6.5 / 3 天）降到约每天 +0.7（均值 2 / 3 天），外观补感知
- 16 抽内未集满属正常（3 天一箱；有重复更长）
- **不做** 30 抽传说保底（那是阶段二抽卡）。箱子池无稀有度，件件普通
- 尘不能兑换阳光或商店物品

## 3.7 测试（扩现有或新 `backend/test_box_cosmetics.py`）

| 用例 | 断言 |
|---|---|
| 无箱 | 409，bag 不变，ledger COUNT 不变 |
| 新色 | owned+1，delta∈[1,3]，ledger 一笔 `reason=box`，companion.tint=该色 |
| 重复 | owned 长度不变，dust+3，装备不变 |
| 尘 12 | stars=1，dust 余数 0 |
| 已 3 星再重复 | stars 仍 3，尘继续加 |
| equip 未拥有 / 非法 id | 400 |
| 开箱 earned 增加 = delta | 尘不加 earned |
| 家庭 B 读不到家庭 A 的袋 | 隔离 |

工期：**1 天**。

---

## 4. 庆祝总队列（两刀落地后）

`App.vue` 只保留一层全屏：

1. `companionEvolve`（①）
2. 抽出墙外的 `ach-pop`（③B，仅 fromAction 的 newHit）
3. `celebrate` 升级（已有）
4. `boxOpen` 开箱（用户点击，插在徽章前如果箱还开着）
5. 顶栏 `.pulse` + 「今天长了一点」（②，非全屏）

登录：不进 2、不进 5（5 若 flash 且无遮罩，登录当天已经关满可以闪一次——允许，因为这是今日状态不是历史惊吓。若不想登录闪：仅 `fromAction` 后才 pulse。**采用后者**：登录已关满只显示实心环+文案，不闪；当天第一次从「未满→满」的 refresh 才闪）。

## 5. 明确不做

- 第四环、周环、月环、学期进度条当环
- 关不满扣阳光 / 断环惩罚 / 关环发阳光
- 签到当作打卡环
- 宝箱付费、概率公示页（无氪金；家长以后若要可在小卡展示「箱子出外观+1～3 阳光」一句）
- 贴纸画成第三方 IP
- 尘兑换阳光或商店物品
- 新表、新迁移、新依赖
- 和阶段二蛋/图鉴同一 PR

## 6. 涉及文件

| 刀 | 文件 |
|---|---|
| ③B | `frontend/src/App.vue`（`refresh({ fromAction })`、把 `ach-pop` 搬出墙、接入 `closeCompanionEvolve`） |
| ② | `backend/main.py`（`rings_info`、tasks 字段、`POST /api/rings/ack`）、`frontend/src/api.js`、`frontend/src/App.vue`（`.today-summary` 左侧三环 + pulse）、`backend/test_rings.py` |
| ③A | `backend/main.py`（`open_box`、`companion_info`、equip、白名单）、`App.vue` 开箱遮罩 + 小卡换装 + `avatar-wrap`、测试 |

`backend/db.py` **不改**。

## 7. 验收（孩子一句话）

- 「今天三个圈，关完小芽会闪一下，说今天长了一点。」
- 「开箱子会出颜色或小标，出过的变成星星粉末。」
- 「打完卡徽章自己跳出来，不用去点成就墙。」
