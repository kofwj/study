# 运维速查

> 所有命令按「本机(Mac)」和「VPS」区分。源码在本机 `/Users/jian/Downloads/study`，线上在 VPS `/home/kofwj/sunshine`（以下用 `~` 代指）。

## 一、改教材（多学期 / 多科目）

教材目录从「电子课本网 dzkbw.com」抓取，再转成多学期 seed。**只改数据不碰代码**。

> 口径：目录只到「单元 + 课」粒度；每课的「动作/怎么做」仍靠 `gen_seed.py` 里的关键词规则给默认值，精确到手录级仍需人工过（参照当年五上实物核对）。

### 数据流

```
dzkbw 目录 → scripts/fetch_catalog.py(单本) → scripts/gen_catalog.py(批量) → data/catalog.json
                                                                                  ↓
                                                                     scripts/gen_seed.py(转换)
                                                                                  ↓
                                                          data/tasks.seed.multi.json + 核对表
```

### 下册 / 新学期换新版

1. 抓最新目录（实时抓站点书目，新版 slug 一上线自动覆盖）：
   ```bash
   cd /Users/jian/Downloads/study && python3 scripts/gen_catalog.py --save
   ```
2. 重新生成多学期 seed（五上语数英科学道法会自动使用人工核实版覆盖）：
   ```bash
   python3 scripts/gen_seed.py
   ```
3. 重建考点字典和单元映射：
   ```bash
   python3 scripts/gen_knowledge_tags.py
   ```
4. 升级 `gen_seed.py` 顶部 `curriculum_ver`——**这个值变了，线上才会刷新系统任务；考点映射变更还需要在 `backend/db.py` 增加迁移**。
5. 提交推送 + 部署（见「三、日常更新」）。

### 补 4 科 / 加新学科

- 目录来源见 `data/textbook-index.md`（版本 × 年级 × 站点路径 + 版次推进）。
- 在 `scripts/gen_seed.py` 的 `SUBJECTS`/`SPLIT`/`ACTION` 里加对应的切分与动作规则。
- 主课（语数英科道法）已配好；音美/综合因无稳定电子课本，当前不做。

> 换学期后旧完成记录自动隔离（任务 ID 带 `g5s1-`/`g5x2-` 等学期前缀），不污染等级/流水。家长端「已学到」游标也带前缀，新学期重新拨。

## 二、备份与还原（只用 SQLite）

生产库：`/home/kofwj/sunshine/data/sunshine.db`。不要再启 PostgreSQL，也不要写 `DATABASE_URL`。

**定时备份**（每天 02:15、18:15，保留最近 20 份）：

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'cd /home/kofwj/sunshine && bash scripts/install_backup_cron.sh'
```

手动备份：

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'cd /home/kofwj/sunshine && bash scripts/enhanced_backup.sh'
```

备份落在 `/home/kofwj/sunshine/data/backups/sqlite_YYYYMMDD_HHMMSS.db`。部署脚本也会先备份再拉代码。

**还原**（会先停容器、再把当前库另存为 `pre_restore_*.db`，然后拷回指定备份）：

```bash
# 列出备份（流水条数 / 阳光）
ssh root@192.168.100.5 'cd /home/kofwj/sunshine && bash scripts/restore_db.sh'

# 先看会还原哪一份
ssh root@192.168.100.5 'cd /home/kofwj/sunshine && bash scripts/restore_db.sh --latest --dry-run'

# 真正还原最近一份
ssh root@192.168.100.5 'cd /home/kofwj/sunshine && bash scripts/restore_db.sh --latest'
```

## 2.5 本地前端（改 Vue 必跑，不用上 VPS 才知道白屏）

本机 PATH 经常没有 node，脚本会用 `~/.hermes/node/bin`。

```bash
bash scripts/smoke_frontend.sh          # vite build + 产物/结构冒烟
bash scripts/pre_deploy.sh              # pytest + 上面这条
```

冒烟会拦住「`.login-screen` 套进 `.desk`」那种白屏。不装 Playwright。

## 三、日常更新（备份 → 拉代码 → 重新构建 → 起容器）

在本机仓库根执行（会 SSH 到 VPS 跑检查 → 备份 → 拉代码 → 构建）：

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'cd /home/kofwj/sunshine && bash scripts/deploy_vps.sh'
```

前端烘焙进镜像，**改前端必须 build**。部署后等几秒，手机/PWA 会提示刷新。孩子端底栏、家长端顶栏和 `curl https://study.anemy.org/api/health` 都能看到当前版本号。健康检查走内网 `http://192.168.100.5:9000/api/health`（端口绑在这台机器上，不是 127.0.0.1）。

本机首次克隆后执行一次 `bash scripts/install_git_hooks.sh`。之后每次提交会自动把 `VERSION` 最后一位加 1（`0.1.0` → `0.1.1`，`0.1.99` → `0.2.0`）。如果这次已经手动改并暂存了 `VERSION`，就不会再自动加。跳过用 `SKIP_VERSION_BUMP=1 git commit`。

## 四、重置数据（清打卡，回到零起点）

清空所有活动数据（流水/完成/签到/每日记录/兑换/测试/里程碑/宝箱），**保留课程、商店、等级、游标**。

```bash
ssh -o BatchMode=yes root@192.168.100.5 'cd ~/sunshine && ./scripts/reset_data.py'
```

> 必须 root（DB 文件归属 root）。执行前建议先备份（见「二」）。

## 五、健康检查

```bash
# 外网（本地可直接访问）
curl -s https://study.anemy.org/api/health
# VPS 内网（绑的是 192.168.100.5，不是 127.0.0.1）
ssh -o BatchMode=yes root@192.168.100.5 'curl -s http://192.168.100.5:9000/api/health'
```

期望返回 `{"ok":true}`。

## 六、直接查库 / 调试（root）

```bash
ssh root@192.168.100.5 'SUNSHINE_DB=/home/kofwj/sunshine/data/sunshine.db python3 -c "
import sqlite3; c = sqlite3.connect(\"/home/kofwj/sunshine/data/sunshine.db\")
print(c.execute(\"SELECT key,value FROM settings ORDER BY key\").fetchall())
print(c.execute(\"SELECT COALESCE(SUM(delta),0) FROM ledger\").fetchone())
"'
```

常用表：`ledger`(流水) / `completions`(完成) / `checkins`(签到) / `redemptions`(兑换) / `tests`(测试) / `settings`(键值配置，含 PIN、游标、版本号)。

## 七、安卓平板 APK（绕开 Chrome）

壳是 `android/` 里一个 WebView，打开 `https://study.anemy.org/`，不走 Chrome。改前端不用重打 APK。

下载：https://github.com/kofwj/study/releases/latest/download/sunshine.apk

1. 装到平板，允许安装未知应用（或管控白名单加 `org.anemy.sunshine`）
2. 给这个 App 联网权限，**不要开 Chrome**

## 八、本地开发

```bash
# 后端 http://localhost:8000
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000 --reload
# 前端 http://localhost:5173（代理 /api → 8000）
cd frontend && npm install && npm run dev
```

---

**登录**：家长 `parent` / `parent88`（至少 8 位）；孩子 `lele` / `888888`（至少 6 位，不要重复或连续数字）。HttpOnly Cookie：家长 `pid`、娃 `sid`。公网 HTTPS 带 `Secure`；内网 `http://192.168.100.5:9000` 无 `Secure`。改密后旧会话失效。`SECRET_KEY` 写在 VPS `.env`，不进 git。