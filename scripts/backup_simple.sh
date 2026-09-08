#!/bin/bash
# 简化的备份脚本 - 只备份SQLite

set -e

BACKUP_DIR="/home/kofwj/sunshine/data/backups"
SQLITE_PATH="/home/kofwj/sunshine/data/sunshine.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$BACKUP_DIR/backup.log"

# 确保备份目录存在
mkdir -p "$BACKUP_DIR"

# 记录日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 开始备份 ==="

# 1. 检查SQLite文件
if [ ! -f "$SQLITE_PATH" ]; then
    log "❌ SQLite文件不存在: $SQLITE_PATH"
    exit 1
fi

# 2. 备份SQLite
SQLITE_BACKUP="$BACKUP_DIR/sqlite_${TIMESTAMP}.db"
cp "$SQLITE_PATH" "$SQLITE_BACKUP"
SQLITE_SIZE=$(du -h "$SQLITE_BACKUP" | cut -f1)

# 3. 查询记录数（使用Python，VPS可能没有sqlite3命令）
SQLITE_INFO=$(python3 << EOF
import sqlite3
try:
    conn = sqlite3.connect("$SQLITE_BACKUP")
    count = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    balance = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger").fetchone()[0]
    conn.close()
    print(f"{count},{balance}")
except Exception as e:
    print("0,0")
EOF
)

SQLITE_COUNT=$(echo $SQLITE_INFO | cut -d',' -f1)
SQLITE_BALANCE=$(echo $SQLITE_INFO | cut -d',' -f2)

log "✅ SQLite 备份: $SQLITE_BACKUP ($SQLITE_SIZE, $SQLITE_COUNT 条记录, $SQLITE_BALANCE 阳光)"

# 4. 清理旧备份（保留最近20个）
log "清理旧备份..."
cd "$BACKUP_DIR"
ls -t sqlite_*.db 2>/dev/null | tail -n +21 | xargs rm -f 2>/dev/null || true
REMAINING=$(ls sqlite_*.db 2>/dev/null | wc -l)
log "✅ 保留最近 $REMAINING 个备份"

log "=== 备份完成 ==="
