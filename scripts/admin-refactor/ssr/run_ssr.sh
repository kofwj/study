#!/usr/bin/env bash
# 家长工作台的 SSR 渲染体检：把壳 / 子组件用桩数据挂载一次，抓 Vue 警告、抛错和关键文案。
#
# 能抓到什么：模板引用了不存在的名字（少传 prop、少导入组件）、computed 炸掉、关键文案丢了。
# 抓不到什么：只在事件回调里才求值的错（例如 isDirty 那条 shopRef 漏声明）——那类靠
# ../check_undeclared.mjs。两套是互补的。
#
# 用法（仓库根目录或任意位置）：
#     bash scripts/admin-refactor/ssr/run_ssr.sh
#
# 反向对照（确认体检有牙）：把 fixtures 里某个名字故意改回壳专属写法（例如把 kidName 改成
# currentKidName、把 meAccount 改成 me.account），重跑应当看到「警告 N 条」和缺失项。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
export PATH="${HOME}/.hermes/node/bin:${PATH}"

command -v node >/dev/null 2>&1 || { echo "没有 node。装 Node 20，或确认 ~/.hermes/node/bin/node 存在。"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "先装前端依赖：cd frontend && npm install"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/frontend"
for p in src index.html vite.config.js package.json; do
  [ -e "$ROOT/frontend/$p" ] && cp -R "$ROOT/frontend/$p" "$TMP/frontend/"
done
ln -s "$ROOT/frontend/node_modules" "$TMP/frontend/node_modules"

fail=0
for f in "$HERE"/fixtures/*.mjs; do
  name="$(basename "$f" .mjs)"
  cp "$f" "$TMP/frontend/$name.mjs"
  if ! ( cd "$TMP/frontend" && npx vite build --ssr "$name.mjs" --outDir "out-$name" --logLevel error >/dev/null ); then
    echo "✗ $name 构建失败"; fail=1; continue
  fi
  echo "--- $name"
  out="$(node "$TMP/frontend/out-$name/$name.js")" || { echo "✗ $name 运行抛错"; fail=1; continue; }
  echo "$out"
  if echo "$out" | grep -qE "警告 [1-9][0-9]* 条|问题 [1-9][0-9]* 条|THROW|缺失"; then
    echo "✗ $name 有问题"; fail=1
  fi
done

if [ "$fail" -eq 0 ]; then echo "SSR 渲染体检：全部通过"; else echo "SSR 渲染体检：有失败项"; fi
exit "$fail"
