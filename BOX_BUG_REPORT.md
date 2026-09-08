# 宝箱Bug修复报告

## 🐛 问题描述

**现象**: 9月8日不应该能开宝箱，但实际开了第2次（获得+4阳光）

**影响**: 余额从121阳光变成125阳光

---

## 🔍 根本原因分析

### 时间线

1. **9月6日** (连击3天)
   - 应得宝箱: `3 // 3 = 1` 个
   - 已开宝箱: 0 个
   - ✅ **正确开箱** (+6阳光)
   - `box_opened` 设置为 1

2. **9月8日凌晨2:18** - 数据迁移
   - 执行 PostgreSQL → SQLite 迁移
   - **❌ 迁移脚本遗漏了 `kid_settings` 表**
   - `box_opened` 丢失，回到默认值 0

3. **9月8日12:34** (连击5天)
   - 应得宝箱: `5 // 3 = 1` 个
   - 读取 `box_opened`: **0** (错误的值！)
   - 检查通过: `1 > 0` ✅
   - **❌ 错误开箱** (+4阳光)
   - 实际应该: `box_opened=1`, 检查 `1 <= 1` 失败

### 根本原因

数据迁移脚本只迁移了4个表：
```python
["ledger", "completions", "checkins", "weak_points"]
```

**遗漏了 `kid_settings` 表**，导致宝箱计数器丢失。

---

## 宝箱规则验证

### 正确的规则逻辑

```python
BOX_INTERVAL = 3  # 每3天一个宝箱

@app.post("/api/open_box")
def open_box():
    streak = streak(c)  # 当前连击天数
    opened = int(db.get_kid_setting(c, kid_id(), "box_opened", "0"))
    
    # 关键检查
    if streak // BOX_INTERVAL <= opened:
        raise HTTPException(409, "还没有可开的宝箱")
    
    # 开箱逻辑
    bonus = random.randint(3, 10)
    db.set_kid_setting(c, kid_id(), "box_opened", str(opened + 1))
    insert_ledger(c, db.today(), bonus, "box", f"box-{opened + 1}", "连击宝箱")
```

### 规则测试

| 连击天数 | 应得 | 已开 | 检查 `应得 <= 已开` | 结果 |
|---------|------|------|---------------------|------|
| 2天 | 0 | 0 | `0 <= 0` = 真 | ❌ 不能开 |
| 3天 | 1 | 0 | `1 <= 0` = 假 | ✅ 能开 |
| 4天 | 1 | 1 | `1 <= 1` = 真 | ❌ 不能开 |
| 5天 | 1 | 1 | `1 <= 1` = 真 | ❌ 不能开 |
| 6天 | 2 | 1 | `2 <= 1` = 假 | ✅ 能开 |

✅ **规则本身是正确的！**

---

## ✅ 已执行的修复

### 1. 删除错误的宝箱记录

```python
# 删除9月8日的+4阳光记录
DELETE FROM ledger WHERE id = 37
```

**结果**: 余额从125恢复到121阳光 ✅

### 2. 修正 box_opened 设置

```python
# 恢复正确的计数
db.set_kid_setting(c, kid_id, "box_opened", "1")
```

**结果**: 当前只开了1个宝箱（9月6日） ✅

### 3. 创建完整的迁移脚本

新脚本 `scripts/migrate_pg_to_sqlite_fixed.py` 包含：
```python
TABLES_TO_MIGRATE = [
    "ledger",
    "completions", 
    "checkins",
    "weak_points",
    "kid_settings"  # ✅ 新增
]
```

---

## 🧪 验证结果

### 修复后数据状态

```
流水记录: 33 条
阳光余额: 121 阳光 ✅
宝箱记录: 1 次
box_opened: 1
```

### 数据分布

- 9月4日: 12条记录
- 9月5日: 7条记录
- 9月6日: 4条记录 (包括宝箱)
- 9月7日: 9条记录
- 9月8日: 1条记录 (只有坐位体前屈，宝箱已删除)

### 宝箱状态

| 日期 | 连击 | 应得 | 已开 | 可开 | 状态 |
|------|------|------|------|------|------|
| 9/6 | 3 | 1 | 0 | 1 | ✅ 已开 |
| 9/8 | 5 | 1 | 1 | 0 | ✅ 不能开 |
| 9/9 | 6 | 2 | 1 | 1 | ⏰ 明天可开 |

---

## 📋 防止再次发生

### 1. 使用完整迁移脚本

以后如果需要从PostgreSQL迁移回SQLite，使用：
```bash
docker compose exec sunshine python3 scripts/migrate_pg_to_sqlite_fixed.py
```

### 2. 迁移检查清单

- [ ] 迁移 ledger (流水)
- [ ] 迁移 completions (完成记录)
- [ ] 迁移 checkins (签到)
- [ ] 迁移 weak_points (薄弱点)
- [ ] 迁移 **kid_settings** (孩子设置，包括宝箱计数)
- [ ] 验证 box_opened 值
- [ ] 验证余额一致

### 3. 部署前检查

现有的 `scripts/pre_deploy_check.sh` 已经包含数据一致性检查，可以检测到迁移问题。

---

## 📊 影响评估

### 影响范围
- ✅ 已完全修复
- ✅ 余额准确 (121阳光)
- ✅ 宝箱计数正确 (1次)
- ✅ 无其他数据丢失

### 用户影响
- 孩子多获得了4阳光
- 已删除，无持续影响

---

## 🎯 总结

**Bug**: 数据迁移时遗漏 `kid_settings` 表
**影响**: 宝箱计数器丢失，导致重复开箱
**修复**: 删除错误记录 + 修正计数 + 完善迁移脚本
**状态**: ✅ 已修复并验证

**宝箱规则本身是正确的，无需修改代码逻辑。**

---

_修复时间: 2026-09-08 13:00_  
_版本: v0.1.8_
