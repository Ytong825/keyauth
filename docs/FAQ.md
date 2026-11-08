# 常见问题

按问题类型分组。找不到答案就开 [issue](https://github.com/Ytong825/keyauth/issues/new/choose)。

- [选型与定位](#选型与定位)
- [部署](#部署)
- [使用](#使用)
- [客户端接入](#客户端接入)
- [数据与备份](#数据与备份)
- [性能](#性能)
- [安全](#安全)

---

## 选型与定位

**这和 KeyAuth 官方 / 各种发卡网有什么区别？**

| | 本项目 | KeyAuth 官方 | 常见发卡网 |
|---|---|---|---|
| 语言 | Python 标准库 | PHP / C++ SDK | PHP |
| 数据库 | SQLite | MySQL | MySQL |
| 依赖 | 0 | 一堆 | 一堆 |
| 数据归属 | 自己的服务器 | 他们的服务器 | 自己的 |
| 部署 | 拷过去跑脚本 | 装 PHP 环境 | 装宝塔 + 导入 SQL |

核心差异是「零依赖 + 单机 SQLite」，适合「自己卖软件、量不大、不想维护服务器环境」的场景。

**适合什么规模？**

单实例建议 **日活 5000 以内、卡密 10 万以内**。再往上要么换 PostgreSQL，
要么把日志表按时间分表。

**能商用吗？**

MIT 许可证，可以。改了代码也不用开源。出问题自己承担（见 LICENSE 免责条款）。

## 部署

**必须用 Docker 吗？**

不用，而且不推荐。宿主机直装 + systemd，运维链路更短，Nginx 限流也不会被绕过。

**必须用 Nginx 吗？**

强烈建议。`server.py` 默认只监听 `127.0.0.1`，直接对公网意味着：

- 没有传输层限流兜底
- 没有 HTTPS（Python 标准库不带 TLS 终端）
- 静态文件由 Python 线程处理，浪费

**能不能不用域名、直接用 IP + HTTPS？**

技术上不行——Let's Encrypt 不给纯 IP 签发证书。三个选择：

1. 买个域名（十来块一年），`deploy/enable_https.sh` 一条命令搞定
2. 用 Cloudflare 代理 + 他们的 Universal SSL（回源仍是 http，需要额外配置）
3. 自签证书——浏览器会红警告，不适合给客户用

**装完访问不了**

```bash
systemctl status keyauth          # 服务活着吗
curl http://127.0.0.1:8787/api/health   # 本地通吗
sudo nginx -t && systemctl status nginx # Nginx 通吗
sudo ufw status                   # 防火墙放行了吗
```

本地通但公网不通 → 云厂商安全组没放行 80。

**后台样式全丢 / 一片空白**

Nginx 缺少根路径静态资源转发。`index.html` 现在用绝对路径引 `/app.css`、`/app.js`、
`/login.css`，这些不在 `/static/` 下。对照 [docs/DEPLOY.md](DEPLOY.md#手动安装) 第 3 步补齐。

## 使用

**怎么发第一张卡？**

1. 后台「应用」→ 新建应用，拿到 AppID + AppSecret
2. 后台「制卡」→ 选应用、类型、时长、数量 → 生成
3. 卡密出现在「卡密库」，状态「未使用」
4. 客户端用 `verify` 首次校验时自动激活并开始计时

**天数卡和小时卡的区别？**

都是「从激活时刻开始计时」，区别只是单位：

- 天数卡 `duration_days=30` → 30 天后过期
- 小时卡 `duration_days=8` → 8 小时后过期

`duration_days=0` 是永久卡，不过期。

**卡密的「未激活」和「永久」怎么区分？**

后台列表的「到期 / 额度」列会显示：

- `未激活 · 30天` — 还没人用，激活后从那一刻起算 30 天
- `未激活 · 8小时` — 同上，小时卡
- `永久` — `duration_days=0`，激活后也不过期
- `2026-12-08 05:00:00` — 已激活，具体到期时间

**封禁后客户端多久失效？**

下一次心跳就失效（默认 3 分钟内）。如果客户端做得很差、只在启动时校验一次，
那要等它重启。这是客户端的问题，不是服务端的。

**能限制一台机器吗？**

能。卡密的 `max_devices=1` 就是单设备。超出后新机器 `verify` 会尝试自动解绑最早那台，
前提是 `unbind_left > 0`；用完就返回 `DEVICE_LIMIT`。

**换绑次数用完了怎么办？**

后台「卡密库」搜到这张卡 → 右端「⋯」→「重置换绑次数」。也可以在详情弹窗里先看它绑了几台。

**能批量导卡密进 Excel 吗？**

「卡密库」分页条右侧有「导出 CSV」，带 BOM，Excel 直接打开不乱码。

## 客户端接入

**签名一直报 `BAD_SIGN`**

按这个顺序查：

1. 拼接时排除了 `sign` 吗？（必须排除）
2. 按参数名 ASCII 升序吗？（用 `StringComparer.Ordinal`，别用本地化比较）
3. 空值参数保留成 `k=` 了吗？
4. AppSecret 有没有前后空格？
5. 结果是小写十六进制吗？（不是 Base64）

**一直 `BAD_TS`**

客户端系统时间不对，或字段名写成了 `timestamp`（服务端读 `ts`）。

**一直 `REPLAY`**

`nonce` 用了固定值。每次请求都要新随机串。

**机器码用什么？**

CPU / 主板 / 磁盘序列号拼接后哈希。**别用 MAC 地址**（现代系统随机化）、
别用计算机名（用户会改）。详见 [docs/CLIENT.md](CLIENT.md#机器码怎么定)。

**怎么防止客户端被破解？**

本项目只保证服务端判定可靠。客户端防护（加壳、反调试、关键逻辑下沉）是另一半工程，
不在范围内。但至少要：**启动校验 + 周期心跳 + 关键功能前复查**，
只做启动校验等于没有校验。

## 数据与备份

**数据存在哪？**

`data/keyauth.db`（SQLite）+ `data/config.json`（含管理令牌）。整个 `data/` 目录就是全部状态。

**怎么备份？**

```bash
# 安全做法（走 SQLite 在线备份 API）
sudo python3 -c "import sqlite3;sqlite3.connect('/opt/keyauth/data/keyauth.db').backup(sqlite3.connect('/root/ka-backup.db'))"

# 偷懒做法（低峰期可用）
sudo cp /opt/keyauth/data/keyauth.db ~/ka-backup.db
```

后台「系统设置 → 立即备份数据库」走的是第一种。

**恢复了但数据没变？**

残留的 `keyauth.db-wal` 把旧数据重放了。恢复时必须一起删：

```bash
sudo rm -f data/keyauth.db-wal data/keyauth.db-shm
```

**日志表越来越大怎么办？**

没有自动清理。加个 cron：

```cron
# 保留 30 天
0 4 * * * sqlite3 /opt/keyauth/data/keyauth.db "DELETE FROM logs WHERE ts < strftime('%s','now','-30 days')"
```

删完记得 `VACUUM`（否则文件不会变小），频率低一点，比如每月一次。

**能换 MySQL 吗？**

`kauth/db.py` 是唯一 SQL 入口，替换这一层（约 200 行）即可。注意：SQLite 的
`INSERT OR REPLACE`、`PRAGMA` 这些要改写成 MySQL 方言。

## 性能

**200 并发心跳会挂吗？**

不会。实测 200 req/s 心跳 p99 < 40ms。瓶颈是 SQLite 写锁，不是 Python 线程。

**为什么后台日志页一页只加载 50 条？**

现在支持 50 / 100 / 200 三档，也可以填页码跳转。默认 50 是为了首屏快。

**数据库多大要担心？**

10 万条日志约 30MB，SQLite 处理这个量级毫无压力。到 GB 级才需要考虑分表。

## 安全

**管理令牌怎么改？**

后台「系统设置」→「重置管理令牌」。新令牌会直接复制到剪贴板，当前会话立即失效。

**管理后台能限制 IP 吗？**

可以，在 Nginx 层加：

```nginx
location /admin {
    allow 1.2.3.4;
    deny all;
    proxy_pass http://127.0.0.1:8787;
}
```

`install.sh` 支持安装时指定：`sudo ADMIN_IP=1.2.3.4 bash install.sh`。

**AppSecret 泄露了怎么办？**

后台「应用」页点「重置密钥」。旧密钥立即失效，所有客户端要更新配置。
建议给用户留一个过渡期——比如先发新版本客户端，再重置密钥。

**会不会被拖库？**

数据库文件在 `data/`，不在 web 根目录下，不能通过 URL 访问。能拖库的前提是拿到服务器
shell 或者管理令牌。所以：令牌用强的、SSH 用密钥登录、Nginx 别开目录列表。

**有审计日志吗？**

有。后台「操作审计」记录所有管理动作（制卡、改配置、封禁、删应用、重置令牌…），
含操作者、IP、对象、说明。支持按动作筛选和关键字搜索。
