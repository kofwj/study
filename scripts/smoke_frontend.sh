#!/usr/bin/env bash
# 本地前端：build + 冒烟。本机 PATH 经常没有 node，优先用 Hermes 自带的。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.hermes/node/bin:${PATH}"

if ! command -v node >/dev/null 2>&1; then
  echo "没有 node。装 Node 20，或确认 ~/.hermes/node/bin/node 存在。"
  exit 1
fi
echo "node $(node -v)"

cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund
fi
npm run build
python3 "$ROOT/scripts/smoke_frontend.py"
