#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全层：签名、防重放、限流"""
from __future__ import annotations

import hashlib
import hmac
import threading

from . import config
from .util import now

_nonce_lock = threading.Lock()
_nonces: dict = {}          # nonce -> 首次出现时间

_rate_lock = threading.Lock()
_rate: dict = {}            # ip -> [窗口起点, 计数]


# ---------------------------------------------------------------- 签名
def build_sign_str(params: dict) -> str:
    """
    签名串构造规则：
      除 sign 自身外的**全部**参数参与拼接，按参数名 ASCII 升序，
      拼成 k1=v1&k2=v2，空值也要保留。

    客户端必须用完全相同的规则，否则会一直报签名错误。
    """
    items = sorted(
        (k, "" if v is None else str(v))
        for k, v in params.items() if k != "sign"
    )
    return "&".join("%s=%s" % (k, v) for k, v in items)


def sign(secret: str, params: dict) -> str:
    raw = build_sign_str(params)
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def verify_sign(secret: str, params: dict) -> bool:
    got = str(params.get("sign") or "").strip().lower()
    if not got:
        return False
    return hmac.compare_digest(sign(secret, params), got)


# ---------------------------------------------------------------- 防重放
def nonce_ok(nonce: str) -> bool:
    """同一 nonce 在 TTL 窗口内只允许使用一次"""
    if not nonce:
        return True
    ttl = int(config.CFG.get("nonce_ttl", 600))
    t = now()
    with _nonce_lock:
        if len(_nonces) > 50000:                      # 防止无限增长
            for k in [k for k, v in _nonces.items() if v < t - ttl]:
                _nonces.pop(k, None)
        if _nonces.get(nonce, 0) > t - ttl:
            return False
        _nonces[nonce] = t
        return True


# ---------------------------------------------------------------- 限流
def rate_ok(ip: str) -> bool:
    """单 IP 每分钟请求上限，防卡密爆破"""
    limit = int(config.CFG.get("rate_limit", 120))
    if limit <= 0 or not ip:
        return True
    t = now()
    with _rate_lock:
        if len(_rate) > 20000:
            _rate.clear()
        slot = _rate.get(ip)
        if not slot or t - slot[0] >= 60:
            _rate[ip] = [t, 1]
            return True
        slot[1] += 1
        return slot[1] <= limit


# ---------------------------------------------------------------- 后台令牌
def token_ok(got: str) -> bool:
    return hmac.compare_digest(str(got or ""), config.CFG["admin_token"])


def token_strength() -> dict:
    """评估管理令牌强度。

    只做提示，不做强制——自己人的部署可能就爱用短密码图方便，
    后台弹一条可关闭的提醒，比锁死人更合适。
    """
    tok = str(config.CFG.get("admin_token") or "")
    reasons = []
    if len(tok) < 12:
        reasons.append("长度只有 %d 位（建议 16 位以上）" % len(tok))
    if tok.isdigit():
        reasons.append("全是数字，容易被字典穷举")
    elif tok.isalpha():
        reasons.append("全是字母，缺少数字和符号")
    return {
        "weak": bool(reasons),
        "reasons": reasons,
        "length": len(tok),
        # 给前端做「改过之后就重新提示」的判断，只暴露长度和首尾，不暴露令牌
        "hint": (tok[:2] + "…" + tok[-2:]) if len(tok) > 6 else "…",
    }


def rotate_token() -> str:
    """重置管理员令牌"""
    from .util import gen_token
    config.CFG["admin_token"] = gen_token(32)
    config.save(config.CFG)
    return config.CFG["admin_token"]
