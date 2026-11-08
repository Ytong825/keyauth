# 架构说明

- [设计取舍](#设计取舍)
- [模块划分](#模块划分)
- [请求链](#请求链)
- [数据模型](#数据模型)
- [卡密状态机](#卡密状态机)
- [并发与性能](#并发与性能)
- [扩展点](#扩展点)

---

## 设计取舍

**只用标准库。** 目标是「拷过去就能跑」：客户给的 1 核机器、没有外网、装 pip 包会编译失败。
代价是路由、模板、ORM 都要手写。逐项摊开：

| 需求 | 选择 | 放弃的方案 | 原因 |
|---|---|---|---|
| HTTP 服务 | `http.server.ThreadingHTTPServer` | FastAPI / Flask | 零依赖；这类接口 QPS 不高，线程池够用 |
| 存储 | SQLite（WAL） | MySQL / PostgreSQL | 单机部署，免装免配；写入串行但量级可接受 |
| 前端 | 手写 HTML/CSS/JS | Vue / React + 构建链 | 没有构建步骤，改完刷新即生效；后台不需要复杂状态管理 |
| 配置 | `data/config.json` | 环境变量 + yaml | 后台要能可视化改，改完持久化 |
| 认证 | 单管理令牌 | 账号体系 + JWT | 单人使用场景；多账号已在路线图 |

## 模块划分

```
server.py              启动参数解析 + 建库 + 起服务
kauth/
├─ config.py           配置读写（data/config.json），首次启动生成随机令牌
├─ db.py               连接池（threading.local）+ 表结构 + 初始化
├─ security.py         签名、nonce、限流
├─ service.py          授权核验核心：鉴权链 + 状态机 + 返回结构
├─ admin.py            管理端业务：制卡 / 卡密 / 应用 / 套餐 / 日志 / 审计 / 设置
├─ webhook.py          事件回调（异步，失败不阻塞主流程）
├─ httpd.py            路由、静态文件、请求体解析与护栏
└─ util.py             时间格式化、卡密生成、前缀清洗
```

依赖方向是单向的：

```
httpd ──▶ service ──▶ db
  │          │
  ├──▶ admin ┘
  │      │
  │      └──▶ webhook
  └──▶ config
```

`service` 不感知 HTTP，`admin` 不感知 HTTP 状态码。这样加 CLI 或定时任务可以直接复用业务层。

## 请求链

一次客户端校验要过 8 道关，任何一道失败都直接返回，并写日志：

```
POST /api/v1/verify
  │
  ├─ 1. 路由匹配                    httpd.do_POST
  ├─ 2. 传输层限流（Nginx 20r/s）   ── 前面在 Nginx
  ├─ 3. 请求体上限 64KB / JSON 解析  httpd.body
  ├─ 4. 参数完整性（app_id/code/machine_id）
  │      └─ code 为空 → BAD_PARAM
  ├─ 5. 应用解析 + 状态             resolve_app
  │      ├─ 不存在   → BAD_APP
  │      └─ disabled → APP_DISABLED
  ├─ 6. 业务限流（单 IP 每分钟）     security.rate_ok
  │      └─ 超限 → RATE_LIMIT
  ├─ 7. 签名三件套
  │      ├─ 缺 sign          → BAD_SIGN
  │      ├─ ts 超差          → BAD_TS
  │      ├─ nonce 重复       → REPLAY
  │      └─ HMAC 不匹配      → BAD_SIGN
  └─ 8. 状态机                     service.core
         ├─ 卡密不存在 / 不属于该应用 → CARD_NOT_FOUND
         ├─ 已封禁                   → CARD_BANNED
         ├─ 首次激活（写 expires_at + binds）
         ├─ 已过期                   → CARD_EXPIRED
         ├─ 额度用尽                 → CARD_USED_UP
         ├─ 设备数超限               → DEVICE_LIMIT
         └─ 通过 → OK
```

**先验签、再查库**：签名不过的请求根本没碰 `cards` 表。这条顺序是刻意的——
被刷时不会因为大量无效请求把数据库打满。

每一步失败都调用 `service.fail()`，它做两件事：写 `logs`、返回结构化错误。
所以后台「校验日志」能看到全部失败原因，而不只是成功记录。

## 数据模型

7 张表，全部在 `kauth/db.py` 的 `SCHEMA` 里，`CREATE TABLE IF NOT EXISTS` 幂等建表。

```
apps ────┬── plans ──── cards ──── binds
         │               │
         ├── webhooks    └── logs
         └── notices         audits（独立，记录后台动作）
```

**apps** — 一个软件一套密钥

| 字段 | 说明 |
|---|---|
| `app_id` / `app_secret` | 客户端凭据，`app_secret` 用于 HMAC |
| `status` | `active` / `disabled`，禁用后该应用所有请求拒绝 |
| `require_sign` | 应用级强制签名（与全局开关取或） |
| `heartbeat_interval` | 下发给客户端的心跳间隔建议 |

**plans** — 制卡预设，字段与 `cards` 同构，制卡时整组拷过去。

**cards** — 核心表

| 字段 | 说明 |
|---|---|
| `code` | 主键，卡密本身 |
| `card_type` | `time` / `hour`（历史数据可能有 `count` / `point`） |
| `duration_days` | **复用字段**：天数卡存天数，小时卡存小时数，0 = 永久 |
| `expires_at` | 激活时算出；`NULL` 有两义——永久卡 / 尚未激活 |
| `unbind_limit` / `unbind_used` | 换绑次数上限与已用 |

> `duration_days` 这个字段名在小时卡上是误导性的。历史原因：最初只有天数卡，
> 加小时卡时复用了字段而没做迁移。语义由 `card_type` 决定。改字段名要迁移全部数据，收益不大。

> `expires_at = NULL` 的歧义在显示层统一处理：`service._build_data` 和 `admin.cards`
> 都判断「`card_type` 是时间类且 `duration_days > 0`」→ 显示「未激活」，否则「永久」。
> 这个坑踩过一次：未激活的普通时间卡曾被显示成「永久」。

**binds** — 设备绑定，主键 `(code, machine_id)`

**logs** — 校验日志，索引在 `ts` / `code` / `result` 上。**这是增长最快的表**，
10 万条约 30MB。没有自动清理，需要的话自己加 cron 删老数据。

**audits** — 后台操作留痕，字段含操作者、IP、动作、对象、说明。

## 卡密状态机

```
                  verify（首次）
      ┌────────┐ ──────────────▶ ┌────────┐
      │ unused │                 │ active │
      └────────┘ ◀────────────── └────────┘
          ▲        reset（管理端）      │
          │                            ├── 到期 ────▶ ┌─────────┐
          └────────────────────────────┤              │ expired │
                                       │              └─────────┘
                                       ├── 额度耗尽 ─▶ ┌─────────┐
                                       │              │ used_up │
                                       │              └─────────┘
                                       └── 封禁 ─────▶ ┌────────┐
                                                      │ banned │
                                                      └────────┘
```

**几个容易搞错的点**

1. **激活只发生在 `verify`**。`heartbeat` 和 `query` 传 `bind=False`，不激活、不绑机、不扣额度。
   所以用户可以先 `query` 看状态，再决定要不要 `verify`。
2. **到期是惰性的**。没有定时任务扫描，靠下一次校验时 `t > expires_at` 判定并顺手把
   `status` 改成 `expired`。好处是不用维护调度器，坏处是「已过期」的徽章要等下次访问才更新。
3. **换机自动解绑一台**。设备数已满且 `unbind_left > 0` 时，解绑最早绑定的一台再绑新的。
   这和「用户手动 `unbind` 再 `verify`」效果相同，但少一次往返。
4. **永久卡没有 `expires_at`**。`duration_days = 0` 且时间类卡，激活时 `expires_at` 保持 `NULL`。

## 并发与性能

`ThreadingHTTPServer` 每请求一线程，SQLite 连接用 `threading.local()` 每线程一个。
WAL 模式下**读不阻塞写、写串行**。

实测（1 核 1G 云服务器，SSD）：

| 场景 | 结果 |
|---|---|
| 200 req/s 心跳（8 个客户端） | p99 < 40ms，无排队 |
| 单页 300 行日志查询 | ~15ms（走 `ts` 索引） |
| 制卡 1000 张 | ~180ms（批量 INSERT 在一个事务里） |
| 数据库 6MB / 3.5 万条日志 | 进程常驻 47MB |

瓶颈在写：所有写入串到一把 SQLite 写锁。要再上一个量级，两个方向：

- 换 PostgreSQL（只改 `db.py`）
- 日志表分表 / 只保留最近 N 天（业务上通常够）

## 扩展点

| 想做什么 | 改哪里 |
|---|---|
| 换数据库 | `kauth/db.py`（唯一 SQL 入口，约 200 行） |
| 加接口 | `httpd.py` 加路由 → `service.py` / `admin.py` 加业务 → 更新 `docs/API.md` |
| 加卡密类型 | `service.CARD_TYPES` + 状态机里的时间/额度分支 + 前端两个下拉 |
| 加校验维度（如 IP 白名单） | `service.check_request` 里插一段，返回 `fail(...)` 即可自动进日志 |
| 换前端 | `static/` 整个替掉，接口不变 |
| 加定时任务（清理老日志、到期提醒） | 独立脚本读同一个 `data/keyauth.db`，用 cron 跑 |

**加错误码时注意**：新码要同时加进 `service.RESULT_TEXT`，否则前端会显示原始英文码
（`resultBadge` 拿不到中文就退回 `r` 本身）。
