# 待办事项

## 🔴 高优先级

### 1. 家长角色权限区分
**当前问题**: 所有家长都是 `role='parent'`，权限完全一致
**需求**: 区分家长创建者（管理员）和普通家长成员

**建议方案**:
```sql
ALTER TABLE users ADD COLUMN parent_role TEXT DEFAULT 'member';
-- 'owner': 创建者，可以管理家庭设置、删除成员
-- 'member': 普通家长，只能查看和批准兑换
```

**功能差异**:
- ✅ 所有家长：查看周报、批准兑换、管理任务和考点
- 🔒 仅创建者：删除家长成员、删除孩子账号、修改家庭设置、生成邀请码

**实现位置**: 
- `backend/db.py` - 数据库迁移
- `backend/main.py` - 权限检查函数
- `frontend/src/Admin.vue` - UI权限隐藏

---

## 🟠 中优先级

### 2. CSRF 保护
**当前问题**: Cookie认证但无CSRF token
**影响**: 用户访问恶意网站时，该网站可代替用户发送请求

**建议方案**:
```python
# 方案A: 使用 FastAPI CSRF 中间件
from fastapi_csrf_protect import CsrfProtect

# 方案B: 修改 Cookie SameSite 策略
resp.set_cookie(..., samesite="strict")  # 从 lax 改为 strict
```

**实现位置**: `backend/main.py:87-95`

---

### 3. 限流持久化
**当前问题**: 登录失败记录存储在内存中，应用重启后清空
**影响**: 攻击者可通过重启应用绕过限流

**建议方案**:
```python
# 使用 Redis 或数据库存储
# CREATE TABLE rate_limits (key TEXT, timestamp REAL, expires_at REAL)
```

**实现位置**: `backend/main.py:76-86`

---

### 4. 全局异常处理
**当前问题**: 未捕获的异常会暴露堆栈信息给客户端
**影响**: 泄露内部实现细节

**建议方案**:
```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"}
    )
```

**实现位置**: `backend/main.py` 开头

---

### 5. N+1 查询优化
**当前问题**: `redemptions_admin` 函数对每个孩子执行单独查询
**影响**: 家庭孩子多时性能下降

**优化方案**:
```python
# 修复前
for kid in roster:
    db.apply_scope(c, fam, kid)
    for r in c.execute("SELECT ...").fetchall():
        ...

# 修复后
results = c.execute("""
    SELECT rd.*, u.name as kid_name, rw.name as reward_name
    FROM redemptions rd
    JOIN users u ON rd.kid_id = u.id
    JOIN rewards rw ON rd.reward_id = rw.id
    WHERE u.family_id = ?
""", (fam,)).fetchall()
```

**实现位置**: `backend/main.py:1300-1332`

---

## 🟡 低优先级

### 6. 密码修改时的旧密码验证
**当前问题**: 家长修改PIN时不需要输入旧密码
**影响**: 如果家长会话被劫持，攻击者可直接修改密码

**建议方案**:
```python
@app.post("/api/admin/pin")
def change_pin(body: ChangePinBody, request: Request):
    # 新增：验证旧密码
    if not body.old_pin or not db.verify_pin(body.old_pin, user["pin_hash"]):
        raise HTTPException(400, "旧密码不正确")
    # ... 原有逻辑
```

---

### 7. SQL 拼接改进
**当前问题**: 虽然安全但使用 f-string 拼接表名

**优化方案**:
```python
# 修复前
c.execute(f"UPDATE {t} SET kid_id=? WHERE ...", ...)

# 修复后
ALLOWED_TABLES = {"users", "completions", "ledger", ...}
if t not in ALLOWED_TABLES:
    raise ValueError(f"Invalid table: {t}")
c.execute(f"UPDATE {t} SET kid_id=? WHERE ...", ...)
```

**实现位置**: 
- `backend/db.py:428`
- `scripts/reset_data.py:20`

---

### 8. 结构化日志
**当前需求**: 添加请求ID、用户ID、操作类型的结构化日志

**建议方案**:
```python
import logging
import json
from contextvars import ContextVar

request_id_var = ContextVar('request_id', default=None)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    logger.info(json.dumps({
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "user_id": getattr(request.state, 'user', {}).get('user_id'),
    }))
    response = await call_next(request)
    return response
```

---

### 9. 测试奖励档位校验增强
**当前问题**: 允许设置不合理的分数区间（如 [100, 10], [90, 20]）

**优化方案**:
```python
# 校验分数区间递减、阳光递减
for i in range(len(bands) - 1):
    if bands[i][0] <= bands[i+1][0]:
        raise HTTPException(400, "分数区间必须递减")
    if bands[i][1] <= bands[i+1][1]:
        raise HTTPException(400, "阳光奖励应随分数递减")
```

**实现位置**: `backend/main.py` 测试奖励档位API

---

## ✅ 已完成（v0.1.2）

- [x] 硬编码数据库密码 → 环境变量
- [x] Secret Key 持久化
- [x] 并发余额超支 → 事务锁
- [x] 完成任务竞态 → try-finally
- [x] 连接泄漏 → 8处修复
- [x] 弱密码认证 → 6位起步
- [x] 输入验证 → 阳光上限10000
- [x] Docker端口 → 绑定内网IP

---

## 📅 开发计划

### v0.1.3 (计划)
- [ ] 家长角色权限区分
- [ ] CSRF 保护
- [ ] 全局异常处理

### v0.1.4 (计划)
- [ ] 限流持久化（Redis可选）
- [ ] N+1 查询优化
- [ ] 密码修改验证

### v0.2.0 (计划)
- [ ] 结构化日志
- [ ] 监控告警（可选）
- [ ] 性能优化

---

## 💡 功能增强建议

### 10. 家长操作审计日志
**需求**: 记录家长的关键操作（删除成员、修改奖励、批准兑换）

**方案**:
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    action TEXT,  -- 'delete_member', 'approve_redeem', ...
    target_id TEXT,
    details TEXT,  -- JSON
    created_at TEXT
);
```

---

### 11. 兑换撤回功能
**需求**: 孩子申请兑换后可在家长批准前撤回

**方案**:
```python
@app.post("/api/redemptions/{rid}/cancel")
def cancel_redemption(rid: str):
    # 只能撤回 status='pending' 的申请
    # 只能撤回自己的申请
```

---

### 12. 批量操作API
**需求**: 批量点亮考点、批量添加任务

**方案**:
```python
@app.post("/api/admin/weak-points/batch")
def batch_weak_points(body: BatchWeakPointsBody):
    # body: {kid_id, unit_id, tag_ids: [...]}
    # 一次请求点亮多个考点
```

---

## 📊 性能优化建议

### 13. 数据库索引
**当前问题**: 部分高频查询缺少索引

**建议添加**:
```sql
CREATE INDEX idx_completions_kid_date ON completions(kid_id, date);
CREATE INDEX idx_ledger_kid ON ledger(kid_id);
CREATE INDEX idx_weak_points_kid_unit ON weak_points(kid_id, unit_id);
```

---

### 14. 前端缓存策略
**建议**: 使用 Service Worker 缓存静态资源和API响应

---

## 🔧 技术债务

### 15. 类型注解完善
**当前**: 部分函数缺少类型注解
**建议**: 使用 `mypy` 进行静态类型检查

### 16. 测试覆盖率提升
**当前**: 16个测试，覆盖核心功能
**建议**: 增加边界情况和并发测试

---

## 📝 文档改进

### 17. API 文档
**建议**: 生成 OpenAPI/Swagger 文档供前端参考

### 18. 架构图
**建议**: 添加系统架构图、数据流图

---

_最后更新: 2024-09-08_
