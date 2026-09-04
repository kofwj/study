# 运维速查

> 所有命令按「本机(Mac)」和「VPS」区分。源码在本机 `/Users/jian/Downloads/study`，线上在 VPS `/home/kofwj/sunshine`（以下用 `~` 代指）。

## 一、改教材（下学期 / 补 4 科）

任务卡全由 `scripts/gen_tasks.py` 生成，**只改数据不碰代码**。

### 下学期换教材（如五年级下）

1. 本机编辑 `scripts/gen_tasks.py`：
   - `TERM` 改 `id`（`g5s1`→`g5s2`）、`label`、`term`、`version`
   - 把 `CN` / `MA` / `EN` 三个列表换成新目录（每项 `("动作", "标题")`，如 `("背诵", "《海上日出》")`）
   - `main()` 里 `curriculum_ver` 换一个全新值（如 `2026-g5s2-v1`）——**这个值变了，线上才会刷新任务**
2. 本机重新生成：
   ```bash
   cd /Users/jian/Downloads/study && python3 scripts/gen_tasks.py
   ```
3. 提交推送 + 部署（见「三、日常更新」）

### 补 4 科（科学/道法/音美/综合）

1. 加内容列表（格式同 `CN`）：`SCI = [...]`、`DA = [...]`、`YM = [...]`、`ZH = [...]`
2. `SUBJ_ID` 加对应映射：`"科学": "sci"`、`"道法": "da"`、`"音美": "ym"`、`"综合": "zh"`
3. `build()` 里加循环：
   ```python
   for i, (name, items) in enumerate(SCI, 1):
       u, ts = pack("科学", i, name, items); units.append(u); tasks.extend(ts)
   ```
4. `main()` 里 `curriculum_ver` 升一位（`...-v4` → `...-v5`）
5. 本机 `python3 scripts/gen_tasks.py` → 提交 → 部署

> 换学期后旧完成记录自动隔离（任务 ID 带 `g5s1-`/`g5s2-` 前缀），不会污染等级/流水。妈妈端「已学到」游标也是带前缀的，新学期重新拨。

## 二、备份（只读热备份，留最近 10 份）

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py"'
```

备份落在 `~/sunshine/data/backups/`。

## 三、日常更新（拉代码 → 重新构建 → 起容器）

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py && git pull --ff-only origin main && docker compose build --no-cache && docker compose up -d"'
```

前端烘焙进镜像，**改前端必须 build**。部署后等 3 秒，手机/PWA 会自动检测新版本并提示刷新（不用手动清缓存）。

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

## 七、本地开发

```bash
# 后端 http://localhost:8000
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000 --reload
# 前端 http://localhost:5173（代理 /api → 8000）
cd frontend && npm install && npm run dev
```

---

**家长端 PIN 当前值：0129**（非默认 8888，需改回可 `reset` 或改代码里默认值）。