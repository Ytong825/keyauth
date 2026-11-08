#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""授权核验核心：请求鉴权链、卡密状态机、设备绑定、额度扣减"""
from __future__ import annotations

import sys
import threading

from . import config, db, webhook
from .security import nonce_ok, rate_ok, verify_sign
from .util import DAY, fmt_time, now

# 核验过程串行化：保证「首次激活」「扣次数」在并发下不会算错
_lock = threading.Lock()

CARD_TYPES = {"time": "天数卡", "hour": "小时卡", "count": "次数卡", "point": "点数卡"}

# 时间类卡（time / hour）激活时都写 expires_at，只是换算单位不同：
#   time 用 duration_days 存天数，exp = t + days * DAY
#   hour 用 duration_days 存小时数，exp = t + hours * HOUR
HOUR = 3600

RESULT_TEXT = {
    "OK": "通过",
    "BAD_PARAM": "参数缺失",
    "BAD_APP": "应用不存在",
    "APP_DISABLED": "应用已禁用",
    "BAD_SIGN": "签名错误",
    "BAD_TS": "时间戳异常",
    "REPLAY": "重复请求",
    "RATE_LIMIT": "请求过频",
    "CARD_NOT_FOUND": "卡密不存在",
    "CARD_BANNED": "卡密已封禁",
    "CARD_EXPIRED": "卡密已过期",
    "CARD_USED_UP": "额度已用完",
    "DEVICE_LIMIT": "设备数超限",
    "DEVICE_MISMATCH": "设备不匹配",
    "UNBIND_LIMIT": "换绑次数用尽",
    "NOT_ACTIVATED": "尚未激活",
}


# ---------------------------------------------------------------- 日志
def log(action, app_id, code, machine, ip, result, detail="") -> None:
    try:
        db.execute(
            "INSERT INTO logs(ts,app_id,code,machine_id,ip,action,result,detail)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (now(), app_id or "", code or "", machine or "", ip or "",
             action or "verify", result, detail or ""),
        )
    except Exception as e:
        sys.stderr.write("[log-error] %s\n" % e)


def fail(err, msg, action, ip, app_id="", code="", machine="", **extra) -> dict:
    log(action, app_id, code, machine, ip, err, msg)
    d = {"ok": False, "err": err, "msg": msg}
    d.update(extra)
    return d


# ---------------------------------------------------------------- 应用
def resolve_app(app_id: str):
    """空 app_id 时回退到默认应用，方便单应用场景与联调"""
    app_id = str(app_id or "").strip()
    if not app_id:
        rows = db.query("SELECT * FROM apps ORDER BY id LIMIT 1")
        return rows[0] if rows else None
    return db.one("SELECT * FROM apps WHERE app_id=?", (app_id,))


def _extract(payload: dict):
    return (
        str(payload.get("app_id") or "").strip(),
        str(payload.get("code") or "").strip().upper(),
        str(payload.get("machine_id") or "").strip(),
    )


def check_request(payload: dict, ip: str, action: str):
    """
    请求鉴权链：参数 -> 应用 -> 限流 -> 时间戳 -> nonce -> 签名。
    返回 (app, err)；err 非空时直接返回给客户端。
    **先验签、再查库**：签名不过的请求在触碰卡密表之前就被挡掉。
    """
    app_id, code, machine = _extract(payload)
    if not code:
        return None, fail("BAD_PARAM", "缺少卡密", action, ip, app_id, code, machine)

    app = resolve_app(app_id)
    if not app:
        return None, fail("BAD_APP", "应用不存在", action, ip, app_id, code, machine)
    if app.get("status") != "active":
        return None, fail("APP_DISABLED", "该应用已被禁用", action, ip, app_id, code, machine)

    if not rate_ok(ip):
        return None, fail("RATE_LIMIT", "请求过于频繁，请稍后再试",
                          action, ip, app_id, code, machine)

    need_sign = bool(app.get("require_sign")) or bool(config.CFG.get("require_sign"))
    if need_sign:
        if not str(payload.get("sign") or "").strip():
            return None, fail("BAD_SIGN", "缺少签名", action, ip, app_id, code, machine)
        try:
            ts = int(payload.get("ts"))
        except (TypeError, ValueError):
            return None, fail("BAD_TS", "时间戳无效", action, ip, app_id, code, machine)
        skew = int(config.CFG.get("clock_skew", 300))
        if abs(now() - ts) > skew:
            return None, fail("BAD_TS", "请求已过期，请校准本机时间",
                              action, ip, app_id, code, machine)
        if not nonce_ok(str(payload.get("nonce") or "")):
            return None, fail("REPLAY", "请求重复提交", action, ip, app_id, code, machine)
        if not verify_sign(app["app_secret"], payload):
            return None, fail("BAD_SIGN", "签名校验失败", action, ip, app_id, code, machine)

    return app, None


# ---------------------------------------------------------------- 卡密核验
def _build_data(app: dict, card: dict, t: int) -> dict:
    devices = db.scalar("SELECT COUNT(*) FROM binds WHERE code=?", (card["code"],))
    if card["card_type"] in ("time", "hour"):
        remain = None if card["expires_at"] is None else max(0, card["expires_at"] - t)
    else:
        remain = None
    return {
        "code": card["code"],
        "app_id": card["app_id"],
        "plan": card["plan"],
        "card_type": card["card_type"],
        "card_type_text": CARD_TYPES.get(card["card_type"], card["card_type"]),
        "status": card["status"],
        "activated_at": card["activated_at"],
        "expires_at": card["expires_at"],
        # 同 admin：区分「永久」与「尚未激活」。客户端只需知道能不能用。
        "expires_text": (
            fmt_time(card["expires_at"]) if card["expires_at"] is not None
            else ("未激活" if (card["card_type"] in ("time", "hour")
                              and card["duration_days"] > 0) else "永久")
        ),
        "remaining_seconds": remain,
        "total_value": card["total_value"],
        "used_value": card["used_value"],
        "remaining_value": max(0, card["total_value"] - card["used_value"]),
        "devices": devices,
        "max_devices": card["max_devices"],
        "unbind_left": max(0, card["unbind_limit"] - card["unbind_used"]),
        "heartbeat_interval": app.get("heartbeat_interval", 180),
        "announcement": config.CFG.get("announcement", ""),
        "server_time": t,
    }


def core(app: dict, code: str, machine: str, ip: str, action: str,
         bind: bool = True, cost: int = 1):
    """卡密状态机。bind=False 用于心跳/查询，不激活、不绑机、不扣额度。"""
    t = now()

    card = db.one("SELECT * FROM cards WHERE code=?", (code,))
    if not card:
        return None, fail("CARD_NOT_FOUND", "卡密不存在", action, ip,
                          app["app_id"], code, machine)
    if card["app_id"] and card["app_id"] != app["app_id"]:
        return None, fail("CARD_NOT_FOUND", "该卡密不属于此应用", action, ip,
                          app["app_id"], code, machine)
    if card["status"] == "banned":
        return None, fail("CARD_BANNED", "卡密已被封禁", action, ip,
                          app["app_id"], code, machine)

    # ---- 首次激活 ----
    if card["status"] == "unused" and bind:
        exp = None
        if card["card_type"] == "time" and card["duration_days"] > 0:
            exp = t + card["duration_days"] * DAY
        elif card["card_type"] == "hour" and card["duration_days"] > 0:
            exp = t + card["duration_days"] * HOUR
        db.execute(
            "UPDATE cards SET status='active', activated_at=?, expires_at=?,"
            " last_used_at=? WHERE code=?",
            (t, exp, t, code),
        )
        card = db.one("SELECT * FROM cards WHERE code=?", (code,))
        webhook.emit(app, "card.activated", card, {"machine_id": machine})

    # ---- 状态判定 ----
    if card["card_type"] in ("time", "hour"):
        if card["expires_at"] is not None and t > card["expires_at"]:
            if card["status"] != "expired":
                db.execute("UPDATE cards SET status='expired' WHERE code=?", (code,))
            return None, fail("CARD_EXPIRED", "卡密已过期", action, ip,
                              app["app_id"], code, machine,
                              expires_at=card["expires_at"],
                              expires_text=fmt_time(card["expires_at"]))
    else:
        if card["total_value"] > 0 and card["used_value"] >= card["total_value"]:
            if card["status"] != "used_up":
                db.execute("UPDATE cards SET status='used_up' WHERE code=?", (code,))
            return None, fail("CARD_USED_UP", "卡密额度已用完", action, ip,
                              app["app_id"], code, machine)

    # ---- 设备绑定 ----
    bound = db.one("SELECT 1 AS x FROM binds WHERE code=? AND machine_id=?",
                   (code, machine))
    if bind:
        if bound:
            db.execute("UPDATE binds SET last_seen=? WHERE code=? AND machine_id=?",
                       (t, code, machine))
        else:
            n = db.scalar("SELECT COUNT(*) FROM binds WHERE code=?", (code,))
            if n >= card["max_devices"]:
                return None, fail("DEVICE_LIMIT",
                                  "该卡密最多绑定 %d 台设备，已达上限" % card["max_devices"],
                                  action, ip, app["app_id"], code, machine, bound=n)
            db.execute(
                "INSERT INTO binds(code,machine_id,bind_at,last_seen) VALUES(?,?,?,?)",
                (code, machine, t, t),
            )
            webhook.emit(app, "device.bound", card, {"machine_id": machine})
    else:
        if machine and not bound:
            return None, fail("DEVICE_MISMATCH", "该卡密未绑定当前设备", action, ip,
                              app["app_id"], code, machine)

    # ---- 额度扣减（只有 verify 扣；心跳/查询不扣）----
    use = 0
    if bind and card["card_type"] in ("count", "point"):
        if card["card_type"] == "point":
            use = max(0, int(cost))                    # 点数卡按调用方指定消耗
        else:
            use = 0 if int(cost) <= 0 else 1           # 次数卡固定扣 1，cost=0 表示只校验

    if use > 0:
        left = card["total_value"] - card["used_value"]
        if card["total_value"] > 0 and use > left:
            return None, fail("CARD_USED_UP",
                              "剩余额度不足（需 %d，剩 %d）" % (use, max(0, left)),
                              action, ip, app["app_id"], code, machine,
                              remaining_value=max(0, left))
        db.execute("UPDATE cards SET used_value=used_value+?, last_used_at=?"
                   " WHERE code=?", (use, t, code))
        card = db.one("SELECT * FROM cards WHERE code=?", (code,))
        if card["total_value"] > 0 and card["used_value"] >= card["total_value"]:
            db.execute("UPDATE cards SET status='used_up' WHERE code=?", (code,))
            card = db.one("SELECT * FROM cards WHERE code=?", (code,))
    else:
        db.execute("UPDATE cards SET last_used_at=? WHERE code=?", (t, code))
        card = db.one("SELECT * FROM cards WHERE code=?", (code,))

    log(action, app["app_id"], code, machine, ip, "OK", "")
    return {"ok": True, "data": _build_data(app, card, t)}, None


# ---------------------------------------------------------------- 对外接口
def _handle(payload: dict, ip: str, action: str, bind: bool, cost: int = 1):
    app, err = check_request(payload, ip, action)
    if err:
        return err
    _, code, machine = _extract(payload)
    if not machine:
        return fail("BAD_PARAM", "缺少机器码", action, ip, app["app_id"], code, machine)

    if bool(config.CFG.get("maintenance")) and action == "verify":
        return fail("MAINTENANCE", "服务维护中，请稍后再试", action, ip,
                    app["app_id"], code, machine)

    with _lock:
        ok, err = core(app, code, machine, ip, action, bind=bind, cost=cost)
    return err if err else ok


def api_verify(payload: dict, ip: str) -> dict:
    try:
        cost = int(payload.get("cost", 1))
    except (TypeError, ValueError):
        cost = 1
    return _handle(payload, ip, "verify", True, cost)


def api_heartbeat(payload: dict, ip: str) -> dict:
    return _handle(payload, ip, "heartbeat", False)


def api_query(payload: dict, ip: str) -> dict:
    return _handle(payload, ip, "query", False)


def api_unbind(payload: dict, ip: str) -> dict:
    app, err = check_request(payload, ip, "unbind")
    if err:
        return err
    _, code, machine = _extract(payload)
    if not machine:
        return fail("BAD_PARAM", "缺少机器码", "unbind", ip, app["app_id"], code, machine)

    with _lock:
        card = db.one("SELECT * FROM cards WHERE code=?", (code,))
        if not card:
            return fail("CARD_NOT_FOUND", "卡密不存在", "unbind", ip,
                        app["app_id"], code, machine)
        if card["status"] == "banned":
            return fail("CARD_BANNED", "卡密已被封禁", "unbind", ip,
                        app["app_id"], code, machine)
        if card["status"] == "unused":
            return fail("NOT_ACTIVATED", "卡密尚未激活，无需解绑", "unbind", ip,
                        app["app_id"], code, machine)
        if card["unbind_used"] >= card["unbind_limit"]:
            return fail("UNBIND_LIMIT",
                        "自助换绑次数已用完（%d 次），请联系管理员" % card["unbind_limit"],
                        "unbind", ip, app["app_id"], code, machine)
        # 换绑语义（这里原先是个坑）：
        #   旧实现要求"当前这台机器已绑定"才允许解绑，于是用户换硬盘 / 重装系统后，
        #   在**新机器**上调 unbind 必然报 DEVICE_MISMATCH —— 换绑这条路等于堵死的，
        #   用户只能找管理员手动解绑。
        #   现在改成：当前机器绑着就解绑它；没绑着就解绑**最早绑定的那台**，
        #   这才是"换机自助解绑"该有的行为。换绑次数由 unbind_limit 兜住。
        bound = db.one("SELECT 1 AS x FROM binds WHERE code=? AND machine_id=?",
                       (code, machine))
        if bound:
            target = machine
        else:
            # binds 主键是 (code, machine_id)，**没有 id 列**；
            # 排序要用 bind_at（绑定时间），最早的绑定就是最该被解绑的那台。
            oldest = db.one("SELECT machine_id FROM binds WHERE code=? "
                            "ORDER BY bind_at ASC LIMIT 1", (code,))
            if not oldest:
                return fail("DEVICE_MISMATCH", "该卡密没有绑定任何设备", "unbind",
                            ip, app["app_id"], code, machine)
            target = oldest["machine_id"]

        db.execute("DELETE FROM binds WHERE code=? AND machine_id=?", (code, target))
        db.execute("UPDATE cards SET unbind_used=unbind_used+1 WHERE code=?", (code,))
        left = max(0, card["unbind_limit"] - card["unbind_used"] - 1)

    webhook.emit(app, "device.unbound", card, {"machine_id": target})
    log("unbind", app["app_id"], code, machine, ip, "OK",
        "自助解绑（解绑了 %s）" % ("本机" if target == machine else "旧设备"))
    return {"ok": True,
            "msg": "解绑成功，剩余换绑次数 %d" % left,
            "data": {"unbind_left": left, "unbound_machine": target}}
