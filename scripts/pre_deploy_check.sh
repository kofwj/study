#!/bin/bash
# 部署前检查脚本 - 防止数据丢失

set -e

echo "=== 部署前检查 ==="
echo ""

# 1. 检查当前数据库配置
echo "1. 检查数据库配置..."
if [ -f .env ]; then
    if grep -q "DATABASE_URL=" .env && grep -q "^[^#]*DATABASE_URL=" .env; then
        echo "   ⚠️  检测到 .env 配置了 PostgreSQL"
        WILL_USE_PG=true
    else
        echo "   ✅ .env 配置使用 SQLite"
        WILL_USE_PG=false
    fi
else
    echo "   ⚠️  .env 文件不存在"
    WILL_USE_PG=false
fi

# 2. 检查当前运行的数据库
echo ""
echo "2. 检查当前运行的数据库..."
if docker compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo "   ⚠️  PostgreSQL 容器正在运行"
    CURRENT_PG_RUNNING=true
else
    echo "   ✅ PostgreSQL 容器未运行"
    CURRENT_PG_RUNNING=false
fi

# 3. 比较数据记录数
echo ""
echo "3. 检查数据一致性..."
SQLITE_PATH="data/sunshine.db"
if [ -f "$SQLITE_PATH" ]; then
    SQLITE_COUNT=$(sqlite3 "$SQLITE_PATH" "SELECT COUNT(*) FROM ledger" 2>/dev/null || echo "0")
    SQLITE_BALANCE=$(sqlite3 "$SQLITE_PATH" "SELECT COALESCE(SUM(delta), 0) FROM ledger" 2>/dev/null || echo "0")
    echo "   SQLite: $SQLITE_COUNT 条记录, $SQLITE_BALANCE 阳光"
else
    SQLITE_COUNT=0
    SQLITE_BALANCE=0
    echo "   ⚠️  SQLite 文件不存在"
fi

if [ "$CURRENT_PG_RUNNING" = true ]; then
    PG_COUNT=$(docker compose exec -T postgres psql -U sunshine -d sunshine -t -c "SELECT COUNT(*) FROM ledger" 2>/dev/null | tr -d ' ' || echo "0")
    PG_BALANCE=$(docker compose exec -T postgres psql -U sunshine -d sunshine -t -c "SELECT COALESCE(SUM(delta), 0) FROM ledger" 2>/dev/null | tr -d ' ' || echo "0")
    echo "   PostgreSQL: $PG_COUNT 条记录, $PG_BALANCE 阳光"
else
    PG_COUNT=0
    PG_BALANCE=0
fi

# 4. 检测问题
echo ""
echo "4. 问题检测..."
HAS_ISSUE=false

# 问题1: 数据库切换会导致数据丢失
if [ "$CURRENT_PG_RUNNING" = true ] && [ "$WILL_USE_PG" = false ]; then
    echo "   ❌ 警告: 当前使用 PostgreSQL，部署后将切换到 SQLite"
    echo "      PostgreSQL 有 $PG_COUNT 条记录 ($PG_BALANCE 阳光)"
    echo "      SQLite 只有 $SQLITE_COUNT 条记录 ($SQLITE_BALANCE 阳光)"
    if [ "$PG_COUNT" -gt "$SQLITE_COUNT" ]; then
        echo "      ⚠️  这会导致 $((PG_COUNT - SQLITE_COUNT)) 条记录丢失！"
        HAS_ISSUE=true
    fi
fi

# 问题2: 反向切换
if [ "$CURRENT_PG_RUNNING" = false ] && [ "$WILL_USE_PG" = true ]; then
    echo "   ⚠️  警告: 当前使用 SQLite，部署后将切换到 PostgreSQL"
    echo "      SQLite 有 $SQLITE_COUNT 条记录 ($SQLITE_BALANCE 阳光)"
    if [ "$PG_COUNT" -gt 0 ]; then
        echo "      PostgreSQL 有旧数据: $PG_COUNT 条记录 ($PG_BALANCE 阳光)"
        if [ "$SQLITE_COUNT" -ne "$PG_COUNT" ]; then
            echo "      ⚠️  数据不一致，请先手动同步！"
            HAS_ISSUE=true
        fi
    fi
fi

# 问题3: 数据不一致但都在运行
if [ "$CURRENT_PG_RUNNING" = true ] && [ "$WILL_USE_PG" = true ]; then
    if [ "$SQLITE_COUNT" -ne "$PG_COUNT" ]; then
        echo "   ⚠️  警告: SQLite 和 PostgreSQL 数据不一致"
        echo "      这可能表示之前发生过数据库切换"
        HAS_ISSUE=true
    else
        echo "   ✅ 数据一致"
    fi
fi

# 5. 建议
echo ""
if [ "$HAS_ISSUE" = true ]; then
    echo "❌ 发现问题！建议操作："
    echo "   1. 先运行备份: bash scripts/enhanced_backup.sh"
    echo "   2. 确认要使用的数据库类型"
    echo "   3. 如需迁移数据，联系管理员"
    echo ""
    echo "是否继续部署？(yes/no)"
    read -r CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "❌ 部署已取消"
        exit 1
    fi
else
    echo "✅ 检查通过，可以安全部署"
fi

echo ""
echo "=== 检查完成 ==="
