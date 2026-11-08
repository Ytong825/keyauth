# 接口文档

所有接口都在同一个域名下。请求与响应都是 `application/json; charset=utf-8`。

- [约定](#约定)
- [客户端接口](#客户端接口)
  - [签名算法](#签名算法)
  - [POST /api/v1/verify](#post-apiv1verify)
  - [POST /api/v1/heartbeat](#post-apiv1heartbeat)
  - [POST /api/v1/query](#post-apiv1query)
  - [POST /api/v1/unbind](#post-apiv1unbind)
  - [POST /api/v1/notices](#post-apiv1notices)
  - [GET /api/v1/health](#get-apiv1health)
- [管理端接口](#管理端接口)
- [错误码](#错误码)

---

## 约定

**客户端接口**（`/api/v1/*`）用 AppSecret 做 HMAC 签名，不需要登录态。

**管理端接口**（`/api/admin/*`）走请求头：

```
X-Admin-Token: 你的管理令牌
```

令牌在首次启动时生成，存在 `data/config.json` 的 `admin_token` 字段，后台「系统设置」可重置。

**统一响应结构**

```jsonc
// 成功
{ "ok": true, "data": { ... } }

// 失败
{ "ok": false, "err": "CARD_EXPIRED", "msg": "卡密已过期" }
```

管理端接口大多直接平铺字段（`{"ok": true, "items": [...]}`），见各接口说明。

**限流**

- 业务层：单 IP 每分钟 120 次（后台可配）
- 传输层：Nginx 对 `/api/` 限 20 r/s，burst 40
- 超限返回 `429` + `{"ok":false,"err":"RATE_LIMIT"}`

**请求体上限** 64KB，超了返回 `413`。

---

## 客户端接口

### 签名算法

除 `sign` 外**所有参数都参与签名**，规则：

1. 取所有参数（含空值），按参数名 **ASCII 升序**排列
2. 拼成 `k1=v1&k2=v2&...`，值不做 URL 编码
3. 用 AppSecret 做 `HMAC-SHA256`，输出**小写十六进制**

```python
import hashlib, hmac, time, uuid

def sign(params: dict, secret: str) -> str:
    s = "&".join("%s=%s" % (k, params[k]) for k in sorted(params) if k != "sign")
    return hmac.new(secret.encode(), s.encode(), hashlib.sha256).hexdigest()

params = {
    "app_id": "app_7c1f9a3e5d2b8640",
    "code": "WC48-QELC-UBTB-VSMP",
    "machine_id": "MACH-1709A71",
    "ts": int(time.time()),
    "nonce": uuid.uuid4().hex,
}
params["sign"] = sign(params, "你的AppSecret")
```

> 只有 `ts` 和 `nonce` 两个字段名要注意：时间戳叫 **`ts`**（不是 `timestamp`），随机串叫 **`nonce`**。
> 两者缺一不可——`ts` 用来挡过期请求，`nonce` 用来挡重放。

**强制签名**：应用级 `require_sign` 或全局 `require_sign` 任一为真就校验。默认开启。

**时间戳容差**：默认 ±300 秒（后台可配 `clock_skew`）。客户端机器时间偏差超过这个值会返回 `BAD_TS`。

**nonce 有效期**：默认 600 秒（后台可配 `nonce_ttl`），窗口内重复提交返回 `REPLAY`。

### POST /api/v1/verify

首次激活 / 换机校验。**未激活的卡密在这一步开始计时并绑定当前设备。**

**请求**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `app_id` | string | 是 | 应用 ID；留空则回退到默认应用（仅单应用场景） |
| `code` | string | 是 | 卡密，服务端自动转大写去空格 |
| `machine_id` | string | 是 | 机器码，客户端自己生成并持久化 |
| `ts` | int | 开启签名时必填 | Unix 秒 |
| `nonce` | string | 开启签名时必填 | 随机串，建议 UUID |
| `sign` | string | 开启签名时必填 | 见[签名算法](#签名算法) |

```json
{
  "app_id": "app_7c1f9a3e5d2b8640",
  "code": "WC48-QELC-UBTB-VSMP",
  "machine_id": "MACH-1709A71",
  "ts": 1794090000,
  "nonce": "6f1c2a9d4b8e4f0a9c3d2b1e0f7a8b9c",
  "sign": "9a3f...（64 位十六进制）"
}
```

**响应**

```json
{
  "ok": true,
  "data": {
    "code": "WC48-QELC-UBTB-VSMP",
    "app_id": "app_7c1f9a3e5d2b8640",
    "plan": "月卡 · 单设备",
    "card_type": "time",
    "card_type_text": "天数卡",
    "status": "active",
    "activated_at": 1794090000,
    "expires_at": 1796682000,
    "expires_text": "2026-12-08 05:00:00",
    "remaining_seconds": 2592000,
    "total_value": 0,
    "used_value": 0,
    "remaining_value": 0,
    "devices": 1,
    "max_devices": 1,
    "unbind_left": 1,
    "heartbeat_interval": 180,
    "announcement": "",
    "server_time": 1794090000
  }
}
```

**字段说明**

| 字段 | 说明 |
|---|---|
| `expires_text` | 直接可展示的到期文案。三种取值：具体时间 / `"未激活"` / `"永久"` |
| `remaining_seconds` | 剩余秒数；永久卡为 `null` |
| `devices` / `max_devices` | 已绑定设备数 / 上限 |
| `unbind_left` | 剩余换绑次数 |
| `heartbeat_interval` | 建议心跳间隔（秒），按应用配置 |
| `announcement` | 全局公告，可能为空串 |
| `server_time` | 服务器当前时间，客户端可用它校正本地时钟 |

**首次激活的行为**

- `unused` 状态 → 置 `active`，写入 `activated_at`，按类型算 `expires_at`
- 天数卡：`expires_at = 激活时刻 + duration_days × 86400`
- 小时卡：`expires_at = 激活时刻 + duration_days × 3600`
- `duration_days = 0` 表示永久，`expires_at` 为 `null`
- 绑定当前 `machine_id`，触发 `card.activated` WebHook

**换机**

已激活的卡在**新机器**上调用 `verify`：

- 设备数未满 → 直接绑定新设备，`devices` +1
- 设备数已满 且 `unbind_left > 0` → 自动解绑最早的一台，绑定新设备，`unbind_left` −1
- 设备数已满 且 `unbind_left = 0` → `DEVICE_LIMIT`

### POST /api/v1/heartbeat

运行期心跳。**不激活、不绑机、不扣额度**，只做状态判定。

请求字段同 `verify`。建议每 `heartbeat_interval` 秒调一次（默认 180 秒）。

响应结构同 `verify`。失败时按错误码决定是否让客户端退出：

| 错误码 | 客户端建议 |
|---|---|
| `CARD_EXPIRED` | 提示续费，停止功能 |
| `CARD_BANNED` | 直接退出 |
| `DEVICE_MISMATCH` | 提示换绑 |
| `RATE_LIMIT` / `BAD_TS` | 重试，别立刻退出（可能是网络或时钟问题） |

### POST /api/v1/query

查询状态，**不激活、不绑定**。用于「我的授权」这类只读页面。

请求字段同 `verify`。响应同 `verify`。

### POST /api/v1/unbind

自助解绑当前设备。消耗一次换绑次数。

**请求**

| 字段 | 必填 | 说明 |
|---|---|---|
| `app_id` | 是 | 应用 ID |
| `code` | 是 | 卡密 |
| `machine_id` | 是 | 要解绑的机器码（必须是已绑定的那台） |
| `ts` / `nonce` / `sign` | 开启签名时必填 | 同上 |

**响应**

```json
{ "ok": true, "data": { "unbind_left": 0, "devices": 0 } }
```

**失败**

- `NOT_ACTIVATED` — 卡密尚未激活，没有可解绑的设备
- `DEVICE_MISMATCH` — 这台机器没有绑定到该卡密
- `UNBIND_LIMIT` — 换绑次数已用尽

### POST /api/v1/notices

拉取公告列表（包含全局公告与定向到该应用的公告）。

```json
{
  "ok": true,
  "data": {
    "announcement": "全局公告文本",
    "notices": [
      { "id": 2, "title": "v2.3 已发布", "content": "...", "level": "success" }
    ],
    "server_time": 1794090000
  }
}
```

### GET /api/health

健康检查，免鉴权、免签名。`install.sh` / `update.sh` 用它确认服务起没起来，也可以接监控。

```json
{ "ok": true, "name": "keyauth", "server_time": 1794090000, "version": "1.1.0" }
```

---

## 管理端接口

所有 `/api/admin/*` 都需要 `X-Admin-Token` 头。缺失或错误返回 `401`。

### GET 类

| 接口 | 参数 | 说明 |
|---|---|---|
| `/api/admin/overview` | — | 概览：统计、7 日趋势、结果码分布、最近 15 条记录 |
| `/api/admin/cards` | `page` `size` `q` `status` `app` `plan` `card_type` `batch` | 卡密列表，返回 `total` |
| `/api/admin/cards/export` | `app` `status` `batch` | CSV 下载（`text/csv`，带 BOM，Excel 直接打开） |
| `/api/admin/apps` | — | 应用列表（含 AppSecret） |
| `/api/admin/plans` | — | 套餐列表 |
| `/api/admin/logs` | `page` `size` `q` `result` `action` `app` `from` `to` | 校验日志，`from`/`to` 为 `YYYY-MM-DD` |
| `/api/admin/audits` | `page` `size` `q` `action` `from` `to` | 操作审计 |
| `/api/admin/webhooks` | — | WebHook 列表 |
| `/api/admin/notices` | — | 公告列表 |
| `/api/admin/settings` | — | 系统设置 |

**分页参数**

- `page` 从 1 开始，默认 1
- `size` 默认 50，上限 500
- 兼容旧调用 `?limit=N`（等价于 `size=N&page=1`）

**时间筛选**

`from` / `to` 接受 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM`。只有日期时按整天算：`from` 取当天 0 点，`to` 取次日 0 点（左闭右开）。解析不了就忽略该条件。

### POST 类

统一以 `action` 字段区分操作。

**`POST /api/admin/cards`** —— 制卡

```json
{
  "app_id": "app_7c1f9a3e5d2b8640",
  "card_type": "time",
  "duration_days": 30,
  "max_devices": 1,
  "unbind_limit": 1,
  "count": 10,
  "prefix": "VIP",
  "note": "渠道A",
  "plan_id": null
}
```

| 字段 | 说明 |
|---|---|
| `card_type` | `time`（天数卡）/ `hour`（小时卡） |
| `duration_days` | 天数卡填天数，小时卡填小时数，`0` = 永久 |
| `count` | 1 ~ 10000 |
| `prefix` | 可选，自动补 `-`，最长 8 位，只允许字母数字 |
| `plan_id` | 传了套餐 ID 则以套餐参数为准 |

响应 `{"ok":true,"batch":"202611-月卡","codes":["..."],"count":10}`。

**`POST /api/admin/cards/action`** —— 卡密批量操作

```json
{ "codes": ["WC48-QELC-UBTB-VSMP"], "action": "ban", "amount": 30 }
```

| `action` | 说明 | `amount` |
|---|---|---|
| `ban` | 封禁 | — |
| `unban` | 解封 | — |
| `unbind` | 解绑全部设备 | — |
| `unbind_reset` | 重置换绑次数 | — |
| `renew` | 续期 / 加额度 | 天数或小时数，可负数 |
| `reset` | 重置为未使用 | — |
| `delete` | 删除（不可恢复） | — |
| `ban_devices` | 解绑并封禁 | — |

响应 `{"ok":true,"affected":1}`。

**`POST /api/admin/apps`**

| `action` | 字段 | 说明 |
|---|---|---|
| `create` | `name` `note` | 生成新 AppID + AppSecret |
| `update` | `id` `name` `status` `heartbeat_interval` `require_sign` `note` | 改应用 |
| `reset_secret` | `id` | 重置 AppSecret（旧密钥立即失效） |
| `delete` | `id` | 删除应用；应用下还有卡密时返回 `HAS_CARDS`，需再传 `force: true` |

**`POST /api/admin/plans`**

`create`（带 `id` 则为更新）/ `delete`。字段：`name` `app_id` `card_type` `duration_days` `total_value` `max_devices` `unbind_limit` `price` `note`。

**`POST /api/admin/webhooks`**

`create` / `toggle` / `delete`。字段：`app_id` `url` `events` `secret`。
`events` 逗号分隔：`card.activated` `device.bound` `card.unbound`。

> **回调请求**：`POST` 到你的 URL，JSON body 含 `event` / `app_id` / `code` / `machine_id` / `ts`，
> 请求头 `X-KeyAuth-Signature: hex(hmac_sha256(secret, body))`。收到的第一时间验签。

**`POST /api/admin/notices`**

`create` / `delete`。字段：`app_id`（空 = 全局）`title` `content` `level`（`info` / `success` / `warn` / `danger`）。

**`POST /api/admin/settings`**

可改字段：`site_name` `site_desc` `announcement` `min_client_version` `public_base_url`
`clock_skew` `nonce_ttl` `rate_limit` `require_sign` `maintenance`。

数值范围会被夹紧：`clock_skew` 30~3600，`nonce_ttl` 60~86400，`rate_limit` 0~100000。

**`POST /api/admin/token/rotate`** —— 重置管理令牌，返回新令牌。当前会话立即失效。

**`POST /api/admin/backup`** —— 热备份数据库，返回 `{"ok":true,"path":"keyauth-20261108-050000.db"}`。

**`POST /api/admin/login`** —— 校验令牌是否有效，返回 `server_time`。

---

## 代理商接口

代理商是独立的一套账号，令牌走 **`X-Agent-Token`**，与 `X-Admin-Token` 互不相通。
令牌打 `/api/admin/*` 一律 401，管理令牌也打不进 `/api/agent/*`。

**`POST /api/agent/login`** —— 唯一免令牌的代理商接口

```json
{ "username": "agent01", "password": "pass123456" }
```

响应：

```json
{ "ok": true, "token": "…", "expires_at": 1794690000,
  "agent": { "id": 1, "username": "agent01", "name": "华东-张三", … } }
```

失败：`BAD_LOGIN`（账号或密码错）/ `AGENT_DISABLED`（已停用）。令牌有效期 7 天。

**`GET /api/agent/me`** —— 账号信息 + 配额清单

```json
{ "ok": true,
  "agent": { "id": 1, "username": "agent01", "name": "华东-张三", "cards_made": 7 },
  "quotas": [
    { "id": 3, "app_id": "app_xxx", "app_name": "演示软件", "card_type": "time",
      "card_type_text": "天数卡", "duration_days": 30, "max_devices": 1,
      "unbind_limit": 1, "quota_total": 20, "quota_used": 5, "quota_left": 15 }
  ],
  "quota_left": 15 }
```

**`POST /api/agent/cards`** —— 制卡

```json
{ "quota_id": 3, "count": 5, "prefix": "VIP", "note": "渠道A" }
```

**规格不能自填**：卡类型、时长、设备数、换绑次数全部取自 `quota_id` 对应的配额记录。
`count` 上限 1000。配额不足返回 `QUOTA_EXCEEDED`。

响应 `{"ok":true,"batch":"agent01-1794088634","codes":[…],"count":5,"quota_left":10}`。

**`GET /api/agent/cards`** —— 只返回自己制的卡

参数与 `/api/admin/cards` 相同（`page` `size` `q` `status` `app` `card_type`），
但强制带 `agent_id` 条件，翻不出别人的卡。

**`POST /api/agent/cards/action`** —— 操作自己制的卡

```json
{ "codes": ["WC48-QELC-UBTB-VSMP"], "action": "ban" }
```

| `action` | 说明 |
|---|---|
| `ban` | 封禁 |
| `unban` | 解封（按到期时间还原成 active / expired / unused） |
| `unbind` | 解绑全部设备 |
| `unbind_reset` | 重置换绑次数 |
| `reset` | 重置为未使用 |

**刻意不提供的**：`delete`（明确禁止）、`renew`（续期能绕过配额）、`ban_devices`。

不在白名单的动作返回 `FORBIDDEN`。不是自己制的卡**静默跳过**，
响应里给 `{"affected":1,"skipped":2}`，不暴露别人的卡。

**`POST /api/agent/logout`** —— 清掉当前令牌。

### 管理端的代理商接口

**`GET /api/admin/agents`** —— 列表，含每个账号的配额明细、已制卡数、最近登录

**`POST /api/admin/agents`**

| `action` | 字段 | 说明 |
|---|---|---|
| `create` | `username` `password` `name` `note` | 建账号，密码至少 6 位 |
| `update` | `id` `name` `status` `note` | 改资料；`status=disabled` 立即踢下线 |
| `reset_password` | `id` `password` | 改密并清空会话 |
| `kick` | `id` | 强制下线 |
| `set_quotas` | `id` `items[]` | 整体覆盖配额，已用数量保留 |
| `delete` | `id` `force` | 删账号；名下有卡时返回 `HAS_CARDS`，`force:true` 后卡保留、归属清空 |

`items[]` 每项：`{app_id, card_type, duration_days, max_devices, unbind_limit, quota_total}`。

**`POST /api/admin/agents/quota`** —— 调单条配额上限

```json
{ "id": 3, "quota_total": 50 }
```

不能小于已用数，否则 `BAD_PARAM`。

> 卡密列表 `/api/admin/cards` 多了一个筛选参数 **`agent`**：传数字按代理商 id 筛，
> 传 `0` 表示「管理员自己制的」，不传则不限。返回的每条卡带 `agent_id` 与 `agent_name`。

## 管理员账号

`config.admin_token` 是**超级令牌**（写死在配置文件里，等同 owner，永远有效），脚本和监控继续用它。
下面这套是给人用的：有用户名、有角色、能单独停用。

令牌走同一个 `X-Admin-Token` 头——超级令牌或账号登录拿到的会话令牌都能通过。

**角色**

| role | 能做什么 |
|---|---|
| `owner` | 全部，包含管理管理员账号 |
| `admin` | 除「管理员账号管理」外的全部 |
| `viewer` | 只读，所有 POST 一律 403 |

**`POST /api/admin/auth`** —— 账号登录（唯一不需要已有令牌的管理接口）

```json
{ "username": "ops", "password": "ops12345678", "code": "123456" }
```

`code` 只在账号开了两步验证时才需要，可以填 6 位 TOTP 码，也可以填一个恢复码。

响应 `{"ok":true,"token":"…","expires_at":…,"admin":{…}}`，令牌有效期 3 天。

失败时 `err` 分这几种，前端要区别处理：

| err | HTTP | 含义 | 该怎么做 |
|---|---|---|---|
| `BAD_LOGIN` | 200 | 账号或密码错 | 提示重试 |
| `ADMIN_DISABLED` | 200 | 账号被停用 | 联系拥有者 |
| `NEED_TOTP` | 200 | 密码对了，缺验证码 | 展开验证码输入框 |
| `BAD_TOTP` | 200 | 验证码不对 | 重输 |
| `LOCKED` | 429 | 连错太多被锁 | 响应体带 `retry_after` 秒数，响应头带 `Retry-After` |

**登录节流**：同一账号 15 分钟内连错 5 次锁 15 分钟。锁定期内连正确密码也返回 `LOCKED`
（先查锁再验密码，不给「边猜边试」留窗口）。登录成功即清零。按账号计，不按 IP——
撞库是分布式打的，按 IP 拦不住。传输层还有一层按 IP 的粗粒度限流（120/分钟）。

**`GET /api/admin/me/totp`** —— 自己的两步验证状态

```json
{ "ok": true, "enabled": true, "recovery_left": 7 }
```

**`POST /api/admin/me/totp`** —— 自助管理（任何角色都能调，包括 `viewer`）

| `action` | 字段 | 说明 |
|---|---|---|
| `setup` | — | 生成密钥，返回 `secret` / `secret_grouped` / `uri`。此时**还没开启** |
| `enable` | `code` | 用认证器当前显示的 6 位码确认，成功后返回 8 个恢复码（只此一次） |
| `disable` | `password` | 关掉，要验当前密码 |
| `recovery` | `password` | 重新生成恢复码，旧的全部作废 |

`uri` 是标准的 `otpauth://totp/...` 链接，能直接粘进 1Password 等支持链接导入的 App。
超级令牌（`is_super`）调这个会返回 `SUPER_NO_TOTP`——它本身就是一把密钥。

两步验证绑定是**两段式**：先 `setup` 拿密钥，用户录进 App，再拿 App 上的码 `enable`。
中间那步不能省，否则密钥存了但用户没存，下次登录就把自己锁在外面。

同一个验证码不能用两次：服务端记住已用过的时间步（`totp_last_step`），
30 秒内重放会被拒。窗口是 ±1 步（±30 秒），容忍手机时钟漂移。

**`GET /api/admin/me`** —— 当前身份

```json
{ "ok": true,
  "admin": { "id": 1, "username": "ops", "name": "运营", "role": "admin", "is_super": false },
  "roles": { "owner": "拥有者", "admin": "管理员", "viewer": "只读" } }
```

**`POST /api/admin/logout`** —— 退出（清掉当前会话令牌，任何角色都能调）

**`GET /api/admin/admins`** —— 账号列表（仅 owner）

列表第一行是虚拟的超级令牌（`is_super: true`），不可编辑。

**`POST /api/admin/admins`**（仅 owner）

| `action` | 字段 | 说明 |
|---|---|---|
| `create` | `username` `password` `name` `role` | 密码至少 8 位 |
| `update` | `id` `name` `role` `status` | 改角色或停用；停用立即清空会话 |
| `reset_password` | `id` `password` `confirm` | 改密并踢下线；`confirm` 必须是该账号名 |
| `kick` | `id` | 强制下线 |
| `delete` | `id` `confirm` | 不能删自己；`confirm` 必须是该账号名 |
| `totp_disable` | `id` `confirm` | 对方丢手机时由拥有者解锁；`confirm` 必须是该账号名 |

**高危操作要输账号名**：`reset_password` / `delete` / `totp_disable` 都要求
`confirm` 字段等于目标账号的用户名（不区分大小写），否则返回 `CONFIRM_REQUIRED`。
前端弹窗会先拦一道，服务端再查一次——**一个被盗的会话不该能一次请求删掉账号**。

**关于「最后一个 owner」**：配置文件里的超级令牌永远是一个 owner，且不受账号体系管，
所以把账号表里的 owner 全删了也不会锁死——随时能用超级令牌登进来重建。
因此这里**不设**「最后一个 owner 不能动」的拦截（设了反而导致唯一的业务 owner 永远删不掉），只禁止删除自己。

> 审计里记的 actor 是 `admin:<用户名>`，超级令牌记作 `admin`。原来固定写死的 `"admin"` 已经改成按请求取。

---

## 错误码

| 码 | HTTP | 含义 | 客户端建议 |
|---|---|---|---|
| `OK` | 200 | 通过 | 放行 |
| `BAD_PARAM` | 200 | 缺少必要参数 | 检查调用代码 |
| `BAD_APP` | 200 | AppID 不存在 | 检查配置 |
| `APP_DISABLED` | 200 | 应用已禁用 | 联系管理员 |
| `BAD_SIGN` | 200 | 签名错误 | 检查拼接顺序与密钥 |
| `BAD_TS` | 200 | 时间戳超差 | 提示用户校准本机时间 |
| `REPLAY` | 200 | 重复请求 | `nonce` 换新值 |
| `RATE_LIMIT` | 429 | 请求过于频繁 | 降低频率后重试 |
| `CARD_NOT_FOUND` | 200 | 卡密不存在 | 提示卡密错误 |
| `CARD_BANNED` | 200 | 卡密已封禁 | 禁止使用 |
| `CARD_EXPIRED` | 200 | 卡密已过期 | 提示续费 |
| `CARD_USED_UP` | 200 | 额度已用完 | 提示充值或换卡 |
| `DEVICE_LIMIT` | 200 | 绑定设备数已满 | 提示换绑或联系客服 |
| `DEVICE_MISMATCH` | 200 | 未绑定当前设备 | 提示换绑 |
| `UNBIND_LIMIT` | 200 | 换绑次数用尽 | 提示联系管理员 |
| `NOT_ACTIVATED` | 200 | 尚未激活 | 无需解绑 |
| `AGENT_NO_AUTH` | 401 | 代理商令牌无效或过期 | 重新登录 |
| `BAD_LOGIN` | 200 | 代理商账号或密码错 | 检查后重试 |
| `AGENT_DISABLED` | 200 | 代理商账号已停用 | 联系管理员 |
| `DUP_USER` | 200 | 代理商账号已存在 | 换一个 |
| `BAD_QUOTA` | 200 | 没有这条配额 | 刷新后重选 |
| `QUOTA_EXCEEDED` | 200 | 配额不足 | 找上游加量 |
| `FORBIDDEN` | 403 | 动作不在白名单 / 角色不够 | — |
| `ADMIN_DISABLED` | 200 | 管理员账号已停用 | 联系拥有者 |
| `CONFIRM_REQUIRED` | 200 | 高危操作没带对账号名 | 带上 `confirm` |
| `NEED_TOTP` | 200 | 该账号开了两步验证 | 带 `code` 重新提交 |
| `BAD_TOTP` | 200 | 验证码 / 恢复码不正确 | 重输，或换下一个恢复码 |
| `LOCKED` | 429 | 登录失败次数过多 | 等 `retry_after` 秒 |
| `SUPER_NO_TOTP` | 200 | 超级令牌不支持两步验证 | 用账号密码登录 |
| `LAST_OWNER` | 200 | 这是最后一个拥有者 | 先新建一个 owner 再改 |
| `FORBIDDEN` | 403 | 静态目录穿越 | — |
| `NOT_FOUND` | 404 | 无此接口 | 检查路径 |
| `HAS_CARDS` | 200 | 应用下仍有卡密 | 传 `force: true` 确认 |
| `BACKUP_FAIL` | 200 | 备份失败 | 查磁盘空间与权限 |

> 业务错误一律返回 `200` + `ok:false`，只有限流（429）、鉴权（401）、路由（404）、
> 请求体过大（413）走 HTTP 状态码。客户端判断成功与否**只看 `ok` 字段**。
