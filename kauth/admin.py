#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理端业务逻辑：制卡、卡密管理、应用、套餐、日志、审计、WebHook、公告"""
from __future__ import annotations

import threading
import time

from . import config, db, security, service
from .util import (DAY, clean_prefix, day_start, fmt_time, gen_card,
                   gen_hex, gen_token, now)

# 当前请求的操作者（thread-local：ThreadingHTTPServer 一请求一线程）。
# 定了这个就不用给几十个 audit() 调用点挨个加 actor 参数。
_actor = threading.local()


def set_actor(name: str) -> None:
    _actor.name = name or "admin"


def current_actor() -> str:
    return getattr(_actor, "name", "admin")


def _day_ts(raw, end: bool = False):
    """把 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM' 转成本地时间戳。

    只有日期时按整天算：起点取那天 0 点，终点取次日 0 点（左闭右开）。
    带时分时精确到秒。解析不了返回 None，让调用方忽略该条件。
    """
    s = str(raw or "").strip()
    if not s:
        return None
    for fmt, whole_day in (("%Y-%m-%d %H:%M:%S", False),
                           ("%Y-%m-%d %H:%M", False),
                           ("%Y-%m-%d", True)):
        try:
            t = int(time.mktime(time.strptime(s, fmt)))
        except ValueError:
            continue
        if whole_day:
            return t + (DAY if end else 0)
        return t + (1 if end else 0)
    return None


# ---------------------------------------------------------------- 审计
def audit(action: str, target: str = "", detail: str = "", ip: str = "",
          actor: str = "") -> None:
    try:
        db.execute(
            "INSERT INTO audits(ts,actor,ip,action,target,detail) VALUES(?,?,?,?,?,?)",
            (now(), actor or current_actor(), ip or "", action, target or "", detail or ""),
        )
    except Exception:
        pass


# ---------------------------------------------------------------- 概览
def overview() -> dict:
    t = now()
    d0 = day_start()

    def n(sql, *a):
        return db.scalar(sql, a)

    stats = {
        "cards_total": n("SELECT COUNT(*) FROM cards"),
        "cards_unused": n("SELECT COUNT(*) FROM cards WHERE status='unused'"),
        "cards_active": n("SELECT COUNT(*) FROM cards WHERE status='active'"),
        "cards_banned": n("SELECT COUNT(*) FROM cards WHERE status='banned'"),
        "cards_expired": n("SELECT COUNT(*) FROM cards WHERE status='expired'"),
        "cards_used_up": n("SELECT COUNT(*) FROM cards WHERE status='used_up'"),
        "devices": n("SELECT COUNT(*) FROM binds"),
        "online": n("SELECT COUNT(DISTINCT machine_id) FROM binds WHERE last_seen > ?", t - 300),
        "checks_today": n("SELECT COUNT(*) FROM logs WHERE ts >= ?", d0),
        "checks_total": n("SELECT COUNT(*) FROM logs"),
        "cards_today": n("SELECT COUNT(*) FROM cards WHERE created_at >= ?", d0),
        "active_today": n("SELECT COUNT(DISTINCT code) FROM logs"
                          " WHERE ts >= ? AND machine_id != ''", d0),
        "apps": n("SELECT COUNT(*) FROM apps"),
        "plans": n("SELECT COUNT(*) FROM plans"),
    }

    trend = []
    for i in range(6, -1, -1):
        s = day_start(-i)
        trend.append({
            "label": fmt_time(s)[5:10],
            "value": n("SELECT COUNT(*) FROM logs WHERE ts >= ? AND ts < ?", s, s + DAY),
        })

    plans = db.query(
        "SELECT plan, COUNT(*) AS n FROM cards WHERE plan != ''"
        " GROUP BY plan ORDER BY n DESC LIMIT 8")
    plan_dist = [{"plan": r["plan"], "value": r["n"]} for r in plans]

    # 最近记录：优先展示「有信息量」的动作。整页都是同一张卡的心跳等于没信息，
    # 所以先按卡密去重，再按动作优先级挑，心跳只在凑不够时补位。
    def _row(r):
        return {
            "time": fmt_time(r["ts"]), "code": r["code"], "app_id": r["app_id"],
            "machine_id": r["machine_id"], "ip": r["ip"],
            "action": r["action"], "result": r["result"],
            "result_text": service.RESULT_TEXT.get(r["result"], r["result"]),
        }

    recent, seen = [], set()
    for r in db.query("SELECT * FROM logs WHERE action != 'heartbeat'"
                      " ORDER BY id DESC LIMIT 80"):
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        recent.append(_row(r))
        if len(recent) >= 15:
            break
    if len(recent) < 15:
        for r in db.query("SELECT * FROM logs WHERE action = 'heartbeat'"
                          " ORDER BY id DESC LIMIT 400"):
            if r["code"] in seen:
                continue
            seen.add(r["code"])
            recent.append(_row(r))
            if len(recent) >= 15:
                break

    # 结果码分布，用于排障（total 供前端算占比）
    dist = db.query("SELECT result, COUNT(*) AS n FROM logs GROUP BY result ORDER BY n DESC LIMIT 8")
    result_dist = [{"result": r["result"],
                    "text": service.RESULT_TEXT.get(r["result"], r["result"]),
                    "value": r["n"]} for r in dist]
    result_total = sum(x["value"] for x in result_dist)

    return {"ok": True, "stats": stats, "trend": trend,
            "plan_dist": plan_dist, "recent": recent, "result_dist": result_dist,
            "result_total": result_total,
            "token_check": security.token_strength(),
            "result_text": service.RESULT_TEXT}


# ---------------------------------------------------------------- 卡密
def cards(q="", status="", app="", plan="", card_type="", batch="",
          page=1, size=50, agent="") -> dict:
    try:
        page = max(1, int(page))
        size = max(1, min(int(size), 500))
    except (TypeError, ValueError):
        page, size = 1, 50

    where, args = [], []
    if agent not in ("", None):
        # agent=0 表示「管理员自己制的」，agent=<id> 指定代理商
        where.append("agent_id=?")
        args.append(int(agent) if str(agent).isdigit() else 0)
    if q:
        like = "%" + str(q).strip().upper() + "%"
        where.append("(code LIKE ? OR note LIKE ? OR batch LIKE ?)")
        args += [like, like, like]
    if status == "expired":
        where.append("((card_type IN ('time','hour') AND expires_at IS NOT NULL AND expires_at < ?)"
                     " OR status IN ('expired','used_up'))")
        args.append(now())
    elif status:
        where.append("status = ?")
        args.append(status)
    if app:
        where.append("app_id = ?")
        args.append(app)
    if plan:
        where.append("plan = ?")
        args.append(plan)
    if card_type:
        where.append("card_type = ?")
        args.append(card_type)
    if batch:
        where.append("batch = ?")
        args.append(batch)

    w = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.scalar("SELECT COUNT(*) FROM cards %s" % w, args)
    rows = db.query(
        "SELECT * FROM cards %s ORDER BY created_at DESC, code DESC LIMIT ? OFFSET ?" % w,
        args + [size, (page - 1) * size])

    counts = {r["code"]: r["n"] for r in db.query(
        "SELECT code, COUNT(*) AS n FROM binds GROUP BY code")}
    apps = {r["app_id"]: r["name"] for r in db.query("SELECT app_id, name FROM apps")}
    t = now()

    items = []
    for r in rows:
        expired = bool(r["expires_at"] and r["expires_at"] < t)
        items.append({
            "code": r["code"],
            "app_id": r["app_id"],
            "app_name": apps.get(r["app_id"]) or (r["app_id"] or "-"),
            "agent_id": r["agent_id"] if "agent_id" in r.keys() else 0,
            "agent_name": (r["agent_name"] if "agent_name" in r.keys() else "") or "",
            "plan": r["plan"],
            "card_type": r["card_type"],
            "card_type_text": service.CARD_TYPES.get(r["card_type"], r["card_type"]),
            "duration_days": r["duration_days"],
            "total_value": r["total_value"],
            "used_value": r["used_value"],
            "remaining_value": max(0, r["total_value"] - r["used_value"]),
            "max_devices": r["max_devices"],
            "unbind_left": max(0, r["unbind_limit"] - r["unbind_used"]),
            "status": r["status"],
            "expired": expired,
            "note": r["note"],
            "batch": r["batch"],
            "devices": counts.get(r["code"], 0),
            "created_text": fmt_time(r["created_at"]),
            "activated_text": fmt_time(r["activated_at"]) if r["activated_at"] else "-",
            # expires_at 为空有两义：真永久卡 / 尚未激活。必须分清，
            # 否则未激活的普通时间卡会被显示成「永久」。
            "expires_text": (
                fmt_time(r["expires_at"]) if r["expires_at"] is not None
                else ("未激活 · %d天" % r["duration_days"]
                      if (r["card_type"] == "time" and r["duration_days"] > 0)
                      else ("未激活 · %d小时" % r["duration_days"]
                            if (r["card_type"] == "hour" and r["duration_days"] > 0)
                            else "永久"))
            ),
            "last_used_text": fmt_time(r["last_used_at"]) if r["last_used_at"] else "-",
        })
    return {"ok": True, "items": items, "total": total, "page": page, "size": size}


def gen_cards(data: dict) -> dict:
    try:
        count = max(1, min(int(data.get("count", 1)), 10000))
        duration = max(0, int(data.get("duration_days", 30)))
        total_value = max(0, int(data.get("total_value", 0)))
        devices = max(1, int(data.get("max_devices", 1)))
        unbind = max(0, int(data.get("unbind_limit", 1)))
    except (TypeError, ValueError):
        return {"ok": False, "err": "BAD_PARAM", "msg": "参数格式错误"}

    app_id = str(data.get("app_id") or "").strip()
    plan_id = data.get("plan_id")
    try:
        plan_id = int(plan_id) if plan_id not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        plan_id = None

    plan_name = str(data.get("plan") or "").strip()
    card_type = str(data.get("card_type") or "time").strip()
    if card_type not in service.CARD_TYPES:
        card_type = "time"
    prefix = clean_prefix(data.get("prefix"))
    note = str(data.get("note") or "").strip()
    batch = str(data.get("batch") or "").strip() or time_stamp()

    if plan_id:
        p = db.one("SELECT * FROM plans WHERE id=?", (plan_id,))
        if not p:
            return {"ok": False, "err": "BAD_PLAN", "msg": "套餐不存在"}
        plan_name = p["name"]
        card_type = p["card_type"]
        duration = p["duration_days"]
        total_value = p["total_value"]
        devices = p["max_devices"]
        unbind = p["unbind_limit"]
        if p["app_id"]:
            app_id = p["app_id"]

    if not app_id:
        row = db.query("SELECT app_id FROM apps ORDER BY id LIMIT 1")
        app_id = row[0]["app_id"] if row else ""

    if card_type not in ("time", "hour") and total_value <= 0:
        return {"ok": False, "err": "BAD_PARAM", "msg": "次数卡/点数卡必须设置初始额度"}

    # 小时卡复用 duration_days 字段存小时数；正整数值即可，负数/非法已被 int() 挡掉
    if card_type == "hour" and duration <= 0:
        return {"ok": False, "err": "BAD_PARAM", "msg": "小时卡必须设置大于 0 的小时数"}

    t = now()
    codes = []
    while len(codes) < count:
        code = gen_card(prefix)
        if db.one("SELECT 1 AS x FROM cards WHERE code=?", (code,)):
            continue
        try:
            db.execute(
                "INSERT INTO cards(code,app_id,plan_id,plan,card_type,duration_days,"
                "total_value,used_value,max_devices,unbind_limit,unbind_used,status,"
                "note,batch,created_at) VALUES(?,?,?,?,?,?,?,0,?,?,0,'unused',?,?,?)",
                (code, app_id, plan_id, plan_name, card_type, duration,
                 total_value, devices, unbind, note, batch, t),
            )
        except Exception as e:
            return {"ok": False, "err": "DB_ERROR", "msg": str(e)}
        codes.append(code)

    audit("card.generate", batch, "生成 %d 张卡密" % len(codes))
    return {"ok": True, "batch": batch, "codes": codes, "count": len(codes)}


def time_stamp() -> str:
    import time as _t
    return _t.strftime("%Y%m%d%H%M%S")


def card_action(codes, action: str, amount: int = 0, ip: str = "") -> dict:
    if isinstance(codes, str):
        codes = [codes]
    codes = [str(c).strip().upper() for c in (codes or []) if str(c).strip()]
    if not codes:
        return {"ok": False, "err": "BAD_PARAM", "msg": "未选择卡密"}
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = 0

    n = 0
    t = now()
    for code in codes:
        row = db.one("SELECT * FROM cards WHERE code=?", (code,))
        if not row:
            continue

        if action == "ban":
            db.execute("UPDATE cards SET status='banned' WHERE code=?", (code,))
            service.log("ban", row["app_id"], code, "", ip, "OK", "后台封禁")
        elif action == "unban":
            st = "active" if row["activated_at"] else "unused"
            if row["card_type"] in ("time", "hour") and row["expires_at"] \
                    and row["expires_at"] < t:
                st = "expired"
            elif row["card_type"] not in ("time", "hour") and row["total_value"] > 0 \
                    and row["used_value"] >= row["total_value"]:
                st = "used_up"
            db.execute("UPDATE cards SET status=? WHERE code=?", (st, code))
        elif action == "unbind":
            db.execute("DELETE FROM binds WHERE code=?", (code,))
        elif action == "unbind_reset":
            db.execute("UPDATE cards SET unbind_used=0 WHERE code=?", (code,))
        elif action == "renew":
            if row["card_type"] in ("time", "hour"):
                base = row["expires_at"] or t
                if base < t:
                    base = t
                unit = service.HOUR if row["card_type"] == "hour" else DAY
                db.execute("UPDATE cards SET expires_at=?, status='active' WHERE code=?",
                           (base + amount * unit, code))
            else:
                newv = max(0, row["total_value"] + amount)
                st = "active" if row["used_value"] < newv else "used_up"
                db.execute("UPDATE cards SET total_value=?, status=? WHERE code=?",
                           (newv, st, code))
        elif action == "reset":
            db.execute("UPDATE cards SET status='unused', activated_at=NULL,"
                       " expires_at=NULL, used_value=0, unbind_used=0,"
                       " last_used_at=NULL WHERE code=?", (code,))
            db.execute("DELETE FROM binds WHERE code=?", (code,))
        elif action == "delete":
            db.execute("DELETE FROM cards WHERE code=?", (code,))
            db.execute("DELETE FROM binds WHERE code=?", (code,))
        elif action == "ban_devices":
            db.execute("DELETE FROM binds WHERE code=?", (code,))
            db.execute("UPDATE cards SET status='banned' WHERE code=?", (code,))
        else:
            return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作：%s" % action}
        n += 1

    audit("card." + action, ",".join(codes[:5]) + ("..." if len(codes) > 5 else ""),
          "受影响 %d 张" % n, ip)
    return {"ok": True, "affected": n}


def export_cards(app="", status="", batch="") -> str:
    """导出 CSV（Excel 可直接打开）"""
    d = cards(app=app, status=status, batch=batch, page=1, size=500)
    lines = ["卡密,应用,套餐,类型,状态,设备,到期时间,剩余额度,备注,批次,创建时间"]
    for x in d["items"]:
        row = [x["code"], x["app_name"], x["plan"], x["card_type_text"],
               x["status"], "%d/%d" % (x["devices"], x["max_devices"]),
               x["expires_text"], str(x["remaining_value"]) if x["total_value"] else "-",
               x["note"], x["batch"], x["created_text"]]
        lines.append(",".join('"%s"' % str(c).replace('"', '""') for c in row))
    return "\r\n".join(lines)


# ---------------------------------------------------------------- 应用
def list_apps() -> dict:
    items = []
    for r in db.query("SELECT * FROM apps ORDER BY id"):
        n = db.scalar("SELECT COUNT(*) FROM cards WHERE app_id=?", (r["app_id"],))
        used = db.scalar(
            "SELECT COUNT(*) FROM cards WHERE app_id=? AND status!='unused'", (r["app_id"],))
        items.append({
            "id": r["id"], "name": r["name"], "app_id": r["app_id"],
            "app_secret": r["app_secret"], "status": r["status"],
            "require_sign": r["require_sign"],
            "heartbeat_interval": r["heartbeat_interval"],
            "webhook_url": r["webhook_url"], "note": r["note"],
            "cards": n, "used": used, "created_text": fmt_time(r["created_at"]),
        })
    return {"ok": True, "items": items}


def app_action(data: dict, ip: str = "") -> dict:
    action = data.get("action", "")
    aid = data.get("id")

    if action == "create":
        name = str(data.get("name") or "").strip()
        if not name:
            return {"ok": False, "err": "BAD_PARAM", "msg": "应用名不能为空"}
        app_id = "app_" + gen_hex(8)
        secret = gen_hex(24)
        try:
            hb = max(30, int(data.get("heartbeat_interval", 180)))
        except (TypeError, ValueError):
            hb = 180
        db.execute(
            "INSERT INTO apps(name,app_id,app_secret,status,require_sign,"
            "heartbeat_interval,webhook_url,note,created_at) VALUES(?,?,?,'active',?,?,?,?,?)",
            (name, app_id, secret, 1 if data.get("require_sign", True) else 0,
             hb, str(data.get("webhook_url") or "").strip(),
             str(data.get("note") or "").strip(), now()))
        audit("app.create", name, app_id, ip)
        return {"ok": True, "app_id": app_id, "app_secret": secret}

    if not aid:
        return {"ok": False, "err": "BAD_PARAM", "msg": "缺少应用 ID"}

    if action == "update":
        try:
            hb = max(30, int(data.get("heartbeat_interval", 180)))
        except (TypeError, ValueError):
            hb = 180
        db.execute(
            "UPDATE apps SET name=?, require_sign=?, heartbeat_interval=?,"
            " webhook_url=?, note=?, status=? WHERE id=?",
            (str(data.get("name") or "").strip(),
             1 if data.get("require_sign", True) else 0, hb,
             str(data.get("webhook_url") or "").strip(),
             str(data.get("note") or "").strip(),
             str(data.get("status") or "active"), int(aid)))
        audit("app.update", str(aid), data.get("name", ""), ip)
        return {"ok": True}

    if action == "reset_secret":
        secret = gen_hex(24)
        db.execute("UPDATE apps SET app_secret=? WHERE id=?", (secret, int(aid)))
        audit("app.reset_secret", str(aid), "", ip)
        return {"ok": True, "app_secret": secret}

    if action == "delete":
        row = db.one("SELECT * FROM apps WHERE id=?", (int(aid),))
        if not row:
            return {"ok": False, "err": "NOT_FOUND", "msg": "应用不存在"}
        n = db.scalar("SELECT COUNT(*) FROM cards WHERE app_id=?", (row["app_id"],))
        if n and not data.get("force"):
            return {"ok": False, "err": "HAS_CARDS",
                    "msg": "该应用下还有 %d 张卡密，确认后将一并删除" % n}
        db.execute("DELETE FROM apps WHERE id=?", (int(aid),))
        if data.get("force"):
            db.execute("DELETE FROM cards WHERE app_id=?", (row["app_id"],))
            db.execute("DELETE FROM binds WHERE code NOT IN (SELECT code FROM cards)")
        audit("app.delete", row["name"], "force=%s" % bool(data.get("force")), ip)
        return {"ok": True}

    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


# ---------------------------------------------------------------- 套餐
def list_plans() -> dict:
    apps = {r["app_id"]: r["name"] for r in db.query("SELECT app_id, name FROM apps")}
    items = []
    for r in db.query("SELECT * FROM plans ORDER BY id DESC"):
        n = db.scalar("SELECT COUNT(*) FROM cards WHERE plan_id=?", (r["id"],))
        items.append({
            "id": r["id"], "name": r["name"], "app_id": r["app_id"],
            "app_name": apps.get(r["app_id"], "通用") if r["app_id"] else "通用",
            "card_type": r["card_type"],
            "card_type_text": service.CARD_TYPES.get(r["card_type"], r["card_type"]),
            "duration_days": r["duration_days"], "total_value": r["total_value"],
            "max_devices": r["max_devices"], "unbind_limit": r["unbind_limit"],
            "price": r["price"], "note": r["note"], "cards": n,
        })
    return {"ok": True, "items": items}


def plan_action(data: dict, ip: str = "") -> dict:
    action = data.get("action", "")

    if action in ("create", "update"):
        name = str(data.get("name") or "").strip()
        if not name:
            return {"ok": False, "err": "BAD_PARAM", "msg": "套餐名不能为空"}
        card_type = str(data.get("card_type") or "time")
        if card_type not in service.CARD_TYPES:
            card_type = "time"
        try:
            dur = max(0, int(data.get("duration_days", 30)))
            val = max(0, int(data.get("total_value", 0)))
            dev = max(1, int(data.get("max_devices", 1)))
            unb = max(0, int(data.get("unbind_limit", 1)))
            price = float(data.get("price", 0) or 0)
        except (TypeError, ValueError):
            return {"ok": False, "err": "BAD_PARAM", "msg": "参数格式错误"}

        if card_type not in ("time", "hour"):
            dur = 0
        if card_type in ("time", "hour"):
            val = 0

        fields = (str(data.get("app_id") or "").strip(), name, card_type, dur, val,
                  dev, unb, price, str(data.get("note") or "").strip())
        if action == "create":
            new_id = db.insert_id(
                "INSERT INTO plans(app_id,name,card_type,duration_days,total_value,"
                "max_devices,unbind_limit,price,note,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)", fields + (now(),))
            audit("plan.create", name, "", ip)
        else:
            db.execute("UPDATE plans SET app_id=?,name=?,card_type=?,duration_days=?,"
                       "total_value=?,max_devices=?,unbind_limit=?,price=?,note=? WHERE id=?",
                       fields + (int(data.get("id", 0)),))
            audit("plan.update", name, "", ip)
        return {"ok": True, "id": new_id,
                    "data": {"id": new_id, "name": name,
                              "card_type": card_type,
                              "duration_days": dur, "total_value": val,
                              "max_devices": dev, "unbind_limit": unb}}

    if action == "delete":
        db.execute("DELETE FROM plans WHERE id=?", (int(data.get("id", 0)),))
        audit("plan.delete", str(data.get("id")), "", ip)
        return {"ok": True}

    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


# ---------------------------------------------------------------- 日志
def logs(page=1, size=50, q="", result="", action="", app="",
         ts_from="", ts_to="", limit=0) -> dict:
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 50
    # 兼容旧的 ?limit=N 调用。注意 httpd 传进来的是字符串，
    # 空串/"0" 都不能当真正处理，否则 size 会被打成 0。
    try:
        lim = int(limit or 0)
    except (TypeError, ValueError):
        lim = 0
    if lim > 0:
        size, page = lim, 1
    size = max(1, min(size, 500))

    where, args = [], []
    if q:
        like = "%" + str(q).strip().upper() + "%"
        where.append("(code LIKE ? OR machine_id LIKE ? OR ip LIKE ?)")
        args += [like, "%" + str(q).strip() + "%", "%" + str(q).strip() + "%"]
    if result:
        where.append("result = ?")
        args.append(result)
    if action:
        where.append("action = ?")
        args.append(action)
    if app:
        where.append("app_id = ?")
        args.append(app)
    start, end = _day_ts(ts_from), _day_ts(ts_to, end=True)
    if start is not None:
        where.append("ts >= ?")
        args.append(start)
    if end is not None:
        where.append("ts < ?")
        args.append(end)
    w = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.scalar("SELECT COUNT(*) FROM logs %s" % w, args)
    items = []
    for r in db.query("SELECT * FROM logs %s ORDER BY id DESC LIMIT ? OFFSET ?" % w,
                      args + [size, (page - 1) * size]):
        items.append({
            "time": fmt_time(r["ts"]), "app_id": r["app_id"], "code": r["code"],
            "machine_id": r["machine_id"], "ip": r["ip"], "action": r["action"],
            "result": r["result"],
            "result_text": service.RESULT_TEXT.get(r["result"], r["result"]),
            "detail": r["detail"],
        })
    return {"ok": True, "items": items, "total": total, "page": page, "size": size,
            "result_text": service.RESULT_TEXT}


def audits(page=1, size=50, q="", action="", ts_from="", ts_to="", limit=0) -> dict:
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 50
    try:
        lim = int(limit or 0)
    except (TypeError, ValueError):
        lim = 0
    if lim > 0:
        size, page = lim, 1
    size = max(1, min(size, 500))

    where, args = [], []
    if q:
        like = "%" + str(q).strip() + "%"
        where.append("(action LIKE ? OR target LIKE ? OR detail LIKE ? OR ip LIKE ?)")
        args += [like, like, like, like]
    if action:
        where.append("action = ?")
        args.append(action)
    start, end = _day_ts(ts_from), _day_ts(ts_to, end=True)
    if start is not None:
        where.append("ts >= ?")
        args.append(start)
    if end is not None:
        where.append("ts < ?")
        args.append(end)
    w = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.scalar("SELECT COUNT(*) FROM audits %s" % w, args)
    items = [{"time": fmt_time(r["ts"]), "actor": r["actor"], "ip": r["ip"],
              "action": r["action"], "target": r["target"], "detail": r["detail"]}
             for r in db.query("SELECT * FROM audits %s ORDER BY id DESC LIMIT ? OFFSET ?" % w,
                               args + [size, (page - 1) * size])]
    return {"ok": True, "items": items, "total": total, "page": page, "size": size}


# ---------------------------------------------------------------- WebHook
def list_webhooks() -> dict:
    apps = {r["app_id"]: r["name"] for r in db.query("SELECT app_id, name FROM apps")}
    items = []
    for r in db.query("SELECT * FROM webhooks ORDER BY id DESC"):
        items.append({
            "id": r["id"], "app_id": r["app_id"],
            "app_name": apps.get(r["app_id"], "全局") if r["app_id"] else "全局",
            "url": r["url"], "events": r["events"], "secret": r["secret"],
            "enabled": r["enabled"], "created_text": fmt_time(r["created_at"]),
        })
    return {"ok": True, "items": items}


def webhook_action(data: dict, ip: str = "") -> dict:
    action = data.get("action", "")
    if action == "create":
        url = str(data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "err": "BAD_PARAM", "msg": "回调地址必须以 http(s):// 开头"}
        events = data.get("events") or ["card.activated"]
        if isinstance(events, list):
            events = ",".join(events)
        db.execute("INSERT INTO webhooks(app_id,url,events,secret,enabled,created_at)"
                   " VALUES(?,?,?,?,?,?)",
                   (str(data.get("app_id") or "").strip(), url, events,
                    str(data.get("secret") or gen_hex(16)), 1, now()))
        audit("webhook.create", url, "", ip)
        return {"ok": True}
    if action == "toggle":
        db.execute("UPDATE webhooks SET enabled=? WHERE id=?",
                   (1 if data.get("enabled") else 0, int(data.get("id", 0))))
        return {"ok": True}
    if action == "delete":
        db.execute("DELETE FROM webhooks WHERE id=?", (int(data.get("id", 0)),))
        audit("webhook.delete", str(data.get("id")), "", ip)
        return {"ok": True}
    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


# ---------------------------------------------------------------- 公告
def list_notices() -> dict:
    items = [{"id": r["id"], "app_id": r["app_id"], "title": r["title"],
              "content": r["content"], "level": r["level"],
              "enabled": r["enabled"], "created_text": fmt_time(r["created_at"])}
             for r in db.query("SELECT * FROM notices ORDER BY id DESC")]
    return {"ok": True, "items": items}


def notice_action(data: dict, ip: str = "") -> dict:
    action = data.get("action", "")
    if action in ("create", "update"):
        title = str(data.get("title") or "").strip()
        if not title:
            return {"ok": False, "err": "BAD_PARAM", "msg": "公告标题不能为空"}
        if action == "create":
            db.execute("INSERT INTO notices(app_id,title,content,level,enabled,created_at)"
                       " VALUES(?,?,?,?,?,?)",
                       (str(data.get("app_id") or "").strip(), title,
                        str(data.get("content") or ""), str(data.get("level") or "info"),
                        1 if data.get("enabled", True) else 0, now()))
            audit("notice.create", title, "", ip)
        else:
            db.execute("UPDATE notices SET title=?,content=?,level=?,enabled=?,app_id=?"
                       " WHERE id=?",
                       (title, str(data.get("content") or ""),
                        str(data.get("level") or "info"),
                        1 if data.get("enabled", True) else 0,
                        str(data.get("app_id") or "").strip(),
                        int(data.get("id", 0))))
        return {"ok": True}
    if action == "delete":
        db.execute("DELETE FROM notices WHERE id=?", (int(data.get("id", 0)),))
        return {"ok": True}
    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


# ---------------------------------------------------------------- 设置
def get_settings() -> dict:
    c = config.CFG
    return {"ok": True, "settings": {
        "site_name": c.get("site_name", ""),
        "site_desc": c.get("site_desc", ""),
        "announcement": c.get("announcement", ""),
        "maintenance": bool(c.get("maintenance")),
        "require_sign": bool(c.get("require_sign")),
        "clock_skew": c.get("clock_skew", 300),
        "nonce_ttl": c.get("nonce_ttl", 600),
        "rate_limit": c.get("rate_limit", 120),
        "min_client_version": c.get("min_client_version", ""),
        "public_base_url": c.get("public_base_url", ""),
        "log_retention_days": c.get("log_retention_days", 90),
        "token_check": security.token_strength(),
    }}


def save_settings(data: dict, ip: str = "") -> dict:
    c = config.CFG
    for k in ("site_name", "site_desc", "announcement", "min_client_version",
              "public_base_url"):
        if k in data:
            c[k] = str(data.get(k) or "").strip()
    if c.get("public_base_url"):
        u = c["public_base_url"]
        if not u.startswith(("http://", "https://")):
            c["public_base_url"] = "http://" + u
        c["public_base_url"] = c["public_base_url"].rstrip("/")
    for k in ("maintenance", "require_sign"):
        if k in data:
            c[k] = bool(data.get(k))
    for k, lo, hi in (("clock_skew", 30, 3600), ("nonce_ttl", 60, 86400),
                      ("rate_limit", 0, 100000),
                      ("log_retention_days", 0, 3650)):
        if k in data:
            try:
                c[k] = max(lo, min(int(data[k]), hi))
            except (TypeError, ValueError):
                pass
    config.save(c)
    audit("settings.save", "", ",".join(sorted(data.keys())), ip)
    return {"ok": True, "settings": get_settings()["settings"]}


def cleanup_logs(days=None, ip: str = "") -> dict:
    """删除超过保留期的校验日志。

    心跳是每 3 分钟一次，一台机器一天 480 条——不回收的话日志表会一直长，
    几个月后卡密库翻页都会变慢。默认保留 90 天，后台可改，0 = 不清理。
    """
    if days is None:
        days = config.CFG.get("log_retention_days", 90)
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0
    if days <= 0:
        return {"ok": True, "deleted": 0, "days": 0, "msg": "未启用自动清理"}
    cutoff = now() - days * DAY
    total = db.scalar("SELECT COUNT(*) FROM logs")
    n = db.execute("DELETE FROM logs WHERE ts < ?", (cutoff,))
    audit("system.cleanup_logs", "", "删除 %d 条（早于 %d 天）" % (n, days), ip)
    return {"ok": True, "deleted": n, "left": total - n, "days": days}


def backup_info() -> dict:
    """备份列表 + 数据库当前大小，给「数据维护」那块用。"""
    import os
    rows = db.list_backups()
    for r in rows:
        r["time_text"] = fmt_time(r["mtime"])
        r["size_text"] = ("%.1f MB" % (r["size"] / 1048576.0)
                          if r["size"] >= 1048576
                          else "%.0f KB" % (r["size"] / 1024.0))
    size = os.path.getsize(config.DB_FILE) if os.path.isfile(config.DB_FILE) else 0
    return {"ok": True, "items": rows,
            "db_size_text": ("%.1f MB" % (size / 1048576.0)
                             if size >= 1048576 else "%.0f KB" % (size / 1024.0)),
            "logs_total": db.scalar("SELECT COUNT(*) FROM logs"),
            "retention_days": config.CFG.get("log_retention_days", 90)}


def rotate_admin_token(ip: str = "") -> dict:
    tok = security.rotate_token()
    audit("settings.rotate_token", "", "管理员令牌已重置", ip)
    return {"ok": True, "admin_token": tok}
