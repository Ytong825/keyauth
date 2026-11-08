# 客户端接入

服务端只是一个「判决器」。真正让软件不被白嫖的，是客户端怎么用这个判决结果。
这份文档讲接入流程、签名实现、机器码设计，以及几个容易踩的坑。

**现成示例**（都在仓库里，改两行常量就能用）：

- Python → [`client_demo.py`](../client_demo.py)
- C# → [`examples/client.cs`](../examples/client.cs)（.NET Framework 4.6+ / .NET 6+）
- 易语言 → [`examples/client_eyuyan.md`](../examples/client_eyuyan.md)（不依赖任何模块）

- [整体流程](#整体流程)
- [Python 接入](#python-接入)
- [其他语言](#其他语言)
- [签名实现](#签名实现)
- [机器码怎么定](#机器码怎么定)
- [心跳与容错](#心跳与容错)
- [常见错误排查](#常见错误排查)

---

## 整体流程

```
启动
 ├─ 读本地保存的卡密
 ├─ 没有 → 弹授权窗口 → 用户输入 → verify
 ├─ 有   → verify（首次即激活，之后是状态检查）
 │
 ├─ ok=false → 按错误码提示 / 退出
 └─ ok=true
      ├─ 进入主功能
      ├─ 起一个后台线程：每 heartbeat_interval 秒调 heartbeat
      │    └─ 连续失败 3 次 or 返回 CARD_BANNED → 停止功能
      └─ 需要展示「剩余 X 天」时调 query
```

三个关键决定：

1. **心跳失败不要立刻退出**。网络抖动很常见，建议连续 3 次失败再判定，
   并且区分错误码：`CARD_EXPIRED` / `CARD_BANNED` / `DEVICE_MISMATCH` 是硬失败，
   `RATE_LIMIT` / `BAD_TS` / `NETWORK` 是软失败。
2. **卡密存本地要加密**，别明文放配置文件。
3. **不要把 AppSecret 写在前端 JS 里**。它是服务端密钥，只能放在客户端可执行文件里（并接受被逆的可能）。

## Python 接入

直接拷 [`client_demo.py`](../client_demo.py)：

```python
from client_demo import KeyAuth

ka = KeyAuth("https://auth.example.com", "app_xxx", "AppSecret")

r = ka.verify("WC48-QELC-UBTB-VSMP")
if not r["ok"]:
    print(r["err"], r["msg"])
else:
    d = r["data"]
    print("到期", d["expires_text"], "设备", d["devices"], "/", d["max_devices"])
```

心跳线程示例：

```python
import threading, time

def heartbeat_loop(ka, card):
    fail = 0
    while True:
        time.sleep(180)
        r = ka.heartbeat(card)
        if r.get("ok"):
            fail = 0
            continue
        err = r.get("err")
        if err in ("CARD_BANNED", "CARD_EXPIRED", "DEVICE_MISMATCH"):
            notify_and_exit(r.get("msg"))
            return
        fail += 1
        if fail >= 3:
            notify_offline_mode()   # 或者退出，看你产品策略
            return

threading.Thread(target=heartbeat_loop, args=(ka, card), daemon=True).start()
```

## 其他语言

只要会发 HTTP 和算 HMAC-SHA256 就能接。三步：

1. 组装参数：`app_id` / `code` / `machine_id` / `ts` / `nonce`（可选 `ver`）
2. 按[签名规则](#签名实现)算 `sign`
3. `POST` JSON 到 `https://你的域名/api/v1/verify`

curl 手测：

```bash
BODY='{"app_id":"app_xxx","code":"WC48-QELC-UBTB-VSMP","machine_id":"MACH-TEST","ts":1794090000,"nonce":"abc123","sign":"..."}'
curl -s https://auth.example.com/api/v1/verify \
     -H 'Content-Type: application/json' -d "$BODY"
```

> 手测时 `ts` 要用当前时间，`nonce` 每次换新值，否则会收到 `BAD_TS` / `REPLAY`。

## 签名实现

规则：**除 `sign` 外所有参数参与**，按参数名 ASCII 升序，拼 `k=v&k=v`（值不编码、空值保留），
HMAC-SHA256 后取**小写十六进制**。

**Python**

```python
def sign(params: dict, secret: str) -> str:
    raw = "&".join("%s=%s" % (k, params[k] if params[k] is not None else "")
                   for k in sorted(params) if k != "sign")
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
```

**JavaScript**

```js
const crypto = require('crypto');
function sign(params, secret) {
  const raw = Object.keys(params).filter(k => k !== 'sign').sort()
    .map(k => `${k}=${params[k] == null ? '' : params[k]}`).join('&');
  return crypto.createHmac('sha256', secret).update(raw).digest('hex');
}
```

**C#**

```csharp
static string Sign(Dictionary<string, string> p, string secret) {
    var raw = string.Join("&", p.Where(kv => kv.Key != "sign")
        .OrderBy(kv => kv.Key, StringComparer.Ordinal)
        .Select(kv => kv.Key + "=" + (kv.Value ?? "")));
    using var h = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
    return Convert.ToHexString(h.ComputeHash(Encoding.UTF8.GetBytes(raw))).ToLower();
}
```

**Go**

```go
func sign(p map[string]string, secret string) string {
    keys := make([]string, 0, len(p))
    for k := range p { if k != "sign" { keys = append(keys, k) } }
    sort.Strings(keys)
    var b strings.Builder
    for i, k := range keys {
        if i > 0 { b.WriteByte('&') }
        b.WriteString(k + "=" + p[k])
    }
    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(b.String()))
    return hex.EncodeToString(mac.Sum(nil))
}
```

> **最容易错的地方**：排序用 `sorted()` 默认比较即可（都是 ASCII 小写字母 + 下划线），
> 但别用 locale 相关的排序（C# 的 `OrderBy` 要带 `StringComparer.Ordinal`），否则大小写混排会错。

## 机器码怎么定

原则：**同一台机器每次算出来都一样，换硬件或重装系统才变**。

| 可用 | 避免 |
|---|---|
| CPU 序列号、主板序列号、磁盘序列号 | MAC 地址（现代系统默认随机化） |
| 系统安装 ID（Windows `MachineGuid`） | 计算机名（用户随手改） |
| 多个硬件标识拼接后哈希 | 屏幕分辨率 / 时区（会变） |

示例（Windows）：

```python
import hashlib, subprocess
out = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Processor | Select-Object -Expand SerialNumber;"
     "Get-CimInstance Win32_BaseBoard | Select-Object -Expand SerialNumber;"
     "Get-CimInstance Win32_DiskDrive | Select-Object -Expand SerialNumber"],
    capture_output=True, text=True).stdout
machine_id = hashlib.sha256(out.encode()).hexdigest()[:32]
```

**取值失败要有兜底**。某些虚拟机读不到主板序列号，这时退到 `MachineGuid` 或
`platform.node()` + `uuid.getnode()`，别让程序因为读不到硬件直接崩。

**机器码只是「弱标识」**：能被伪造、能被共享。它的作用是提高传播成本，不是防破解。
真正的防线是服务端的状态机 + 设备数上限 + 换绑次数。

## 心跳与容错

| 情况 | 建议处理 |
|---|---|
| `network` 异常 | 重试，指数退避（1s / 3s / 9s），最多 3 次 |
| 连续 3 次失败 | 进入「离线宽限」：再给 30~60 分钟，之后停止功能 |
| `CARD_EXPIRED` | 提示续费，停止功能 |
| `CARD_BANNED` | 直接退出，不给提示 |
| `DEVICE_MISMATCH` | 提示「已在其他设备登录」，给自助换绑入口 |
| `RATE_LIMIT` | 拉长间隔重试，别立刻重发 |
| `BAD_TS` | 提示用户校准系统时间（这是真实用户最常见的失败原因） |
| `REPLAY` | `nonce` 生成有 bug，检查是否用了固定值 |

**离线宽限是产品决策**：完全不允许离线，用户断网就骂你；允许太久，破解者拔网线就能一直用。
常见做法是按卡密类型区分——体验卡不给宽限，年卡给 24 小时。

## 常见错误排查

**一直 `BAD_SIGN`**

1. 拼接时把 `sign` 也算进去了（必须排除）
2. 排序用了本地化比较导致大小写顺序不同
3. AppSecret 前后有空格 / 复制时漏了字符
4. 空值参数被丢掉（必须保留 `k=`）
5. 签名用了标准 Base64 而不是十六进制

**一直 `BAD_TS`**

- 客户端机器时间不对。让用户校准，或在客户端用 `server_time` 做偏移补偿
- 字段名写错：服务端读的是 `ts`，不是 `timestamp` / `time`

**一直 `REPLAY`**

- `nonce` 用了固定值或时间戳。每次请求都要新的随机串

**`DEVICE_LIMIT`**

- 该卡已经绑满设备且换绑次数用完。后台「卡密库」搜这张卡，能看到绑了哪些机器码

**验过了但功能还是被绕过**

- 说明判定结果没真正约束功能。常见错误是 `verify` 只在启动时调一次，
  之后再也不检查，用户把卡密文件一删或者断网就一直用。
  至少要：启动校验 + 周期心跳 + 关键功能前复查。
