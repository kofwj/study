# CI/CD 自动构建与部署配置

本项目已配置 GitHub Actions 自动化流程，每次 push 到 main 分支时自动构建 APK 并部署到 VPS。

## 前置准备

### 1. 在 VPS 上添加 GitHub Actions SSH 公钥

SSH 连接到 VPS 并执行：

```bash
# 方式一：直接添加
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGSj/J1sNgT9ik9qQ75+pIOAQvQ5FcTgBdYk4PWnFmam github-actions@sunshine" >> ~/.ssh/authorized_keys

# 方式二：手动编辑
vi ~/.ssh/authorized_keys
# 然后粘贴上面的公钥
```

### 2. 在 GitHub 仓库中配置 Secrets

访问 GitHub 仓库 Settings → Secrets and variables → Actions → New repository secret

需要添加以下 3 个 secrets：

| Name | Value | 说明 |
|------|-------|------|
| `VPS_SSH_KEY` | (见下方私钥内容) | GitHub Actions 用于连接 VPS 的 SSH 私钥 |
| `VPS_HOST` | `192.168.100.5` | VPS 的 IP 地址或域名 |
| `VPS_USER` | `root` | VPS 的 SSH 用户名 |

#### VPS_SSH_KEY 私钥内容

```
-----BEGIN OPENSSH PRIVATE KEY-----
(私钥内容将在下面单独提供，请复制完整内容)
-----END OPENSSH PRIVATE KEY-----
```

## 工作流程

1. **触发条件**：push 到 main 分支，且修改了以下目录之一
   - `frontend/**` - 前端代码
   - `android/**` - Android 配置
   - `backend/**` - 后端代码
   - `VERSION` - 版本号文件

2. **构建步骤**：
   - 检出代码
   - 安装 Node.js 20 和 Java 17
   - 构建前端（`npm ci && npm run build`）
   - 构建 Android APK（`./gradlew assembleRelease`）
   - 通过 SSH 上传 APK 到 VPS `/home/kofwj/sunshine/static/sunshine-latest.apk`

3. **部署结果**：
   - APK 自动上传到 VPS
   - 平板可通过 `http://192.168.100.5:9000/api/apk/latest` 下载最新版本
   - 在 GitHub Actions 页面可查看构建日志和部署摘要

## 平板端更新流程

### 方式一：手动下载安装（当前）

1. 平板浏览器访问 `http://192.168.100.5:9000/api/apk/latest`
2. 下载 APK 并安装

### 方式二：应用内更新（后续实现）

需要在 Android 应用中添加版本检查和自动下载功能（见 MainActivity 更新逻辑）

## 本地测试 CI 流程

```bash
# 1. 模拟前端构建
cd frontend
npm ci
npm run build

# 2. 模拟 Android 构建
cd ../android
chmod +x gradlew
./gradlew assembleRelease

# 3. 检查输出
ls -lh app/build/outputs/apk/release/app-release.apk

# 4. 手动上传到 VPS（测试用）
scp app/build/outputs/apk/release/app-release.apk \
  root@192.168.100.5:/home/kofwj/sunshine/static/sunshine-latest.apk
```

## 查看构建状态

- GitHub Actions：https://github.com/kofwj/study/actions
- 每次 push 后会自动触发构建
- 构建时间约 5-10 分钟（取决于 GitHub Actions 排队情况）
- 构建失败会在 Actions 页面看到红色标记并收到邮件通知

## 故障排查

### SSH 连接失败
```
Error: Permission denied (publickey)
```
→ 检查 VPS 上的 `~/.ssh/authorized_keys` 是否包含公钥，权限是否正确（600）

### APK 构建失败
```
Error: Could not find or load main class org.gradle.wrapper.GradleWrapperMain
```
→ 检查 `android/gradlew` 是否有执行权限

### 前端构建失败
```
Error: Cannot find module
```
→ 检查 `frontend/package-lock.json` 是否存在且已提交

## 禁用自动构建

如果需要临时禁用自动构建：

1. 在 commit message 中添加 `[skip ci]` 或 `[ci skip]`
2. 或者在 `.github/workflows/build-and-deploy-apk.yml` 中注释掉 `on:` 触发条件
# CI/CD 测试
