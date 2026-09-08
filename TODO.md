# 待办事项

> 单家庭、SQLite。紧急安全和家长端体验已在 v0.1.3–v0.1.43 做完。下面只留还没做、且值得做的。

## 现在还开着

- [ ] **B4 家庭共同目标**（见 PLAN.md）：同时只 1 个进行中目标；达标每人发一次阳光。单孩家庭收益不大，可后做。
- [ ] 教材实物复核 / 下学期目录（PLAN.md P2）。音美暂不做。

## 已完成

- [x] 家长角色 owner / member（后端 `require_owner` + 前端隐藏删孩子/成员/邀请，可转让创建者）
- [x] CSRF：Cookie SameSite=strict
- [x] 全局 500 不回堆栈
- [x] 家长改密要当前密码 + 确认
- [x] SQLite 备份 cron + `scripts/restore_db.sh` 还原
- [x] 硬编码库密码、Secret Key、并发锁、PIN 规则、阳光上限、Docker 绑内网 IP

## 单家庭不做

这些在 TODO 旧稿里还开着，当前规模用不上：

- 登录限流落 Redis（内存 10 分钟窗口够用）
- 兑换审批 N+1（一个孩子无感）
- 扣分自定义原因 / 分页 / 导出
- 结构化日志、审计表、Swagger、Service Worker
- PostgreSQL / 双库备份

_最后更新: 2026-09-08_
