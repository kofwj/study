# 阳光学习工作台

娃的自主打卡 + 阳光奖励系统。P0 已跑通核心闭环：**签到领阳光 → 完成任务 +5/点错 -5 → 商店兑换 → 等级成长**。

## 技术栈

- 后端：FastAPI + SQLite（流水账是唯一真相源，余额/累计/等级/连击全由流水推导）
- 前端：Vue3 + Vite（单页，移动优先）
- 当前科目内容：语文 / 数学 / 英语（单元卡）+ 体育跳绳（每日卡，带破纪录叠加）

## 运行

### 本地开发

```bash
# 后端（端口 8000）
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000 --reload

# 前端（端口 5173，自动代理 /api 到 8000）
cd frontend
npm install
npm run dev
```

浏览器开 http://localhost:5173

### 单进程（构建后由后端直接托管）

```bash
cd frontend && npm install && npm run build
cd ../backend && ./.venv/bin/uvicorn main:app --port 8000
# 访问 http://localhost:8000
```

## 部署到 VPS（Docker + Cloudflare Tunnel）

### 首次部署

```bash
# 用有 GitHub SSH 访问的普通用户（如 kofwj），别用 root（root 无 GitHub 密钥）
ssh -T git@github.com                 # 先验证：应回 Hi kofwj!
cd ~ && git clone git@github.com:kofwj/study.git sunshine
cd sunshine
sudo usermod -aG docker kofwj && exit   # 加入 docker 组（重登生效），之后无需 sudo
docker compose up -d --build
curl -s http://127.0.0.1:9000/api/health   # 应回 {"ok":true}
```

> 端口绑 `0.0.0.0:9000`（仅内网可达，App 无公网暴露；管理端有 PIN 保护）。

### Cloudflare Tunnel（零信任面板）

1. Cloudflare Zero Trust → Networks → Tunnels → 选你已有的隧道
2. Public Hostnames → Add a public hostname
3. Hostname 填 `study.anemy.org` → Service 填 `http://192.168.100.5:9000`（cloudflared 与 App 不同机时，填 App 的内网 IP）
4. 保存，浏览器开 `https://study.anemy.org` 即可

### 日常更新（拉代码后重新构建，前端烘焙进镜像必须 build）

```bash
cd /opt/sunshine
python3 scripts/backup_db.py
./scripts/deploy_vps.sh
```

> 若 UI 没变：`docker compose build --no-cache && docker compose up -d`，用户侧强刷新（Ctrl/Cmd+Shift+R）。

### 数据与备份

- SQLite 挂在 `./data/sunshine.db`（宿主 repo 的 data/ 目录）
- 备份：宿主机 `python3 scripts/backup_db.py`（只读热备份，落在 `data/backups/`，只留最近 10 份）

## 目录

- `PLAN.md` —— 设计思路与数据模型
- `CONTENT.md` —— 教材版本 + 目录
- `data/` —— 任务卡草稿（`tasks_review.md` 给人看，`tasks.seed.json` 给机器）
- `scripts/gen_tasks.py` —— 任务卡生成器。下学期改其中 UNITS 后重跑即可再生
- `backend/` —— FastAPI 后端（`db.py` 存储与种子，`main.py` 接口）
- `frontend/` —— Vue3 单页

## 家长管理端

孩子端右下角「👤 家长」→ 输密码进入。默认密码 **8888**（进入后可改）。可增删改：商店奖励、等级阈值、单元任务、每日任务（含记录维度）。

## 关键规则（已在代码中落定）

- 等级看「累计获得」= 流水之和但排除兑换消费 → **消费不掉级**
- 取消 = 一条负流水，逻辑上正负抵消 → **点错扣回、且刷不出等级**
- 跳绳「进步」= 破个人纪录（非比昨天）→ 防囤分
- 连续打卡天数由日期推导

## 重置数据

删除 `backend/sunshine.db`，下次启动会自动重新导入种子。

## 待办（P1+）

- PWA 安装 + 桌面优化
- 其余 4 科（科学/道法/音美/综合）目录录入