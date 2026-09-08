# 部署说明补充

## 网络拓扑

当前架构：
- **VPS (192.168.100.5)**: 运行 Docker 容器，监听 `192.168.100.5:9000`
- **隧道机器**: 运行 Cloudflare Tunnel，通过内网连接 VPS

```
Internet → Cloudflare CDN → Tunnel机器 → 内网 → VPS:9000
```

## Docker 端口配置

修改后的 `docker-compose.yml`:
```yaml
ports:
  - "192.168.100.5:9000:8000"  # 绑定内网IP
```

**为什么不用 127.0.0.1**:
- 隧道和VPS不在同一机器
- 需要跨机器内网访问
- 192.168.100.5 是 VPS 的内网IP

**安全性**:
- ✅ 不暴露到公网（只绑定内网IP）
- ✅ 只能内网访问（Cloudflare Tunnel 通过内网连接）
- ✅ 外部访问必须经过 Cloudflare CDN

## 隧道配置

Cloudflare Tunnel 配置应该指向:
```yaml
ingress:
  - hostname: study.anemy.org
    service: http://192.168.100.5:9000
```

## 防火墙规则

VPS 防火墙应该:
```bash
# 允许内网访问 9000 端口
ufw allow from 192.168.100.0/24 to any port 9000

# 拒绝公网访问 9000 端口
ufw deny 9000
```

## 健康检查

从隧道机器检查:
```bash
curl -s http://192.168.100.5:9000/api/health
# 应返回: {"ok":true}
```

从公网检查:
```bash
curl -s https://study.anemy.org/api/health
# 应返回: {"ok":true}
```

## 常见问题

### 1. 连接被拒绝

**症状**: `curl: (7) Failed to connect to 192.168.100.5 port 9000`

**检查**:
```bash
# 1. 检查容器是否运行
docker compose ps

# 2. 检查端口绑定
netstat -tlnp | grep 9000

# 3. 检查防火墙
ufw status
```

### 2. 502 Bad Gateway

**症状**: Cloudflare 返回 502

**检查**:
```bash
# 1. 从隧道机器测试 VPS
curl -v http://192.168.100.5:9000/api/health

# 2. 检查隧道日志
journalctl -u cloudflared -f

# 3. 检查容器日志
docker compose logs --tail 50 sunshine
```

### 3. 修改 VPS IP

如果 VPS 内网IP变更:

1. 修改 `docker-compose.yml`:
   ```yaml
   ports:
     - "新IP:9000:8000"
   ```

2. 更新隧道配置指向新IP

3. 重启容器:
   ```bash
   docker compose down
   docker compose up -d
   ```

## 维护命令

```bash
# 查看容器状态
docker compose ps

# 查看实时日志
docker compose logs -f sunshine

# 重启服务
docker compose restart sunshine

# 完全重建（代码更新后）
docker compose down
docker compose up -d --build
```
