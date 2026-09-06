#!/usr/bin/env bash
# 部署前检查：后端测试 + 前端 build/冒烟全绿才允许上线。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
for t in test_dialect test_auth test_kids test_family test_insights; do
  echo "== $t =="
  python3 "$t.py"
done
echo "== frontend =="
bash "$ROOT/scripts/smoke_frontend.sh"
echo "✅ 后端测试 + 前端冒烟全绿，可以部署"