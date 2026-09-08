# 数据丢失预防（SQLite only）

2026-09-08 曾经把流量从 PostgreSQL 切回 SQLite，旧库只有 35 阳光，完整数据在 PG（33 条流水 / 121 阳光）。已经迁回 SQLite，PostgreSQL 服务、compose profile、迁移脚本都拿掉了。

## 现在怎么防

1. **只用 SQLite**。VPS `.env` 只写 `SUNSHINE_DB=/data/sunshine.db`，不要写 `DATABASE_URL`。`scripts/pre_deploy_check.sh` 发现 `DATABASE_URL` 或 postgres 容器会直接停部署。
2. **部署先备份**。`scripts/deploy_vps.sh` 会跑 `enhanced_backup.sh`，拷到 `data/backups/sqlite_YYYYMMDD_HHMMSS.db`，保留最近 20 份。
3. **每天再备两次**。在 VPS 仓库根执行一次：

   ```bash
   bash scripts/install_backup_cron.sh
   ```

   写入 crontab：每天 02:15、18:15。
4. **还原有脚本、有演练**。

   ```bash
   bash scripts/restore_db.sh                 # 列出备份
   bash scripts/restore_db.sh --latest --dry-run
   bash scripts/restore_db.sh sqlite_....db   # 真还原：停容器 → 快照当前库 → 拷回 → 再启动
   ```

## 发现余额不对时

1. 先别再部署、别再打卡。
2. `bash scripts/restore_db.sh` 看最近备份的流水条数和阳光。
3. `--dry-run` 确认目标后还原。
4. 还原前会留下 `pre_restore_*.db`，还原错了还能再切回去。

不要手动 `cp` 覆盖正在跑的库，也不要再启动 PostgreSQL。
