#!/usr/bin/env bash
# 部署前检查：后端测试全绿才允许上线。今后改动先跑这个，再 push。
set -euo pipefail
cd "$(dirname "$0")/../backend"
for t in test_dialect test_auth test_kids test_family; do
  echo "== $t =="
  python3 "$t.py"
done
echo "✅ 后端测试全绿，可以部署"