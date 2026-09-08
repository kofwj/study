#!/usr/bin/env python3
"""
PostgreSQL → SQLite 数据迁移脚本（修复版）
增加了 kid_settings 表的迁移
"""
import sys
import sqlite3
import psycopg

print("=== 开始数据迁移（完整版）===\n")

# 连接数据库
print("1. 连接数据库...")
sqlite_conn = sqlite3.connect("/data/sunshine.db")
pg_conn = psycopg.connect("host=postgres dbname=sunshine user=sunshine password=sunshine")
print("   ✅ 完成\n")

# 要迁移的表
TABLES_TO_MIGRATE = ["ledger", "completions", "checkins", "weak_points", "kid_settings"]

# 清空SQLite
print("2. 清空SQLite表...")
for table in TABLES_TO_MIGRATE:
    try:
        sqlite_conn.execute(f"DELETE FROM {table}")
        print(f"   清空 {table}")
    except Exception as e:
        print(f"   ⚠️  清空 {table} 失败: {e}")
sqlite_conn.commit()
print("   ✅ 完成\n")

# 迁移数据
print("3. 迁移数据...")

total_records = 0

for table in TABLES_TO_MIGRATE:
    try:
        # 从PostgreSQL读取
        pg_cursor = pg_conn.cursor()
        pg_cursor.execute(f"SELECT * FROM {table}")
        rows = pg_cursor.fetchall()
        
        if not rows:
            print(f"   {table}: 0 条")
            continue
        
        # 获取列名
        columns = [desc[0] for desc in pg_cursor.description]
        placeholders = ','.join(['?' for _ in columns])
        cols_str = ','.join(columns)
        
        # 插入到SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.executemany(
            f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})",
            rows
        )
        sqlite_conn.commit()
        
        count = len(rows)
        total_records += count
        print(f"   {table}: {count} 条 ✅")
        
    except Exception as e:
        print(f"   {table}: 迁移失败 - {e}")
        import traceback
        traceback.print_exc()

print(f"\n   总计迁移: {total_records} 条记录")
print("   ✅ 完成\n")

# 验证
print("4. 验证迁移结果...")
try:
    # 验证ledger
    ledger_count = sqlite_conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    balance = sqlite_conn.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger").fetchone()[0]
    print(f"   ledger: {ledger_count} 条, 余额 {balance} 阳光")
    
    # 验证completions
    comp_count = sqlite_conn.execute("SELECT COUNT(*) FROM completions").fetchone()[0]
    print(f"   completions: {comp_count} 条")
    
    # 验证checkins
    checkin_count = sqlite_conn.execute("SELECT COUNT(*) FROM checkins").fetchone()[0]
    print(f"   checkins: {checkin_count} 条")
    
    # 验证weak_points
    wp_count = sqlite_conn.execute("SELECT COUNT(*) FROM weak_points").fetchone()[0]
    print(f"   weak_points: {wp_count} 条")
    
    # 验证kid_settings
    ks_count = sqlite_conn.execute("SELECT COUNT(*) FROM kid_settings").fetchone()[0]
    print(f"   kid_settings: {ks_count} 条")
    
    # 验证box_opened设置
    box_opened = sqlite_conn.execute(
        "SELECT value FROM kid_settings WHERE key='box_opened'"
    ).fetchone()
    if box_opened:
        print(f"   box_opened: {box_opened[0]}")
    
    print("   ✅ 验证通过\n")
    
except Exception as e:
    print(f"   ⚠️  验证失败: {e}\n")

# 关闭连接
sqlite_conn.close()
pg_conn.close()

print("=== 迁移完成 ===")
print("\n注意：迁移后请重启应用并确认.env未设置DATABASE_URL")
