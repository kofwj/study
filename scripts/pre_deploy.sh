#!/usr/bin/env bash
# 部署前检查：后端 pytest + 前端 build/冒烟全绿才允许上线。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
echo "== pytest =="
python3 -m pytest -q
echo "== frontend =="
bash "$ROOT/scripts/smoke_frontend.sh"
echo "✅ 后端测试 + 前端冒烟全绿，可以部署"
