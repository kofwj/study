#!/usr/bin/env bash
# 一键部署/更新：拉代码 → 重新构建（前端烘焙进镜像 → 必须 build）→ 起容器 → 健康检查
set -euo pipefail
cd "$(dirname "$0")/.."

git pull --ff-only

docker compose build
docker compose up -d

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9000/api/health >/dev/null 2>&1; then
    echo "✅ 已启动并健康: $(git log -1 --oneline)"
    docker compose ps
    exit 0
  fi
  sleep 1
done

echo "❌ 健康检查未通过，最近日志："
docker compose logs --tail 50
exit 1