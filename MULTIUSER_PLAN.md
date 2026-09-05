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

**硬骨头（上一步没想的）**
0. **`kid_settings` 接线（P0 COPY 了、读写仍走 settings）**：`cursor_%`/`box_opened`/`milestone_%` 必须改 `get_kid_setting/set_kid_setting`，否则两娃游标/盲盒/里程碑串。
0b. **娃 PIN 独立改接口**：P1 把娃 `pin_hash` 复制成家长 PIN，`/api/admin/pin` 只改家长；`force_pin_change` 是全局的。P2 拆 active/passive 时必须给娃单独改 PIN，并把 `force_pin_change` 改成 per-user。
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
7. 孩子账号加 `active/passive` 角色开关：大娃 active 自己登录打卡；小娃 passive 由家长在「切换娃」下代打卡或只读（省掉小娃的多设备登录 + 「免密击穿」问题，参考 nitin27may 的 read-only child）。

**验收**：哥哥 `g5s1`、弟弟 `g2s1` 各自登录只看到自己的卡；两人同一天都能完成「跳绳」和各自的签到；哥哥完成 `g5s1-cn-1-1` 后弟弟再完成同一张不报「已做过」；家长切换娃，周报/流水/审批/游标/盲盒全跟着切；伪造 `kid_id` 查别家娃返回空/403。

### P3 多家庭（SaaS 多租户）

目标：不同家庭完全隔离；商店/等级/自定义任务按 `family_id`，课程仍走全局多学期目录。（Postgres+RLS 已在 P0 一次性就位，本阶段只做多家庭隔离。）

**硬骨头（上一步没想的）**
0. **`users` 上 RLS（或 login 走独立路径）**：P1 后 `pin_hash/account` 是真敏感数据，`sunshine_app` 现在能 `SELECT * FROM users`。单家庭可忍，多家庭前必须挡住。
1. **Postgres 迁移/RLS 是 P0 的事，别塞回 P3**：本阶段只做「多家庭隔离」，数据库已 Postgres+RLS 就位。
2. **`curriculum_ver` 全局重灌逻辑要按家庭拆**：现在 `apply_curriculum` 用全局 `settings.curriculum_ver` 决定是否重灌；一旦「每家庭独立课程版本」（第 7 节第 10 条）成立，版本号要变成 `family_curriculum_ver(family_id)`、重灌按家庭触发——否则 A 家一换教材，B 家的系统任务也被删了重插。
3. **课程共享、家庭配置不共享**：`terms/units/tasks(教材)/daily_tasks` 全局共享（正确）；`rewards/ranks/custom/ledger/completions/redemptions/tests/kid_settings` 全要 `family_id`（或由 `kid→family` 反查）在 **SQL 层强制**。任何一处漏 `AND family_id=?` 就是跨租户数据泄漏，不能只靠前端藏。
4. **成员权限要回收语义**：parent（全权）/observer（只读）；删成员、删家庭时，该成员名下数据归属怎么处理（软删 / 级联 / 移交给首家长）——不定义就是孤儿数据。
5. **会话里的 family 是权威**：所有 `kid_id → family_id` 解析从服务端 `users` 表来，不读前端传的 `family_id` 参数。

**步骤**
1. 隔离在 RLS 之上盖最后一层：`rewards/ranks/custom` 走 family 维度 RLS（P0 已建好），少数跨表聚合过 `family_scope()` 一个 choke point；`/api/admin/*` 从会话注入（不信任前端）。
2. `POST /api/auth/register`（新家庭+首家长；「邀请码入场」：建家庭出码、成员输码加）；`initialize_family()` 为每个新家庭灌默认商店/等级（替代全局 seed）。
3. 成员模型改 **memberships 连接表**（`user_id, family_id, role`）：一个用户可跨家庭/多角色，配合邀请码 + 角色回收（Cal.com/Dub 教训）；`parent/observer` 不再写死在 `users` 上。
4. 每家庭课程版本 → `family_curriculum_ver(family_id)`，`apply_curriculum` 按家庭重灌。

**验收**：两家庭各建娃，A 改的商店/等级/自定义 B 不可见、流水互不可查；删 A 家一个家长后其权限即时失效、数据不孤儿；课程目录两边共享、各自绑学期；用 B 家会话伪造 `kid_id/family_id` 查 A 家返回空/403。

### P4 功能扩展

见第 7 节（排行榜/全家汇总/家庭共同任务/长辈红包/班级模式/成就战报…），按「多娃单家庭（P2 解锁）」优先、多家庭（P3 后解锁）次之逐个上。**不改第 7 节现在的顺序。**

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