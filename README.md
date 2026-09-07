# 阳光学习工作台

面向家庭的自主学习打卡与阳光奖励系统：孩子完成任务赚阳光，家长记录薄弱考点并安排复习，阳光可以兑换家庭奖励。

当前主版本：**2026 秋五年级上册，江苏南通**。课程内容由数据驱动，任务 ID 带学期前缀，换教材时不会覆盖历史完成记录。

## 当前状态

- 后端：FastAPI + SQLite，支持 PostgreSQL/RLS 运行路径
- 前端：Vue 3 + Vite，移动优先，支持 PWA
- 平板：Android WebView 壳，可从 [Releases](https://github.com/kofwj/study/releases) 下载 APK
- 部署：Docker Compose + Cloudflare Tunnel
- 多学期种子：12 个学期、350 个单元、1349 张任务卡
- 五上当前可用：35 个单元、149 张单元任务卡、10 个每日任务、125 个可点选考点

## 孩子端

- 每日签到：记录今天来过和连续打卡，不发阳光
- 单元任务：语文、数学、英语、科学、道法按教材单元展示，每张卡都有具体完成标准
- 今日流程：按“先做复习、然后每日打卡、最后本课下一步”安排任务
- 每日任务：阅读、练字、日记、口算、自然拼读、运动、眼保健操、围棋等；支持提示、数字指标和个人纪录
- 复习任务：家长记录薄弱考点后，孩子看到到期复习项和复习轮次
- 阳光规则：完成任务获得阳光，点错可以取消并冲正；测试成绩奖励由家长设置的分数区间计算
- 成长系统：等级、连击、盲盒、成就墙、成长地图、周报
- 趋势记录：跳绳、仰卧起坐、坐位体前屈、口算等数字任务显示趋势；无数字任务显示近 14 天日历
- 进度锁：默认开启，每科只能完成当前单元，家长可以关闭
- 多孩子：每个孩子有独立账号、学期、游标、完成记录和个人纪录

## 家长端

- 任务与考点：教材任务只读，家长自定义任务可以新增、修改和删除
- 薄弱考点：按孩子、科目和单元点亮考点；点亮后进入复习队列
- 今日复习：查看到期考点，判断“会了，晚点再练”“还不熟，明天再练”或“已经掌握”
- 每日任务：家长自定义任务排在系统任务前面；自定义任务可以填写怎么做和指标记录说明
- 已学到：根据当前学期有单元任务的科目动态显示，五上包括语文、数学、英语、科学、道法
- 单元测试：录入任意科目成绩，按家庭设置的分数区间发阳光；历史记录不重算
- 奖励商店：商品增删改、兑换审批、兑现确认
- 等级管理：等级名称和累计阳光阈值可配置
- 周报：查看近 4 周趋势、近 7 天完成量、各科完成情况和孩子对比
- 家庭与账号：家长成员、孩子账号、学期、性别和 PIN 管理

## 五上教材

已按电子课本目录核对以下版本：

| 学科 | 版本 | 入口 |
|---|---|---|
| 语文 | 人教部编版，六三制，`xs5s_2026` | `/books/rjb/yuwen/xs5s_2026/` |
| 数学 | 苏教版，`xs5s_2026` | `/books/sjb/shuxue/xs5s_2026/` |
| 英语 | 译林版，`5a_2026` | `/books/yilin/yingyu/5a_2026/` |
| 科学 | 苏教版，`5s_2026` | `/books/sjb/kexue/5s_2026/` |
| 道德与法治 | 人教部编版，`5s_2026` | `/books/rjb/zhengzhi/5s_2026/` |

五上考点已经覆盖 35 个单元：

- 语文 8 个单元，按阅读策略、习作、口语交际、背诵和说明方法等动作整理
- 数学 8 个单元，覆盖图形运动、统计、多边形面积、小数、可能性、因数倍数、字母式和观察物体
- 英语 8 个 Unit + 2 个 Project，覆盖词汇、拼读、跟读、语法和主题表达
- 科学 5 个单元，覆盖光、热、力、简单机械和仿生实验
- 道法 4 个单元，覆盖中国革命、新中国建设、改革开放和新时代主题

目录和版本记录见 [data/textbook-index.md](data/textbook-index.md) 和 [CONTENT.md](CONTENT.md)。

## 快速运行

### 本地开发

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000 --reload
```

另开终端：

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>。

### 构建后单进程运行

```bash
cd frontend
npm install
npm run build
cd ../backend
./.venv/bin/uvicorn main:app --port 8000
```

打开 <http://localhost:8000>。

## 教材数据流

```text
data/catalog.json
  -> scripts/gen_seed.py
  -> data/tasks.seed.multi.json
  -> backend/db.py 启动时同步课程

scripts/gen_tasks.py
  -> data/tasks.seed.json
  -> 五上语数英人工任务卡和每日任务

scripts/gen_knowledge_tags.py
  -> data/knowledge_tags.json
  -> 五上语数英科学道法人工考点映射
```

重新抓取教材目录：

```bash
python3 scripts/gen_catalog.py --save
python3 scripts/gen_seed.py
python3 scripts/gen_knowledge_tags.py
```

五上人工任务和考点的真源分别是：

- `scripts/gen_tasks.py`
- `scripts/gen_seed.py` 中对五上科学、道法的覆盖
- `scripts/gen_knowledge_tags.py`

改完课程数据要升级 `curriculum_ver`，已有数据库启动时才会刷新系统课程；自定义任务、完成记录、阳光流水和复习记录会保留。

## 部署

线上目录默认是 `/home/kofwj/sunshine`。更新前先备份，再拉代码、构建镜像和重启：

```bash
ssh -o BatchMode=yes root@192.168.100.5 \
  'su - kofwj -c "cd ~/sunshine && python3 scripts/backup_db.py && git pull --ff-only origin main && docker compose build --no-cache && docker compose up -d"'
```

健康检查：

```bash
curl -s https://study.anemy.org/api/health
```

应返回 `{"ok":true}`。

前端改动必须重新构建镜像。PWA 或 Android WebView 更新后需要重新打开或刷新页面。

## 验证

后端当前使用可直接执行的回归脚本：

```bash
for f in backend/test_auth.py backend/test_family.py backend/test_dialect.py \
  backend/test_insights.py backend/test_kids.py backend/test_weak_points.py; do
  python3 "$f" || exit 1
done

python3 -m py_compile backend/*.py scripts/*.py
git diff --check
```

前端构建：

```bash
npm --prefix frontend run build
```

当前开发环境如果提示 `env: node: No such file or directory`，说明机器没有可用 Node.js，不代表已发现 Vue 源码错误；需要在完整 Node 环境补跑构建和浏览器验证。

## 目录

- `backend/main.py`：API、认证、任务、复习、奖励和周报
- `backend/db.py`：数据库、种子同步和迁移
- `frontend/src/App.vue`：孩子端
- `frontend/src/Admin.vue`：家长端
- `frontend/src/ui.css`：公共界面样式
- `data/tasks.seed.multi.json`：多学期任务种子
- `data/knowledge_tags.json`：考点字典和单元映射
- `data/catalog.json`：电子教材目录缓存
- `scripts/`：教材生成、备份、部署和重置脚本
- `OPS.md`：运维速查
- `CONTENT.md`：教材版本和目录
- `PLAN.md`：当前路线和后续计划
- `CHANGELOG.md`：版本变更记录

## 已知限制

- 音乐、美术没有确认本地实际版本，暂不生成教材单元卡
- 综合实践没有统一教材，继续使用家长自定义任务
- 电子课本网主要提供目录和页面入口，正文级复核仍应以孩子手上的实物教材为准
- 正式 pytest 尚未收集现有 `test_*.py`，当前回归通过直接执行脚本完成
- 浏览器截图、Android WebView 和真实手机布局仍需在有 Node 和设备的环境补做

后续工作按 [PLAN.md](PLAN.md) 执行。
