#!/usr/bin/env bash
# 给 sunshine 装定时备份：每天 02:15、18:15 各一次。
# 在 VPS 仓库根执行：bash scripts/install_backup_cron.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP="$ROOT/scripts/enhanced_backup.sh"
LOG="${SUNSHINE_BACKUP_LOG:-/var/log/sunshine-backup.log}"

if [ ! -x "$BACKUP" ] && [ -f "$BACKUP" ]; then
  chmod +x "$BACKUP"
fi
if [ ! -f "$BACKUP" ]; then
  echo "找不到 $BACKUP" >&2
  exit 1
fi

touch "$LOG" 2>/dev/null || LOG="/tmp/sunshine-backup.log"
touch "$LOG"

marker="# sunshine-sqlite-backup"
line1="15 2,18 * * * cd $ROOT && bash scripts/enhanced_backup.sh >> $LOG 2>&1 $marker"

tmp="$(mktemp)"
crontab -l 2>/dev/null | grep -v "$marker" > "$tmp" || true
printf '%s\n' "$line1" >> "$tmp"
crontab "$tmp"
rm -f "$tmp"

echo "已写入 crontab："
crontab -l | grep "$marker"
echo "日志: $LOG"
echo "手动跑一次: bash $BACKUP"
