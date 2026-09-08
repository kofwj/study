#!/usr/bin/env bash
# 一键部署/更新：检查 → 备份 → 拉代码 → 重新构建 → 起容器 → 健康检查
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
[ -f .env ] && . ./.env
set +a

echo "=== 阳光学习工作台部署 ==="
echo ""

# 1. 部署前检查
echo "步骤1: 部署前检查..."
if [ -f scripts/pre_deploy_check.sh ]; then
    bash scripts/pre_deploy_check.sh || {
        echo "❌ 检查失败，部署已取消"
        exit 1
    }
else
    echo "⚠️  跳过部署前检查（pre_deploy_check.sh不存在）"
fi
echo ""

# 2. 增强备份
echo "步骤2: 备份数据库..."
if [ -f scripts/enhanced_backup.sh ]; then
    bash scripts/enhanced_backup.sh
else
    python3 scripts/backup_db.py
fi
echo ""

# 3. 拉取代码
echo "步骤3: 拉取最新代码..."
git pull --ff-only

# 4. 构建镜像
echo ""
echo "步骤4: 构建镜像..."
export APP_REVISION="$(git rev-parse --short=7 HEAD)"
docker compose build --build-arg APP_REVISION="$APP_REVISION"
docker compose up -d

# 5. 健康检查
echo ""
echo "步骤5: 健康检查..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9000/api/health >/dev/null 2>&1; then
    echo "✅ 已启动并健康: $(git log -1 --oneline)"
    docker compose ps
    echo ""
    echo "=== 部署完成 ==="
    exit 0
  fi
  sleep 1
done

echo "❌ 健康检查未通过，最近日志："
docker compose logs --tail 50
exit 1