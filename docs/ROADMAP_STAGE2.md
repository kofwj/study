# 阶段二 · 阳光图鉴（收集，不是十连抽卡）

> 状态：**2.0 已落地**（迁移 `034_sprites`）。②③ 仍搁在 [ROADMAP_RINGS_BOX.md](ROADMAP_RINGS_BOX.md)，本文不改那两刀。  
> 取代总图 [ROADMAP_GAMEIFICATION.md](ROADMAP_GAMEIFICATION.md) §4.2 初稿的「单抽 30 / 十连 270 / 70·25·5 / 30 保底 / 涂色上传 / 迁移 029_sprites」。  
> 主屏芽已在 v0.2.16，见 [ROADMAP_COMPANION.md](ROADMAP_COMPANION.md)。图鉴是芽的朋友册，**不换物种。**  
> 铁律：ledger 唯一阳光真相；消费不掉级；无第三方 IP；无新 npm/pip；无真实货币。  
> 迁移尾号现在是 `033_bank_interest`，本阶段 `034_sprites`。

## 0. 一页结论

| 孩子要看见 | 家长要守住 |
|---|---|
| 开箱子孵出一只小东西，图鉴格子亮起来 | 阳光还去兑「看动画」，不要进卡池 |
| 重复也不亏，变成能喂给喜欢那只的星尘 | 没有 SSR、没有「再抽一次」按钮 |

2.0 只做一件事：**现有连击宝箱（每 3 天）改成「1–3 阳光 + 一枚未拥有精灵」**，加一页 12 格图鉴。

不新开抽卡口、不花阳光买随机、不给主屏芽第二套星尘。

工期 **2.5–3.5 天**。孩子验收句：「开箱子会孵出一只小精灵，图鉴一页一页亮起来；重复的变成星星粉末。」

---

## 1. 初稿为什么必须改

1. 商店「看动画 30 分钟 = 30 阳光」。初稿一发单抽 = 一次真奖励打成一次随机。  
2. 顶栏已有阳光芽。再抽「主角」= 两套养成。  
3. ③A 的 companion 星尘和本阶段图鉴星尘不能并存。尘只这一套，对象是图鉴。  
4. `029` 已是单词。  
5. 涂色上传与「无新依赖、本机 SQLite、Android WebView」不合。  
6. 70/25/5 + pity 是二游卡池，不是小学生书桌。

随机惊喜改挂在**已经在做的开箱仪式**上。

---

## 2. 调研：机制拆到能抄的那一层

只对照**收集层**，不对照战斗。来源：维基百科 API 摘要（2026-09 抓取）、Habitica 官方玩法（开源项目长期公开）、产品公开机制。小红书仍用总图 §2.1 的二手转载。

### 2.1 一张对照表（读完就能定规则）

| 产品 | 收集物怎么来 | 重复怎么办 | 主屏是谁 | 货币几套 | 我们抄 | 我们禁 |
|---|---|---|---|---|---|---|
| Habitica | 做真实习惯**掉**蛋/药水/食物 | 喂宠物变坐骑 | 可换装的冒险者 | 金、宝石、蛋、药水、食物、沙漏… | 掉落来自正事；外观不改任务难度 | 血条、负向习惯扣血、货币地狱 |
| Finch | 完成自我照顾 → 彩虹石 → 衣服 | 已有衣服不再给 | **一只**小鸟 | 石 + 订阅装 | 一只伙伴 + 衣柜 | 订阅、社交庭院 |
| 多邻国 | 课末开箱；宝石商店**标价** | 已有皮肤商店会标已拥有 | 一只猫头鹰换装 | XP、宝石、连击 | 开箱当仪式；商店若有必须明码 | 联赛排行、连击恐吓、十连 |
| Forest 专注森林 | 专注结束种一棵进自己的林子 | 同种可重复，林子变密 | 林子就是图鉴 | 金币买树种（明码） | 视觉林/册；树种商店明码 | **中途退出树枯死**（损失厌恶） |
| 蚂蚁森林 | 低碳行为积「绿色能量」→ 种真树，证书进相册 | 能量继续攒下一棵 | 自己的林子 | 只有能量 | 正事变收藏；证书相册 | 偷好友能量（变相 PK） |
| 动森博物馆 | 抓到/钓到 → 捐赠一格；第一次有 New 音效 | 多余卖掉换铃钱 | 玩家角色 + 岛 | 铃钱 | **空格子剪影 + New 仪式 + 重复变货币**；馆藏地位平等 | 成百种、交易市场 |
| 星露谷物语博物馆 | 捐赠矿物/文物填 95 格 | 多余卖掉 | 农场主 | 金 | 捐满里程碑给奖（我们用成就 2.1） | 战斗、矿井 |
| Neko Atsume | 买玩具食物吸引猫，相册+纪念品 | 猫反复来；纪念物收集 | 庭院 | **银鱼+金鱼** | 相册、来了就看 | 双货币、稀有猫、闲置等待 |
| 宝可梦图鉴（只学 UX） | 看见/抓住两态 | 重复可放生/交换 | 训练家 | 多种 | 剪影、看见 vs 拥有 | 捕捉率、闪光、IP、场地捕捉（帕鲁案） |
| 超级马里奥奥德赛 | 探索拿到 Power Moon，清单勾掉 | 月亮不重复编号 | 马里奥 | 金币 | 「拿到了！」一声就够 | 平台动作 |
| Apple 健身奖章 | 关环/挑战发奖章 | 奖章不重复发 | 圆环 | 无 | 奖章墙；关环已是 ② | 月挑战 KPI |
| ClassDojo | 老师给点；每生一个小怪物 | 不收集第二只 | **一只**可换装怪物 | Dojo 分 | 身份一只 | 当众加减分（有教育界批评） |
| 小红书积分卡 | 涂满 20 格抽一张真券 | — | 纸卡 | 星/分 | 攒满才抽；积分主用途兑真奖励 | 每次打卡都抽 |
| 扭蛋 / Kinder | 一开一物 | 重复靠换 | — | 真钱 | 一箱一物 | 真钱、盲盒稀有度 |
| Khan Academy | 能量点**明码买**头像 | 已买不再买 | 头像 | 能量点 | 2.1 若卖蛋必须明码 | 能量点通胀 |
| 电子宠物 / QQ 宠物 | 喂养 | — | 一只 | 真钱道具 | — | **饿死、付费续命** |
| 原神十连 | 花抽卡石 | 重复转尘 | 角色池 | 原石/纠缠 | 重复转尘这一句 | 整套卡池 |

### 2.2 每条「抄」落成我们的一条规则

1. **正事才开箱**（Habitica 掉落、多邻国课末箱、小红书涂满卡、蚂蚁森林能量）  
   → 不新做抽卡按钮。蛋绑在已有 `BOX_INTERVAL=3` 的连击宝箱。

2. **一只身份 + 一册收藏**（Finch、ClassDojo、多邻国猫头鹰）  
   → 顶栏芽零改 stage 算法。图鉴是册子。

3. **格子平等、剪影、New**（动森博物馆、星露谷、宝可梦图鉴 UX、马里奥月亮清单）  
   → 12 只无 SSR。未拥有灰剪影。开箱那一下就是 New，不另做稀有度光效。

4. **重复变收藏货币，不白抽**（动森铃钱、星露谷卖掉、Habitica 食物、二游「尘」里唯一可学的一句）  
   → 星尘只升图鉴星，不进 ledger。

5. **货币 ≤ 2 套**（Habitica 反面教材：蛋+药水+食物+金+宝石…社区长期抱怨「玩收集先学会计」）  
   → 阳光（真奖励）+ 星尘（升星）。蛋不是库存，是开箱动画。

6. **禁止损失厌恶养成**（Forest 枯树、Tamagotchi/QQ 宠物饿死、Habitica 掉血）  
   → 断连击不收回已得精灵。不饥饿。

7. **禁止社交掠夺与排行**（蚂蚁森林偷能量、多邻国联赛、PLAN.md 已禁多娃 PK）  
   → 图鉴不展示给兄弟姐妹比较。

8. **开箱公示用一句话，不用概率表**（中国对付费箱要求公示概率，见 Wikipedia: Loot box § China；我们无真钱，仍对家长说人话）  
   → 「箱子会优先给你还没有的；有过的变成星尘。」因为未拥有优先，根本没有 70/25/5。

### 2.3 为什么未拥有优先（算给家长看）

真随机抽 12 种（coupon collector）：集齐期望约 \(12 H_{12} \approx 37\) 次箱 ≈ **111 天连击**。前 12 次还期望只抽到约 8 只，孩子会说「总是重复」。

未拥有优先：前 12 次箱 = 12 只新的 = **36 天连击集满**。重复只发生在集满后，那时转尘是「给喜欢的升星」，不是诈骗。

这是儿童收集相对成人卡池最大的差别（Neko Atsume 的稀有猫、Kinder 重复款都是反例）。

---

## 3. 和现码怎么叠

```text
ledger / earned / 10 档等级     不动
兑换商店                        阳光主用途，价格不改
主屏芽 companion_info           不改 stage/aura/name
成就墙                          2.1 才加「集齐日光系」
GET/POST /api/boxes、open_box   改掉落内容，不改 3 天一箱
单词 / ② 三格                   2.0 不读
③A companion_bag               不要并行改 open_box
```

现码开箱（`backend/main.py`）：

```python
BOX_INTERVAL = 3
# avail = streak // 3 - box_opened
bonus = random.randint(3, 10)
insert_ledger(..., 'box', f'box-{opened+1}', '连击宝箱')
```

`box5` 仍读 `box_opened`。前端 `boxResult` 现在是数字，本刀改成对象（只有 `App.vue` 用）。

---

## 4. 产品规则（2.0）

### 4.1 十二只是什么：带脸的阳光小怪，不是科目图标

上一版写成 Lucide + 色圆。**那不够。** 小朋友要的是「这是我的朋友」，不是「又一个按钮图标」。顶栏芽已经是 Lucide 的蛋/芽/叶/花；图鉴如果再摆 12 个同样语言的图标，孩子分不清「这是功能」还是「这是宠物」，也不会给它起名。

学 ClassDojo 小怪物、Finch 小鸟、多邻国 Duo：一个色块身体 + **两只眼睛 + 一张嘴** + 一个能认出的小特征。纯 CSS（圆、伪元素），不引图、不加依赖、不画成奥特曼/帕鲁/豌豆。无稀有度仍然成立——**12 张脸长得不一样时，新朋友本身就是奖**；只有长得一样才需要 SSR 制造兴奋。

手测标准：把名字遮住，44px 格子里仍能指出「这是滴滴、那是果果」。指不出来就重画，不准上线。静态预览见 [buddy-preview.html](buddy-preview.html)（未接入 App）。

**定稿立绘已入库（PNG，透明底 256px）**：`frontend/public/sprites/sp-{id}.png`，清单 `frontend/public/sprites/manifest.json`，总图原件 `docs/sprites/sheet.png`。2.0 图鉴/开箱/值班用 `<img src="/sprites/{id}.png">`，**不再用 Lucide、不再把 CSS 团子当正脸**。CSS 预览页只作降级草稿。Android WebView 直接吃 PNG，无新依赖。

纯 CSS 卡通怎么才好看（不是再摆一个正圆）：

| 手法 | 出处 | 用在我们身上 |
|---|---|---|
| 八值 `border-radius: 70% 50% 60% 80% / 50% 60% 70% 60%` 做团子，不要 `50%` 正圆 | CSS-Tricks *The Shapes of CSS*、MDN `border-radius` 椭圆角 | 每只身体一套不同半径，坐着、水滴、梨形才分得开 |
| `::before`/`::after` + **0 模糊**的 `box-shadow: 20px 0 0 0 同色` 当第二块肉（耳、鼓包、云朵） | CSS-Tricks 画图文；Lynn Fisher [A Single Div](https://a.singlediv.com/) | 朵朵/苔苔/闪闪少加 DOM |
| 叠 `radial-gradient`：左上高光 + 本体色 | CSS-Tricks *Drawing Images with CSS Gradients*（Jon Kantner, 2018） | 体积，不是平涂色板 |
| 阴影分层、跟身体同色相、近实远糊 | Josh Comeau [*Designing Shadows*](https://www.joshwcomeau.com/css/designing-shadows/) | `0 0 0 3px` 描边（略深于身体，不要纯黑）+ 一条软落地影；全页一个左上光源 |
| 头身比：图标尺度下**脸就是身体**；眼宽约脸宽 1/4，两眼间距约一只眼，瞳孔略向内，小嘴、腮红 | ClassDojo / 日式 Q 版公开画法，不是 CSS 专文 | 正圆+两点眼会像按钮；团子+大眼才像朋友 |

不学 Diana Smith 那种照片级多层（太重、44px 糊成一团）。预览页按上表重画，CSS 以后原样搬进 `App.vue`。

共用骨架：

```html
<span class="buddy" :class="'feat-' + feature" :style="{ '--c': tint }">
  <i class="acc"></i><i class="body"></i>
  <i class="blush l"></i><i class="blush r"></i>
  <i class="eye l"><i class="pupil"></i><i class="glint"></i></i>
  <i class="eye r"><i class="pupil"></i><i class="glint"></i></i>
  <i class="mouth"></i>
  <i class="foot l"></i><i class="foot r"></i>
</span>
```

| id | 系 | 默认名 | tint | feature | 孩子看见的 | 默认介绍 |
|---|---|---|---|---|---|---|
| `sp-sun` | 日光 | 暖暖 | `#f5a524` | `sunbun` | 一颗晒得发亮的太阳团，背着小光圈，笑起来会露两颗小牙 | 喜欢晒太阳，也喜欢给别人分一点光 |
| `sp-dusk` | 日光 | 霞霞 | `#e07a5f` | `sleeper` | 橘粉色的晚霞团，抱着一朵小云，半睁眼 | 傍晚是它的下午 |
| `sp-seed` | 日光 | 籽籽 | `#e8c547` | `seedling` | 小种子身体，头顶两片嫩叶，脚步短短的 | 喜欢把小秘密藏在口袋里 |
| `sp-iris` | 日光 | 虹虹 | `#7c6cf0` | `rainbow` | 紫色小团，头顶一弯彩虹，脸上有彩色雀斑 | 喜欢把不同颜色排成朋友 |
| `sp-leaf` | 绿意 | 叶叶 | `#2e8f55` | `leafcloak` | 叶片斗篷包住身体，只露出一张小脸 | 喜欢躲在课本的页角 |
| `sp-moss` | 绿意 | 苔苔 | `#7dba6a` | `mushroom` | 软乎乎的苔球，戴一顶不对称小蘑菇帽 | 喜欢阴凉又安静的角落 |
| `sp-chime` | 绿意 | 铃铃 | `#5aae8a` | `windbell` | 梨形小风铃，肚子里挂着一颗会晃的铃舌 | 喜欢听窗边的风 |
| `sp-fruit` | 绿意 | 果果 | `#c46b4a` | `acorn` | 小橡果身体，头顶一片叶子，抱着自己的圆肚子 | 喜欢圆圆的午后 |
| `sp-cloud` | 天气 | 朵朵 | `#c5ced6` | `cloudpuff` | 三朵软云叠在一起，最上面那朵是它的头 | 喜欢发呆和做白日梦 |
| `sp-rain` | 天气 | 滴滴 | `#2fa6de` | `raindrop` | 上尖下圆的小水滴，脸旁有两颗透明雨珠 | 喜欢敲窗户的节奏 |
| `sp-moon` | 天气 | 弯弯 | `#6b7c93` | `moonboat` | 一弯月牙小船，坐着一只会眨眼的脸 | 喜欢把晚安送到每个房间 |
| `sp-star` | 天气 | 闪闪 | `#4a5560` | `sparkstar` | 四瓣圆角星，不是硬邦邦的五角图标，胸口有一颗亮点 | 喜欢被点名，也会给人打气 |

叠词名（暖暖、滴滴）是给孩子喊的；孩子改的昵称优先。系名「日光/绿意/天气」只做图鉴分组，不印在开箱大字上——开箱喊「遇到了滴滴」，不喊「获得天气系精灵」。

禁止：变身器、精灵球、豌豆身体+叶子炮、奥特曼眼纹、帕鲁尖耳、宝可梦腮红球、Kirby 粉圆无特征（果果必须有梗，暖暖必须有射线）。UI 写「一句介绍」，不写技能/攻击。

`SPRITE_DEFS` 字段：`id, series, series_name, name, tint, feature, flavor`。**没有 `icon` 键**，前端不要再挂 Lucide。

### 4.2 蛋从哪来（2.0 只有宝箱）

`BOX_INTERVAL`、`box_opened`、`box5` **不改**。改 `open_box` 内容：

| 图鉴开关 | 阳光 | 精灵 |
|---|---|---|
| 开（默认） | `randint(1,3)` 仍 `reason=box` `ref=box-{n}` | 未拥有均匀 1 只；满 12 则 duplicate，`dust+=6` |
| 关 | 保持今天 `randint(3,10)`，不写 sprites | 无 |

无箱：仍 409「还没有可开的宝箱，再坚持坚持吧！」，settings / 图鉴不动。

断连击：**已得精灵不收回**（规则 6）。`avail = max(0, streak//3 - opened)` 与现在相同，可能变为 0。

### 4.3 未拥有优先算法

```python
def pick_def_id(c, kid):
    owned = {r["def_id"] for r in c.execute(
        "SELECT def_id FROM kid_sprites WHERE kid_id=?", (kid,))}
    fresh = [d["id"] for d in SPRITE_DEFS if d["id"] not in owned]
    if fresh:
        return random.choice(fresh), False
    return random.choice([d["id"] for d in SPRITE_DEFS]), True
```

测试可 `random.seed` 或先插入 11 只再开箱，断言第 12 只是剩下那只。

### 4.4 星尘（全站唯一）

1. 仅 `duplicate=true` 时 `dust += 6`（§4.7.5 推荐档）。新精灵 `stars=0`。  
2. `POST .../star`：拥有且 `stars<3` 且 `dust>=12` → `stars+=1`，`dust-=12`。  
3. 满 3 星按钮消失。尘可继续攒。  
4. 不自动升（Habitica 也是玩家选喂谁；自动会升错）。  
5. 尘不进 ledger、不能兑阳光。主屏芽无 stars。

`kid_settings.sprite_dust` 存十进制字符串，读写夹在 `0..9999`。

### 4.5 改名 / 介绍

- 昵称：strip，1–8 字，与 `POST /api/companion/name` 同一句 400。空昵称展示默认名。  
- 介绍：strip，0–16 字。空用上表默认句。  
- 不能改 `def_id`、不能删除（只增不减）。

### 4.6 入口

伙伴小卡加按钮「阳光图鉴 3/12」。顶栏不新药丸。开关关则隐藏按钮。

2.1 才做：别针（③A 贴纸的归宿）、今日学习掉蛋、阳光换蛋。

### 4.7 秘密基地（选项 A）+ 值班精灵（选项 B）— v2 优化稿

星尘的意义问题（「卡片角落的 ★ 对孩子没意义」）已定案：**A+B**。星尘买基地玩具（A），最喜欢的精灵值班到主屏（B）。C（星星不封顶）不做。

本轮对照的是**基地/庭院循环**（不是收集卡池）。开源仓库浅克隆于会话 scratch `repos/`；商业产品用 Wikipedia 明文机制。结论先写在 4.7.0，下面 4.7.1 起才是我们的规则。

#### 4.7.0 基地循环对照（本轮补完）

| 产品 | 基地是什么 | 循环 | 我们抄 | 我们禁 |
|---|---|---|---|---|
| TamoStudy（narlock，Java） | 一只 Tamo + 买来的背景/边框 | 专注 → Token（`50*秒/3600` ≈ 72 秒一枚）→ 商店食物/背景；跨日饥饿 −2/−3/−10；饥饿或开心 &lt;2 记 strike；3 strike 或 30 天没开 → **宠物死亡**进 Tamo History | **正事变代币**；商店只卖外观且明码（背景 1000/5000） | 饥饿条、strike、死亡相册、食物续命 |
| Pixelquarium（jjochum-code） | 一只鱼缸 | 闲置鱼游、点鱼、图鉴；但有 **Gacha 包 + 6 稀有度 + 饥饿/过喂 + 鱼互相吃** | **看着就在玩**（闲置动画是内容）；图鉴剪影 | 卡包、稀有度、饥饿、死亡、掠食 |
| Habitica（HabitRPG/habitica） | 头像 + 宠物棚，**不是**场景 | 完成任务 `direction=up` 才 `randomDrop`；蛋+药水孵宠物；喂到 50 变坐骑；掉落日上限 `5+PER/25` | **掉落绑正事**（我们已用连击箱）；棚=图鉴 | 掉率公式、HP、Armoire 扭蛋、金/宝石/沙漏货币地狱 |
| Neko Atsume / CLI 移植 | **庭院就是家** | 放食物+玩具 → 离开后猫按 `entry_chance` 滚进来坐上玩具 → 走时留银/金鱼 + 纪念物；空碗=没猫 | 玩具是**座位**（精灵坐上去玩）；相册；纪念品 | 银鱼+金鱼、稀有猫、空碗惩罚、玩具磨损 |
| Porchcats（Neko 翻拍） | 门廊 | 同上，加 **traces**（没碰上猫也留「Biscuit 在盒子里趴了 2 小时」）和点摸上限 3 次/只 | **空场也有痕迹**；点按有上限、不刷货币 | IAP 金鱼包、订阅 Club、金币食物锁稀有 |
| 旅行青蛙（Hit-Point，同 Neko 厂） | 房间 | 备货 → 蛙出门 → 几小时到几天后带回照片和特产 | **出门期间发生的故事**，早上回来看 | 把「干等」做成唯一玩法 |
| Forest | 自己的林子 | 专注结束种一棵；林子是视觉履历 | **努力变成看得见的东西**（我们的留痕） | **中途退出树枯死** |
| 动森 NH | 一座岛 | 昼夜、村民自己过日子、家具自定义 | 昼夜；场景自己活；不惩罚 | 自由摆放网格、21 套系统 |
| Pokémon Sleep | 睡前营地 / 卡比兽岛 | 睡觉 → **今早研究报告** → 卡比兽吸引访客宝可梦 | **晨间=昨晚报**（数字藏进一句话） | 喂卡比兽涨战力、饼干抽卡、稀有度阶 |
| Pikmin Bloom | 地图花径 + 身边一队 | 走路开花；Pikmin **跟着走**；花蜜/衣服 | **值班精灵跟着你**（主屏小脸） | GPS、AR、定位 |
| Pokémon GO | 地图道馆 | 走路捕捉、对战 | — | 捕捉、道馆、战斗 |
| Mini-pets / realtime-pet / Bastet | 需求条 | 8 小时照料 / 墙钟饥饿 / 30 秒掉 1 点；可永久死 | — | 整套饥饿照料 |
| Studygatchi | 卡片宠物 | README 自称 gachapon；血 −0.1/秒归零重置 | — | 抽卡、掉血 |

落到我们桌上的五句话：

1. **赢的循环都是「正事 → 看得见的地方变了」**（Forest 林子、Neko 庭院、Sleep 今早报告、Pikmin 花径）。不是「正事 → 数字 +1」。
2. **家只有一座。** Neko / Sleep / Pixelquarium / 动森都是一个场景。三个主题并存（已定，避免选了天台没树屋），但是**同一页秘密基地的三个角落**，不是三款游戏。
3. **玩具是座位，不是墙纸。** Neko 的猫坐在纸箱上；买火箭是为了点它、让精灵坐上去，不是为了填收藏格。
4. **空场不能空。** Porchcats：没碰上猫也留痕迹。没精灵时昼夜仍转；没学习时基地安静但不枯。
5. **禁止把 KPI 和饥饿做成基地。** TamoStudy 的饥饿/死亡、Forest 枯树、Habitica HP、蚂蚁森林「本周种了 N 棵」数字墙，都不进 2.0。周记角落（原层④）降到 2.1。

#### 4.7.1 基地是什么：会动的学习日记（v2 优化）

图鉴**本身就是三个基地**：日光系住天台、绿意系住树屋、天气系住云上营地。图鉴页每个系不是一列卡片，而是一块约 300×200 的场景（CSS 画，色板沿用现有变量），该系已拥有的精灵直接住在场景里。

v2 与 v1 的本质差别：**基地不是摆件橱窗，是会动的学习日记。** 对照之后，2.0 只交货四层玩法 + 玩具子集 + 值班；周记 KPI 和其余玩具进 2.1。

| 层 | 内容 | 学谁 | 2.0? | 说明 |
|---|---|---|---|---|
| ① 活基地（免费） | 昼夜（真时间：天黑萤火虫/星星灯亮）、云叶空转 | 动森 / Pixelquarium 闲置 | **做** | 没精灵也转。无饥饿条 |
| ② 精灵入住 | 已拥有的住进去，各有小动作；**点一下有反应**（挥手/跳/躲），不给货币、不计数 | Neko 点猫；Porchcats 轻触上限 | **做** | 精灵优先坐上已买玩具 |
| ③ 学习留痕（核心） | 今日打卡→场景里那架**免费**风车转；单元完成→纸飞机从树屋飞到天台（1 架/条）；单词 session→夜空一颗星；到期复习空→云散月圆 | Forest 林子；Pikmin 花径 | **做** | 只读、跨天清零；**不把风车/纸飞机再卖一遍** |
| ④ 周记角落 | 一角堆本周飞机数 / 星星数 | 蚂蚁森林数字墙 | **2.1** | 成人 KPI，小孩看 7 架飞机比看「这周 7」懂 |
| ⑤ 晨间惊喜 | 今早一条**昨晚报**，不是空喊加油 | Pokémon Sleep 报告；旅行青蛙；Porchcats traces | **做** | 见 4.7.3 |
| ⑥a 回忆物 | 首次单词全对→「全对小奖状」；streak≥7→小旗。挂树屋，点开看日期 | 旅行青蛙照片；蚂蚁森林证书 | **做**（就这 2 件） | 免费，不花尘 |
| ⑥b 玩具商店 | 尘明码；精灵会坐上去、点了会动 | Neko 玩具；TamoStudy 外观店 | **2.0 六件** | 其余 4 件 2.1 |

闭环：开箱→精灵住进基地→学习在基地留痕→早上回来看昨晚报→重复变尘→尘买会动的座位/升星→值班那只跟到主屏。

**学习留痕的数据口径（只读，不碰 ledger、不发明新货币）**——与 ② 三格的 rings 同源，服务端在 `GET /api/sprites` 里顺带返回 `today` 字段：

```json
"today": { "unit_done": 2, "word_done": false, "daily_done": 1, "review_clear": true }
```

- `unit_done`：今日 `kind='unit'` 完成且未被 cancel 对冲的条数 → 纸飞机起飞 1 架/条
- `word_done`：今日单词 session `state='completed'` → 夜空亮一颗星
- `daily_done`：今日 `kind='daily'` 完成条数 ≥1 → 风车转起来
- `review_clear`：`_due_queue` 为空 → 云散月圆

**明确不做**：不惩罚（没学基地只是安静，不枯萎、不黑脸）、不新货币、不碰 ledger、无对战。③ 若 ② 三格已上，两者数据同源、动画各自播，互不阻塞。

#### 4.7.2 三个主题（2.0 六件玩具）

三个场景仍同时在图鉴页里，当作**一座秘密基地的三个角落**（Tab 或上下叠，不要做成选岛）。免费基础场景一直在；玩具买下即常驻，无随机无退款。

**日光 · 天台** — **朝霞**天空 + 楼顶栏杆 + 空地（不要落日）。白天是一天的开始，和「去学习」同向；夜里换月亮星空。2.0 可买：

| id | 名字 | 价 | 画法（CSS） | 动效 / 谁坐 |
|---|---|---|---|---|
| `sun-rocket` | 小火箭 | 30 | 银色小火箭，橙尾翼，空座舱 | 点一下发射 1.5s；一张小脸从座舱探出 |
| `sun-telescope` | 望远镜 | 20 | 三脚架朝天 | 可水平转 180°（`scaleX(-1)`）；点了精灵走到镜筒朝向那侧看 |

**绿意 · 树屋** — 树冠 + 树干 + 落叶。2.0 可买：

| id | 名字 | 价 | 画法（CSS） | 动效 / 谁坐 |
|---|---|---|---|---|
| `leaf-hammock` | 吊床 | 25 | 两树之间 | 轻摇；一只精灵躺着 |
| `leaf-jars` | 萤火虫瓶 | 20 | 瓶里光点 | 光点一闪一闪（夜里更亮） |

**天气 · 云上** — 蓝紫夜空 + 月亮 + 星点。2.0 可买：

| id | 名字 | 价 | 画法（CSS） | 动效 / 谁坐 |
|---|---|---|---|---|
| `sky-balloon` | 热气球 | 30 | 彩色球 + 空藤篮 | 闲置上升下降；点一下再抬高一截 |
| `sky-moonbed` | 月亮吊床 | 25 | 弯月床 | 晚上值班精灵躺在上面（若有） |

2.0 六件合计 **150 尘**。

**故意不进 2.0 商店**（避免和层③留痕撞车）：风车、纸飞机是今天学没学的痕迹，免费出现，不卖。Neko 的教训是玩具=座位；Forest 的教训是努力=看得见的东西。同一物件不能既是日记又是商品。

**2.1 再卖的四件静物/座位**（合计再 60 尘，全套 210）：`leaf-ladder` 木梯 15、`leaf-chest` 小木箱 10（3 星坐上去）、`sky-lights` 星星灯 20、`sky-umbrella` 雨伞 15。

#### 4.7.3 基地规则 + 晨间惊喜

**基地规则**
- 三个角落**同时存在**，不用选主题（避免「选了天台就没有树屋」）。
- 玩具只属于该系角落，不能跨系摆。不自由拖放（禁抄动森网格）。
- 已买常驻，不能卖、不能拆（只增不减）。无磨损（Neko 2 评测槽点）。
- 目录是代码常量 `BASE_ITEMS`，家长不可改。2.0 白名单只有上面六件；2.1 四件可追加进同一常量，旧存档数组向前兼容。
- 未拥有的精灵不进场景；已拥有的**优先坐上已买玩具**，坐不下的按 `obtained_at` 在地面排。不要「十二只排队的卡片」。
- **空场不能空**：还没精灵时，昼夜+今日留痕照常；今天没学，基地只是安静，不枯、不黑脸、不扣东西。
- 学习留痕在三个角落之间联动：单元卡的纸飞机**从树屋起飞、飞向天台**；单词的星**挂在云上夜空**；打卡的风车在天台（免费那架）。只展示「今天」，跨天清零（与 ② 三格同日历）。
- 回忆物只做 2 件 MVP：`全对小奖状`（首次 word session 全对）、`坚持小旗`（streak≥7）。挂树屋，点开看日期。

**晨间惊喜（层⑤）— 昨晚报，不是加油口号**

学 Pokémon Sleep 的睡眠报告和 Porchcats 的 traces：孩子打开 App，看见的是**昨天基地里发生过的事**，数字藏进句子，不弹统计表。

`GET /api/sprites` 返回：

```json
"morning": {
  "new": true,
  "who": "sp-rain",
  "text": "昨晚滴滴试飞了 2 架纸飞机，夜空多了 1 颗星。它说：今天也加油！"
}
```

- 判定：`sprite_morning_ack != 今天` 且 **昨天有任意学习活动**（单元/每日完成、单词 session、签到其一）。
- `who`：值班精灵优先，否则随机一只昨天已拥有的；还没有精灵则 `who=""`，文案改成「秘密基地昨晚自己转了一晚风车。」这种无人称句。
- 句子由服务端用昨天的 `today` 口径拼：飞机数 / 有无星 / 风车转没转 / 月圆没圆。不要只喊加油。最高光事件（单词全对 > 单元卡 > 打卡）决定那句「它说：…」的尾巴。
- 前端只在孩子端登录后第一次 refresh 展示（非全屏：图鉴入口小气泡 + 顶栏值班跳一下），展示后 `POST /api/sprites/morning-ack`。同一天不再弹（跨设备也一致）。
- 昨天没学习：`new=false`，不弹，不写 ack。
- 不占庆祝队列。

#### 4.7.4 值班精灵（B）

学 Pikmin Bloom：收集物会**跟着走**，不是只躺在图鉴里。

- 图鉴详情页「设为值班」。**每次只能一只**；设新的替换旧的；可取消。
- 主屏：顶栏阳光芽旁 24px `.buddy`，**不替换芽**——芽是身份，值班是来陪你的朋友。
- 完成一个任务（单元/每日/单词 session）后跳一下（1.2s CSS）。
- 3 星显示一圈小星环（星有了主屏可见的意义）。
- 晚上若买了 `sky-moonbed`，值班那只躺在云上营地的月亮床上。
- 跳动画与升级全屏不冲突。
- `kid_settings.sprite_on_duty` = def_id，空串=没设。

#### 4.7.5 尘价格调参（已定）

| 档 | 每箱尘 | 2.0 六件（150） | 六件 + 36 星 | 2.1 十件（210）+ 36 星 |
|---|---|---|---|---|
| **定稿** | **+6** | 25 箱 ≈ **2.5 个月** | 25+72 箱 ≈ **9.7 个月** | 35+72 箱 ≈ **10.7 个月** |

+6：最便宜的 2.0 玩具（望远镜/萤火虫瓶 20）约 4 箱一件，火箭/热气球 5 箱一件；升星仍每 2 箱一颗。实现为常量 `DUST_PER_DUP = 6`，一处可调。

#### 4.7.6 摆放坐标（已定，百分比，禁止前端猜）

> **锁定**：与 `docs/base-layout-preview.html` 的 `SPEC` 同一套数字（火箭 13,86 w22 / 望远镜 46,99 w16 / 风车 95,70 w12 / 吊床 82,115 w28 / 萤火虫瓶 20,34 w11 / 奖状 45,43 w10 / 小旗 11,87 w10 / 热气球 19,56 w18 / 月亮床 75,82 w22）。`y` 可超过 100（锚点在画布底边以下）。未再拖动前不要改。

场景画布 = 图鉴里那块横幅（底板 1448×543，`object-fit: cover`）。原点左上。所有 `x,y` 是**锚点**在画布上的位置（%），`w` 是玩具占画布宽度的 %，高度跟 PNG 比例走。

玩具锚点 = 图片**底边中点**（让它们站在地上）。精灵坐上去时：`sit.x / sit.y` 是相对该玩具盒子的 %（玩具左上为 0），`pose` = `sit`（坐进）/ `lie`（躺）/ `stand`（站旁边）。未占用的精灵走该系 `floor` 槽，按 `obtained_at` 从左到右。

日夜同一套坐标（底板已对齐）。不自由拖放。实现为 `sprites.py` 常量 `BASE_LAYOUT`，前端只读、不写死魔法数。

**天台 `sun`**（栏杆约在画布 55% 高，地砖是下半）

| id | 2.0? | x | y | w | 精灵 |
|---|---|---|---|---|---|
| `sun-rocket` | 商店 | 13 | 86 | 22 | 座舱开口 `sit 58,70 sit`，脸宽 18%，锚在舱口里探头（不要坐在火箭顶上） |
| `sun-telescope` | 商店 | 46 | 99 | 16 | 不坐。可 **水平转 180°**（一张图 `scaleX(-1)`，不必第二张）。闲置缓转；点一下翻到朝另一边。精灵走到**镜筒朝向的那一侧**看 1.2s |
| `trace-pinwheel` | 留痕 | 95 | 70 | 12 | 不坐。`daily_done` 才出现。叶片从原表抠**全形**（禁止圆裁），手柄单独一层压在叶片上不转。枢轴 `transform-origin: 49.5% 43.3%` |
| floor | — | 52 / 66 / 78 | 90 | 10 | 最多 3 只站地砖上 |

纸飞机是**飞过**的动画（从树屋方向进、横穿天台），不占固定槽。

**树屋 `leaf`**（树干偏中，木屋在干右侧上方，地面是最下一条）

| id | 2.0? | x | y | w | 精灵 |
|---|---|---|---|---|---|
| `leaf-hammock` | 商店 | 82 | 115 | 28 | 布面中央 `sit 50,55 lie`，身宽约玩具的 **20%**。锚点在画布底边以下 |
| `leaf-jars` | 商店 | 20 | 34 | 11 | 不坐。光点呼吸明灭（夜里更亮） |
| `memo-award` | 回忆 | 45 | 43 | 10 | 不坐。钉在木屋，点开看日期 |
| `memo-flag` | 回忆 | 11 | 87 | 10 | 不坐。旗面从旗杆一侧 `scaleX` **左右飘**（原点约 16%, 38%），杆不转。禁止 `rotate` / 上下点头 |
| `leaf-ladder` | 2.1 | 48 | 78 | 12 | 不坐。靠树干（白名单不卖） |
| `leaf-chest` | 2.1 | 58 | 90 | 12 | 3 星才坐 `sit 50,8 sit`（白名单不卖） |
| floor | — | 30 / 42 / 72 | 92 | 10 | 地面落叶上 |

纸飞机从木屋开口起飞（约 `70,36`），飞出画面右上，再在天台入场。

**云上 `sky`**（云台在画面中下部）

| id | 2.0? | x | y | w | 精灵 |
|---|---|---|---|---|---|
| `sky-balloon` | 商店 | 19 | 56 | 18 | 篮子里 `sit 50,88 sit`，身宽约玩具的 **16%**。闲置缓缓升沉；点了再抬高一截再落下 |
| `sky-moonbed` | 商店 | 75 | 82 | 22 | 月牙凹面可 **水平转 180°**（`scaleX(-1)`，点一下翻转）。`sit 50,72 lie`，身宽 20%。仅夜晚 + 值班那只；白天空床 |
| `sky-lights` | 2.1 | 50 | 42 | 36 | 不坐。挂云台后沿（白名单不卖） |
| `sky-umbrella` | 2.1 | 50 | 82 | 14 | 不坐（白名单不卖） |
| floor | — | 38 / 50 / 62 | 86 | 10 | 云面中央 |

单词星：夜空 `18,18` 起向右一颗。月圆：`review_clear` 时夜空月亮 CSS 略放大，不换图。

**占用规则（孩子自己放精灵）**
1. **玩具钉死**（商店坐标，不能拖）。**精灵由孩子拖**：在本系场景里挪位置。
2. 松手时若靠近座位中心（火箭舱 / 吊床 / 气球篮 / 月亮床，距离 &lt; 8%）则吸附到该座位；每种座位同时 1 只，后放的挤走先放的到旁边地面。
3. 否则停在松手处，夹在画布 4–96%。不要拖出场景。
4. 存 `kid_sprites.place`：`{"x":52,"y":90,"seat":""}` 或 `seat` 为玩具 id。从未拖过的用默认：值班晚上优先月亮床，其余按 `obtained_at` 坐第一件空座位，再不然站地面。
5. 点精灵：跳/挥手，不给尘。不进 ledger。
6. 望远镜、瓶子、奖状、旗、灯、伞、风车不是座位。

手测：375px 宽场景里玩具不挡栏杆/树屋门；点火箭能看出座舱里有脸。实现后若差 ±4% 可微调，**不要改锚点定义**。

对着图改坐标：打开 [base-layout-preview.html](base-layout-preview.html)，拖玩具，把表格数字发回来改本节。

#### 4.7.7 家长两个开关（已定）

不是一个开关。图鉴管「有没有这些朋友」，基地管「朋友住不住进场景」。

| key | 默认 | 家长文案 | 关了怎样 |
|---|---|---|---|
| `sprites_enabled` | **开**（`!= "0"`） | 「连击宝箱会孵出阳光精灵，进图鉴。关掉则宝箱只给阳光。」 | 开箱回 `randint(3,10)` 纯阳光；无尘、无改名升星。基地若仍开，孩子端秘密基地显示「建设中」 |
| `sprite_base_enabled` | **开** | 「打开秘密基地：精灵住进天台/树屋/云上，星尘可以买小玩具。关掉则图鉴只显示格子。」 | 图鉴退回 12 格卡片（仍可改名升星）；无三场景、无玩具店、无留痕动画、无晨间、无顶栏值班 |

| 图鉴 | 基地 | 开箱 | 孩子看见 |
|---|---|---|---|
| 开 | 开 | 1–3 阳光 + 精灵 | 完整：场景 + 玩具 + 值班 + 晨间 |
| 开 | 关 | 1–3 阳光 + 精灵 | 12 格图鉴，无基地 |
| 关 | 关 | 3–10 纯阳光 | 没有入口 |
| 关 | 开 | 3–10 纯阳光 | 秘密基地入口，场景写「建设中」。数据全留 |

关开关不删数据。再打开还在。GET 图鉴关时仍 200、剪影 `owned=0`（不泄露）。**关图鉴不顺手关基地。**

晨间 / 值班：图鉴关或基地关，孩子端都不展示。

Admin：`GET/PUT /api/admin/sprites-config`，`{ "enabled": true, "base_enabled": true }`。两个独立 toggle。

#### 4.7.8 资源格式（WebP，已定）

运行时只发 WebP。PNG 留在 `docs/sprites/` 当原件，不进 App 包。

| 类 | 原件 | 运行时 | 建议 |
|---|---|---|---|
| 底板 6 张 | `docs/sprites/base/*.png` 1448×543 | `/sprites/base/{sun,leaf,sky}-{day,night}.webp` 宽 **900** | quality ~80 |
| 12 只精灵 | 现 public PNG 当原件，转完可撤 public 的 png | `/sprites/{id}.webp` **256** | quality ~90，alpha |
| 玩具/留痕 | `docs/sprites/toys/*.png` | `/sprites/toys/{id}.webp` **256** | quality ~90，alpha |

实现时本机转一版再提交（`cwebp` 或已有 Pillow，**不新增项目 npm/pip 依赖**）。Android WebView 直接吃 WebP。本稿不改仓库二进制。

---

## 5. 数据 · 迁移 `032_sprites`

不建 `sprite_defs` 表。

```sql
CREATE TABLE kid_sprites (
  id INTEGER PRIMARY KEY,          -- PG: GENERATED BY DEFAULT AS IDENTITY
  kid_id TEXT NOT NULL,
  family_id TEXT NOT NULL,
  def_id TEXT NOT NULL,
  nickname TEXT NOT NULL DEFAULT '',
  flavor TEXT NOT NULL DEFAULT '',
  stars INTEGER NOT NULL DEFAULT 0,
  obtained_at TEXT NOT NULL,
  UNIQUE (kid_id, def_id)
);
CREATE INDEX ix_kid_sprites_fam ON kid_sprites(family_id, kid_id);

CREATE TABLE sprite_opens (
  id INTEGER PRIMARY KEY,
  kid_id TEXT NOT NULL,
  family_id TEXT NOT NULL,
  def_id TEXT NOT NULL,
  duplicate INTEGER NOT NULL DEFAULT 0,
  dust_gain INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL,            -- 2.0 只有 'box'
  ref_id TEXT NOT NULL,            -- 与 ledger 相同 'box-{n}'
  created_at TEXT NOT NULL,
  UNIQUE (kid_id, source, ref_id)
);
```

`def_id` 必须在 `SPRITE_DEFS` 白名单，否则当损坏数据跳过。`stars` 读写夹 0–3。

PG：两表 `ENABLE/FORCE ROW LEVEL SECURITY`，策略抄 `word_sessions`：

```sql
USING (kid_id = current_setting('app.kid_id', true))
WITH CHECK (kid_id = current_setting('app.kid_id', true))
```

`GRANT SELECT, INSERT, UPDATE, DELETE` + sequence 给 `sunshine_app`。SQLite 仍靠 `kid_id()`。

`kid_settings`：

| key | 默认 | 含义 |
|---|---|---|
| `sprite_dust` | 缺省当 0 | 尘 |
| `sprite_base_items` | 缺省当 `[]` | 已买的基地物件 id（JSON 数组） |
| `sprite_on_duty` | 缺省当 `""` | 值班精灵 def_id，空=没设 |
| `sprite_morning_ack` | 缺省当 `""` | 晨间惊喜已展示的日期 |
| `sprites_enabled` | 缺省当 **开**（`!= "0"`） | 图鉴；关则开箱回退旧阳光 |
| `sprite_base_enabled` | 缺省当 **开** | 秘密基地场景；关则图鉴只显示格子。关图鉴**不**顺手关基地 |

2.1 再加 `sprites_shop`。

把 `032_sprites` 追加进 `MIGRATIONS` 元组（`backend/db.py` 约 1000 行）。

---

## 6. `open_box` 事务（必须一次 commit）

现函数一次 `commit`。保持。顺序：

```text
s = streak(c); opened = int(box_opened)
if s // 3 <= opened: 409
n = opened + 1
enabled = sprites_on(c, kid)          # != "0"
set box_opened = n                    # 先推游标，防重
if enabled:
    bonus = randint(1, 3)
    def_id, dup = pick_def_id(...)
    if not dup:
        INSERT kid_sprites (stars=0, nickname='', flavor='')
    else:
        dust += 6          # 调参已定：+6（见 §4.7.5 推荐档）
    INSERT sprite_opens (source='box', ref_id=f'box-{n}', duplicate, dust_gain)
else:
    bonus = randint(3, 10)
insert_ledger(today, bonus, 'box', f'box-{n}', '连击宝箱')
commit
```

**防重（已定稿）**：`sprite_opens UNIQUE(kid_id,source,ref_id)` 是唯一兜底。整个 `open_box` 在一个事务内完成，任一写失败或唯一键冲突 → 整笔 rollback（阳光、游标、蛋、尘全部回退），对外 409「这箱已经开过啦」。

返回（开关开）：

```json
{
  "delta": 2,
  "item": "sp-leaf",
  "kind": "sprite",
  "duplicate": false,
  "dust": 0,
  "dust_gain": 0,
  "sprite": {
    "id": "sp-leaf", "name": "叶叶", "series": "leaf",
    "feature": "leafcloak", "tint": "#2e8f55",
    "nickname": "", "flavor": "喜欢藏在课本里", "stars": 0
  },
  "streak": 9,
  "level": {}
}
```

开关关：保持 `{ delta, streak, level }`，不要 `kind`（前端以 `r.kind === 'sprite'` 分岔）。

不要同时做 ③A 的 tint 池。

---

## 7. 其它 API

前缀 `/api/sprites`。孩子登录。`family_id` 写入当前 `_fam.get()`。

### 7.1 `GET /api/sprites`

始终 200。`enabled:false` 时 `series` 仍返回 12 只剪影（方便家长预览），`owned=0`，不泄露其它孩子。`base_enabled` 见 §4.7.7。孩子端：图鉴关且基地开 → 秘密基地「建设中」；基地关则只渲染 12 格（图鉴开时）、不渲染三场景/晨间/值班。

```json
{
  "enabled": true,
  "base_enabled": true,
  "dust": 6,
  "base_items": ["sun-rocket"],
  "on_duty": "sp-leaf",
  "today": { "unit_done": 2, "word_done": false, "daily_done": 1, "review_clear": true },
  "morning": { "new": true, "who": "sp-leaf", "text": "昨晚叶叶试飞了 2 架纸飞机。它说：今天也加油！" },
  "owned": 3,
  "total": 12,
  "series": [
    {
      "id": "sun", "name": "日光", "owned": 2, "total": 4,
      "items": [
        {
          "id": "sp-sun", "name": "暖暖", "feature": "rays", "tint": "#f5a524",
          "owned": true, "nickname": "小暖",
          "flavor": "喜欢晒太阳", "stars": 1,
          "obtained_at": "2026-09-10T12:00:00"
        },
        { "id": "sp-dusk", "name": "霞霞", "owned": false, "nickname": "", "stars": 0 }
      ]
    }
  ]
}
```

未拥有不返回孩子写的昵称/介绍。`flavor` 在拥有且空时填默认句。

### 7.2 `POST /api/sprites/{def_id}/profile`

`{ "nickname": "青青", "flavor": "喜欢爬窗台" }`。未拥有 404；非法 id 400；超长 400「给它起个 1 到 8 个字的名字」/「介绍最多 16 个字」。返回该只（同 GET item）。

### 7.3 `POST /api/sprites/{def_id}/star`

无 body。400：「还没遇到它」/「星尘不够，先开重复的箱子」/「已经三颗星了」。返回 `{ "stars": 1, "dust": 0 }`。无 ledger。

### 7.4 家长 `GET/PUT /api/admin/sprites-config`

`require_parent`。按当前 `selected_kid` 读写 `sprites_enabled` + `sprite_base_enabled`。见 §4.7.7。

```json
{ "enabled": true, "base_enabled": true }
```

两个开关独立。关图鉴不改 `base_enabled`。  
放 Admin 学习组，单词开关附近，两个 toggle。

### 7.5 `POST /api/sprites/base/{item_id}/buy`

尘明码买基地物件。`item_id` 必须在 `BASE_ITEMS` 白名单且属于对应系。未拥有该系精灵也可买（物件可以先备着）。已拥有 → 409「已经买过啦」。尘不足 → 400「星尘不够」。成功：`dust -= price`，`sprite_base_items` 数组加一项，返回 `{ "dust": 3, "base_items": [...] }`。无 ledger。

### 7.6 `POST /api/sprites/{def_id}/duty` / `POST /api/sprites/duty-clear`

设为/取消值班精灵。必须已拥有；空 body。写 `kid_settings.sprite_on_duty`。返回 `{ "on_duty": "sp-leaf" }` 或 `{ "on_duty": "" }`。无 ledger。

### 7.7 `POST /api/sprites/morning-ack`

把 `sprite_morning_ack` 写成今天。幂等。无 ledger。前端展示完晨间惊喜后调用。

2.1 才有 `POST /api/sprites/buy-egg`。

---

## 8. 前端（钉在现文件）

### 8.1 `api.js`

```js
sprites: () => j('/api/sprites'),
spriteProfile: (id, o) => j(`/api/sprites/${encodeURIComponent(id)}/profile`, { method: 'POST', ...body(o) }),
spriteStar: (id) => j(`/api/sprites/${encodeURIComponent(id)}/star`, { method: 'POST' }),
baseBuy: (itemId) => j(`/api/sprites/base/${encodeURIComponent(itemId)}/buy`, { method: 'POST' }),
spriteDuty: (id) => j(`/api/sprites/${encodeURIComponent(id)}/duty`, { method: 'POST' }),
spriteDutyClear: () => j('/api/sprites/duty-clear', { method: 'POST' }),
morningAck: () => j('/api/sprites/morning-ack', { method: 'POST' }),
admin: { ..., spritesConfig: () => j('/api/admin/sprites-config'),
         setSpritesConfig: (o) => j('/api/admin/sprites-config', { method: 'PUT', ...body(o) }) }
```

### 8.2 开箱状态机（改 `openBox` / `boxOpen`）

现在：`boxResult = r.delta`（数字），模板 `+{{ boxResult }}`。

改为：

```js
const boxResult = ref(null) // 整个响应
const boxPhase = ref('sun') // sun | egg | hatch | dust
async function openBox() {
  if (boxes.avail <= 0) { /* 现 toast */ return }
  const r = await api.openBox()
  boxResult.value = r
  boxPhase.value = 'sun'
  boxOpen.value = true
  await refresh()
  if (r.kind === 'sprite') {
    setTimeout(() => { boxPhase.value = 'egg' }, 600)
    setTimeout(() => { boxPhase.value = r.duplicate ? 'dust' : 'hatch' }, 1400)
  }
}
```

遮罩：

```text
sun:   +2 阳光
egg:   蛋图标轻晃（CSS rotate，1s）
hatch: 带脸小怪 + 「遇到了滴滴」
dust:  「已经有了 · 星尘 +3」
[收下]
```

点蒙层：`hatch/dust/纯阳光` 才能关；`sun/egg` 忽略，避免孩子没看见孵化。关闭后若 `boxes.avail>0` 药丸仍 `ready`。

`boxResult.delta` 兼容：纯阳光分岔走旧 UI。

### 8.3 图鉴遮罩（学成就墙 `.shop-modal.ach-modal`）

从伙伴小卡打开。无 vue-router。

```text
阳光图鉴  3/12     星尘 6
日光 2/4  绿意 1/4  天气 0/4

[脸] [剪影] [脸] [剪影]
 暖暖    ？？    籽籽    ？？
 ★☆☆
```

- 未拥有：同骨架但灰度、无眼睛（空剪影），点 toast「连续打卡开宝箱才会遇到它」  
- 拥有：彩色带脸，点进详情  
- 详情：大圆、默认名、昵称 input、介绍 input、★、`12 星尘升一星`（尘<12 或满星则禁用）  
- 375px：三系 `details` 折叠（抄 `.ach-series`）；格子 `minmax(88px,1fr)` 与成就细胞一致，≥44px

CSS 不新色板。未拥有只留身形剪影（无眼睛），不要画第三方剪影。

### 8.4 庆祝队列

开箱是用户点的，盖住其它全屏。关箱后再走 ③B 的徽章（若已做）。2.0 不接进化（开箱不加 earned 以外的阶段跳跃，1–3 阳光偶尔升级：关箱后走现有 `refresh` 升级检测）。

`refresh()` 仍在开箱成功后调用（更新余额/药丸）。列表被遮罩挡住，符合「先看孵化」。

### 8.5 伙伴小卡

在「关闭」上方：

```html
<button v-if="sprites.enabled" type="button" class="ghost" @click="openSprites">
  阳光图鉴 {{ sprites.owned }}/12
</button>
```

`openCompanion` 时可懒拉 `api.sprites()`，失败则藏按钮。开关关：藏图鉴按钮、值班小脸、晨间气泡；GET 仍可带 `today`/`morning`（只读），前端不展示。

---

## 9. 模块切分

新建 `backend/sprites.py`（学 `words.py` 的薄模块），`main.py` 只挂路由和改 `open_box`。

```python
# sprites.py
SPRITE_DEFS = [ {"id","series","series_name","name","tint","feature","flavor"}, ... ]
SERIES_ORDER = ["sun", "leaf", "sky"]
CFG_ENABLED, CFG_DUST = "sprites_enabled", "sprite_dust"

def enabled(c, kid) -> bool
def dust_of(c, kid) -> int
def set_dust(c, kid, n)
def catalog(c, kid, fam) -> dict          # GET
def pick_def_id(c, kid) -> (str, bool)
def grant_from_box(c, kid, fam, ref_id) -> dict
def set_profile(c, kid, def_id, nickname, flavor)
def add_star(c, kid, def_id)
def base_items_of(c, kid) -> list          # 已购物件
def buy_base_item(c, kid, item_id) -> dict # 尘扣减 + 数组追加
def set_on_duty(c, kid, def_id)            # '' = 取消
```

`grant_from_box` 不写阳光、不改 `box_opened`（由 `open_box` 调）。非法 `def_id` 抛 `SpriteError`，main 转 400。

`earned()` 2.0 不改。注释写明 2.1 `reason='sprite'` 必须加入排除和 `fingerprints.earned_sum`。

---

## 10. 测试 `backend/test_sprites.py`

学 `test_companion.py`：临时库、`TestClient`、双家庭隔离。

造箱：

```python
def _give_boxes(kid, n):
    # n 个可开箱 → 需要 streak >= 3n，且 box_opened=0
    today = date.today()
    c = db.connect()
    for i in range(3 * n):
        d = (today - timedelta(days=i)).isoformat()
        c.execute("INSERT INTO checkins(date,sunshine,created_at,kid_id) VALUES(?,?,?,?)",
                  (d, 0, db.now(), kid))
    c.commit(); c.close()
```

| 用例 | 断言 |
|---|---|
| 无箱 | 409，sprites=0，ledger COUNT 不变，dust 缺省 |
| 开关开第一次 | 200，delta∈[1,3]，kid_sprites=1，opens=1，ledger 一笔 `reason=box` `ref=box-1`，`kind=sprite` |
| 未拥有优先 | 给 12 箱，连开 12 次：每次 `duplicate=false`，owned 1…12，12 个不同 def_id |
| 第 13 次 | **需 39 天连击（`_give_boxes(13)`）**：duplicate，行数仍 12，dust=6，kid_sprites.stars 全 0 |
| 升星尘不足 | 400 |
| POST star 12 尘 | stars=1，dust=0，ledger COUNT 不变 |
| 连续升到 3 再点 | 400，stars=3 |
| 改名 空 / 9 字 | 400 |
| 介绍 17 字 | 400 |
| 未拥有改名 | 404 |
| 关开关 | PUT enabled=false 后再开箱：无 sprites 新行，delta∈[3,10]，无 `kind` |
| 家庭隔离 | A 的 GET owned≥1，B owned=0 |
| fingerprints | 开箱 earned 增加 = delta，不是 dust |
| box5 口径 | `box_opened` +1 与现在相同 |
| 非法 def 升星 | 400 |
| 开箱 409 后 dust | 不变 |
| 买基地物件（尘够） | 200，`sprite_base_items` +1，dust 减价，ledger COUNT 不变 |
| 买基地物件（尘不足/重复买/非法 id） | 400/409/400 |
| 值班（未拥有） | 404 |
| 设为值班→替换→取消 | `sprite_on_duty` 依次 = def_id、新 def_id、空串 |
| 家庭隔离（基地/值班） | B 读不到 A 的 base_items 和 on_duty |
| 晨间惊喜 | 昨天有学习且 ack≠今天 → `morning.new=true` 且 `text` 含昨天飞机/星数字；ack 后再 GET → false；昨天无学习 → false |
| 晨间无精灵 | 昨天有学习但 owned=0 → `who=""`，无人称句，`new=true` |
| 买 2.0 白名单外（`sun-pinwheel` / `leaf-ladder`） | 400 非法 id |
| morning-ack 无 ledger | COUNT 不变 |

手测：375px 图鉴；孵化未完点蒙层不关；关开关后小卡无按钮；进化全屏与开箱不同时（用户自己点箱）。

```bash
cd backend && python3 -m pytest -q
npm --prefix frontend run build
```

---

## 11. 和 ②③、商店、单词

| | |
|---|---|
| ② 三格 | 不依赖。不要把关满当掉蛋（一天两只太多） |
| ③B | 关箱后再弹 `box5`。未做 ③B 也不阻塞 |
| ③A | **禁止同一 PR。** 都改 `open_box`。2.0 先落地则 ③A 的 companion_bag 取消，颜色/贴纸并进 2.1 别针 |
| 商店 | 阳光主用途。2.0 不准用阳光买蛋 |
| 单词 | 2.0 不读 word 表 |

推荐：**只做 2.0**，②③ 继续放。穿插 ③B/② 可以（它们不改掉落）。

---

## 12. 分期

**2.0（本文，约 5 天）**  
迁移、`sprites.py`（含 `BASE_LAYOUT`）、改 `open_box`、图鉴（三角落 + **只卖六件**）、开箱两拍、改名升星、值班、晨间、**家长双开关（图鉴 / 秘密基地）**、WebP 资源、测试。周记和 2.1 四件玩具不进商店（图已入库，白名单不卖）。

**2.1（1.5–2 天，需另开一刀）**  
- 周记角落（层④）：本周飞机/星星堆在一角  
- 四件玩具：`leaf-ladder` / `leaf-chest` / `sky-lights` / `sky-umbrella`  
- 今日第一次单元或单词完成：30% 掉蛋，每天最多 1，不写阳光  
- 阳光换蛋 40，明码，每周 1，默认关；`earned` 排除 `sprite`；指纹同步  
- 成就：日光/绿意/天气各集齐 4 只（D）  
- ③A 贴纸/别针已由「值班精灵」取代，不再单独做

**2.2**  
JSON 8 色填色（仍不上传）。照片上传要配额和家长相册权限后再谈。

**整段不做**  
十连、pity、稀有度、概率后台、对战、饥饿、排行、PK、第三方 IP、新依赖、音效文件、精灵改任务阳光、主屏芽换种、尘兑阳光、蛋作为库存再孵一次。

---

## 13. 涉及文件

| 文件 | 改什么 |
|---|---|
| `backend/db.py` | `_migrate_032`、`MIGRATIONS`、PG GRANT |
| `backend/sprites.py` | **新** |
| `backend/main.py` | `open_box`；sprites 路由（图鉴/改名/升星/**基地购买/值班**）；admin config |
| `frontend/src/api.js` | 4 个方法 |
| `frontend/src/App.vue` | 开箱状态机、图鉴遮罩（**三个角落场景 + 六件玩具店**）、值班精灵顶栏小脸、晨间气泡、小卡按钮、`.buddy` CSS |
| `frontend/src/Admin.vue` | 学习组开关 |
| `backend/test_sprites.py` | **新** |

不改单词、不改 `companion_info` 阈值、不改 `RANKS`。

---

## 14. 来源

| # | 来源 | 用在 |
|---|---|---|
| 1 | Wikipedia Habitica（2026-09 REST extracts） | 正事→奖励；不抄掉血 |
| 2 | Habitica 公开玩法（宠物=蛋+药水+食物，货币过多为社区常识） | 反面：货币地狱；正面：外观不改难度 |
| 3 | Wikipedia Duolingo · Gamification | 短课+奖励；不抄联赛 |
| 4 | Wikipedia Forest (application) | 林子当图鉴；不抄树枯死 |
| 5 | Wikipedia Ant Forest | 行为→证书相册；不抄偷能量 |
| 6 | Wikipedia Animal Crossing: New Horizons | 岛上收集；博物馆 UX 来自系列公开机制（剪影、New、重复卖） |
| 7 | Wikipedia Stardew Valley | 捐赠博物馆、里程碑 |
| 8 | Wikipedia Neko Atsume | 相册；不抄双货币和稀有猫 |
| 9 | Wikipedia Tamagotchi | 不抄饿死 |
| 10 | Wikipedia Loot box § China | 无真钱仍对人话公示 |
| 11 | Wikipedia ClassDojo | 一只怪物身份；不抄当众打分 |
| 12 | 总图 §2.1 小红书积分卡（二手） | 攒满才抽 |
| 13 | Wikipedia Palworld / Ultraman（总图 §4.1） | 禁 IP 与场地捕捉 |
| 14 | Finch、Khan Academy 头像店、马里奥月亮、Apple 健身奖章 | 公开产品机制，非抓包 |
| 15 | TamoStudy `FocusState.java:650` / `ProfileUpdateManager.java:61-88` | Token=正事；禁饥饿/strike/死亡 |
| 16 | Habitica `randomDrop.js` + `ops/hatch.js` + `ops/feed.js` | 掉落绑 `direction=up`；禁掉率公式与 HP |
| 17 | Neko Atsume CLI `lib/update.py` 庭院 tick | 玩具是座位；禁空碗惩罚、双货币 |
| 18 | Porchcats `src/logic/sim.ts` traces | 空场留痕迹；点按不刷货币 |
| 19 | Pixelquarium README v0.8.9 | 闲置看着就玩；禁 gacha/饥饿/掠食 |
| 20 | Wikipedia Pokémon Sleep / Pikmin Bloom / Travel Frog / Forest / ACNH（2026-09 extracts） | 昨晚报、跟着走、林子履历；禁枯树/GPS/饼干抽卡 |

> 检索：Wikipedia REST/Action API（本节抓取）；Habitica / TamoStudy / Neko CLI / Porchcats / Pixelquarium 为公开源码或 README，不引用 Fandom 未抓到的掉率数字。
