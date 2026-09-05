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
2. 重新生成多学期 seed（五上语数英会自动用手工核实版覆盖）：
   ```bash
   python3 scripts/gen_seed.py
   ```
3. 改 `gen_seed.py` 顶部 `curriculum_ver`（或每次重跑自然变，因为内容变了）——**这个值变了，线上才会刷新任务**。
4. 提交推送 + 部署（见「三、日常更新」）。

### 补 4 科 / 加新学科

- 目录来源见 `data/textbook-index.md`（版本 × 年级 × 站点路径 + 版次推进）。
- 在 `scripts/gen_seed.py` 的 `SUBJECTS`/`SPLIT`/`ACTION` 里加对应的切分与动作规则。
- 主课（语数英科道法）已配好；音美/综合因无稳定电子课本，当前不做。

> 换学期后旧完成记录自动隔离（任务 ID 带 `g5s1-`/`g5x2-` 等学期前缀），不污染等级/流水。家长端「已学到」游标也带前缀，新学期重新拨。

## 二、备份（只读热备份，留最近 10 份）

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py"'
```

备份落在 `~/sunshine/data/backups/`。设了 `DATABASE_URL` 时改走 `pg_dump -Fc`（需本机 `pg_dump` 或 `docker exec sunshine-postgres pg_dump ...`）。

SQLite → Postgres（**只在切流前跑一次**；会清空 PG 重灌，切流后勿重跑）。

前置：postgres 已起且 healthy；`.env` 已写好 `DATABASE_URL`/`DATABASE_APP_URL`（两者都必须是 `@postgres:5432`，容器网络名）。

宿主机没装 psycopg、postgres 也没开 host 端口，所以在 **app 镜像里借 psycopg、走 docker 网络**跑。在 VPS 上（kofwj）执行：

```bash
cd ~/sunshine
set -a; . ./.env; set +a
docker run --rm --network sunshine_default \
  -v /home/kofwj/sunshine:/app -w /app \
  -e DATABASE_URL -e DATABASE_APP_URL \
  sunshine-sunshine python3 scripts/migrate_to_pg.py
```

通过后 `docker compose up -d`（`.env` 的 `COMPOSE_PROFILES=postgres` 会让 postgres 一起起并切流量）。请求必须走 `sunshine_app`，`sunshine` 是 superuser 会绕过 RLS。

## 三、日常更新（备份 → 拉代码 → 重新构建 → 起容器）

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py && git pull --ff-only origin main && docker compose build --no-cache && docker compose up -d"'
```

或直接跑本地脚本 `scripts/deploy_vps.sh`（同样先备份再构建）。前端烘焙进镜像，**改前端必须 build**。部署后等 3 秒，手机/PWA 会自动检测新版本并提示刷新（不用手动清缓存）。

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
# VPS 内网
ssh -o BatchMode=yes root@192.168.100.5 'curl -s http://127.0.0.1:9000/api/health'
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

**家长端 PIN 当前值：0129**（非默认 8888，需改回可 `reset` 或改代码里默认值）。