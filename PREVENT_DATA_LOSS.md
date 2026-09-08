# 数据丢失预防指南

本文档总结了本次数据丢失事件的根本原因，并提供完整的预防措施。

---

## 📋 事件回顾

### 问题
- **现象**: 阳光余额从121降到35
- **根本原因**: 数据库类型切换（PostgreSQL → SQLite）
- **发生时间**: 2026-09-08 凌晨2:18部署时

### 时间线
1. **9月4-5日**: 数据写入SQLite (17条记录)
2. **9月6日**: 某次部署启动PostgreSQL容器
3. **9月6-7日**: 新数据写入PostgreSQL (16条记录)
4. **9月8日凌晨**: 安全加固部署，.env配置改为SQLite
5. **9月8日上午**: 应用切回SQLite，显示旧数据(35阳光)

### 数据分布
- **SQLite**: 17条记录，35阳光 (9月4-5日)
- **PostgreSQL**: 33条记录，121阳光 (9月4-8日) ✅ 完整

---

## 🔐 核心预防措施

### 1. 明确数据库策略

**决策**: 使用 SQLite（单家庭场景）

**配置文件 `.env`**:
```bash
# 明确指定使用SQLite
SUNSHINE_DB=/data/sunshine.db

# 不设置这些PostgreSQL变量
# DATABASE_URL=  
# DATABASE_APP_URL=
# COMPOSE_PROFILES=
```

**Docker Compose**:
- PostgreSQL 已配置为 `profiles: ["postgres"]`
- 默认不启动PostgreSQL容器
- 只在明确指定 `--profile postgres` 时启动

### 2. 自动备份增强

**新脚本**: `scripts/enhanced_backup.sh`

**功能**:
- ✅ 自动检测当前使用的数据库类型
- ✅ 同时备份SQLite和PostgreSQL
- ✅ 数据一致性检查（如果两个都在运行）
- ✅ 记录备份日志
- ✅ 自动清理旧备份（保留20个）

**使用**:
```bash
cd /home/kofwj/sunshine
bash scripts/enhanced_backup.sh
```

**Cron自动备份**:
```bash
# 每天凌晨2点和下午6点备份
0 2,18 * * * cd /home/kofwj/sunshine && bash scripts/enhanced_backup.sh >> /tmp/backup.log 2>&1
```

### 3. 部署前检查

**新脚本**: `scripts/pre_deploy_check.sh`

**检查项**:
1. 当前数据库配置（.env）
2. 当前运行的数据库容器
3. 数据记录数对比
4. 数据库切换风险检测

**告警场景**:
- ❌ 切换数据库会导致数据丢失
- ❌ SQLite和PostgreSQL数据不一致
- ⚠️ PostgreSQL有旧数据

**使用**:
```bash
cd /home/kofwj/sunshine
bash scripts/pre_deploy_check.sh
```

### 4. 集成到部署流程

**更新后的 `scripts/deploy_vps.sh`**:
```bash
步骤1: 部署前检查 (pre_deploy_check.sh)
  ↓ 发现问题 → 要求确认
步骤2: 增强备份 (enhanced_backup.sh)
步骤3: 拉取代码
步骤4: 构建镜像
步骤5: 健康检查
```

---

## 🚀 使用指南

### 日常部署

```bash
# SSH登录VPS
ssh root@192.168.100.5

# 进入项目目录
cd /home/kofwj/sunshine

# 运行部署脚本（自动包含检查和备份）
bash scripts/deploy_vps.sh
```

### 手动备份

```bash
# 定期手动备份
bash scripts/enhanced_backup.sh

# 查看备份日志
tail -f data/backups/backup.log
```

### 数据恢复

**如果发现数据丢失**:

1. **立即停止所有操作**
2. **检查备份目录**:
```bash
ls -lh data/backups/
```

3. **查看最近的备份**:
```bash
# SQLite备份
sqlite3 data/backups/sqlite_YYYYMMDD_HHMMSS.db "SELECT COUNT(*) FROM ledger"

# PostgreSQL备份
grep "INSERT INTO ledger" data/backups/postgres_YYYYMMDD_HHMMSS.sql | wc -l
```

4. **恢复数据**:
```bash
# 恢复SQLite
cp data/backups/sqlite_YYYYMMDD_HHMMSS.db data/sunshine.db

# 或从PostgreSQL导出
docker compose exec -T postgres pg_dump -U sunshine > backup.sql
```

---

## 📊 监控建议

### 1. 每日检查

每天查看备份日志，确认：
- ✅ 备份成功
- ✅ 记录数量合理增长
- ❌ 无数据不一致告警

```bash
tail -30 data/backups/backup.log
```

### 2. 告警设置（可选）

如果数据不一致，`enhanced_backup.sh` 会记录告警到日志。

可以配置邮件或webhook告警:
```bash
# 在 enhanced_backup.sh 中添加
if [ "$SQLITE_COUNT" != "$PG_COUNT" ]; then
    # 发送告警邮件
    echo "数据不一致" | mail -s "数据库告警" your@email.com
    
    # 或 webhook
    curl -X POST https://your-webhook-url \
      -H "Content-Type: application/json" \
      -d '{"text":"数据库不一致告警"}'
fi
```

### 3. 健康检查脚本

**新建 `scripts/health_check.sh`**:
```bash
#!/bin/bash
# 快速健康检查

echo "=== 系统健康检查 ==="

# 1. 服务状态
curl -s http://192.168.100.5:9000/api/health | python3 -m json.tool

# 2. 数据库记录数
RECORDS=$(docker compose exec -T sunshine python3 << EOF
import sys
sys.path.insert(0, "/app/backend")
import db
db.init_db()
c = db.connect()
count = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
balance = c.execute("SELECT SUM(delta) FROM ledger").fetchone()[0]
c.close()
print(f"{count},{balance}")
EOF
)

echo "数据记录: $RECORDS"
echo "✅ 健康检查完成"
```

---

## ⚠️ 重要提醒

### 禁止的操作

1. **不要手动修改 `.env` 中的 `DATABASE_URL`**
   - 除非明确要切换数据库，并已做好数据迁移准备

2. **不要手动启动PostgreSQL容器**
   ```bash
   # ❌ 不要执行
   docker compose --profile postgres up
   ```

3. **不要删除备份目录**
   - 备份是数据安全的最后防线

### 推荐的操作

1. **每次部署前都运行检查**
   ```bash
   bash scripts/pre_deploy_check.sh
   ```

2. **定期查看备份日志**
   ```bash
   cat data/backups/backup.log
   ```

3. **遇到异常立即停止并查看日志**
   ```bash
   docker compose logs sunshine --tail=100
   ```

---

## 📝 检查清单

### 部署前
- [ ] 运行 `pre_deploy_check.sh`
- [ ] 确认数据库类型正确
- [ ] 查看最近的备份
- [ ] 确认数据记录数正常

### 部署后
- [ ] 健康检查通过
- [ ] 登录验证数据正确
- [ ] 查看Docker日志无异常
- [ ] 备份文件已生成

### 每周
- [ ] 查看备份日志
- [ ] 检查磁盘空间
- [ ] 验证数据完整性
- [ ] 清理旧备份（自动）

---

## 🔧 故障排查

### 问题：阳光数据不对

1. **检查当前使用的数据库**:
```bash
docker compose ps
# 看是否有 postgres 容器在运行
```

2. **检查.env配置**:
```bash
grep DATABASE_URL .env
# 应该为空或被注释
```

3. **比较两个数据库的数据**:
```bash
# SQLite
sqlite3 data/sunshine.db "SELECT COUNT(*), SUM(delta) FROM ledger"

# PostgreSQL（如果在运行）
docker compose exec -T postgres psql -U sunshine -d sunshine \
  -c "SELECT COUNT(*), SUM(delta) FROM ledger"
```

4. **恢复数据**:
```bash
# 参考上面的"数据恢复"部分
```

### 问题：备份失败

1. **检查磁盘空间**:
```bash
df -h
```

2. **检查权限**:
```bash
ls -ld data/backups
# 应该可写
```

3. **手动备份**:
```bash
cp data/sunshine.db data/backups/manual_backup_$(date +%Y%m%d_%H%M%S).db
```

---

## 📞 紧急联系

如果遇到数据丢失且无法自行恢复：

1. **立即停止所有操作**
2. **保留所有日志和备份文件**
3. **联系技术支持**（提供本文档和日志）

---

_最后更新: 2024-09-08_
_版本: v1.0_
