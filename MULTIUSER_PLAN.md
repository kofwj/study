# 多用户改造方案（多娃 → 多家庭）

> 范围：先「多孩子」，再「多家庭/SaaS」；身份识别用**每个孩子独立账号**。
> 前提不变：**ledger 仍是唯一真相源**，等级/余额/连击全由流水+日期推导，消费不掉级。本次改造不改这套不变式，只给数据「加归属」。

---

## 1. 一句话方案

给每条数据加**归属者**：活动数据（打卡/流水/兑换/测试/连击）加 `kid_id`，配置数据（课程/商店/等级）加 `family_id`，`settings` 拆成「家庭级」和「娃级」。登录从「单人 PIN Header」换成「账号 + HttpOnly 会话 Cookie」，后端每个接口按登录人 `kid_id/family_id` 强制过滤（不信任前端传的 id）。

---

## 2. 现状为什么是单用户（症结）

| 问题 | 具体表现 | 后果 |
|---|---|---|
| 无用户表 | 只有一个隐式孩子「乐乐」，存在 `settings.kid_name` | 无法有第二个娃 |
| 数据表无归属 | `checkins / completions / ledger / redemptions / tests` 都没有 `kid_id` 列 | 所有娃数据混在一起，无法隔离 |
| settings 混装 | 娃级（`kid_name`、`cursor_*`、`box_opened`、`milestone_*`）和家庭级（`admin_pin`、`progress_lock`、`curriculum_ver`、`ranks_ver`）放同一张表 | 多娃时游标/盲盒/里程碑会互相打架 |
| 认证是明文单 PIN | 家长用 `x_admin_pin` 请求头，PIN 明文存 `settings` | 多用户/多租户下等于裸奔，必须换成密码哈希 + 会话 |

核心不变式记录（改造时一条都不能破坏）：
- `ledger` append-only，余额 = SUM(全部 delta)，累计获得 = SUM(非 redeemd delta)。
- 「点错取消」= 一条负 delta + completion 置 cancelled，不删历史。
- 连击由日期集合推导，不硬存 streak 数字。

---

## 3. 归属模型（三张逻辑层次）

```
family（家庭）                     ← 1 个家庭 = 1 份商店/等级配置 + 它家的自定义任务
 ├─ parent（家长，≥1）            ← 每个家长一个账号，可全家管理
 ├─ kid（孩子，≥1，各有 term_id） ← 每个孩子独立账号 + 绑定自己的年级/学期
 ├─ 教材目录（全局共享，多学期）: terms/units/tasks/daily_tasks  ← 所有人共用一套教材书，不归家庭
 ├─ 家庭配置: rewards / ranks / 自定义任务(custom)            ← family_id 归属
 └─ 活动: checkins/completions/ledger/redemptions/tests       ← kid_id 归属
```

- **subjects（8 学科名）**：全局字典，所有家庭共用（学科名是固定的），不用改。
- **教材内容（terms/units/tasks/daily_tasks）**：全局共享目录，只读种子，**不归家庭也不归娃**。目录里放满各年级各学期（g5s1/g5s2/g2s1…），孩子靠 `term_id` 挑自己那一套做（详见 4.5）。
- **家庭配置（rewards/ranks/自定义任务）**：family_id 归属，各家庭自改商店/等级/加自家任务。
- **活动流水（completions/checkins/ledger/redemptions/tests）**：娃级，隔离单位是 `kid_id`。

---

## 4. 数据模型改造清单

### 新增表

```sql
CREATE TABLE families (
  id TEXT PRIMARY KEY, name TEXT, created_at TEXT
);
CREATE TABLE users (
  id TEXT PRIMARY KEY, family_id TEXT, role TEXT NOT NULL,   -- 'parent' | 'kid'
  name TEXT, avatar TEXT DEFAULT '', pin_hash TEXT,           -- 密码/PIN 只存哈希
  term_id TEXT,                                               -- 仅 kid 用：绑定的年级/学期
  created_at TEXT
);
-- 娃级专属状态（从 settings 拆出来）
CREATE TABLE kid_settings (
  kid_id TEXT, key TEXT, value TEXT, PRIMARY KEY(kid_id, key)
);
```

### 已有表加列（迁移）

| 表 | 加列 | 说明 |
|---|---|---|
| rewards / ranks | `family_id TEXT` | 商店/等级按家庭隔离 |
| tasks（仅自定义任务） | `family_id TEXT NULL` | NULL=全局教材；非空=该家庭的自定义任务 |
| terms / units / daily_tasks | 不加列 | 全局教材目录，多学期共存 |
| checkins / completions / ledger / redemptions / tests | `kid_id TEXT` | 活动按娃隔离 |

### settings 拆分规则

- 移到 `kid_settings`：`kid_name`(→users.name)、`cursor_*`、`box_opened`、`milestone_*`。
- 留在 `settings`（家庭级，必要时再加 `family_id` 键前缀）：`admin_pin`(→ 改存哈希)、`progress_lock`、`curriculum_ver`、`ranks_ver`。

### 迁移脚本要点（务必幂等）

1. `INSERT OR IGNORE` 默认家庭 `f-default` + 默认娃 `kid-default`（名字沿用旧 `kid_name`）。
2. 现有全部活动数据 `UPDATE ... SET kid_id='kid-default'`（先 ALTER 加列再回填）。
3. 旧 `settings` 里娃级 key 全部 COPY 进 `kid_settings`（一个 `INSERT ... SELECT`）。
4. 用现有 `init_db()` 的 `try/except sqlite3.OperationalError` 模式包住每个 ALTER，保证老库直接升级不清数据。
5. **迁移前先跑 `scripts/backup_db.py`**，这是硬性前置。

---

## 4.5 不同年级、不同课程怎么办（关键设计）

「课程内容不一样」不是按家庭区分，而是**按孩子绑定「学期」区分**：

- 教材目录是**全局共享的多学期目录**：`terms` 表放 g5s1（五上）、g5s2（五下）、g2s1（二上）… 每个 term 挂自己的 units/tasks（`unit.term_id → task` 这条链现在就有）。
- 每个孩子一个 `term_id`（`users.term_id`）＝「我上几年级哪个学期」。哥哥绑 g5s1、弟弟绑 g2s1，各打卡各的卡。
- 打什么卡 = 按 `kid.term_id` 过滤：`tasks JOIN units ... WHERE units.term_id = :kid.term_id`。今日推荐、进度游标、进度锁都跟着走，天然 per-kid。
- **任务 ID 学期前缀 `g5s1-*` 就是为这件事留的**：升年级把 `kid.term_id` 从 g5s1 切到 g5s2 即可，历史 g5s1 完成记录/流水不污染 g5s2，累计阳光跨学期继续累计（等级不带学期）。
- **升年级 = 改一个 `term_id` 绑定值**，不迁移数据、不重算流水，一键切。
- 当前 `tasks.seed.json` 顶层 `term` 是**单数**，要扩成 `terms[]` 数组；`gen_tasks.py` 里 `TERM` 常量改成可生成多学期。这是「上多年级」唯一的种子改造点。
- daily_tasks（跳绳/眼保健操/口算/拼读）跨年级通用，不绑 term；若某年级要差异化（如二年级口算口头、五年级笔算），再给 daily_tasks 加可空 `term_id`（NULL=通用），现在不用做。

> 一句话：**内容（教材书）全局共用多学期，孩子各拿各的「学期标签」，看到/做到的就是自己年级那套课。**

---

## 5. 认证与权限改造

### 登录（替换 `x_admin_pin`）

- `POST /api/auth/login`：账号（家长名称或孩子头像名）+ PIN/密码 → 校验 `pin_hash` → 下发 **HttpOnly 会话 Cookie**（HMAC 签名的无状态 token，内嵌 `user_id` 和 `family_id`）。
- 密码哈希：用标准库 `hashlib.pbkdf2_hmac`（盐 + 迭代），**不再明文存 PIN**。
- 孩子登录：头像 + 家长设的 PIN（或家长允许时设为「免密头像直选」，但默认要 PIN，因为本次选了「独立账号」）。

### 权限中间件

```python
def get_current_user(request) -> User:
    uid = decode_signed_cookie(request.cookies.get("sid"))   # 失败=401
    return users[uid]  # 内含 user_id / family_id / role

def require_parent(user=Depends(get_current_user)):
    if user.role != "parent": raise HTTPException(403, ...)
```

所有查询按 `kid_id`（或由 kid 反查 `family_id`）过滤。**隔离必须在 SQL WHERE 层生效，不能只靠前端藏按钮**——这是安全边界，不能偷懒。

---

## 6. 分阶段步骤

| 阶段 | 目标 | 交付 / 验收 |
|---|---|---|
| **P0 地基（不动单用户行为）** | `families/users/kid_settings` 建表 + 活动表加 `kid_id` + settings 拆分 + 默认家庭/娃回填 | 老数据一个字节不丢，单娃跑得和现在一模一样 |
| **P1 登录与会话** | 账号登录、PBKDF2 哈希、HttpOnly Cookie、`get_current_user` 依赖 | 能登录登出，未登录 401；旧 `x_admin_pin` 全部替换掉 |
| **P2 多娃（单家庭）** | 家长账号创建/编辑多个孩子、设各自 PIN/头像；孩子登录后只看到自己；家长端「切换查看娃」+ 全家汇总周报 | 两个娃同时打卡互不干扰；游标/盲盒/里程碑各自独立 |
| **P3 多家庭（SaaS 多租户）** | `families` 注册/邀请、商店/等级/自定义任务按 `family_id` 隔离（课程走 term 全局目录）、邀请第二位家长(共同管理)或观察员 | 两个家庭数据完全隔离，A 家庭看不到 B 家庭的配置和流水 |
| **P4 功能扩展** | 见第 7 节，按价值排序逐个上 | — |

**建议先锁 P0+P1+P2**（多娃单家庭），这是自用价值的 90% 所在；P3 多家庭是「要不要对外开放/给别家用」的岔路口，到那一步再决定商业模式，现在先把 `family_id` 的坑位留好即可。

---

## 7. 多用户带来的新功能（按价值排序）

**多娃单家庭（P2 即解锁）**
1. **多娃排行榜**：周/月阳光榜、连击榜，良性竞争（孩子天然爱看谁在前）。
2. **家长汇总面板**：一眼看到每个娃今日完成、余额、连击；周报从「单娃」升级成「全家对比」。
3. **每娃独立进度**：游标、进度锁、盲盒、里程碑各自独立，大娃超前学、小娃慢慢来互不干扰。
4. **家庭共同任务**：全家一起达成一个目标 → 每人各自 +N（或进一个「家庭阳光池」换集体奖励）。
5. **娃间友好互动（慎做）**：送阳光/帮忙打卡——**有通胀风险**，必须限额度或走家长审核，默认不做。

**多家庭（P3 后解锁）**
6. **家长邀请制**：短信/二维码邀请另一位家长成共同管理员、爷爷奶奶成「只读观察员」。
7. **长辈红包/充值**：观察员可给学生发「奖励阳光」（需设额度上限，防通胀）。
8. **班级/小团体模式**：老师统一布置任务，多家庭学生一起做（类似 ClassDojo 的班级点）。
9. **成就战报分享卡片**：期末生成一张「本学期成长图」，可分享到朋友圈（拉新 + 留存）。
10. **每家庭独立课程版本**：不同家庭绑定不同年级/教材目录，一学期新课一键下发。

> 参考方向：ClassDojo（家庭+班级点）、`nitin27may/child-reward-system`（多子女 + 行级隔离的现成实现，可借鉴其 `kid_id` 归属和 RLS 思路）。

---

## 8. 关键技术决策

| 决策点 | 推荐 | 理由 |
|---|---|---|
| 多租户隔离模式 | **共享库 + 行级 `family_id` 过滤**（pooled + row-level） | 家庭量级下最简单；`kid_id` 已经天然是行级隔离，加 `family_id` 只是往上套一层。参考 sequere.com / eltherion.com 的三种模型对比 |
| SQLite vs Postgres | **单家庭继续 SQLite；多家庭对外开放时上 Postgres** | SQLite 单写锁扛得住一家庭几口人；一旦多家庭并发写，换 Postgres（行级过滤逻辑不变，只换驱动和部署） |
| 密码存储 | `hashlib.pbkdf2_hmac`（标准库） | 不新增依赖；把现在的明文 PIN 清掉 |
| 会话 | HttpOnly Cookie + HMAC 签名 token | 无状态、免新增依赖、CSRF 用 SameSite+Lax 挡；token 内嵌 user_id，不存服务端会话表 |
| 前端 | 登录页 + 路由守卫 + `provide/inject` 当前用户 | 娃端独立登录入口；家长端一个「切换娃」下拉，数据源切到 `/api/...?kid=xxx`（后端校验该 kid 属于当前 family） |

---

## 9. 风险与必守边界（不可偷懒项）

1. **数据隔离在 SQL 层强制**，不靠前端藏按钮——否则 A 娃能看 B 娃流水。
2. **明文 PIN 必修成哈希**——现在 `admin_pin=8888` 明文存在库/接口里，单家庭局域网勉强能忍，一旦多账号/多租户就属于安全漏洞。
3. **迁移幂等 + 先备份**：每个 ALTER 都 `try/except`，`backup_db.py` 是前置。
4. **ledger 不动**：仍 append-only，新增 `kid_id` 列只回填不重算，历史余额/等级不变。
5. 娃「独立账号」意味着娃要多一步登录——保留「记住这台设备」的免密选项（绑定设备 + 可选 PIN），避免娃每天嫌烦弃用。

---

## 10. 参考资料

- 多租户三种数据隔离模型对比：https://sequere.com/multi-tenant-saas-data-model 、https://eltherion.com/blog/multi-tenant-data-isolation-schema-per-tenant-vs-row-level
- 多子女奖励系统现成实现（REWARD+RLS 隔离）：https://github.com/nitin27may/child-reward-system
- ClassDojo 家庭/班级点与家长账号模型：ClassDojo 官方帮助（家长账号跨多个孩子/班级查看 Point Report）
- 家庭多成员隔离与角色权限讨论：https://forum.trae.cn/t/topic/49537