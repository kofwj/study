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
 ├─ 家庭配置: rewards / ranks / 自定义任务(custom)            ← family_id 归属（自定义任务可再挂 kid，见 4）
 └─ 活动: checkins/completions/ledger/redemptions/tests       ← kid_id 归属
```

- **subjects（8 学科名）**：全局字典，所有家庭共用（学科名是固定的），不用改。
- **教材内容（terms/units/tasks/daily_tasks）**：全局共享目录，只读种子，**不归家庭也不归娃**。目录里放满各年级各学期（g5s1/g5s2/g2s1…），孩子靠 `term_id` 挑自己那一套做（详见 4.5）。
- **家庭配置（rewards/ranks）**：family_id 归属，各家庭自改商店/等级。
- **自定义任务**：family 级（`kid_id` 可空，NULL=全家可见）或指定某娃——「给哥哥加奥数、给弟弟加口算」是刚需，纯 family 归属不够。
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
| tasks（仅自定义任务） | `family_id TEXT NULL` + `kid_id TEXT NULL` | family_id=归属家庭；kid_id NULL=全家可见、非空=只该娃 |
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

- `POST /api/auth/login`：账号 + PIN/密码 → 校验 `pin_hash` → 下发 **HttpOnly 会话 Cookie**。
- 密码哈希：`hashlib.pbkdf2_hmac`（每用户随机 salt、迭代量按 OWASP ~60 万、`hmac.compare_digest` 恒时比较；校验失败统一报「账号或密码不对」，不泄露账号是否存在）。
- 孩子登录：头像 + 家长设的 PIN；**默认强制 PIN**，「免密头像直选」只能按娃显式 opt-out。

### 权限中间件

```python
def get_current_user(request) -> User:
    uid = decode_signed_cookie(request.cookies.get("sid"))   # 失败=401
    return users[uid]  # 内含 user_id / family_id / role

def require_parent(user=Depends(get_current_user)):
    if user.role != "parent": raise HTTPException(403, ...)
```

所有查询按 `kid_id`（或由 kid 反查 `family_id`）过滤。**隔离必须在 SQL WHERE 层生效，不能只靠前端藏按钮**——这是安全边界，不能偷懒。

### 登录设计的坑（开始写代码前必须定死）

1. **无状态 token 不能光签名，要有「过期 + 能撤销」**：HMAC 签名的 token 一旦发出，偷到 cookie 就永久有效；改 PIN/删账号后旧 token 照样能用。→ 会话 token 带 `exp`（短，如 7 天滑动）；「记住这台设备」用单独的长期 token 且换 PIN/删号时失效。撤销策略二选一并写死：极小「失效 token 表」（改 PIN 插一条），或短过期强制重登。
2. **「免密头像直选」会直接击穿隔离**：多娃共平板，点哥哥头像不输 PIN 就能当哥哥，娃间乱点/抢阳光。→ 共设备默认强制 PIN，免密仅作个别娃的显式开关，且家长被告知「这会破坏隔离」。
3. **一个 cookie = 一个身份，家长和娃不能同设备共存**：`sid` 单 cookie 下，家长在娃的平板上登管理端会覆盖娃的会话。→ 家长会话（`pid`）与娃会话（`sid`）用**不同 cookie 名**分开，或明确「家长用自己手机、娃用平板」并照此限制登录。不能假设同设备同 cookie 能共存。
4. **家长「当前看哪个娃」是可变的，塞不进无状态 cookie**：`current_kid` 写进签名 token 的话，切娃就要重签 cookie、各设备各不相同。→ 二选一：`selected_kid` 作**请求参数**（每请求校验 `kid 属于 family`）+ 无状态 cookie；或为此引入一小张服务端 session 表。推荐前者（校验简单、无服务端状态）。
5. **admin PIN → 账号的过渡缺「用户名」**：现在家长只输 PIN 没有账号名；改 `account + pin` 后要定默认账号（如 `parent`），否则老家长登不进去。文档化默认凭据 + 首登强制改。
6. **公网 + 4 位 PIN = 可爆破，必须限流**：`study.anemy.org` 走 CF Tunnel 对公网开放，登录端点要失败限流/锁定（按账号 + 按 IP），记尝试次数。
7. **签名密钥要持久化**：`SECRET_KEY`（HMAC 用）每次重启随机生成＝重启即全员掉线。→ 存 env 或 `data/` 文件（不进 git），轮换=全体登出。
8. **签名别手搓**：手写 HMAC 会话 token 是经典踩坑（canonicalization/恒时/版本）。安全边界不偷懒——用现成 `itsdangerous`（或至少写死 alg、payload 规范化、`exp`、`hmac.compare_digest` 验签），别「自己实现一遍 HMAC token」。
9. **Cookie 属性 vs 内网直连**：CF 侧 HTTPS 要 `Secure + HttpOnly + SameSite`；但内网 `http://192.168.100.5:9000` 直连时 `Secure` cookie 会失效。→ 要么全走 HTTPS（CF），要么接受内网直连用无 `Secure` 的降级 cookie，写明取舍。
10. **威胁模型分两层，别用一套标准糊**：外部攻击者（要真密码 + 限流 + 哈希 + 过期）vs 家里兄弟捣乱（要 PIN / 分设备 / 首登教育）要求不同——家长账号按「真密码质」设计，娃账号按「轻 PIN + 防捣乱」设计。

---

## 6. 分阶段步骤（细化版）

> 每阶段通用前置：① 线上先备份（换 Postgres 后 `pg_dump`，之前 `backup_db.py`）；② 迁移走版本化脚本、可重放，不用 `ALTER IF NOT EXISTS` 堆叠；③ 改完在本机对生产库副本跑一遍迁移，并对比 `ledger` 余额、`completions` 条数、等级、游标逐项一致。
>
> 代码现状关键锚点：认证= `main.py:require_admin` 读 `x_admin_pin` 头；娃端全无鉴权；所有聚合助手 `earned/balance/level_info/streak/maybe_milestone/locked_task_ids/subject_order/is_past` 都无归属参数；写入统一走 `db.insert_ledger`。

### P0 换底到 Postgres + RLS（行为零变化）

目标：后端从 SQLite 换到 Postgres，业务一字节不变；顺便把多租户所需的 RLS 底座铺好。

**步骤**
1. `docker-compose` 加单个 `postgres:16` 服务 + 持久化卷；`db.py` 换驱动，SQL 方言改写：`INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`、`ON CONFLICT(key) DO UPDATE`、`cursor.lastrowid`→`RETURNING`、部分唯一索引→`CREATE UNIQUE INDEX ... WHERE`。
2. 一次性迁移 SQLite→Postgres（导出→导入→**校验 `ledger.SUM(delta)`、`completions` 条数、游标、`settings` 逐项一致**后才切流量）。
3. 迁移改成**版本化脚本**（alembic 或 `supabase/migrations/*.sql` 风格），停用 `init_db` 的 `ALTER IF NOT EXISTS` 堆叠。
4. 铺 RLS 底座：
   - 身份表 `users` + 映射表 `profiles(user_id, family_id)`（P1 起用，P0 只建表）。
   - 业务表全开 RLS；登录/请求进入时 `SET LOCAL app.family_id/app.kid_id`（会话上下文），RLS policy 用 `current_setting('app.kid_id', true)` 过滤——**隔离从此在库层自动生效，不再逐函数传 `kid_id`**。
   - ⚠️ **RLS 对表 owner/superuser 默认不生效**（会绕过）：必须 `ALTER TABLE ... FORCE ROW LEVEL SECURITY` 或让 app 用低权限非 owner 角色连接，否则整个隔离是幻觉。
5. 默认家庭/娃回填：`f-default`+`kid-default`(名取旧 `kid_name`)+`parent-default`；活动数据全 `kid_id='kid-default'`；三条原「单娃唯一」约束改成带 `kid_id` 的唯一约束（否则第二个娃点一卡/签一到就冲突）。`settings` 键**全量枚举去向**：`kid_name/cursor_%/box_opened/milestone_%`→`kid_settings`；`admin_pin`→P1 进 `pin_hash`；`active_term`→**废弃**改用 `users.term_id`；`progress_lock/curriculum_ver/ranks_ver`→家庭级（P3 变 `family_curriculum_ver`）。
6. 本地开发可留 SQLite，但生产一律 Postgres；隔离逻辑**只写一次**（RLS + 上下文），不允许回退到逐处 `AND kid_id=?`。

**验收**：迁移后余额/完成数/等级/连击/游标/盲盒与现在逐项一致；`/api/health` ok；拿「另一个娃」的上下文查同一行数据返回空（RLS 真的挡住了）。

> 隔离的「过滤点」从 P0 就定死：**一律靠 RLS + 会话上下文自动过滤，不靠前端藏，也不逐函数手写 `AND kid_id`**。

**P0 自查清单（这轮补的坑）**
- **SQLite 方言改造点（代码具体位置）**：`INSERT OR IGNORE` 共 10 处（db.py ×6、main.py ×4）→ `ON CONFLICT DO NOTHING`；`lastrowid` 共 5 处（main.py 440/457/579/792/794）→ `RETURNING id`（psycopg3 `fetchone()[0]`）；判重用 `rowcount==0` 3 处（main.py 376/437/454）→ 用 `ON CONFLICT ... RETURNING` 有无返回行更稳；`set_setting` 的 `ON CONFLICT(key) DO UPDATE ... excluded.value` 语法 PG 兼容但要核对；`AUTOINCREMENT` 5 表 → `GENERATED ALWAYS AS IDENTITY`；部分唯一索引 PG 支持（`CREATE UNIQUE INDEX ... WHERE`）。
- **依赖/部署**：`requirements.txt` 现在只有 fastapi+uvicorn，要加 `psycopg[binary]`（psycopg3）；`docker-compose` 加 `postgres:16` 服务 + 持久化卷 + `depends_on` 健康检查 + 连接串密钥（env，不进 git）。
- **RLS 别覆盖共享课程表**：`subjects/terms/units/tasks(custom=0)/daily_tasks/daily_metrics` 是全局共享，收紧 RLS 会让谁都读不到；`tasks` 表混了共享教材(custom=0)+自定义(custom=1)，policy 要 `USING (custom=0 OR (family_id=current_family AND (kid_id IS NULL OR kid_id=current_kid)))`。
- **`SET LOCAL` + 连接池**：`SET LOCAL` 是事务/连接级；当前「每请求 `connect()` 一条 + helpers 共享同一条 `c`」正好合适，但上连接池后必须 per-request 设置与复位。
- **日期存 TEXT 保持**：现在全是 ISO 字符串，`ORDER BY/BETWEEN` 对 ISO 日期排序仍正确——继续 TEXT（最省），换 `DATE/TIMESTAMPTZ` 是后续可选项，不在 P0 做。
- **备份切 pg_dump**：`scripts/backup_db.py` 是 sqlite 的 `backup()` API，换 PG 后重写成 `pg_dump -Fc`，并接进 `deploy_vps.sh` / OPS「三」。
- **DDL 与 DML 拆开**：alembic/版本化只管 DDL（建表/加列/索引）；`seed/apply_curriculum/migrate_task_ids` 这类 DML 仍在启动 init 跑，别混进迁移工具。
- **切流前校验要含两个 SUM**：`SUM(delta)`（余额）和 `SUM(delta WHERE reason!='redeem')`（累计获得）都对比，外加 `completions/redemptions/tests/checkins` 计数、`settings` 键值、游标、`daily_metrics` 数。

### P1 登录与会话（替换明文 PIN）

目标：孩子和家长都有账号登录；`x_admin_pin` 头 → HttpOnly 会话 Cookie；未登录 401。

**步骤**
1. `db.py` 加 `hash_pin/verify_pin`（`pbkdf2_hmac`，每用户随机 salt、OWASP 迭代量、`hmac.compare_digest` 恒时比较、失败统一报错不泄露账号是否存在）；旧 `settings.admin_pin` 一次性哈希进 `parent-default.pin_hash`，默认账号定为 `parent`、文档化首登凭据 + 首登强制改。
2. `main.py` 加认证组：
   - `POST /api/auth/login`（`{account, pin}`）→ 校验 → 双 cookie：家长 `pid` / 娃 `sid`（分开身份域，见第 5 节第 3 条）；token 用 `itsdangerous` 签名、带 `exp`，内嵌 `user_id/family_id/role/term_id`。
   - 登录失败限流/锁定（按账号+IP 计数）；改 PIN/删号时写「失效 token 表」（第 5 节第 1 条撤销策略）。
   - `POST /api/auth/logout` → 清对应 cookie。
   - `get_current_user`：解 cookie 失败 401；`require_parent`：`role=='parent'` 否则 403。
   - `current_kid`：`role=='kid'` → 自己；家长 → 从 `selected_kid` **请求参数**取并校验该娃属于本 `family_id`（P1 只有默认娃，先返回 `kid-default`）。
3. `SECRET_KEY` 持久化到 env/`data/`（不进 git）；`Secure + HttpOnly + SameSite=Lax`，内网直连的降级取舍写进 OPS。
4. 把现有 `require_admin`（比对 `x_admin_pin` 头）替换成 `require_parent`；替换全部 `dependencies=[Depends(require_admin)]`（约 18 个 admin 路由）。
5. 把 P0 的 `DEFAULT_KID` 桩换成「每请求 `Depends` 设置 `SET LOCAL app.kid_id/app.family_id`，业务 SQL 靠 RLS 的 `current_setting()` 自动过滤」，不再逐函数穿 `kid_id`；少数走不了 RLS 的（如跨表聚合）统一过 `kid_scope()` 一个 choke point。

**验收**：未登录访问 `/api/tasks` 返回 401；家长登录（默认账号 `parent`）后 admin 路由正常；`settings` 不再有明文 `admin_pin`；旧 `x_admin_pin` 头失效；连错 PIN 多次触发限流；重启后会话不掉（`SECRET_KEY` 持久）；改 PIN 后旧会话/旧设备 token 失效。部署当天在真实 PG 上再验：`sunshine_app` + `kid-other` 看 ledger=0。

### P2 多娃（单家庭）

目标：一个家庭多个孩子，各看各的课、各有各的游标/盲盒/里程碑/成就/个人纪录。**P0 那三条 `kid_id` 维度唯一索引是前提**，少了它第二个娃任何卡都点不了、也签不了到。

**已定决定（2026-09）**
- 每个娃都建账号（active），**不设 passive/只读角色**；小娃由家长在「切换娃」下代点打卡。
- 娃账号用拼音/小名（唯一，`ux_users_account` 已卡），display 名用中文小名；名/账号/PIN/`term_id` 家长在「管理孩子」页可改。
- 学期切换：删掉全家 `settings.active_term` 下拉，改成「管理孩子」页按娃改 `users.term_id`（读源换成 `users.term_id`、删 `/api/admin/term` 全家端点）。属破坏性变更，当变更点处理。

**硬骨头（上一步没想的）**
0. **`kid_settings` 接线（P0 COPY 了、读写仍走 settings）**：`cursor_%`/`box_opened`/`milestone_%` 必须改 `get_kid_setting/set_kid_setting`，否则两娃游标/盲盒/里程碑串。
0b. **娃 PIN 独立改接口**：P1 把娃 `pin_hash` 复制成家长 PIN，`/api/admin/pin` 只改家长；`force_pin_change` 是全局的。P2 每娃独立 PIN（家长在「管理孩子」页设，不做 active/passive），`force_pin_change` 改成 per-user。
1. **唯一约束必须 kid 化（P0 已做）**：`complete()`/`checkin()` 靠「已完成」唯一约束判重复（PG 用 `ON CONFLICT DO NOTHING`），约束带 `kid_id` 后两娃才能各自完成同一张 `g5s1-cn-1-1` 且不串。这条漏了 P2 直接是坏的。
2. **不止游标，这些推导全要按娃**：`earned/balance/level_info/streak`（P0 已带参）、`locked_task_ids` 查 `completions` 判「已解锁」、`is_past`、`/api/tasks` 的 `done_ids`、每日任务的个人纪录 `pb` 好成绩循环、`achievements()` 全部徽章计数。漏一处 =「哥哥打了卡，弟弟的课被判已完成」。
3. **刚上线的「学期切换下拉」语义要变**：现在写的是全局 `settings.active_term`（全家一个学期）；多娃后应删掉这个全家开关，改成「在某娃的管理页改该娃的 `users.term_id`」。这是对上一个 commit 已上线功能的**破坏性变更**，要当变更点列出，不是新增。
4. **兑换审批要带娃**：`redemptions` 加 `kid_id`；家长审批「同意」时扣的是**申请人那个娃**的 `balance`（不是全家混账），`balance()` 也按娃。
5. **自定义任务归属要 kid 化**（见第 4 节已改）：`custom-task` 加可选 `kid_id`（NULL=全家），后端校验该娃属于当前家庭。
6. **多娃共用一台平板是常态**：按娃 `Set-Cookie`；「记住这台设备」要按娃分别签名；换娃需登出语义；家长会话里的 `current_kid` 是「当前查看/编辑的娃」，**后端必须校验它属于本 `family_id`**，否则家长靠改参数能看别家娃。
7. **周报从单娃改成全家**：现在 `weekly()` 返回单娃形状（每天一行 earned/spent + by_subject + streak），多娃要重做成「每娃一行汇总 + 全家对比」，是数据结构返工，不是加字段。

**步骤**
1. 把 P1 的会话上下文（`SET LOCAL app.kid_id/app.family_id`）接入所有娃端路由与第 2 条列出的推导助手；业务 SQL 靠 RLS 自动过滤，无需逐函数传 `kid_id`。
2. `/api/tasks` 的 `active_term(c)` → 当前娃 `users.term_id`。
3. `kid_settings` 成 `cursor_%`/`box_opened`/`milestone_%` 读写主源（`get_kid_setting/set_kid_setting`）。
4. 家长端「管理孩子」：增删娃、名字/头像/PIN/`term_id`；`/api/admin/kids` CRUD + 校验 `family_id`。
5. 家长端「切换查看娃」下拉 + `current_kid` 校验；周报/流水/审批按选中娃查。
6. `/api/custom-task` 加可选 `kid_id`。
7. 每娃都建账号（active，不设 passive）：大娃自己登录打卡，小娃由家长在「切换娃」下代点；所有娃 PIN 家长在「管理孩子」页设。

**验收**：哥哥 `g5s1`、弟弟 `g2s1` 各自登录只看到自己的卡；两人同一天都能完成「跳绳」和各自的签到；哥哥完成 `g5s1-cn-1-1` 后弟弟再完成同一张不报「已做过」；家长切换娃，周报/流水/审批/游标/盲盒全跟着切；伪造 `kid_id` 查别家娃返回空/403。

### P3 多家庭（SaaS 多租户）

目标：不同家庭完全隔离；商店/等级/自定义任务按 `family_id`，课程仍走全局多学期目录。（Postgres+RLS 已在 P0 一次性就位，本阶段只做多家庭隔离。）

**已定决定（2026-09）**
- 账号**全局唯一**（`ux_users_account` 保持）：像用户名，先到先得，登录只填一个账号。
- 用户**单家庭单账号**（默认）：`users` 留 `family_id` 单列；一人管多家（memberships 连接表）以后再上。
- `users` 上 RLS（`family_id = 当前家庭`）；登录 + 会话 token 校验走**特权路径**（登录时无 family 上下文，须按 account/id 反查），其余业务查询强制走 `sunshine_app` + RLS。
- **不做「删整个家庭」入口**：只删成员/娃（users/profiles 硬删 + revoked，ledger 流水保留）。整家删除不可逆，危险区，YAGNI。
- **`families` 是目录表，无 RLS**：本身没有 family 维度。不要加「列出全部家庭」的端点。

**硬骨头（上一步没想的）**
0. **`users` 上 RLS（或 login 走独立路径）**：P1 后 `pin_hash/account` 是真敏感数据，`sunshine_app` 现在能 `SELECT * FROM users`。单家庭可忍，多家庭前必须挡住。
1. **Postgres 迁移/RLS 是 P0 的事，别塞回 P3**：本阶段只做「多家庭隔离」，数据库已 Postgres+RLS 就位。
2. **`curriculum_ver` 全局重灌逻辑要按家庭拆**：现在 `apply_curriculum` 用全局 `settings.curriculum_ver` 决定是否重灌；一旦「每家庭独立课程版本」（第 7 节第 10 条）成立，版本号要变成 `family_curriculum_ver(family_id)`、重灌按家庭触发——否则 A 家一换教材，B 家的系统任务也被删了重插。
3. **课程共享、家庭配置不共享**：`terms/units/tasks(教材)/daily_tasks` 全局共享（正确）；`rewards/ranks/custom/ledger/completions/redemptions/tests/kid_settings` 全要 `family_id`（或由 `kid→family` 反查）在 **SQL 层强制**。任何一处漏 `AND family_id=?` 就是跨租户数据泄漏，不能只靠前端藏。
4. **成员权限要回收语义**：**已定不做观察员**（没只读界面，用不上）。家庭里只有家长。删成员/娃 = 硬删 users/profiles + revoked；ledger 流水不删。不做删整个家庭。
5. **会话里的 family 是权威**：所有 `kid_id → family_id` 解析从服务端 `users` 表来，不读前端传的 `family_id` 参数。

**步骤**
1. 隔离在 RLS 之上盖最后一层：`rewards/ranks/custom` 走 family 维度 RLS（P0 已建好），少数跨表聚合过 `family_scope()` 一个 choke point；`/api/admin/*` 从会话注入（不信任前端）。
2. `POST /api/auth/register`（新家庭+首家长；「邀请码入场」：建家庭出码、成员输码加）；`initialize_family()` 为每个新家庭灌默认商店/等级（替代全局 seed）。
3. ~~成员模型改 memberships~~ **以后再上**（已定：单家庭单账号）。P3 邀请码只加家长；删家长立刻 `revoked`。
4. ~~每家庭课程版本~~ **以后再上**（第 7 节第 10 条）。现在教材仍全局一份，`apply_curriculum` 不按家庭拆。

**验收**：两家庭各建娃，A 改的商店/等级/自定义 B 不可见、流水互不可查；删 A 家一个家长后其权限即时失效、数据不孤儿；课程目录两边共享、各自绑学期；用 B 家会话伪造 `kid_id/family_id` 查 A 家返回空/403。

### P4 功能扩展

见 §7.1 P4 总路线图（学习科学纵深为主线、激励/协同次之、多家庭/传播最后），分项详情见 §7.5~§7.8。

---

**发布节奏建议**：P0 单独发一次（纯迁移，最安全，先证明「老数据零丢」）；P1 单独发（账号层，不引入新数据）；P2 单独发（多娃，价值兑现点）；P3 是「是否对外开放」的岔路口，到那一步再定。每阶段都走「备份 → 本机副本升级自检 → commit → 部署 → 冒烟」五步。**先锁 P0+P1+P2**，这是自用价值的 90%。

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

## 7.1 P4 总路线图（2026-09 定稿）

> 把 §7.5（激励/协同）+ §7.6/7.7/7.8（学习纵深）收拢成一条可执行的线。**主线 = 学习科学纵深**（已定重心），激励/协同靠后，多家庭/传播最后。分项详情见 §7.5~§7.8。

### 主线 M · 学习科学纵深（单家庭即用）

| 步 | 做什么 | 依赖 | 交付感 |
|---|---|---|---|
| M1.1 | 结论引擎一期 + 家长端「本周盯点」卡（测试低分/连击/完成量） | 现有数据 | 家长一眼结论 ★ |
| M1.2 | `fitness_standards`（国标）+ 体测弱项结论 | 现有 metrics | 体测可诊断 ★ |
| M1.3 | 打卡页：单元头状态行 + 运动达标进度条 | M1.2 + tests(已有) | 孩子端看到状态 ★ |
| M2.1 | 教材套餐底座（只有江苏，行为零变化） | 无 | 打地基 |
| M2.2 | 考点标签 knowledge_tags（半自动） | M2.1 | 数据 |
| M2.3 | 薄弱点 weak_points（**家长写/孩子读 + RLS**） | M2.2 | 可标记薄弱 |
| M2.4 | 复习提醒 review queue（**家长一键过关**） | M2.3 | 到点提醒重默 |
| M3.1 | 打卡页：今日复习卡 + 孩子版提醒 | M2.4 | 孩子看到动作 |
| M3.2 | 复习到期结论并入「本周盯点」（优先级顶到最高） | M2.4 + M1.1 | 结论达峰 |

> **建议节奏**：M1 整段可先做（现有数据、最快「变聪明」），再回头补 M2 内功底座，最后 M3 收口——即「先让产品看起来聪明，再让它真正聪明」。

### 支线 B · 激励/协同（§7.5，看反馈再启动）

扣分/负分、多娃排行榜、家长汇总面板（全家对比）、家庭共同任务、长辈红包、专注计时/星级（候选）。

### 重线 C · 多家庭/传播（开放给他人再启动）

成长相册、战报分享卡片、班级模式、多版本教材扩展（人教版/北师大目录）。

---

## 7.5 P4 拆分（2026-09 更新 · 结合受欢迎产品对标）

> 定义「受欢迎」= 目前市面上使用多/口碑好的同类品：**ClassDojo**（4500 万学生+家庭）、**Habitica**（游戏化习惯头部）、以及 App Store 家庭积分类头部（家庭积分银行 / Tally 积点 / 成长积分 / 亲子积分乐园）。它们反复出现的机制只有这几条，对照当前项目缺口：
>
> | 受欢迎机制（来源） | 当前项目 | P4 动作 |
> |---|---|---|
> | 任务→打卡→积分→兑奖闭环（全部） | ✅ 已有 | 保持 |
> | 多孩子独立管理（全部） | ✅ P2 已有 | 保持 |
> | **扣分/负分**（家庭积分银行「扣分规则」、Habitica 扣 HP） | ❌ 只有 cancel 回滚 | P4.1 |
> | **星级/质量评分**（亲子积分乐园 1-3 星） | ❌ 固定阳光 | P4.1 候选 |
> | **目标 + 进度条**（ClassDojo goal、Tally 奖励进度） | ⚠️ 只有升级进度 | P4.2 |
> | **家庭共同庆祝**（ClassDojo 邀请家人一同庆祝里程碑） | ❌ | P4.2 |
> | **专注计时**（成长积分） | ❌ | P4.2 |
> | **成长相册/拾光**（成长积分、ClassDojo portfolio） | ❌ | P4.3 |
> | **战报分享卡片**（ClassDojo 成果分享） | ❌ | P4.3 |
> | **自动化周报文案**（成长积分 AI 分析） | ⚠️ 有周报、无自动小结 | P4.3 |
> | **班级点/统一布置任务**（ClassDojo 班级） | ❌ | P4.4 |
> | **排行榜良性竞争**（Habitica party 对比） | ❌ | P4.1 |

### Wave P4.1 —— 家长侧收口（多娃单家庭即用，自用价值最大）

1. **家长汇总面板（全家对比）**
   - 1a. 「全家今日」速览：一屏看每个娃今日完成数 / 余额 / 连击 / 待办。
   - 1b. 周报升级：从「单娃周报」→「全家对比」，每娃本周阳光、完成卡数、连击、环比，末尾给一句通俗结论。
   - 1c. 月报 + CSV 导出（家长按月留档、打印贴墙）。
2. **多娃排行榜**
   - 2a. 三个榜：周阳光榜 / 月阳光榜 / 连击榜。
   - 2b. 只显示名次 + 昵称 + 分数，不显示其他娃明细（保护隐私、不伤大娃）。
   - 2c. 每周日 20:00 结算仪式：家长一键给「周冠军」发额外阳光（对应 Tally「家长确认兑现」）。
3. **扣分 / 负分**（引入受欢迎机制）
   - 3a. 家长主动扣分：写 ledger 负 delta，带原因标签（磨蹭 / 没完成 / 没礼貌）。
   - 3b. 下限保护：不扣到负数、**消费不掉级**铁律不变（沿用）。
   - 3c. 周报单列「本周扣分」诚实反馈。
4. **星级质量评分**（候选，引入亲子积分乐园机制）
   - 4a. 打卡时家长可选 1-3 星质量 → 阳光按星级浮动（1 星基础、3 星加成）。
   - 4b. 星级计入等级进度权重。

### Wave P4.2 —— 家庭协同（多娃单家庭）

5. **家庭共同任务 + 目标进度**
   - 5a. 家长设「家庭目标」：本周全家累计 N 张卡 / 连击 N 天 / 运动 N 次。
   - 5b. 实时进度条 + 每个娃贡献了多少。
   - 5c. 达成 → 全家庆祝动画 + 每人额外阳光（对应 ClassDojo「家庭共同庆祝」）。
6. **专注计时器**（引入成长积分机制）
   - 6a. 学习 / 运动番茄钟，计时结束自动 +N（或计入学时）。
   - 6b. 计时记录进周报「本周专注时长」。
7. **长辈红包**（多家庭，P3 后）
   - 7a. 观察员给娃发「奖励阳光」，额度上限。
   - 7b. 红包留痕：谁发 / 多少 / 为什么。
   - 7c. 频率与额度双重限制（防通胀）。

### Wave P4.3 —— 成长可视化 + 留存拉新（多家庭）

8. **成长相册**（引入「拾光」机制）
   - 8a. 打卡附照片 / 语音（作品照、跳绳视频）存家庭相册。
   - 8b. 时间轴成长墙，按日期翻阅。
9. **成就战报分享卡片**（ClassDojo 分享）
   - 9a. 期末 / 按月生成「成长图」：累计阳光、最高连击、完成卡数、等级曲线。
   - 9b. 一键分享微信 / 朋友圈，自带二维码拉新。
   - 9c. 卡片走 premium-craft 明亮温暖设计语言。
10. **自动化周报**（成长积分 AI 分析）
   - 10a. 每周自动生成一段「本周小结」（模板驱动，不强制依赖大模型）。
   - 10b. 沉到家长端周报卡 + 可推送。

### Wave P4.4 —— 班级 + 课程版本（最重，多家庭，最后做）

11. **班级 / 小团体模式**（ClassDojo 班级点）
   - 11a. 老师建班、学生家庭加入。
   - 11b. 老师统一布置任务，多家庭同做。
   - 11c. 班级榜（匿名昵称）。
   - 11d. 老师-家长站内信（最简）。
12. **每家庭独立课程版本**
   - 12a. 家庭绑定教材版本组合——注意：**语文/道法全国统一部编版**，真正有版本差异的只有**数学（苏教/人教/北师大）、英语（译林/人教）、科学（苏教/教科）**三科。
   - 12b. 新课一键下发、旧课保留。细节见 §7.6 ①。

> **优先级建议**：P4.1 全做（自用立即有回报，全是已验证机制）；P4.2 做 5（家庭目标）和 7（长辈红包），6/4 看孩子反馈再定；P4.3/P4.4 等要开放给其他家庭或老师时再启动。

---

## 7.6 学习科学纵深 + 多版本教材（方案 2026-09）

> 定位一句话：**不做题库、不推题、不判题**（那是作业帮/小猿的主场，硬碰必死）；做的是它们视野外的**补集**——孩子**线下**（作业本/听写/默写/背诵）哪里薄弱、何时该再练，结构化记下来、到点提醒。底盘是**多版本教材**（先做全江苏，架构预留其他省）。

### 四层架构

| 层 | 作用 | 新表/改动 | 作业帮做的？ |
|---|---|---|---|
| ① 教材套餐 bundle | 不同版本教材可切（先江苏） | `bundles` / `bundle_subjects` / `units.bundle_id` / `families.curriculum_bundle` | ✗ 只在它题库内 |
| ② 考点标签 | 单元→课往下钻到「考什么」 | `knowledge_tags`（科目级字典） | ✗ |
| ③ 薄弱点记录 | 线下「哪里没掌握」结构化 | `weak_points` | ✗（它只记待过的题） |
| ④ 间隔复习提醒 | 何时该重练 | `weak_points.review_due_at` + 日队列 | ✗ 它推题不推线下回访 |

---

### ① 教材套餐 bundle（多版本底座）

**现状痛点**：`terms.version="江苏南通"` 写死全局一份；`unit_id = g5s1-cn-1`、`task_id = g5s1-cn-1-1` **不含版本**。所以换个省/出版社，同年级同学期的单元顺序、考点全不同，现有 id 撞不上、也没地方存。

**已确认现状**：当前 catalog 已经就是江苏南通组合（语文部编 / 数学苏教 / 英语译林 / 科学苏教 / 道法部编），56 本，只缺「多版本可切」的壳。所以这一步**不是重新抓教材，是给现有目录装上版本维度**。

**id 约定（关键、写死）**：
- **江苏 = 默认 bundle `js`，id 不带前缀**：`g5s1-cn-1` 原样保留。**completions/ledger/五上手工 id 全部零破坏**。
- **其他 bundle 带前缀**：`rj-g5s1-cn-1`。
- `term_id` 仍是全局学期轴（g5s1~g6x2），不动；版本由「家庭选了哪个 bundle」决定。

**表改动**（迁移 `_migrate_014_curriculum_bundles`）：
```sql
CREATE TABLE bundles (id TEXT PK, name TEXT, region TEXT, is_default INT, created_at TEXT);
ALTER TABLE units ADD COLUMN bundle_id TEXT DEFAULT 'js';  -- 存量回填 js
ALTER TABLE families ADD COLUMN curriculum_bundle TEXT DEFAULT 'js';
```
- `bundle_subjects`（科目→出版社明细表）**第一版不建**：只做江苏单 bundle，映射写死在 seed 即可；上第二套版本再补这张表（YAGNI）。
- `units.bundle_id` 显式标记版本（江苏 js）；tasks 不加列，通过 `unit_id → units.bundle_id` 间接归属。
- **家庭级**选版本（`families.curriculum_bundle`）：同一城市全家用同一套，不比 per-kid；`users.term_id` 仍 per-kid 管年级。
- 查询统一加 `WHERE units.bundle_id = (SELECT curriculum_bundle FROM families WHERE id = :fid)`（走现有 `get_conn()` choke point，RLS 已就位）。

**前端**：设置页「教材版本」下拉（先只有「江苏南通」，人教版/北师大版灰着标「数据未接」）。切 bundle 只影响 units/tasks 显示，不动已完成历史（历史 task 值在 ledger/completions 里留着）。

---

### ② 考点标签 knowledge_tags（科目级字典）

catalog 只有「单元名 + 课次名」，没有「这课考什么」。补一张**科目级**考点字典（跨版本通用，版本特化以后再说）：

```sql
CREATE TABLE knowledge_tags (id TEXT PK, subject_id TEXT, kind TEXT, name TEXT);
-- 示例：cn/字词、cn/背诵、cn/古诗、cn/习作；ma/口算、ma/计算、ma/应用题、ma/图形；en/词汇、en/句型、en/听力
```
- **生成方式**：跟现在 `action` 一样自动预生成（识字课→字词、古诗→背诵、口算→计算…），标 `auto:true`；江苏版五上/五下人工精标。
- 作用：让「薄弱」能从单元粒度精确到「语文第二单元 · 字词」。没有它，复习提醒只能到"第二单元"，太粗、家长还得自己去翻书看哪块错。

> **⚠️ 补充约定 · 考点质量保障（2026-09）**
>
> 上面 20 个考点是「通用能力维度」（字词/计算…），**不是**逐条知识点大纲——那是教师用书 / 作业帮的战场。定位 = 诊断维度，维度粗反而抗错。五条硬约定：
>
> 1. **硬底线 = 映射不错**：有古诗才标古诗、有图形才标图形；维度对不上单元内容的宁缺毋滥。破这条就是误人子弟。
> 2. **诚实文案**：`auto:true` → 家长端必须显示「自动建议，请核对」，**不得**以"本单元重点"的权威姿态出现；仅 `auto:false`（hand）才显示"已核对"。
> 3. **出处可溯源**：20 个考点显式标注"引自课标内容领域"（语文＝识字写字/阅读/习作/口语交际；数学＝数与代数/图形几何/统计概率；英语＝词汇/语法/听说读写），不做无出处的手写。
> 4. **权威精标只覆盖「当前在用单元」**：用苏教数学 / 译林英语 / 部编语文的**教师用书教参**（单元教学目标 / 重难点公开可核对）一对一精标"当前学期在用单元"，**替换**现在"对照手工任务卡"的假精标（英语每单元标满 5 项 = 没精标）。其余单元保持 `auto:true`，不追求 60 单元全对标。
> 5. **家长反馈闭环**：勾选界面留"考点不对"反馈口，家长纠"明显错标"，平台吸纳（家长讲不清完整重点，但纠错标能做主）。

---

### ③ 薄弱点记录 weak_points（线下结构化入口）

`tests` 现在只存 `score + note`，没有「错在哪」。补一张**并与 tests 解耦**（tests 管分数+阳光，weak_points 管诊断+复习，职责不同、不合并）：

```sql
CREATE TABLE weak_points (
  id TEXT PK,                 -- wp-<uuid>
  kid_id TEXT, family_id TEXT,
  unit_id TEXT,               -- 该版本该单元（unit 已带 bundle_id）
  tag_id TEXT,                -- 考点标签，可空（没标签时降级到单元粒度）
  level INT DEFAULT 1,        -- 1薄弱 2未掌握 3待巩固
  note TEXT,
  review_due_at TEXT,         -- 下次该复习时间
  review_count INT DEFAULT 0,
  resolved INT DEFAULT 0,
  created_at TEXT, resolved_at TEXT
);
```
- **埋点**：现有「单元测试」录入表单里（家长端），打完分**追加一步「勾薄弱点」**（从该科目 knowledge_tags 里勾，0~N 个，**勾选不手打**）。这是线下错题的唯一入口。
- **权限（已定）**：weak_points/knowledge_tags 上 RLS；**家长写、孩子只读**——孩子端不暴露「新增薄弱点」入口，只读「今日复习」和「薄弱角标」，防止孩子自评"全会了"把诊断清空（自评水分）。

---

### ④ 间隔复习提醒 review queue

对未 resolved 的 weak_point，按艾宾浩斯轻度间隔推下次时间：**间隔序列 [1,3,7,14,30] 天**（首次 1 天后、过再过 3 天…）。

- `review_due_at = 标记时间 + 间隔[review_count]`。
- 到点 → 孩子端/家长端出现「**今日复习**」队列：该重默的字词、该重背的课文、该重做的口算类型。
- 复习结果**由家长判定（已定）**：家长在面板上对到期的点一键「**已巩固** → resolved=1（或 level 降档）」「**还在错** → 间隔重置、从 1 天重来」。**不靠孩子自评**。
- **只提醒「去做你练习册上的这件事」**，不推题不判题——这是和作业帮最后一线差异：它把你焊在屏幕里刷题，我们提醒你回到纸上。

---

### 闭环数据流

```
家长选「教材版本」--(families.curriculum_bundle)
  → 该家 units/tasks 切到对应版本
  → 单元测试打分(tests) + 勾薄弱点(weak_points, tag 来自 knowledge_tags)
  → 按间隔算 review_due_at
  → 到点 →「今日复习」提醒重默字词/重背课文
  → 复习完成 → 家长判「已巩固 resolved / 还在错重置间隔」
  → 全家未 resolved 薄弱点 → 家长面板「下周该盯什么」
```

### 与作业帮的边界（收敛成一句）

**它做「题在哪、对错、再给我题」；我们做「你纸上哪里错、哪天该重练、数据是你自家 Postgres 的」。** 互补的补集，不是同一根赛道。唯一诚实的前提：孩子已在刷作业帮的家庭，我们这条价值有限；但「记录线下学习」的用户，作业帮就是失明的。

### 实施顺序（对应 §7.1 总表 M 编号）

1. **M2.1 教材套餐底座**：`bundles` + `units.bundle_id` + `families.curriculum_bundle` + 迁移 + 设置页下拉（只有江苏）。架构就位、行为零变化。
2. **M2.2 考点标签**：`knowledge_tags` 建表 + seed 入库。**数据已就绪**（`data/knowledge_tags.json`，精标 50 + auto 199，`gen_knowledge_tags.py` 可复现）。
3. **M2.3 + M2.4 薄弱点 + 复习提醒**：weak_points 表 + 测试表单勾选埋点 + 孩子端「今日复习」队列 + 家长面板「下周盯点」。← 核心交付。
4. **重线 C（以后）**：人教版/北师大版目录抓取接入，回到 7.5 Wave P4.4 的「新课一键下发」。

---

## 7.7 语义化家长视图（结论引擎）

> 定位：把「数据看板」升级成「家庭医生式诊断」。别人停在一屏数字（本周 23 张卡），我们给每娃每周**只一句话**：「下周盯它」，判断 + 动作，不是数字。
>
> **与 7.6 的关系**：7.6 是**数据生产**（薄弱点/复习），7.7 是**数据消费**（把一堆数据翻成结论）。但结论引擎能**先用现有数据跑起来**，不必等 7.6。

### 结论类型（数据源 → 一句话 → 可点动作）

**第一期（现有数据，不依赖 7.6）**
1. **测试连续低分**（`tests`）：某单元最近 2~3 次 score < 阈值 → «语文第二单元连续两次没过 80 分» → 跳该单元重做。
2. **体测弱项**（`daily_metrics` 记录 vs 达标线）：«跳绳离一年男子达标 100 个还差 20» → 跳运动打卡（需新建 `fitness_standards`，见下）。
3. **连击断裂**（`checkins`/`completions` 推 streak）：«这周连击断了 2 次» → 跳「签到”。
4. **完成量下滑**（`completions` 环比）：«完成卡数比上周少了三成» → 无强动作，进周报即可。

**第二期（依赖 7.6）**
5. **复习提醒到期**（`weak_points.review_due_at`）：«语文第二单元·字词该重默了» → 跳「今日复习」。**最高优先级、最可执行**。

### 优先级（一次只出一条，按序取第一条）

复习到期 > 薄弱单元(连续低分) > 体测弱项 > 连击断裂 > 完成量下滑

### 结论引擎实现（规则，不调大模型）

- 纯函数 `build_insights(kid) -> Insight | None`，if-then 规则。**可解释、可复现、家长能看懂**（契合反术语 + 数据准确）。
- Insight 结构：`{ type, severity, text, action_link, source }`；`source` 带原始数据（哪次测试几分、哪项指标差多少）。
- 生成时机：**实时算**（数据量小，跟「ledger 纯推导、不物化周报」同一原则），家长打开面板/周报时算。
- 一条结论必须能落到**一个动作**；给不出动作的（如「成绩下滑」这种空话）不生成。

### 结论规则阈值（默认值 + 家庭可改，已定）

「每个家庭对孩子的要求不同」，阈值**不写死**：内置默认值，家长在设置页可改。

```python
INSIGHT_DEFAULTS = {
  "test_fail_count": 2,    # 连续几次低分算「薄弱单元」
  "test_fail_score": 80,   # 低于多少分算低
  "drop_ratio": 0.3,       # 完成量比上周少多少算「下滑」
  "streak_break": 2,       # 连击断几次值得在结论里提
}
```

- 存储：`families.insight_rules TEXT DEFAULT ''`（JSON 覆盖项，空 = 全用内置默认）；引擎 `merge(INSIGHT_DEFAULTS, family.insight_rules)`。
- 家长在设置页「诊断阈值」区块改（每项带「恢复默认」）；结论文案里的数字（如「没过 80 分」）随阈值变。
- **家庭级一个值**（不比 per-kid）：家长对全家孩子的标准通常一致；真有个别娃要单独标准，以后再加 per-kid 覆盖。

### 新表 fitness_standards（国家体测达标线，数据已就绪）

```sql
CREATE TABLE fitness_standards (
  grade INT, gender TEXT, item TEXT, pass_value REAL, unit TEXT, direction TEXT, -- high 越多越好
  PRIMARY KEY (grade, gender, item)
);
-- item：跳绳(次/分)、仰卧起坐(次/分)、体前屈(cm)
```
- 数据源：**《国家学生体质健康标准(2014 年修订)》**（全国统一、江苏执行同一套），按年级+性别录单项评分表；**必须据官方文件录，不拍脑袋填数字**。
- **达标基准 = `pass_value`（60 分及格线）**；`good_value`/`excellent_value` 留作「良好/优秀」进阶展示。
- **数据已就绪**：`data/fitness_standards.json`（跳绳/体前屈 1-6 年级、仰卧起坐 3-6 年级，男/女三档），seed 入库即可。

### 呈现

- 家长端首页顶部「**本周盯点**」卡：每娃一行 `[头像+名字] [一句话结论] [去解决 →]`。
- **反堆砌**：一娃最多一条，其余数字收进周报详情，不在首页铺。
- 「去解决」跳对应单元/测试/运动打卡锚点。

### 与 7.6 的依赖与先后建议

- **7.7 一期可先于 7.6 交付**：测试低分 / 连击 / 完成量现在就有数据，体测弱项只差一张标准表，做完即「比积分器聪明」的观感。
- 7.7 二期「复习到期」依赖 7.6 的 weak_points，等底座好再并入。
- 推荐顺序变更：**先 7.7 一期（快见效）→ 再 7.6（把结论变精确）→ 7.7 二期（结论达峰）**。

### 实施顺序（对应 §7.1 总表 M 编号）

1. **M1.1** 结论引擎骨架 + 测试低分 / 连击 / 完成量三类（纯现有数据）+ 家长端「本周盯点」卡。
2. **M1.2** `fitness_standards` 建表 + seed 国标入库 + 体测弱项结论（**数据已就绪** `data/fitness_standards.json`，达标 = `pass_value` 60 分线）。
3. **M1.3(运动卡)** 打卡页运动达标进度条（比对 `completions.metrics`）。
4. **M3.2（等 7.6）** 复习到期结论并入，优先级顶到最高。

---

## 7.8 打卡页（孩子端）呈现层

> 对——现在打卡页确实薄：每个单元就是「任务卡 + 勾选 + 阳光」，单元名旁挂一个测试分数，没了。没有任何「学习状态」：这单元我学得怎么样，不知道；哪些字词该重默了，不知道；体测差多少，不知道。
>
> 而这个面才是 7.6/7.7 的**最后落地一公里**：复习提醒、薄弱点、体测达标这些纵深，如果不落进孩子每天点的这个页，就成了「家长端有个结论，孩子端啥也没变」——前面全白做。

### 两条铁律（儿童产品，别堆）

1. **反堆砌**：不往每张卡塞东西，只往「单元头」「今日推荐顶部」加少量状态，详情点进去看。孩子要的是清爽的“今天做什么 + 做完有奖励”。
2. **给动作，不给评价**：孩子版只出「今天该重默第二单元字词了」，**绝不**出「你第二单元没掌握」这种诊断。诊断给家长（7.7），动作给孩子。

### 丰富清单（对齐 7.6/7.7）

| 位置 | 加什么 | 来源 |
|---|---|---|
| 今日推荐 · 顶部 | 「今日复习」卡 1~2 条（该重默的字词 / 背的课文） | 7.6 review queue |
| 今日推荐 · 顶部 | 孩子版一句提醒（«体测跳绳还差 20 个»） | 7.7 结论引擎（转儿童向文案） |
| 单元页 · 单元头 | 状态行：测试分 + 「薄弱」小标签 + 「该复习了」 | 7.6 weak_points + tests |
| 单元页 · 任务卡 | 有薄弱点的课，卡上加个小角标圆点（不做全卡变色） | 7.6 knowledge_tags × weak_points |
| 每日任务 · 运动卡 | 达标进度条（`离达标差 X`，不是光勾选） | 7.7 fitness_standards |

### 与 7.6/7.7 的接线

- 今日复习卡 / 薄弱角标 = 7.6 的 `weak_points` + `review_due_at` 反哺回任务卡。
- 体测进度条 = 7.7 的 `fitness_standards` 比对 `completions.metrics`。
- 孩子版提醒 = 7.7 `build_insights()` 同源，但套**儿童向模板**（只动作、无评价）。

### 实施顺序（对应 §7.1 总表 M 编号）

1. **M1.3a** 单元头状态行（测试分已有，加薄弱标签 + 该复习），纯前端 + tests 数据。
2. **M1.3b** 运动卡达标进度条（等 M1.2 建表）。
3. **M3.1** 「今日复习」卡 + 孩子版提醒（等 M2.4 的 weak_points + M1.1 引擎）。

> 依赖关系：P4.7a 可独立先做（现在就有 tests 分数）；P4.7b 等 7.7 的达标表；P4.7c 等 7.6 全套。

---

## 7.9 M1.1 开工规格（结论引擎一期 + 本周盯点卡）

> 范围：一期结论引擎（3 类，纯现有数据）+ 阈值可配 + 家长端「本周盯点」卡。**不含**体测弱项（M1.2）、复习到期（M3.2）。

### 数据模型（迁移 014）

```sql
ALTER TABLE families ADD COLUMN insight_rules TEXT DEFAULT '';  -- JSON 覆盖，空=全默认
```
- `db.py` 加 `_migrate_014_insight_rules` + 注册 `("014_insight_rules", _migrate_014_insight_rules)`。

### 规则常量（main.py）

```python
INSIGHT_DEFAULTS = {
    "test_fail_count": 2,    # 连续几次低分算薄弱
    "test_fail_score": 80,   # 低于多少分算低（0-100）
    "drop_ratio": 0.3,       # 完成量比上周少多少算下滑
    "streak_break": 2,       # 连击断几天值得提
}

def insight_rules(c):
    raw = c.execute("SELECT insight_rules FROM families WHERE id=?", (_fam.get(),)).fetchone()
    merged = dict(INSIGHT_DEFAULTS)
    try: merged.update(json.loads(raw["insight_rules"] or "{}"))
    except Exception: pass
    return merged
```

### 结论引擎（build_insights，按优先级取 1 条）

优先级（一期） = `weak_unit > streak_break > drop`。每类结论给出 `{type, text, action, source}`。

**① weak_unit — 测试连续低分**
```
对每个该娃有 tests 的 unit_id（date desc, id desc）：
  取最近 test_fail_count 次；若凑够 count 且全部 score < test_fail_score，
  且最近一次 date 距今 <= 30 天 → 命中。
text = f"{subject}《{unit名}》连续 {count} 次低于 {score} 分"
action = "单元测试"  source = {unit_id, 各 score}
```

**② streak_break — 连击断裂**
```
weekdays_passed = (today - 本周一).days + 1
active_days = COUNT(DISTINCT date) WHERE date IN [周一, today] 来自 checkins ∪ completions(completed)
gap = weekdays_passed - active_days
if gap >= streak_break → text = f"这周有 {gap} 天没打卡"  action = "每日打卡"
```

**③ drop — 完成量下滑**
```
this = COUNT(completions completed, date∈[本周一, today])
last = COUNT(completions completed, date∈[上周一, 上周日])
if last > 0 and this < last * (1 - drop_ratio)
  → text = f"完成比上周少 {round((1 - this/last)*100)}%"  action = None（进周报即可）
```

### Endpoint（2 个，均 require_parent；RLS 下逐娃 apply_scope，仿 redemptions_admin）

1. `GET /api/admin/insights` → `{ rules, kids: [{kid_id, name, insight|null}] }`
   - 遍历 roster，`apply_scope(c, fam, kid)` → `build_insights(c, kid)` 取 1 条。
2. `PUT /api/admin/insight-rules` body `{test_fail_count, test_fail_score, drop_ratio, streak_break}`
   - 校验范围（score 0-100 / count 1-10 / ratio 0.1-0.9 / break 1-7），写 `families.insight_rules` JSON，返回合并后的 rules。

### 前端落点（Admin.vue）

- 新 **section `insights`「本周盯点」**，挂进「概览」组（weekly 旁）：每娃一行 `[头像+名字] [text] [去解决→]`，一娃最多一条。
- 家长端设置页新增「诊断阈值」卡：4 个数字输入 + 每项「恢复默认」，调 `PUT /api/admin/insight-rules`。
- `text` 里的数字（如「连续 2 次」「少 30%」）跟 rules 实时挂钩。

### 验证（挂进 pre_deploy.sh）

- 新增 `backend/test_insights.py`：造 tests/completions/checkins 数据 → 断言 3 类结论各命中/不命中边界 + 阈值 merge + PUT 校验。
- `pre_deploy.sh` 加一行 `python3 test_insights.py`。

---

## 7.10 M1.2 开工规格（体测达标后端）

> 范围：`fitness_standards` 建表 + seed 入库 + 引擎加「体测弱项」第 4 类结论 + kids 加 gender。前端运动卡进度条属 M1.3。

### 前置缺口（M1.2 独有）：孩子没有性别

- `fitness_standards` 分**年级 × 性别**，`users` 无 `gender` 列 → 必须补。
- `gender` 由家长在「管理孩子」页设（可选）；**未设时体测结论直接跳过**，不硬设默认，避免瞎判。

### 数据模型（迁移 015）

```sql
ALTER TABLE users ADD COLUMN gender TEXT DEFAULT NULL;   -- '男' / '女' / NULL
CREATE TABLE fitness_standards (
  grade INT, gender TEXT, item TEXT,
  pass_value REAL, good_value REAL, excellent_value REAL,
  unit TEXT, direction TEXT DEFAULT 'high',
  PRIMARY KEY (grade, gender, item)
);
```
- `db.py` 加 `_migrate_015_fitness` + 注册；**迁移内读 `data/fitness_standards.json` 的 `rows` 幂等 INSERT**（`ON CONFLICT DO NOTHING`，同 `seed_ranks` 套路）。

### 指标对齐映射（main.py 常量）

```python
FITNESS_METRIC = {
    "跳绳":     ("pe-jump-rope", "n1m"),   # 1 分钟跳多少个
    "仰卧起坐":  ("pe-situp",    "cnt"),   # 1 分钟做多少个
    "坐位体前屈": ("pe-bend",     "cm"),    # 手指过脚尖多远
}
```

### build_insights 加第 4 类 fitness

优先级涨为 = `weak_unit > fitness > streak_break > drop`。口径：
```
gender = kid.gender; grade = int(term_id 首个数字); 无 gender/grade → 跳过
对每个 FITNESS_METRIC item：
  pass_ = fitness_standards[grade, gender, item].pass_value
  last = 该娃最近 14 天 completions.metrics[metric_id] 的最新非空值
  若 last 存在且 last < pass_（均为越高越好）→ 候选，取差距最大的 1 项
  text = f"{item}离达标还差 {round(pass_-last,1)}{unit}"  action = "运动打卡"
  source = {item, last, pass_}
```

### endpoint 变更

- **并入** `GET /api/admin/insights`（体测结论只是第 4 类，不新增独立端点；无阈值可配）。
- `Kids create/update`（`KidIn` 加 `gender`）+ 前端「管理孩子」页加性别下拉（可选，年级/性别用于推导体测）。

### 前端

- 后端只需让 `insights` 的 fitness 结论带 `item/pass/last/unit`；运动卡达标进度条在 M1.3 做。

### 验证（并入 test_insights.py）

- 造 daily completion `metrics` + 达标线 → 断言「低于达标」命中、「高于达标」不命中、「gender 为空」跳过。

---

## 7.11 M2.3 开工规格（薄弱点记录：家长写 / 孩子读）

> 范围：`weak_points` 建表 + 家长勾选薄弱考点 + 孩子端单元页「薄弱」只读标签。**不含**复习提醒队列 / 一键过关（M2.4）。
> 权限：复用 tests 模式 —— `kid_id` RLS + 家长 admin 特权读写 + 孩子 kid scope 只读。

### 数据模型（迁移 018）

```sql
CREATE TABLE IF NOT EXISTS weak_points (
  id {pk},
  kid_id TEXT NOT NULL,
  unit_id TEXT NOT NULL,
  tag_id TEXT NOT NULL,               -- → knowledge_tags.id（勾选，不手打）
  note TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',          -- open(待巩固) / resolved(已巩固)
  interval_idx INTEGER NOT NULL DEFAULT 0,      -- 0..4 → [1,3,7,14,30] 天
  review_due_at TEXT,                           -- 下次复习到期日；NULL=还没排期（M2.4 才排）
  created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_wp_kid ON weak_points(kid_id);
CREATE INDEX IF NOT EXISTS ix_wp_kid_unit ON weak_points(kid_id, unit_id);
```
- `db.py` 加 `_migrate_018_weak_points`；**PG 下**同 003 套路：`ENABLE/FORCE RLS` + policy `iso USING (kid_id = current_setting('app.kid_id', true)) WITH CHECK (同)`。sqlite 跳过 RLS。
- 注册 `("018_weak_points", _migrate_018_weak_points)`。

### 复习间隔 + 状态机（M2.4 才排期，M2.3 只建字段）

```python
WEAKPOINT_INTERVALS = [1, 3, 7, 14, 30]   # 天；interval_idx 是数组下标
# 状态机语义（在此定死，避免 M2.4 返工）：
#   新建 → status='open', interval_idx=0, review_due_at=NULL
#   M2.4 到期：家长「已巩固」→ status='resolved'（review_due_at 留痕）
#             家长「还在错」→ interval_idx=0（重置），review_due_at=今天+1 天
#   review_due_at=NULL 表示该薄弱点尚未进入复习队列
```

### API（家长 3 + 孩子 1）

- `GET /api/admin/weak-points?kid_id=x&unit_id=y`（require_parent）→ 该娃该单元当前 weak_points（含 tag name）。
- `PUT /api/admin/weak-points`（require_parent）body `{kid_id, unit_id, tag_ids[], note}` → **替换式**（先删该 kid+unit 旧行，再插勾选的；`tag_ids` 至少 1 个）。
- `DELETE /api/admin/weak-points/{id}`（require_parent）→ 删单条。
- `GET /api/weak-points?unit_id=y`（require_kid）→ 当前娃该单元 weak_points（只读，RLS 过滤）。
- 家长读写都应 `db.apply_scope(c, fam, kid)` 到目标娃（仿 insights_admin / redemptions_admin），否则 RLS 会把目标行滤掉。

### 前端落点

- 家长端 Admin.vue「单元测试」区，每单元加「标薄弱」按钮 → dialog 列 `unit_tags → knowledge_tags`（该单元考点）勾选 + 可选 note → `PUT`。
- 孩子端 App.vue 单元页：单元名下方显示「薄弱：字词 / 计算」小标签（来自 `GET /api/weak-points`，只读，**无新增入口**）。

### 验证（新增 test_weak_points.py，挂 pre_deploy）

- 家长 PUT 勾选 → 孩子 GET 读到自己、**读不到别人的**（RLS/scope）。
- 替换式语义：二次 PUT 覆盖旧勾选。
- `tag_ids` 空 → 400。
- 孩子无写接口（`/api/weak-points` 只有 GET）。

---

## 8. 关键技术决策

| 决策点 | 推荐 | 理由 |
|---|---|---|
| 多租户隔离模式 | **共享库 + 行级 `family_id` 过滤**（pooled + row-level） | 家庭量级下最简单；`kid_id` 已经天然是行级隔离，加 `family_id` 只是往上套一层。参考 sequere.com / eltherion.com 的三种模型对比 |
| 数据库 | **Postgres + 自写 RLS（单容器）** | 已拍板上 Postgres+RLS，隔离在库层一次生效、无法遗漏；但**只上裸 Postgres 单容器**，不上完整 Supabase 栈（GoTrue/PostgREST/Kong 7+ 容器、≥4GB 内存，家庭 app 用不上）。SQLite 仅作起步过渡 |
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
6. **weak_points / knowledge_tags 上 RLS**（跟 profiles/daily_tasks 同套路），诊断数据不比打卡数据松。
7. **诊断权归家长**：薄弱点家长写、孩子只读，孩子端不暴露「新增薄弱点」入口——否则孩子自评"全会了"把诊断清空。
8. **复习过关由家长判**（一键「已巩固/还在错」），不靠孩子自评。
9. **fitness_standards 达标线必须据《国家学生体质健康标准》官方文件录**，禁止拍脑袋填数字。

---

## 10. 参考资料

- 多租户三种数据隔离模型对比：https://sequere.com/multi-tenant-saas-data-model 、https://eltherion.com/blog/multi-tenant-data-isolation-schema-per-tenant-vs-row-level
- 多子女奖励系统现成实现（REWARD+RLS 隔离）：https://github.com/nitin27may/child-reward-system
- ClassDojo 家庭/班级点与家长账号模型：ClassDojo 官方帮助（家长账号跨多个孩子/班级查看 Point Report）
- 家庭多成员隔离与角色权限讨论：https://forum.trae.cn/t/topic/49537

## 11. 对照开源项目的取舍（2026-09 调研）

对照两个真实项目：**nitin27may/child-reward-system**（Next.js 16 + Supabase Postgres/RLS + Auth，多娃多家庭、双轨积分、孩子可只读）和 **bibinantony1998/family-command-center**（React + Supabase RLS，家务/积分/兑换 + 邀请码）。两人都不约而同选了 **Postgres + 数据库层 RLS + 托管 Auth + 邀请码入场**。

| 它们的做法 | 对我们的含义 | 采纳？ |
|---|---|---|
| **RLS 在库层强隔离**（每表 policy + `get_my_family_id()`/`auth.uid()`），不是 app 里到处 `WHERE family_id` | P3 别在 20 个端点手写 `AND family_id`；用一个 choke point / RLS 一次生效、无法遗漏。也意味着 SQLite（无 RLS）到 P3 就该上 Postgres | ✅ 采纳（P3 步骤已改） |
| **托管 Auth**（Supabase Auth：邮箱/密码、Google OAuth；`auth.users` 是身份，业务表只存 `profile` 映射 family+role） | P1 别手搓 token；身份认证交给成熟库/提供商 | ✅ 采纳（P1 第 8 条已定） |
| **邀请码入场**（建家庭 → 出码 → 成员输码加入，角色 parent/kid） | P3 注册用邀请码而非邮箱/手机，最简 | ✅ 采纳 |
| **signup 触发建 profile → `initialize_family()` 灌默认** | rewards/ranks 默认从「全局 seed」改成「每家庭 initialize_family()」 | ✅ 采纳（P3 步骤 2） |
| **孩子可只读、家长是主操作者**（nitin27may：child 可选 read-only login） | 给娃加 `active/passive` 角色：大娃 active 自己打卡、小娃 passive 家长代打卡/只读 | ✅ 采纳（P2 步骤 7） |
| **双轨积分**（周刷新屏幕时间 / 累计基金，可负） | ledger 加可空 `track` 列留坑，支持平行账户；现在用不到先不加 | ⚠️ 留坑（P4 定） |
| **扣分/负分**（deductions，表现不好扣点） | 我们现在只有 cancel（负回滚），无「主动扣分」；家长大概率要 | ⚠️ P4 候选 |
| **物化周报 + 触发器**（`weekly_summaries` + trigger 同步） | 我们「ledger 纯推导」更干净、无状态漂移 | ❌ 刻意不抄 |
| **版本化迁移**（`supabase/migrations/*.sql` + `db push`） | SQLite 现在用 `init_db` 的 `ALTER IF NOT EXISTS` 先扛；上 Postgres 时改版本化迁移 | ⚠️ P3b 一并做 |

**最大的一条教训**：两个「家庭 reward」项目都站在「Postgres + RLS + 托管 Auth」肩上，多租户隔离和登录几乎是免费的；我们之前 P0-P2 要逐函数穿 `kid_id`、手搓 token，是因为还站在 SQLite + 手写认证上。现已拍板：**上 Postgres + RLS，走裸 Postgres 单容器路线，不搬整套 Supabase**。

### 第二轮对照（更成熟的标杆）

| 项目 | 强项 | 对我们：采 / 不采 |
|---|---|---|
| **Habitica**（HabitRPG，GPL，最成熟的游戏化习惯 App） | 领域模型：XP/HP/金币/法力**多轨积分**、任务分 habit/daily/todo/**reward 四型**、Party(≤30)小团体、失败扣 HP（主动负分） | ✅ 借多轨积分 + 负分 + Party≈未来「班级/团」（第 7 节）；❌ 仍是 MongoDB，数据模型对我们不适用 |
| **Cal.com**（自托管多租户 SaaS） | 组织/团队 + **memberships 连接表**（用户可跨多组织多角色 Owner/Admin/Member）+ PBAC 细粒度权限 | ✅ 借 memberships 连接表——不要把 `role` 写死在 `users`；⚠️ PBAC 对家庭 app 过度，先不抄 |
| **Dub.co**（Next.js+Prisma+Postgres） | 干净多租户：`projectId`≈family_id + members 角色 join，作用域按项目维度过滤 | ✅ 印证「family_id + members join」这版图；❌ 它用 Upstash Redis 做缓存/重定向，我们规模不需要 |
| **PocketBase**（15MB 单 Go 二进制） | 单二进制自带 Auth + 实时 + 文件存储 + 内嵌 SQLite，RPi 上 50MB RAM 跑 | ✅ 记住「轻量自托管」这个选项当退路；❌ 内嵌 SQLite **无 RLS**，不符合已定的 Postgres+RLS |

**关键澄清——「Postgres+RLS」≠「Supabase」**：完整 Supabase 自托管是 7+ 容器、≥4GB 内存（GoTrue/PostgREST/Kong…）。我们要的是**裸 Postgres 单容器 + 自写 RLS + 轻量登录（itsdangerous 或单独 GoTrue）**，拿到「隔离在库层自动生效」的全部收益，同时保持轻量部署。

**结论**：Postgres+RLS 已定，走裸 Postgres 单容器；领域机制向 Habitica 借（多轨积分/负分），权限模型向 Cal.com/Dub 借（memberships join），部署复杂度向 PocketBase 看齐（能单进程不铺多容器）。