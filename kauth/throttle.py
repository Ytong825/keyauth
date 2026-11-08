#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录失败节流：按「类型 + 账号」计数，连续错 5 次锁 15 分钟。

为什么不是按 IP：撞库是分布式打的，按 IP 拦不住；而按账号拦
对正常用户的影响也就是「自己连错 5 次要等一会儿」，代价可接受。
传输层的按 IP 限流（httpd._RateLimiter）继续保留，两层各管一段：
IP 层挡洪水，这里挡慢速猜密码。

计数放库里的原因：进程重启不该把锁定状态清掉——那等于给攻击者
一个「打满 5 次就等你重启」的玩法。表很小，一天清一次就够。
"""
from __future__ import annotations

from . import db
from .util import now

WINDOW = 900        # 15 分钟内累计
MAX_FAILS = 5       # 错 5 次
LOCK = 900          # 锁 15 分钟


def _k(kind: str, username: str) -> str:
    return "%s:%s" % (kind, str(username or "").strip().lower()[:64])


def status(kind: str, username: str) -> dict:
    """看当前还能不能试。locked=True 时 retry_after 是剩余秒数。"""
    k = _k(kind, username)
    t = now()
    row = db.one("SELECT * FROM login_throttle WHERE key=?", (k,))
    if not row:
        return {"locked": False, "retry_after": 0, "left": MAX_FAILS}

    lu = int(row["locked_until"] or 0)
    if lu > t:
        return {"locked": True, "retry_after": lu - t, "left": 0}
    if lu:                                  # 锁已到期，重新开始计数
        _clear(k)
        return {"locked": False, "retry_after": 0, "left": MAX_FAILS}
    if t - int(row["first_at"] or 0) > WINDOW:   # 窗口过期
        _clear(k)
        return {"locked": False, "retry_after": 0, "left": MAX_FAILS}
    return {"locked": False, "retry_after": 0,
            "left": max(0, MAX_FAILS - int(row["fails"] or 0))}


def fail(kind: str, username: str) -> dict:
    """记一次失败。返回和 status() 同构的字典。"""
    k = _k(kind, username)
    t = now()
    row = db.one("SELECT * FROM login_throttle WHERE key=?", (k,))
    if not row:
        fails, first = 1, t
        db.execute("INSERT INTO login_throttle(key,fails,first_at,last_at,locked_until)"
                   " VALUES(?,?,?,?,0)", (k, fails, first, t))
    else:
        fails = int(row["fails"] or 0) + 1
        first = int(row["first_at"] or t)
        if t - first > WINDOW:              # 距第一次失败太久，重新计数
            fails, first = 1, t
        db.execute("UPDATE login_throttle SET fails=?, first_at=?, last_at=?"
                   " WHERE key=?", (fails, first, t, k))

    if fails >= MAX_FAILS:
        db.execute("UPDATE login_throttle SET locked_until=? WHERE key=?", (t + LOCK, k))
        return {"locked": True, "retry_after": LOCK, "left": 0}
    return {"locked": False, "retry_after": 0, "left": MAX_FAILS - fails}


def reset(kind: str, username: str) -> None:
    _clear(_k(kind, username))


def _clear(k: str) -> None:
    try:
        db.execute("DELETE FROM login_throttle WHERE key=?", (k,))
    except Exception:
        pass


def sweep(days: int = 1) -> int:
    """清掉很久没动的记录，别让表无限长。"""
    try:
        return db.execute("DELETE FROM login_throttle WHERE last_at < ?",
                          (now() - days * 86400,))
    except Exception:
        return 0
