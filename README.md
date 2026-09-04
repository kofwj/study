# 阳光学习工作台

娃的自主学习打卡 + 阳光奖励系统。核心闭环：**完成任务赚阳光 → 攒阳光兑奖励 → 等级成长**。签到只记录「今天来过」和连击，不发阳光（无门槛白拿会通胀）。

> 五年级上 · 江苏南通 · 2026 秋季教材。内容全部是数据，下学期换目录只改数据、不动代码。

## 技术栈

- 后端：FastAPI + SQLite（流水账 ledger 是唯一真相源，余额/累计/等级/连击全由流水推导）
- 前端：Vue3 + Vite（单页 SPA，移动优先，PWA 可装桌面）
- 部署：Docker Compose + Cloudflare Tunnel

## 现在能做什么

**孩子端（打开即用，无需登录）**
- 📅 每日签到：记录「今天来过」+ 连击兜底，**不发阳光**
- 📚 114 张单元卡（语 43 / 数 29 / 英 42），每张带「怎么做」提示，完成 +5、点错取消 -5
- 🏃 6 个每日循环任务：跳绳、仰卧起坐、坐位体前屈、眼保健操、课外阅读、练字；前三个「破个人纪录」每维度 +3
- ⭐ 今日推荐：自动挑今天该做的（未做每日任务 + 语数英「当前单元」各 2 张）
- 🛒 商店兑换（明码标价，大额走家长审批）
- 🌱→👑 10 档等级（满级 5000，消费不掉级）
- 📈 成长趋势：有数值看折线+个人纪录，无数值（阅读/练字/眼保健操）看 14 天打卡日历
- 🎁 连击盲盒：连续打卡每 3 天开一个盲盒，随机 +3~+10 阳光
- 🗺️ 成长地图：点顶栏等级看「登山路径」，10 站走到哪一目了然
- 🎖️ 成就墙：10 枚徽章（初来乍到/十卡/运动/坚持/阳光）带进度
- 🔥 连击里程碑：连续 7/14/30 天各奖励 +20/+50/+100（一次性）
- 📱 PWA 装桌面 + 手机/桌面双布局，空学科（科学/道法/音美/综合）自动隐藏

**家长端（右下角「👤 家长」，PIN 默认 **8888**，可改）**
- 商店奖励增删改、兑换**审批 + 兑现**（同意扣阳光 → 标记已兑现）
- 等级阈值增删改、单元任务/每日任务增删改
- 「已学到」进度游标（游标之前的课标灰「已学过」，不再计分）
- 📝 单元测试成绩奖励：录分数按档自动发阳光（通用任意科目）
- 📊 每周周报（近 4 周趋势 + 7 天柱状 + 各科完成排行）+ 跳绳趋势图

## 等级（10 档，满级 5000 ≈ 一学期坚持）

| 🌱 | 🌿 | 🌼 | ⭐ | 🔥 | 🏆 | 🥇 | 💎 | 🚀 | 👑 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 50 | 150 | 350 | 700 | 1200 | 2000 | 3000 | 4000 | 5000 |

前期密集（几天一升给反馈），后期递增（每级约半个月）。

## 运行

### 本地开发

```bash
# 后端（端口 8000）
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000 --reload

# 前端（端口 5173，自动代理 /api → 8000）
cd frontend && npm install && npm run dev
```

浏览器开 http://localhost:5173

### 单进程（构建后由后端直接托管）

```bash
cd frontend && npm install && npm run build
cd ../backend && ./.venv/bin/uvicorn main:app --port 8000
# 访问 http://localhost:8000
```

## 部署到 VPS（Docker + Cloudflare Tunnel）

```bash
# 用有 GitHub 访问的普通用户（kofwj），别用 root
ssh -T git@github.com                    # 验证 → Hi kofwj!
cd ~ && git clone git@github.com:kofwj/study.git sunshine
cd sunshine && docker compose up -d --build
curl -s http://127.0.0.1:9000/api/health   # {"ok":true}
```

Cloudflare Zero Trust → Tunnels → Public Hostnames：`study.anemy.org` → Service `http://192.168.100.5:9000`（App 内网 IP，端口绑 `0.0.0.0:9000`）。

### 日常更新

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py && git pull --ff-only origin main && docker compose build --no-cache && docker compose up -d"'
```

前端烘焙进镜像，改前端**必须 build**；改完后手机强刷新（或 PWA 重开）。

## 数据与脚本

- SQLite：`./data/sunshine.db`（Docker 卷挂载到宿主 `data/`）
- 备份：`python3 scripts/backup_db.py`（只读热备份 → `data/backups/`，留最近 10 份）
- 清数据：`python3 scripts/reset_data.py`（清活动数据，保留课程/商店/等级/游标；DB 归属 root，需 root 跑）
  ```bash
  ssh root@192.168.100.5 'cd ~/sunshine && ./scripts/reset_data.py'
  ```

## 目录结构

- `OPS.md` —— 运维速查（改教材/部署/备份/重置/查库命令一页）
- `PLAN.md` —— 设计思路与数据模型
- `CONTENT.md` —— 教材版本 + 目录
- `data/tasks.seed.json` —— 任务卡种子（机器读）；`data/tasks_review.md`（人读）
- `scripts/gen_tasks.py` —— 任务卡生成器。下学期改 UNITS 重跑即可
- `backend/`（`db.py` 存储+种子，`main.py` 接口）、`frontend/`（Vue3 单页）

## 关键规则（已在代码落定）

- 等级看「累计获得」= 流水和排除兑换消费 → **消费不掉级**
- 点错取消 = 一条负流水，正负抵消 → 扣回且刷不出等级
- 跳绳「进步」= 破个人纪录（非比昨天）→ 防囤分
- 连击天数由日期推导，不硬存
- 任务 ID 带学期前缀 `g5s1-`，下学期换目录不污染历史记录
- 阳光来源全部限了额度（里程碑/盲盒一次性、测试按 5 档、破纪录按维度），防通胀
- 测试成绩只能家长录，孩子端无入口（防虚报）

## 待办

- 科学 / 道法 / 音美 / 综合 4 科目录录入（需真实教材目录，录完自动出现在侧栏）