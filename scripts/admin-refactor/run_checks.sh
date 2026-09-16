#!/usr/bin/env bash
# 家长工作台重构的静态体检（不依赖后端、不写仓库）：
#   1) 壳的 <script setup> 里有没有「用了没声明」的标识符（v0.3.40 的 shopRef 白屏就是这类）
#   2) 子组件模板用到的 class 是否都在全局样式表里（v0.3.36 的 .a-item、v0.3.41 的 .kid-card 是这类）
#
# 用法：
#     bash scripts/admin-refactor/run_checks.sh              # 只跑静态体检
#     bash scripts/admin-refactor/run_checks.sh --with-ssr   # 再跑一遍 SSR 渲染体检（慢一些）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="${HOME}/.hermes/node/bin:${PATH}"
fail=0

echo "== 1/2 壳里「用了没声明」的标识符 =="
if command -v node >/dev/null 2>&1; then
  node "$HERE/check_undeclared.mjs" || fail=1
  echo "（正常噪音只有 NaN / setup / __props / __expose / __emit；出现别的名字就是漏声明）"
else
  echo "跳过：没有 node"
fi

echo
echo "== 2/2 子组件样式有没有拿不到的 =="
python3 "$HERE/check_child_styles.py" || fail=1

if [ "${1:-}" = "--with-ssr" ]; then
  echo
  echo "== 附加：SSR 渲染体检 =="
  bash "$HERE/ssr/run_ssr.sh" || fail=1
fi

echo
if [ "$fail" -eq 0 ]; then echo "静态体检：通过"; else echo "静态体检：有失败项"; fi
exit "$fail"
