# 部署指南

- [环境要求](#环境要求)
- [一键安装](#一键安装)
- [手动安装](#手动安装)
- [HTTPS](#https)
- [更新与回滚](#更新与回滚)
- [备份与恢复](#备份与恢复)
- [迁移到新机器](#迁移到新机器)
- [Docker](#docker)
- [监控](#监控)
- [排错](#排错)

---

## 环境要求

| 项 | 要求 |
|---|---|
| 系统 | Ubuntu 20.04+ / Debian 11+ / CentOS 8+（其他 Linux 也行，脚本按 Debian 系写） |
| Python | 3.8+（只用标准库，不需要 pip） |
| 内存 | 512MB 够用，1GB 舒坦 |
| 磁盘 | 100MB + 数据（10 万条日志约 30MB） |
| 端口 | 80 / 443（Nginx），8787 只监听本地 |

**不需要** Docker、MySQL、Redis、Node.js。

## 一键安装

```bash
git clone https://github.com/Ytong825/keyauth.git ~/keyauth
cd ~/keyauth && sudo bash install.sh
```

脚本做的事：

1. 装 `python3` / `nginx` / `sqlite3`（缺什么装什么）
2. 把目录属主收敛成 `root:root`（避免 SFTP 传上来的文件属主混杂）
3. 写 systemd 单元 `/etc/systemd/system/keyauth.service`，开机自启
4. 写 Nginx 站点 `/etc/nginx/sites-available/keyauth` 并启用
5. 放行防火墙（ufw / firewalld）
6. 打印管理后台地址与管理令牌

可选参数：

```bash
# 管理后台锁到指定 IP（推荐，安装时定，之后也能改 Nginx）
sudo ADMIN_IP=1.2.3.4 bash install.sh

# 有域名时顺带申请 HTTPS
sudo bash install.sh auth.example.com
```

装完验证：

```bash
systemctl status keyauth
curl -s http://127.0.0.1:8787/api/health
```

## 手动安装

不想跑脚本就照这个来。

**1. 放代码**

```bash
sudo mkdir -p /opt/keyauth
sudo cp -r ./* /opt/keyauth/
sudo chown -R root:root /opt/keyauth
```

**2. systemd 单元** `/etc/systemd/system/keyauth.service`

```ini
[Unit]
Description=KeyAuth 卡密授权系统
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/keyauth
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=KEYAUTH_DATA=/opt/keyauth/data
ExecStart=/usr/bin/python3 /opt/keyauth/server.py --host 127.0.0.1 --port 8787
Restart=always
RestartSec=3
StandardOutput=append:/opt/keyauth/data/server.log
StandardError=append:/opt/keyauth/data/server.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now keyauth
```

**3. Nginx** `/etc/nginx/sites-available/keyauth`

```nginx
limit_req_zone $binary_remote_addr zone=keyauth_api:10m rate=20r/s;

server {
    listen 80;
    server_name _;
    client_max_body_size 2m;

    access_log /var/log/nginx/keyauth.access.log;
    error_log  /var/log/nginx/keyauth.error.log;

    location /admin {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        limit_req zone=keyauth_api burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # index.html 用绝对路径引 /app.css /app.js /login.css /favicon.svg
    location ~* ^/(app|login)\.css$ { proxy_pass http://127.0.0.1:8787; proxy_set_header Host $host; }
    location = /app.js              { proxy_pass http://127.0.0.1:8787; proxy_set_header Host $host; }
    location ~* \.(svg|png|jpg|jpeg|gif|ico|webp|woff2?)$ {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        expires 7d;
    }

    location / { return 302 /admin; }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/keyauth /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**4. 取管理令牌**

```bash
sudo cat /opt/keyauth/data/config.json | python3 -c "import json,sys;print(json.load(sys.stdin)['admin_token'])"
```

## HTTPS

**必须上**。http 明文传输，运营商和中间人能看到卡密。

Let's Encrypt 不给纯 IP 签证书，所以需要一个解析到本机的域名。

```bash
# 1. DNS 加 A 记录：auth.example.com → 你的公网 IP
# 2. 确认生效
dig +short auth.example.com

# 3. 一条命令
sudo bash deploy/enable_https.sh auth.example.com
```

脚本流程：解析比对 → 装 certbot → 备份 Nginx 配置 → 换 `server_name` → `certbot --nginx` 申请并改写 443 → 配 301 → `certbot renew --dry-run` 验证续期。

失败会打印回滚命令。常见失败原因：

| 现象 | 原因 |
|---|---|
| `Timeout during connect` | 安全组 / 防火墙没放行 80，或 DNS 还没生效 |
| `unauthorized` | 域名解析到的不是这台机器 |
| 签成功但浏览器报警 | 用的是自签证书（`--register-unsafely-without-email` 不影响，检查是否 certbot 生成了临时证书） |

**上完 HTTPS 做两件事**：

1. 后台「系统设置 → 对外访问地址」填 `https://auth.example.com`（让接入文档给出正确地址）
2. 客户端配置里的 base_url 换成 `https://`

证书自动续期由 `certbot.timer` 负责，`systemctl list-timers certbot.timer` 能看到下次执行时间。

## 更新与回滚

```bash
cd ~/keyauth && git pull && sudo bash update.sh
```

`update.sh` 的顺序是：**语法自检 → 备份数据库 → 重启 → 健康检查**。
语法不过就直接中止，不会把服务改挂。

回滚：

```bash
git log --oneline -5
git checkout <上一个commit> -- .
sudo bash update.sh
```

数据库不受影响（`data/` 不在版本库里）。要连数据一起回滚，用 [备份与恢复](#备份与恢复)。

## 备份与恢复

**后台备份（推荐）**

「系统设置 → 数据维护」里有：

- 「立即备份数据库」—— 走 SQLite 在线备份 API，热备不锁库
- 备份列表 —— 显示文件名、大小、时间，点「下载」直接存到本地
- 「立即清理过期日志」—— 按保留天数删旧日志

`GET /api/admin/backups/<文件名>` 就是下载接口，可以写进自己的运维脚本（带 `X-Admin-Token`）。

**命令行备份**：

```bash
sudo cp /opt/keyauth/data/keyauth.db ~/keyauth-$(date +%F).db
```

**定时备份**（crontab）：

```cron
# 每天 03:30，保留 14 天
30 3 * * * cp /opt/keyauth/data/keyauth.db /opt/keyauth/data/backup/keyauth-$(date +\%F).db && find /opt/keyauth/data/backup -name 'keyauth-*.db' -mtime +14 -delete
```

> 用 SQLite 的在线备份 API（后台按钮走的就是这个）比 `cp` 安全——`cp` 时如果有写入，
> 可能拷到不一致的快照。低峰期 `cp` 一般没事，求稳就用 `sqlite3 keyauth.db ".backup out.db"`。

**恢复**：

```bash
sudo systemctl stop keyauth
sudo cp ~/keyauth-2026-11-08.db /opt/keyauth/data/keyauth.db
sudo rm -f /opt/keyauth/data/keyauth.db-wal /opt/keyauth/data/keyauth.db-shm
sudo systemctl start keyauth
```

> 别忘删 `-wal` / `-shm`。残留的 WAL 会把旧数据重放到新库上，导致恢复看起来「没生效」。

## 迁移到新机器

```bash
# 旧机器
sudo systemctl stop keyauth
tar czf keyauth-data.tgz -C /opt/keyauth data

# 新机器
git clone https://github.com/Ytong825/keyauth.git ~/keyauth
cd ~/keyauth && sudo bash install.sh
sudo systemctl stop keyauth
sudo tar xzf keyauth-data.tgz -C /opt/keyauth      # 覆盖 data/
sudo systemctl start keyauth
```

`data/config.json` 里有管理令牌，一起搬过去就还是原来的令牌。

DNS 换到新 IP 后，如果用了 HTTPS，重新跑一次 `deploy/enable_https.sh`。

## Docker

```bash
docker compose up -d --build
```

`docker-compose.yml` 里端口写死 `127.0.0.1:8787`。

**不要改成 `8787:8787`** —— Docker 的端口发布绕过 ufw / firewalld，
等于把服务直接挂到公网，而且 Nginx 的限流也一并绕过。

Docker 方案没有 systemd 的自动重启之外的运维能力，生产环境仍建议宿主机直装。

## 监控

**健康检查**

```bash
curl -fsS http://127.0.0.1:8787/api/health
# {"ok":true,"name":"keyauth","server_time":1794090000,"version":"1.1.0"}
```

**关键指标**（都在后台概览页）

| 指标 | 异常信号 |
|---|---|
| 今日校验次数 | 突然归零 → 客户端连不上 / DNS 挂了 |
| 结果码分布 | `BAD_SIGN` 突增 → 有人在试签名 / 客户端配置错 |
| 结果码分布 | `RATE_LIMIT` 突增 → 被刷，或某个客户端心跳写成了死循环 |
| 绑定设备数 | 单卡设备数异常增长 → 卡密在传播 |

**日志**

```bash
journalctl -u keyauth -f                          # 服务日志
tail -f /opt/keyauth/data/server.log              # 应用日志（systemd 重定向）
tail -f /var/log/nginx/keyauth.access.log         # 访问日志
```

应用日志里每行是一次请求，格式：

```
[05:14:02] "POST /api/v1/heartbeat HTTP/1.0" 200 -
```

## 排错

**服务起不来**

```bash
systemctl status keyauth -l
journalctl -u keyauth -n 50 --no-pager
ss -lntp | grep 8787        # 端口被占？
```

常见原因：端口被占、`data/` 权限不对（必须 root 可写）、Python 版本低于 3.8。

**后台打得开但一片空白 / 没有样式**

Nginx 少了根路径静态资源的转发规则（`/app.css`、`/app.js`、`/login.css`）。
对照[手动安装](#手动安装)第 3 步的 Nginx 配置补上，或直接用 `install.sh` 生成的那份。

**`/admin/` 带尾斜杠时白屏**

资源引用是绝对路径（`/app.js`），正常不会有这问题。如果改过 `index.html` 又改回相对路径，
从 `/admin/` 打开时会被解析成 `/admin/app.js` 而 404。

**客户端全部 `BAD_SIGN`**

1. 后台「应用」页确认 AppSecret 没被重置过
2. 客户端签名实现对照 [docs/CLIENT.md](CLIENT.md#签名实现)
3. 打开校验日志，看 `result` 列是不是全是 `BAD_SIGN`

**后台 401**

令牌不对。从 `data/config.json` 重新取，或在服务器上直接重置：

```bash
sudo systemctl stop keyauth
sudo python3 -c "
import json;p='/opt/keyauth/data/config.json'
c=json.load(open(p));import secrets;c['admin_token']=secrets.token_urlsafe(32)
json.dump(c,open(p,'w'),ensure_ascii=False,indent=2);print(c['admin_token'])"
sudo systemctl start keyauth
```
