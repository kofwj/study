#!/bin/bash
# 增强的备份脚本 - 检测数据库类型并备份

set -e

BACKUP_DIR="/home/kofwj/sunshine/data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$BACKUP_DIR/backup.log"

# 确保备份目录存在
mkdir -p "$BACKUP_DIR"

# 记录日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 开始备份 ==="

# 1. 检测当前使用的数据库类型
if [ -n "$DATABASE_URL" ]; then
    DB_TYPE="PostgreSQL"
    log "检测到使用 PostgreSQL"
else
    DB_TYPE="SQLite"
    log "检测到使用 SQLite"
fi

# 2. 备份SQLite（始终备份）
SQLITE_PATH="/home/kofwj/sunshine/data/sunshine.db"
if [ -f "$SQLITE_PATH" ]; then
    SQLITE_BACKUP="$BACKUP_DIR/sqlite_${TIMESTAMP}.db"
    cp "$SQLITE_PATH" "$SQLITE_BACKUP"
    SQLITE_SIZE=$(du -h "$SQLITE_BACKUP" | cut -f1)
    # 使用Python查询（VPS可能没有sqlite3命令）
    SQLITE_RECORDS=$(python3 << EOF
import sqlite3
try:
    conn = sqlite3.connect("$SQLITE_BACKUP")
    count = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    conn.close()
    print(count)
except:
    print("N/A")
EOF
)
    log "✅ SQLite 备份: $SQLITE_BACKUP ($SQLITE_SIZE, $SQLITE_RECORDS 条记录)"
else
    log "⚠️  SQLite 文件不存在: $SQLITE_PATH"
fi

# 3. 备份PostgreSQL（如果正在使用）
if [ "$DB_TYPE" = "PostgreSQL" ]; then
    PG_BACKUP="$BACKUP_DIR/postgres_${TIMESTAMP}.sql"
    docker compose exec -T postgres pg_dump -U sunshine -d sunshine > "$PG_BACKUP" 2>/dev/null || {
        log "⚠️  PostgreSQL 备份失败"
    }
    if [ -f "$PG_BACKUP" ]; then
        PG_SIZE=$(du -h "$PG_BACKUP" | cut -f1)
        log "✅ PostgreSQL 备份: $PG_BACKUP ($PG_SIZE)"
    fi
fi

# 4. 数据一致性检查
if [ "$DB_TYPE" = "PostgreSQL" ] && [ -f "$SQLITE_PATH" ]; then
    SQLITE_COUNT=$(python3 << EOF
import sqlite3
try:
    conn = sqlite3.connect("$SQLITE_PATH")
    count = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    conn.close()
    print(count)
except:
    print("0")
EOF
)
    PG_COUNT=$(docker compose exec -T postgres psql -U sunshine -d sunshine -t -c "SELECT COUNT(*) FROM ledger" 2>/dev/null | tr -d ' ' || echo "0")
    
    if [ "$SQLITE_COUNT" != "$PG_COUNT" ]; then
        log "❌ 警告: 数据不一致！SQLite: $SQLITE_COUNT 条, PostgreSQL: $PG_COUNT 条"
        log "❌ 可能存在数据库切换问题，请检查！"
        # 发送告警（可选）
        # curl -X POST https://your-webhook-url -d "数据库不一致告警"
    else
        log "✅ 数据一致性检查通过"
    fi
fi

# 5. 清理旧备份（保留最近20个）
log "清理旧备份..."
cd "$BACKUP_DIR"
ls -t sqlite_*.db 2>/dev/null | tail -n +21 | xargs rm -f 2>/dev/null || true
ls -t postgres_*.sql 2>/dev/null | tail -n +21 | xargs rm -f 2>/dev/null || true
log "✅ 旧备份已清理"

# 6. 记录当前数据库配置
log "当前配置: 数据库类型=$DB_TYPE, DATABASE_URL=${DATABASE_URL:-未设置}"

log "=== 备份完成 ==="
