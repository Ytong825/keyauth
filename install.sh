#!/usr/bin/env bash
#
# KeyAuth 一键安装（FinalShell 新手版 · 纯 systemd，不用 Docker）
#
# 装在哪都行 —— 脚本按自身所在目录工作，不绑定 /opt：
#     cd /opt/keyauth        && sudo bash install.sh
#     cd /home/ubuntu/keyauth && sudo bash install.sh
#
# 可选参数：
#     sudo ADMIN_IP=1.2.3.4 bash install.sh     # 把管理后台锁到你的 IP
#     sudo bash install.sh auth.你的域名.com      # 带域名，顺带申请 HTTPS
#     sudo ADMIN_TOKEN='你的令牌' bash install.sh  # 自己指定管理令牌（默认随机生成）
#
# 做这些：装依赖 → 装成开机自启服务 → 配 Nginx → 放防火墙 → 打印访问地址和令牌
# 不做这些：不改 SSH 配置、不删你已有的服务、不装 Docker

set -euo pipefail

# ============================================================ 可调参数
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8787
ADMIN_IP="${ADMIN_IP:-}"
DOMAIN="${1:-}"
# 可选：直接指定管理令牌。留空则首次启动自动生成 32 字节随机令牌。
#     sudo ADMIN_TOKEN='你的令牌' bash install.sh
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
PY=python3
# ============================================================

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[36m'; N=$'\033[0m'
info() { echo "${G}==>${N} $*"; }
warn() { echo "${Y}[!]${N} $*"; }
die()  { echo "${R}[x]${N} $*" >&2; exit 1; }
step() { echo; echo "${B}────────────────────────────────────────────${N}"; echo "${B}  $*"; echo "${B}────────────────────────────────────────────${N}"; }

[[ $EUID -eq 0 ]] || die "请用 sudo 运行：sudo bash install.sh"

# ---------------------------------------------------------------- 0 环境
step "0/7  检查系统环境"
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  info "系统：${PRETTY_NAME:-未知}"
  [[ "${ID:-}" == "ubuntu" ]] || warn "脚本按 Ubuntu 编写，${ID:-当前系统} 可能略有差异"
fi
info "项目目录：$APP_DIR"
[[ -f "$APP_DIR/server.py" ]] || die "这里不像项目目录（找不到 server.py），请先 cd 到 keyauth 目录再执行"

# ---------------------------------------------------------------- 1 Python
step "1/7  准备 Python"
if command -v python3 >/dev/null 2>&1; then
  V=$(python3 -V 2>&1 | awk '{print $2}')
  MINOR=${V%%.*}
  if [[ "$MINOR" -lt 3 ]]; then
    die "Python 版本过低（$V），请装 Python 3.8+"
  fi
  info "已有 Python $V"
else
  info "没装 Python，正在安装…"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv >/dev/null
  info "安装完成：$(python3 -V 2>&1)"
fi
PYBIN="$(command -v python3)"

# ---------------------------------------------------------------- 2 数据目录
step "2/7  整理文件属主与数据目录"

# 用 FinalShell 之类的 SFTP 拖上来的文件属主是登录用户（通常是 ubuntu），
# 而 systemd 单元以 root 运行。属主混杂会让 data/ 写入行为不可预期，
# 这里统一收敛成 root:root。
if [[ "$(stat -c '%U' "$APP_DIR" 2>/dev/null)" != "root" ]]; then
  info "当前属主是 $(stat -c '%U' "$APP_DIR" 2>/dev/null)，改成 root（服务以 root 运行）"
  chown -R root:root "$APP_DIR"
fi
info "属主：$(stat -c '%U:%G' "$APP_DIR")"

mkdir -p "$APP_DIR/data"
chmod 700 "$APP_DIR/data"
if [[ -f "$APP_DIR/data/config.json" ]]; then
  info "检测到已有配置，保留原管理令牌"
else
  info "首次运行，将自动生成管理令牌"
fi

# ---------------------------------------------------------------- 3 swap（可选）
step "3/7  检查内存 / swap"
MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
SWAP_MB=$(free -m | awk '/^Swap:/{print $2}')
info "内存 ${MEM_MB}MB / Swap ${SWAP_MB}MB"
if [[ "$SWAP_MB" -lt 512 ]]; then
  warn "没有 Swap，内存小的话加 1G 兜底"
  if [[ $EUID -eq 0 ]]; then
    fallocate -l 1G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
    chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    info "已加 1G Swap"
  fi
else
  info "Swap 已就绪，跳过"
fi

# ---------------------------------------------------------------- 4 systemd
step "4/7  安装开机自启服务"
cat > /etc/systemd/system/keyauth.service <<EOF
[Unit]
Description=KeyAuth 卡密授权系统
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=KEYAUTH_DATA=$APP_DIR/data
ExecStart=$PYBIN $APP_DIR/server.py --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
StandardOutput=append:$APP_DIR/data/server.log
StandardError=append:$APP_DIR/data/server.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable keyauth >/dev/null 2>&1
systemctl restart keyauth
info "服务已启动并设为开机自启"

READY=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 1
done
if [[ $READY -ne 1 ]]; then
  echo
  warn "服务 30 秒内没起来，最后 30 行日志："
  tail -n 30 "$APP_DIR/data/server.log" 2>/dev/null || true
  die "启动失败，通常是端口被占：ss -lntp | grep $PORT"
fi
info "健康检查通过（127.0.0.1:$PORT）"

# 可选的指定令牌：自动生成的是 32 字节随机串，够用；
# 但有人喜欢自己定一个好记的，这里就支持覆盖。
if [[ -n "$ADMIN_TOKEN" ]]; then
  info "写入你指定的管理令牌"
  if [[ ${#ADMIN_TOKEN} -lt 12 ]]; then
    warn "这个令牌只有 ${#ADMIN_TOKEN} 位，公网环境容易被穷举（后台会显示提醒）"
  fi
  "$PYBIN" - "$APP_DIR/data/config.json" "$ADMIN_TOKEN" <<'PYEOF'
import json, sys
p, tok = sys.argv[1], sys.argv[2]
with open(p, encoding='utf-8') as f:
    c = json.load(f)
c['admin_token'] = tok
with open(p, 'w', encoding='utf-8') as f:
    json.dump(c, f, ensure_ascii=False, indent=2)
PYEOF
  systemctl restart keyauth
  sleep 2
  if ! curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    die "写入自定义令牌后服务没起来，检查 $APP_DIR/data/config.json"
  fi
  info "已启用你指定的令牌"
fi

# ---------------------------------------------------------------- 5 Nginx
step "5/7  配置 Nginx（80 端口对外）"
export DEBIAN_FRONTEND=noninteractive
if ! command -v nginx >/dev/null 2>&1; then
  info "正在安装 Nginx…"
  apt-get update -qq
  apt-get install -y -qq nginx >/dev/null
fi
info "Nginx：$(nginx -v 2>&1)"

# 自动探测公网 IP（只用于填日志，不影响功能）
PUBIP=$(curl -s --max-time 3 http://metadata.tencentyun.com/latest/meta-data/public-ipv4 2>/dev/null \
        || curl -s --max-time 4 https://ifconfig.me 2>/dev/null || echo "")

if [[ -n "$DOMAIN" ]]; then
  SERVER_NAME="$DOMAIN"
else
  SERVER_NAME="_"
  info "没传域名，先用 IP + 80 端口访问"
fi

# 管理后台白名单：只有传了 ADMIN_IP 才写 deny all
if [[ -n "$ADMIN_IP" ]]; then
  ADMIN_BLOCK="        allow 127.0.0.1;
        allow ${ADMIN_IP};
        deny all;"
  info "后台已锁定 IP：${ADMIN_IP}（换 IP 后要改这里）"
else
  ADMIN_BLOCK="        # 没锁 IP anyone 都能打开登录页，靠管理令牌进。
        # 想锁：sudo ADMIN_IP=你的公网IP bash install.sh
        allow 127.0.0.1;"
  warn "后台未锁 IP（只靠令牌保护）。要锁：sudo ADMIN_IP=你的公网IP bash install.sh"
fi

cat > /etc/nginx/sites-available/keyauth <<EOF
# KeyAuth · 由 install.sh 自动生成，重新生成会覆盖本文件
# 公网 IP: ${PUBIP:-未知}

limit_req_zone \$binary_remote_addr zone=keyauth_api:10m rate=20r/s;

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${SERVER_NAME};

    client_max_body_size 2m;
    access_log /var/log/nginx/keyauth.access.log;
    error_log  /var/log/nginx/keyauth.error.log;

    # ---------- 管理后台 ----------
    location /admin {
${ADMIN_BLOCK}
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # ---------- 客户端接口 ----------
    location /api/ {
        limit_req zone=keyauth_api burst=40 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        expires 1h;
    }

    # ---------- 根路径下的静态资源 ----------
    # index.html 挂在 /admin，里面用的是相对路径（href="app.css"），
    # 浏览器会把它解析成 /app.css、/login.css、/favicon.svg、/app.js；
    # login.css 里的 url(bg-*.svg) 同理会解析成 /bg-*.svg。
    # 这些都不以 /static/ 开头，会掉进下面的兜底 404，页面就成了无样式的裸 HTML。
    # 所以这里按后缀显式放行，白名单写死，不给 /api/ 抢路由的机会。
    location ~* ^/(app|login)\.css$ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
    }
    location ~* ^/app\.js$ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
    }
    location ~* \.(svg|png|jpg|jpeg|gif|ico|webp|woff2?)$ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        expires 1h;
    }

    location = / { return 302 /admin; }
    # 其余一律 404。上面的白名单（/static/、css、js、图片后缀）已覆盖页面所需资源，
    # 剩下的 /xxx 落到这里；/api/ 前缀有更精确的 location，不会走到这。
    location / { return 404; }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/keyauth /etc/nginx/sites-enabled/keyauth

if nginx -t >/dev/null 2>&1; then
  systemctl enable nginx >/dev/null 2>&1
  systemctl reload nginx
  info "Nginx 已生效"
else
  nginx -t || true
  die "Nginx 配置有语法错误，已用 nginx -t 打印上面的详细信息"
fi

# ---------------------------------------------------------------- 6 防火墙
step "6/7  配置防火墙"
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp  >/dev/null 2>&1 || true
  ufw allow 80/tcp  >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
  if ufw status 2>/dev/null | grep -q "Status: active"; then
    info "ufw 已在运行，已放行 22 / 80 / 443"
  else
    info "ufw 已放行 22 / 80 / 443，但没有自动启用（怕挡住你机器上别的服务）"
    warn "想启用：sudo ufw enable   （如果你机器上还有别的服务，先 ufw allow 那些端口）"
  fi
else
  info "没装 ufw，跳过（腾讯云安全组也要放行 80/443）"
fi

# ---------------------------------------------------------------- 7 HTTPS
if [[ -n "$DOMAIN" ]]; then
  step "7/7  申请 HTTPS 证书"
  if command -v certbot >/dev/null 2>&1; then
    info "certbot 已安装"
  else
    info "正在安装 certbot…"
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
  fi
  echo
  info "开始申请证书，请确保域名已解析到 ${PUBIP:-本机公网IP}"
  certbot --nginx -d "$DOMAIN" || warn "证书申请失败，可之后重跑：sudo certbot --nginx -d $DOMAIN"
else
  step "7/7  HTTPS"
  info "本轮没做 HTTPS（需要域名）。以后有了域名："
  echo "    sudo certbot --nginx -d 你的域名"
  echo "    然后把客户端地址改成 https://你的域名"
fi

# ---------------------------------------------------------------- 令牌
TOKEN=""
for _ in $(seq 1 10); do
  [[ -f "$APP_DIR/data/config.json" ]] && \
    TOKEN=$($PYBIN -c "import json;print(json.load(open('$APP_DIR/data/config.json'))['admin_token'])" 2>/dev/null || true)
  [[ -n "$TOKEN" ]] && break
  sleep 1
done

# ---------------------------------------------------------------- 摘要
URL_HOST="${DOMAIN:-${PUBIP:-服务器IP}}"
echo
echo "${B}════════════════════════════════════════════════════${N}"
echo "${G}  装好了${N}"
echo "${B}════════════════════════════════════════════════════${N}"
echo
echo "  ${Y}管理后台${N}   http://${URL_HOST}/admin"
echo "  ${Y}管理令牌${N}   ${TOKEN:-请看 $APP_DIR/data/config.json}"
echo "  ${Y}验证接口${N}   http://${URL_HOST}/api/v1/verify"
echo "  ${Y}安装目录${N}   $APP_DIR"
echo
echo "  登录后台后：粘贴上面这串令牌 → 进入"
echo
echo "  ${B}常用命令${N}"
echo "    查看日志   journalctl -u keyauth -f"
echo "    或者       tail -f $APP_DIR/data/server.log"
echo "    重启服务   systemctl restart keyauth"
echo "    停止服务   systemctl stop keyauth"
echo "    看状态     systemctl status keyauth --no-pager"
echo "    备份数据   cp $APP_DIR/data/keyauth.db ~/keyauth-$(date +%F).db"
echo
echo "  ${B}以后更新代码${N}（重新拖文件覆盖后）"
echo "    cd $APP_DIR && sudo bash update.sh"
echo
echo "  ${Y}还差一步：腾讯云控制台放行 80 端口${N}，否则浏览器打不开"
echo "    轻量应用服务器 → 实例 → 防火墙    → 添加 TCP:80 和 TCP:443"
echo "    普通云服务器   → 安全组 → 入站规则 → 添加 TCP:80 和 TCP:443"
echo "    查自己是哪种：腾讯云控制台搜「轻量」看有没有这台实例"
echo "${B}════════════════════════════════════════════════════${N}"
echo
