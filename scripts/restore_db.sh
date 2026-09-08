#!/usr/bin/env bash
# 从 SQLite 备份还原 sunshine.db。默认停容器 → 备份当前库 → 拷回指定备份 → 再启动。
# 用法：
#   bash scripts/restore_db.sh                         # 列出备份
#   bash scripts/restore_db.sh sqlite_20260908_192721.db
#   bash scripts/restore_db.sh /home/kofwj/sunshine/data/backups/sqlite_xxx.db
#   bash scripts/restore_db.sh --latest
#   bash scripts/restore_db.sh --latest --dry-run
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DATA_DIR="${SUNSHINE_DATA:-$ROOT/data}"
DB_PATH="${SUNSHINE_DB:-$DATA_DIR/sunshine.db}"
BACKUP_DIR="$DATA_DIR/backups"
LIVE_NAME="$(basename "$DB_PATH")"

dry_run=0
src=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --latest)
      src="$(python3 - "$BACKUP_DIR" <<'PY'
import sys
from pathlib import Path
d = Path(sys.argv[1])
files = [p for p in list(d.glob("sqlite_*.db")) + list(d.glob("sunshine_*.db")) if p.is_file()]
files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
print(str(files[0]) if files else "")
PY
)"
      ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    -*)
      echo "未知参数: $1" >&2
      exit 1
      ;;
    *)
      src="$1"
      ;;
  esac
  shift
done

list_backups() {
  echo "备份目录: $BACKUP_DIR"
  python3 - "$BACKUP_DIR" <<'PY'
import sqlite3, sys
from pathlib import Path
d = Path(sys.argv[1])
files = sorted(
    [p for p in list(d.glob("sqlite_*.db")) + list(d.glob("sunshine_*.db")) if p.is_file()],
    key=lambda p: p.stat().st_mtime, reverse=True)
if not files:
    print("（还没有备份）")
    raise SystemExit(0)
print(f"{'文件':<36} {'大小':>8} {'流水':>6} {'阳光':>6}")
for p in files[:20]:
    n = bal = "?"
    try:
        c = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
        n = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        bal = c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger").fetchone()[0]
        c.close()
    except Exception:
        pass
    kb = f"{p.stat().st_size/1024:.0f}K"
    print(f"{p.name:<36} {kb:>8} {str(n):>6} {str(bal):>6}")
PY
}

if [ -z "$src" ]; then
  list_backups
  echo ""
  echo "还原：bash scripts/restore_db.sh <备份文件名或 --latest>"
  exit 0
fi

if [ ! -f "$src" ]; then
  if [ -f "$BACKUP_DIR/$src" ]; then
    src="$BACKUP_DIR/$src"
  else
    echo "找不到备份: $src" >&2
    exit 1
  fi
fi

src="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$src")"
db_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$DB_PATH" 2>/dev/null || echo "$DB_PATH")"
if [ "$src" = "$db_real" ]; then
  echo "不能把正在用的库当备份还原: $src" >&2
  exit 1
fi

info_of() {
  python3 - "$1" <<'PY'
import sqlite3, sys
p = sys.argv[1]
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
n = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
bal = c.execute("SELECT COALESCE(SUM(delta),0) FROM ledger").fetchone()[0]
c.close()
print(f"{n} 条流水, {bal} 阳光")
PY
}

echo "当前库: $DB_PATH  ($( [ -f "$DB_PATH" ] && info_of "$DB_PATH" || echo 不存在 ))"
echo "备份:   $src  ($(info_of "$src"))"

if [ "$dry_run" = 1 ]; then
  echo "dry-run：不会改文件、也不会动容器"
  exit 0
fi

have_compose=0
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  have_compose=1
fi

running=0
if [ "$have_compose" = 1 ] && docker compose ps --status running 2>/dev/null | grep -q sunshine; then
  running=1
fi

if [ "$running" = 1 ]; then
  echo "停止容器..."
  docker compose stop sunshine
fi

mkdir -p "$BACKUP_DIR"
if [ -f "$DB_PATH" ]; then
  stamp="$(date +%Y%m%d_%H%M%S)"
  safety="$BACKUP_DIR/pre_restore_${stamp}.db"
  cp "$DB_PATH" "$safety"
  echo "还原前快照: $safety"
fi

cp "$src" "$DB_PATH"
echo "已还原: $DB_PATH  ($(info_of "$DB_PATH"))"

if [ "$running" = 1 ]; then
  echo "启动容器..."
  docker compose start sunshine
fi

echo "完成。用家长端或 curl /api/health 确认。"
