#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TOTP 两步验证（RFC 6238）与恢复码。零依赖，只用标准库。

算法就是 RFC 6238 规定的 HMAC-SHA1 + 30 秒时间步，
Google Authenticator / Microsoft Authenticator / 1Password / Aegis / Bitwarden 都认。

两个容易踩的点写在这里，免得以后又改坏：

1. **手机时钟不准就一直错**。手机不自动对时时，差个一两分钟验证码就永远不过。
   所以 WINDOW=1，容忍前后各一步（±30 秒）。放宽到 2 步以上就没意义了，
   等于把 6 位码的有效期从 90 秒拉到 150 秒。
2. **同一个码不能再用第二次**。RFC 没强制，但 30 秒内截到码就能重放。
   所以 verify() 会返回命中的时间步，调用方把它存下来，
   下一此校验直接跳过 `<= last_step` 的步数。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6
WINDOW = 1              # ±1 步 = 容忍 30 秒时钟漂移
RECOVERY_N = 8

# 去掉容易看错的 0/O/1/I/L，剩 31 个字符
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


# ---------------------------------------------------------------- 密钥与验证码
def new_secret(nbytes: int = 20) -> str:
    """20 字节随机 → base32（160 bit，RFC 推荐长度）。"""
    return base64.b32encode(secrets.token_bytes(nbytes)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    s = str(secret or "").strip().upper().replace(" ", "").replace("-", "")
    if not s:
        return b""
    s += "=" * ((8 - len(s) % 8) % 8)
    try:
        return base64.b32decode(s)
    except Exception:
        return b""


def code_at(secret: str, step: int) -> str:
    key = _key(secret)
    if not key:
        return ""
    h = hmac.new(key, struct.pack(">Q", int(step)), hashlib.sha1).digest()
    off = h[-1] & 0x0F
    val = struct.unpack(">I", h[off:off + 4])[0] & 0x7FFFFFFF
    return str(val % (10 ** DIGITS)).zfill(DIGITS)


def code(secret: str, at: float = 0) -> str:
    return code_at(secret, int((at or time.time()) // STEP))


def verify(secret: str, given: str, window: int = WINDOW, last_step: int = 0):
    """校验验证码。返回 (是否通过, 命中的时间步)。

    命中步数必须落库，同一码第二次用会被 last_step 挡住。
    """
    g = str(given or "").strip().replace(" ", "")
    if not g.isdigit() or len(g) != DIGITS:
        return False, 0
    now_step = int(time.time() // STEP)
    for d in range(-window, window + 1):
        s = now_step + d
        if s <= 0 or s <= int(last_step or 0):
            continue
        if hmac.compare_digest(code_at(secret, s), g):
            return True, s
    return False, 0


def uri(secret: str, account: str, issuer: str = "KeyAuth") -> str:
    """给认证器 App 的标准 otpauth 链接。"""
    label = quote("%s:%s" % (issuer, account or "admin"))
    return ("otpauth://totp/%s?secret=%s&issuer=%s&algorithm=SHA1&digits=%d&period=%d"
            % (label, secret, quote(issuer), DIGITS, STEP))


def group(secret: str) -> str:
    """把密钥按 4 位分组，手抄到 App 里不容易漏字符。"""
    s = str(secret or "")
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


# ---------------------------------------------------------------- 恢复码
def new_recovery(n: int = RECOVERY_N) -> list:
    """生成恢复码，形如 ABCD-EFGH。丢手机时一次性用掉。"""
    out = []
    for _ in range(n):
        raw = "".join(secrets.choice(ALPHABET) for _ in range(8))
        out.append(raw[:4] + "-" + raw[4:])
    return out


def _rc_hash(s: str) -> str:
    # 忽略大小写、连字符、空格，用户抄错格式也能用
    norm = str(s or "").strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def recovery_store(codes) -> str:
    return json.dumps([_rc_hash(c) for c in codes])


def recovery_consume(stored: str, given: str):
    """用掉一个恢复码，返回 (是否命中, 剩下的 JSON)。命中后该码立即作废。"""
    try:
        left = json.loads(stored or "[]")
    except Exception:
        left = []
    h = _rc_hash(given)
    for i, x in enumerate(left):
        if hmac.compare_digest(str(x), h):
            left.pop(i)
            return True, json.dumps(left)
    return False, stored


def recovery_left(stored: str) -> int:
    try:
        return len(json.loads(stored or "[]"))
    except Exception:
        return 0
