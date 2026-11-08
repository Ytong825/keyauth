#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KeyAuth 客户端接入示例（Python 3，零第三方依赖，可直接抄进你的软件）

四个接口的调用顺序就是软件里的标准流程：
    1. verify     —— 启动时校验卡密，首次成功即激活并开始计时
    2. heartbeat  —— 运行期间每 3 分钟一次；返回 ok=false 就立刻退出
    3. query      —— 需要展示"剩余天数"时调用
    4. unbind     —— 用户换机器时自助换绑（次数有限，用完找发卡方）

签名规则（服务端强校验，不一致会一直报 BAD_SIGN）：
    · 除 sign 外**全部**参数参与拼接，空值也保留
    · 按参数名 ASCII 升序拼成 k1=v1&k2=v2
    · 用 AppSecret 做 HMAC-SHA256，取小写十六进制
    · ts 用 Unix 秒；服务端允许 ±300 秒偏差
    · nonce 建议用 uuid4，600 秒内不可重复

用法：
    python client_demo.py http://你的服务器:8787 app_xxxx 你的AppSecret
"""
from __future__ import annotations

import hashlib
import hmac
import json
import platform
import time
import urllib.error
import urllib.request
import uuid


class KeyAuth:
    """客户端。threading / 心跳调度这些按你自己的框架接即可。"""

    def __init__(self, base_url: str, app_id: str, app_secret: str,
                 version: str = "1.0.0"):
        self.base = base_url.rstrip("/")
        self.app_id = app_id
        self.secret = app_secret
        self.version = version

    # verify / heartbeat / query 成功时 data 的字段：
    #   code                 卡密
    #   status               unused / active / expired / banned / used_up
    #   card_type / card_type_text
    #   activated_at         激活时间戳（0 = 还没激活）
    #   expires_at           到期时间戳（0 = 永久）
    #   expires_text         到期时间字符串，如 "2027-01-01 01:46:46"
    #   remaining_seconds    剩余秒数（自己换算成天/小时）
    #   devices / max_devices
    #   unbind_left          还能自助换绑几次
    #   heartbeat_interval   建议心跳间隔（秒），后台可调
    #   announcement         后台下发的公告文本
    #   server_time          服务端当前时间（可用来校正本地时钟偏差）

    # ---------------------------------------------------------- 底层
    def _machine(self) -> str:
        """机器码。原则：取**重启后不变**的硬件标识。

        下面用 CPU + 主板 + 磁盘的序列号组合，避开 MAC（现代系统装完就随机化）。
        你也可以改成自己的规则，但要保证同一台机器每次算出来都一样。
        """
        import subprocess
        import uuid as _uuid

        parts = [_uuid.getnode().__str__(), platform.node(), platform.machine()]
        if platform.system() == "Windows":
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Processor | Select-Object -Expand SerialNumber;"
                     "Get-CimInstance Win32_BaseBoard | Select-Object -Expand SerialNumber;"
                     "Get-CimInstance Win32_DiskDrive | Select-Object -Expand SerialNumber"],
                    capture_output=True, text=True, timeout=8).stdout
                parts += [x.strip() for x in out.splitlines() if x.strip()]
            except Exception:
                pass
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _sign(self, params: dict) -> dict:
        """按服务端规则算签名：全参数、按名升序、空值保留。"""
        items = sorted((k, "" if v is None else str(v))
                       for k, v in params.items() if k != "sign")
        raw = "&".join("%s=%s" % (k, v) for k, v in items)
        sig = hmac.new(self.secret.encode("utf-8"), raw.encode("utf-8"),
                       hashlib.sha256).hexdigest()
        out = dict(params)
        out["sign"] = sig
        return out

    def _post(self, path: str, **params) -> dict:
        payload = {
            "app_id": self.app_id,
            "ts": int(time.time()),
            "nonce": uuid.uuid4().hex,
            "ver": self.version,
        }
        payload.update(params)
        body = json.dumps(self._sign(payload)).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode("utf-8") or '{"ok":false}')
        except Exception as e:
            return {"ok": False, "err": "NETWORK", "msg": str(e)}

    # ---------------------------------------------------------- 四个接口
    def verify(self, card: str, machine: str = None) -> dict:
        """校验卡密。首次成功 = 激活，开始计时；后续校验检查状态与设备绑定。"""
        return self._post("/api/v1/verify", code=card,
                          machine_id=machine or self._machine())

    def heartbeat(self, card: str, machine: str = None) -> dict:
        """心跳。ok=false（卡密被封/到期/换绑/设备超限）时软件应立即退出。"""
        return self._post("/api/v1/heartbeat", code=card,
                          machine_id=machine or self._machine())

    def query(self, card: str, machine: str = None) -> dict:
        """查询状态：剩余天数、已用次数、设备数等，用于界面展示。"""
        return self._post("/api/v1/query", code=card,
                          machine_id=machine or self._machine())

    def unbind(self, card: str, machine: str = None) -> dict:
        """自助换绑（换硬盘/重装系统）。次数受套餐限制。"""
        return self._post("/api/v1/unbind", code=card,
                          machine_id=machine or self._machine())


# ================================================================ 演示
def demo(base: str, app_id: str, secret: str) -> None:
    ka = KeyAuth(base, app_id, secret)
    machine = ka._machine()
    print("机器码: %s\n" % machine)

    card = input("请输入卡密: ").strip()
    if not card:
        print("没有卡密，退出")
        return

    r = ka.verify(card, machine)
    print("\n[verify ] %s" % json.dumps(r, ensure_ascii=False))
    if not r.get("ok"):
        print("校验失败：%s（%s）" % (r.get("err"), r.get("msg")))
        return

    # 返回字段以服务端实际为准（见下方 _DATA_FIELDS）
    d = r.get("data", {})
    print("  到期: %s | 剩余秒: %s | 设备: %s/%s | 状态: %s | 剩余换绑: %s"
          % (d.get("expires_text"), d.get("remaining_seconds"),
             d.get("devices"), d.get("max_devices"),
             d.get("status"), d.get("unbind_left")))

    r = ka.heartbeat(card, machine)
    print("\n[heartbeat] %s" % json.dumps(r, ensure_ascii=False))

    r = ka.query(card, machine)
    print("\n[query   ] %s" % json.dumps(r, ensure_ascii=False))

    if input("\n演示换绑？输入 y 继续: ").strip().lower() == "y":
        r = ka.unbind(card, machine)
        print("\n[unbind ] %s" % json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    demo(sys.argv[1], sys.argv[2], sys.argv[3])
