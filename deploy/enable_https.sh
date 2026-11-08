#!/bin/bash
# 给 KeyAuth 上 HTTPS（Let's Encrypt + nginx）。
#
# 用法：
#   sudo bash enable_https.sh auth.example.com
#
# 前提：域名的 A 记录已经指向本机公网 IP，且 80 端口能从公网访问
#      （certbot 要走 http-01 校验）。
set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "用法: sudo bash $0 你的域名（例如 auth.example.com）"
  echo "当前没有可用证书：Let's Encrypt 不给纯 IP 签发，必须先有解析到本机的域名。"
  exit 1
fi
if [ "$(id -u)" != "0" ]; then
  echo "请用 root 运行：sudo bash $0 $DOMAIN"
  exit 1
fi

CONF=/etc/nginx/sites-available/keyauth
BAK="$CONF.bak_$(date +%Y%m%d-%H%M%S)"

echo "=== [1/5] 检查域名解析 ==="
IP=$(getent hosts "$DOMAIN" | awk '{print $1; exit}' || true)
MYIP=$(curl -s -m 8 https://api.ipify.org || true)
echo "  $DOMAIN -> ${IP:-未解析}"
echo "  本机公网 -> ${MYIP:-未知}"
if [ -n "$IP" ] && [ -n "$MYIP" ] && [ "$IP" != "$MYIP" ]; then
  echo "  !! 解析到的 IP 和本机公网 IP 不一致，certbot 校验大概率失败"
fi

echo "=== [2/5] 安装 certbot ==="
if ! command -v certbot >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx
fi
certbot --version

echo "=== [3/5] 备份并把 server_name 换成域名 ==="
cp -a "$CONF" "$BAK"
echo "  备份: $BAK"
sed -i "s/^\s*server_name .*;/    server_name $DOMAIN;/" "$CONF"
grep -n "server_name" "$CONF"

echo "=== [4/5] 申请证书并改写 443 配置 ==="
nginx -t
systemctl reload nginx
certbot --nginx -d "$DOMAIN" --agree-tos --redirect -n \
  --register-unsafely-without-email || {
    echo "!! 证书申请失败。常见原因：DNS 未生效 / 80 端口被安全组挡住。"
    echo "   回滚 nginx 配置：cp -a $BAK $CONF && nginx -t && systemctl reload nginx"
    exit 1
  }

echo "=== [5/5] 自动续期 ==="
systemctl list-timers certbot.timer --no-pager 2>/dev/null | head -3 || true
certbot renew --dry-run 2>&1 | tail -3 || true

echo
echo "完成。访问 https://$DOMAIN/admin 验证。"
echo "回滚：cp -a $BAK $CONF && nginx -t && systemctl reload nginx"
echo
echo "建议顺手在后台「系统设置 → 对外访问地址」填 https://$DOMAIN，"
echo "这样「接入文档」里给客户端的地址也会是 https。"
