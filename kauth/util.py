#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用工具函数"""
from __future__ import annotations

import json
import secrets
import time

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 去掉 I O 0 1，避免抄错
DAY = 86400


def now() -> int:
    return int(time.time())


def fmt_time(ts) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))


def day_start(offset_days: int = 0) -> int:
    """今天 0 点（本地时区），可偏移若干天"""
    lt = time.localtime()
    base = int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))
    return base + offset_days * DAY


def gen_card(prefix: str = "", groups: int = 4, size: int = 4) -> str:
    body = "-".join("".join(secrets.choice(ALPHABET) for _ in range(size))
                    for _ in range(groups))
    return (prefix + body) if prefix else body


def gen_token(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


def gen_hex(n: int = 24) -> str:
    return secrets.token_hex(n)


# 前缀用完整字符集（卡密正文才需要避开易混淆字符）
_PREFIX_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


def clean_prefix(raw: str, maxlen: int = 8) -> str:
    """卡密前缀：保留字母数字和横杠，统一补尾部横杠。

    注意不能用 ALPHABET 过滤——那个字符集为可读性去掉了 I/O/0/1，
    拿来过滤前缀会把用户输入的 VIP 之类合法前缀吃掉字母。
    """
    s = "".join(ch for ch in str(raw or "").strip().upper()
                if ch in _PREFIX_CHARS)[:maxlen]
    if s and not s.endswith("-"):
        s += "-"
    return s


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)

