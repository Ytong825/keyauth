#!/usr/bin/env bash
#
# KeyAuth 更新（拖了新代码覆盖后跑这个）
#
#     cd <你安装的目录> && sudo bash update.sh
#
# 做：语法自检 → 备份数据库 → 重启 → 健康检查

set -euo pipefail

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[36m'; N=$'\033[0m'
info() { echo "${G}==>${N} $*"; }
warn() { echo "${Y}[!]${N} $*"; }
die()  { echo "${R}[x]${N} $*" >&2; exit 1; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
[[ $EUID -eq 0 ]] || die "请用 sudo 运行：sudo bash update.sh"

# ---------------------------------------------------------------- 1 语法自检
info "1/4 语法自检"
PYBIN="$(command -v python3)"
"$PYBIN" -m compileall -q server.py kauth >/dev/null \
  || die "代码有语法错误，先修好再更新（上面是详细信息）"
info "语法 OK"

# ---------------------------------------------------------------- 2 备份
info "2/4 备份数据库"
mkdir -p "$APP_DIR/data/backup"
BK="$APP_DIR/data/backup/keyauth-$(date +%F-%H%M%S).db"
if [[ -f "$APP_DIR/data/keyauth.db" ]]; then
  cp "$APP_DIR/data/keyauth.db" "$BK" && info "已备份到 $BK"
else
  warn "还没有数据库文件，跳过备份"
fi

# ---------------------------------------------------------------- 3 重启
info "3/4 重启服务"
systemctl restart keyauth
sleep 2

# ---------------------------------------------------------------- 4 健康检查
info "4/4 健康检查"
OK=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 "http://127.0.0.1:8787/api/health" >/dev/null 2>&1; then
    OK=1; break
  fi
  sleep 1
done

if [[ $OK -ne 1 ]]; then
  echo
  warn "新版本起不来。最后 40 行日志："
  journalctl -u keyauth -n 40 --no-pager || tail -n 40 "$APP_DIR/data/server.log" 2>/dev/null || true
  echo
  warn "数据库已备份在：$BK"
  die "更新失败。把上面的报错发我，我帮你改。"
fi

echo
echo "${G}更新完成，服务正常运行${N}"
echo "  备份：$BK"
echo "  日志：journalctl -u keyauth -f"
echo
