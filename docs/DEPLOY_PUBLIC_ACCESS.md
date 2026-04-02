# 公网访问部署说明

## 1. 目标

这份文档说明如何把本项目部署在你自己的服务器或主机上，并让其他机器通过外网访问网站。

推荐方案是：

- 使用 Docker 运行应用
- 使用 Caddy 作为反向代理
- 通过域名启用 HTTPS

## 2. 为什么推荐 HTTPS

如果只是本机访问，`http://127.0.0.1:8000` 就足够。  
但如果要让外网用户访问，并且还要配合浏览器钱包完成链上操作，更推荐使用 HTTPS。

原因包括：

- 登录会话更安全
- 浏览器环境更标准
- 对钱包扩展兼容性更好

## 3. 前置条件

部署前请准备好：

- 一台拥有公网 IP 的主机或服务器
- 已安装 Docker 和 Docker Compose
- 一个已解析到该服务器公网 IP 的域名或子域名
- 可用的 `.env` 配置

## 4. 配置 `.env`

建议至少配置以下内容：

```env
APP_SECRET_KEY=change-this-secret-in-production
APP_TIMEZONE=Asia/Shanghai
APP_SESSION_HTTPS_ONLY=true

APP_CHAIN_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
APP_CHAIN_PRIVATE_KEY=YOUR_PRIVATE_KEY_WITHOUT_0x
APP_CHAIN_NETWORK_NAME=sepolia

APP_PUBLIC_DOMAIN=vote.example.com
```

说明：

- `APP_SESSION_HTTPS_ONLY=true` 表示会话 Cookie 仅通过 HTTPS 发送
- `APP_PUBLIC_DOMAIN` 必须和你的实际域名一致

## 5. 启动公网部署

在项目根目录运行：

```bash
docker compose -f docker-compose.public.yml up --build -d
```

这个编排会启动两个服务：

- `vote-station`
  FastAPI 应用容器
- `caddy`
  负责 `80/443` 端口、HTTPS 证书和反向代理

## 6. 需要开放的端口

确保服务器或本地主机的网络边界允许外部访问：

- `80/tcp`
- `443/tcp`

如果你的主机在家庭宽带或内网环境下，还需要在路由器上做端口转发，把：

- 外部 `80` 转发到主机 `80`
- 外部 `443` 转发到主机 `443`

如果你用的是云服务器，则需要在安全组中放行 80 和 443。

## 7. 访问方式

配置生效后，其他机器即可通过以下地址访问：

```text
https://你的域名
```

例如：

```text
https://vote.example.com
```

## 8. 常用排查命令

查看容器状态：

```bash
docker compose -f docker-compose.public.yml ps
```

查看应用日志：

```bash
docker compose -f docker-compose.public.yml logs -f vote-station
```

查看反向代理日志：

```bash
docker compose -f docker-compose.public.yml logs -f caddy
```

本机测试应用是否正常：

```bash
curl http://127.0.0.1:8000
```

本机测试 HTTPS 是否正常：

```bash
curl -I https://你的域名
```

## 9. 常见问题

### 9.1 外网打不开，但本机能打开

通常是以下原因之一：

- 没有开放 80/443 端口
- 域名没有正确解析到公网 IP
- 路由器没有做端口转发
- 本地主机防火墙拦截了访问

### 9.2 浏览器钱包不能正常使用

优先检查：

- 访问地址是否是 HTTPS
- 钱包是否连接到正确的网络，例如 Sepolia
- 页面中绑定的钱包地址是否与登录账户一致

### 9.3 证书申请失败

优先检查：

- 域名解析是否已经生效
- `APP_PUBLIC_DOMAIN` 是否填写正确
- 80 和 443 端口是否可以从公网访问

## 10. 如果没有域名怎么办

没有域名时，你仍然可以临时使用：

```text
http://公网IP:8000
```

但这更适合临时调试，不适合作为正式外网访问方案。  
如果后续需要钱包交互、登录会话更稳定和更标准的公网访问方式，仍然建议尽快配置域名和 HTTPS。
