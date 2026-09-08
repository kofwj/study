#!/bin/bash
# 部署前检查脚本 - 简化版（只检查SQLite配置）

set -e

echo "=== 部署前检查 ==="
echo ""

# 1. 检查 .env 配置
echo "1. 检查数据库配置..."
if [ -f .env ]; then
    if grep -q "^[^#]*DATABASE_URL=" .env 2>/dev/null; then
        echo "   ❌ .env 配置了 PostgreSQL（不应该！）"
        echo "   → 请注释掉或删除 DATABASE_URL 行"
        echo ""
        echo "修复建议:"
        echo "   sed -i 's/^DATABASE_URL=/#DATABASE_URL=/' .env"
        exit 1
    else
        echo "   ✅ .env 配置使用 SQLite"
    fi
else
    echo "   ⚠️  .env 文件不存在（将使用默认SQLite）"
fi

# 2. 检查PostgreSQL容器状态
echo ""
echo "2. 检查PostgreSQL容器..."
if docker compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo "   ❌ PostgreSQL 容器正在运行（不应该！）"
    echo "   → 请停止: docker compose stop postgres"
    echo ""
    exit 1
else
    echo "   ✅ PostgreSQL 容器未运行"
fi

# 3. 验证SQLite数据
echo ""
echo "3. 验证SQLite数据..."
SQLITE_PATH="data/sunshine.db"
if [ -f "$SQLITE_PATH" ]; then
    # 使用Python查询（VPS可能没有sqlite3命令）
    SQLITE_INFO=$(python3 << 'EOF'
import sqlite3
import sys
try:
    conn = sqlite3.connect("data/sunshine.db")
    count = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    balance = conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger").fetchone()[0]
    conn.close()
    print(f"{count},{balance}")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    print("0,0")
EOF
)
    if [ $? -eq 0 ]; then
        SQLITE_COUNT=$(echo $SQLITE_INFO | cut -d',' -f1)
        SQLITE_BALANCE=$(echo $SQLITE_INFO | cut -d',' -f2)
        echo "   ✅ SQLite 数据正常: $SQLITE_COUNT 条记录, $SQLITE_BALANCE 阳光"
    else
        echo "   ⚠️  无法读取SQLite数据"
    fi
else
    echo "   ⚠️  SQLite 文件不存在: $SQLITE_PATH"
fi

echo ""
echo "✅ 检查通过，可以安全部署"
echo ""
echo "=== 检查完成 ==="
