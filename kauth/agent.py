#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代理商（分销）子系统。

设计约束（来自业务要求）：

1. 代理商只能**制卡**和**操作自己制的卡**，没有任何删除权限；
2. 能制哪些应用、每种卡多少张，由管理员逐条下发配额；
3. 所有动作落在同一个库里，管理员那边实时可见（卡密带 agent_id，审计带 actor）。

配额是这里唯一需要小心的东西：制卡必须先原子扣减配额再落库，
否则并发请求能把 100 张的配额刷成 200 张。见 `_take_quota()`。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from . import db, service, throttle
from .util import clean_prefix, fmt_time, gen_card, now

TOKEN_TTL = 7 * 86400          # 代理商登录有效期（秒）
PBKDF2_ROUNDS = 120000

# 代理商允许的卡密操作。delete / ban_devices / renew 一律不给：
#   - delete     明确禁止
#   - renew      能把自己的卡无限续期，等于绕过配额
#   - ban_devices 语义含批量封禁，收在 ban 里更清楚
AGENT_ACTIONS = ("ban", "unban", "unbind", "unbind_reset", "reset")


# ---------------------------------------------------------------- 密码
def hash_password(pwd: str, salt: str = "") -> tuple:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"),
                            salt.encode("utf-8"), PBKDF2_ROUNDS)
    return h.hex(), salt


def check_password(pwd: str, pwd_hash: str, salt: str) -> bool:
    h, _ = hash_password(pwd, salt)
    return hmac.compare_digest(h, pwd_hash or "")


# ---------------------------------------------------------------- 审计
def audit(agent: dict, action: str, target: str = "", detail: str = "",
          ip: str = "") -> None:
    """写进主审计表，actor 用 agent:<用户名>，主后台能直接筛出来。"""
    try:
        db.execute(
            "INSERT INTO audits(ts,actor,ip,action,target,detail) VALUES(?,?,?,?,?,?)",
            (now(), "agent:%s" % (agent.get("username") or "?"),
             ip or "", action, target or "", detail or ""),
        )
    except Exception:
        pass


# ---------------------------------------------------------------- 登录
def login(username: str, password: str, ip: str = "") -> dict:
    u = str(username or "").strip()
    p = str(password or "")
    if not u or not p:
        return {"ok": False, "err": "BAD_PARAM", "msg": "请输入账号和密码"}

    # 代理商账号同样按账号节流，撞库打不动
    st = throttle.status("agent", u)
    if st["locked"]:
        m = max(1, int((st["retry_after"] + 59) // 60))
        return {"ok": False, "err": "LOCKED", "retry_after": st["retry_after"],
                "msg": "密码错误次数过多，请 %d 分钟后再试" % m}

    row = db.one("SELECT * FROM agents WHERE username=?", (u,))
    if not row or not check_password(p, row["pwd_hash"], row["pwd_salt"]):
        throttle.fail("agent", u)
        return {"ok": False, "err": "BAD_LOGIN", "msg": "账号或密码错误"}
    if row["status"] != "active":
        return {"ok": False, "err": "AGENT_DISABLED", "msg": "该账号已被停用"}

    throttle.reset("agent", u)
    tok = secrets.token_urlsafe(32)
    exp = now() + TOKEN_TTL
    db.execute("UPDATE agents SET token=?, token_exp=?, last_login_at=?,"
               " last_login_ip=? WHERE id=?", (tok, exp, now(), ip, row["id"]))
    audit(dict(row), "agent.login", ip=ip)
    return {"ok": True, "token": tok, "expires_at": exp,
            "agent": _public(dict(row), tok)}


def check(token: str):
    """用代理商令牌换取 agent 记录。令牌无效/过期/账号停用都返回 None。"""
    t = str(token or "").strip()
    if not t:
        return None
    row = db.one("SELECT * FROM agents WHERE token=?", (t,))
    if not row:
        return None
    if row["status"] != "active" or int(row["token_exp"] or 0) < now():
        return None
    return row


def logout(agent: dict) -> dict:
    db.execute("UPDATE agents SET token='', token_exp=0 WHERE id=?", (agent["id"],))
    return {"ok": True}


def _public(row: dict, token: str = "") -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"] or row["username"],
        "status": row["status"],
        "note": row["note"],
        "created_text": fmt_time(row["created_at"]),
        "last_login_text": fmt_time(row["last_login_at"]) if row["last_login_at"] else "-",
        "last_login_ip": row["last_login_ip"] or "-",
        "token": token or "",
    }


# ---------------------------------------------------------------- 管理端：CRUD
def list_agents() -> dict:
    rows = db.query("SELECT * FROM agents ORDER BY id DESC")
    items = []
    for r in rows:
        apps = [x["app_id"] for x in db.query(
            "SELECT app_id FROM agent_apps WHERE agent_id=?", (r["id"],))]
        quotas = db.query(
            "SELECT q.*, a.name AS app_name FROM agent_quotas q"
            " LEFT JOIN apps a ON a.app_id=q.app_id"
            " WHERE q.agent_id=? ORDER BY q.app_id, q.card_type, q.duration_days",
            (r["id"],))
        made = db.scalar("SELECT COUNT(*) FROM cards WHERE agent_id=?", (r["id"],))
        left = sum(max(0, q["quota_total"] - q["quota_used"]) for q in quotas)
        total = sum(q["quota_total"] for q in quotas)
        d = _public(r)
        d.update({
            "apps": apps,
            "quotas": [_quota_json(q) for q in quotas],
            "cards_made": made,
            "quota_total": total,
            "quota_left": left,
        })
        items.append(d)
    return {"ok": True, "items": items}


def _quota_json(q: dict) -> dict:
    return {
        "id": q["id"], "app_id": q["app_id"],
        "app_name": q.get("app_name") or q["app_id"],
        "card_type": q["card_type"],
        "card_type_text": service.CARD_TYPES.get(q["card_type"], q["card_type"]),
        "duration_days": q["duration_days"],
        "max_devices": q["max_devices"],
        "unbind_limit": q["unbind_limit"],
        "quota_total": q["quota_total"],
        "quota_used": q["quota_used"],
        "quota_left": max(0, q["quota_total"] - q["quota_used"]),
    }


def agent_action(data: dict, ip: str = "") -> dict:
    """管理端：create / update / delete / set_quotas / reset_password / kick"""
    from .admin import audit as admin_audit

    action = str(data.get("action") or "")

    if action == "create":
        u = str(data.get("username") or "").strip()
        p = str(data.get("password") or "").strip()
        if not u or not p:
            return {"ok": False, "err": "BAD_PARAM", "msg": "账号和密码都要填"}
        if len(p) < 6:
            return {"ok": False, "err": "BAD_PARAM", "msg": "密码至少 6 位"}
        if db.one("SELECT 1 AS x FROM agents WHERE username=?", (u,)):
            return {"ok": False, "err": "DUP_USER", "msg": "该账号已存在"}
        h, salt = hash_password(p)
        aid = db.insert_id(
            "INSERT INTO agents(username,pwd_hash,pwd_salt,name,status,note,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (u, h, salt, str(data.get("name") or u).strip(),
             "active", str(data.get("note") or "").strip(), now()))
        admin_audit("agent.create", u, "新建代理商", ip)
        return {"ok": True, "id": aid}

    aid = data.get("id")
    try:
        aid = int(aid)
    except (TypeError, ValueError):
        return {"ok": False, "err": "BAD_PARAM", "msg": "缺少代理商 id"}
    row = db.one("SELECT * FROM agents WHERE id=?", (aid,))
    if not row:
        return {"ok": False, "err": "NOT_FOUND", "msg": "代理商不存在"}

    if action == "update":
        sets, args = [], []
        for k, col in (("name", "name"), ("note", "note"), ("status", "status")):
            if k in data:
                sets.append(col + "=?")
                args.append(str(data.get(k) or "").strip())
        if sets:
            args.append(aid)
            db.execute("UPDATE agents SET %s WHERE id=?" % ",".join(sets), args)
        admin_audit("agent.update", row["username"], ",".join(sets), ip)
        return {"ok": True}

    if action == "reset_password":
        p = str(data.get("password") or "").strip()
        if len(p) < 6:
            return {"ok": False, "err": "BAD_PARAM", "msg": "密码至少 6 位"}
        h, salt = hash_password(p)
        # 改密码同时踢掉现有会话
        db.execute("UPDATE agents SET pwd_hash=?, pwd_salt=?, token='', token_exp=0"
                   " WHERE id=?", (h, salt, aid))
        admin_audit("agent.reset_password", row["username"], "重置密码", ip)
        return {"ok": True}

    if action == "kick":
        db.execute("UPDATE agents SET token='', token_exp=0 WHERE id=?", (aid,))
        admin_audit("agent.kick", row["username"], "强制下线", ip)
        return {"ok": True}

    if action == "delete":
        n = db.scalar("SELECT COUNT(*) FROM cards WHERE agent_id=?", (aid,))
        if n and not data.get("force"):
            return {"ok": False, "err": "HAS_CARDS",
                    "msg": "该代理商名下还有 %d 张卡密，确认后卡密会保留但归属清空" % n}
        db.execute("UPDATE cards SET agent_id=0, agent_name='' WHERE agent_id=?", (aid,))
        db.execute("DELETE FROM agent_apps WHERE agent_id=?", (aid,))
        db.execute("DELETE FROM agent_quotas WHERE agent_id=?", (aid,))
        db.execute("DELETE FROM agents WHERE id=?", (aid,))
        admin_audit("agent.delete", row["username"], "删除代理商", ip)
        return {"ok": True}

    if action == "set_quotas":
        """整体替换某代理商的配额清单。
        items: [{app_id, card_type, duration_days, max_devices, unbind_limit, quota_total}]
        """
        items = data.get("items") or []
        if not isinstance(items, list):
            return {"ok": False, "err": "BAD_PARAM", "msg": "items 必须是数组"}
        apps = {r["app_id"] for r in db.query("SELECT app_id FROM apps")}
        db.execute("DELETE FROM agent_quotas WHERE agent_id=?", (aid,))
        db.execute("DELETE FROM agent_apps WHERE agent_id=?", (aid,))
        keep_apps = set()
        for it in items:
            app_id = str(it.get("app_id") or "").strip()
            if app_id not in apps:
                continue
            ctype = str(it.get("card_type") or "time")
            if ctype not in ("time", "hour"):
                ctype = "time"
            try:
                dur = max(0, int(it.get("duration_days") or 0))
                dev = max(1, int(it.get("max_devices") or 1))
                unb = max(0, int(it.get("unbind_limit") or 0))
                tot = max(0, int(it.get("quota_total") or 0))
            except (TypeError, ValueError):
                continue
            db.execute(
                "INSERT OR IGNORE INTO agent_quotas(agent_id,app_id,card_type,"
                "duration_days,max_devices,unbind_limit,quota_total,quota_used)"
                " VALUES(?,?,?,?,?,?,?,0)",
                (aid, app_id, ctype, dur, dev, unb, tot))
            keep_apps.add(app_id)
        for a in keep_apps:
            db.execute("INSERT OR IGNORE INTO agent_apps(agent_id,app_id) VALUES(?,?)",
                       (aid, a))
        admin_audit("agent.set_quotas", row["username"], "%d 条配额" % len(items), ip)
        return {"ok": True}

    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


def topup_quota(data: dict, ip: str = "") -> dict:
    """给某条配额加量或改上限。"""
    from .admin import audit as admin_audit
    try:
        qid = int(data.get("id"))
        total = max(0, int(data.get("quota_total")))
    except (TypeError, ValueError):
        return {"ok": False, "err": "BAD_PARAM", "msg": "参数错误"}
    q = db.one("SELECT q.*, a.username FROM agent_quotas q"
               " LEFT JOIN agents a ON a.id=q.agent_id WHERE q.id=?", (qid,))
    if not q:
        return {"ok": False, "err": "NOT_FOUND", "msg": "配额不存在"}
    if total < q["quota_used"]:
        return {"ok": False, "err": "BAD_PARAM",
                "msg": "上限不能小于已用（%d）" % q["quota_used"]}
    db.execute("UPDATE agent_quotas SET quota_total=? WHERE id=?", (total, qid))
    admin_audit("agent.quota", "%s/%s" % (q["username"], q["app_id"]),
                "上限 %d → %d" % (q["quota_total"], total), ip)
    return {"ok": True}


# ---------------------------------------------------------------- 代理商端
def me(agent: dict) -> dict:
    rows = db.query(
        "SELECT q.*, a.name AS app_name FROM agent_quotas q"
        " LEFT JOIN apps a ON a.app_id=q.app_id"
        " WHERE q.agent_id=? ORDER BY q.app_id, q.card_type, q.duration_days",
        (agent["id"],))
    quotas = [_quota_json(r) for r in rows]
    made = db.scalar("SELECT COUNT(*) FROM cards WHERE agent_id=?", (agent["id"],))
    return {"ok": True, "agent": _public(agent), "quotas": quotas,
            "cards_made": made,
            "quota_left": sum(q["quota_left"] for q in quotas)}


def gen_cards(agent: dict, data: dict, ip: str = "") -> dict:
    """按配额制卡。所有规格来自配额记录，不接受客户端自填时长/设备数。"""
    try:
        qid = int(data.get("quota_id"))
        count = max(1, min(int(data.get("count") or 1), 1000))
    except (TypeError, ValueError):
        return {"ok": False, "err": "BAD_PARAM", "msg": "参数错误"}

    q = db.one("SELECT * FROM agent_quotas WHERE id=? AND agent_id=?",
               (qid, agent["id"]))
    if not q:
        return {"ok": False, "err": "BAD_QUOTA", "msg": "没有这条配额"}

    # 原子扣减：只有 quota_used + count <= quota_total 时才会更新成功。
    # 并发同一秒打进来，也只会有一批拿到资格。
    n = db.execute(
        "UPDATE agent_quotas SET quota_used = quota_used + ?"
        " WHERE id=? AND agent_id=? AND quota_used + ? <= quota_total",
        (count, qid, agent["id"], count))
    if n != 1:
        left = max(0, q["quota_total"] - q["quota_used"])
        return {"ok": False, "err": "QUOTA_EXCEEDED",
                "msg": "配额不足，剩余 %d 张" % left}

    prefix = clean_prefix(data.get("prefix"))
    note = str(data.get("note") or "").strip()
    aname = agent["name"] or agent["username"]
    batch = "%s-%s" % (agent["username"], now())
    t = now()
    codes = []
    try:
        while len(codes) < count:
            code = gen_card(prefix)
            if db.one("SELECT 1 AS x FROM cards WHERE code=?", (code,)):
                continue
            db.execute(
                "INSERT INTO cards(code,app_id,plan_id,plan,card_type,duration_days,"
                "total_value,used_value,max_devices,unbind_limit,unbind_used,status,"
                "note,batch,created_at,agent_id,agent_name)"
                " VALUES(?,?,NULL,'',?,?,0,0,?,?,0,'unused',?,?,?,?,?)",
                (code, q["app_id"], q["card_type"], q["duration_days"],
                 q["max_devices"], q["unbind_limit"], note, batch, t,
                 agent["id"], aname))
            codes.append(code)
    except Exception as e:
        # 落库失败就把配额退回去，别让代理商白扣
        db.execute("UPDATE agent_quotas SET quota_used = quota_used - ?"
                   " WHERE id=? AND quota_used >= ?", (count, qid, count))
        return {"ok": False, "err": "DB_ERROR", "msg": str(e)}

    audit(agent, "agent.card.generate", batch,
          "%s 生成 %d 张（%s %d）" % (q["app_id"], len(codes), q["card_type"],
                                     q["duration_days"]), ip)
    return {"ok": True, "batch": batch, "codes": codes, "count": len(codes),
            "quota_left": max(0, q["quota_total"] - q["quota_used"] - count)}


def cards(agent: dict, page=1, size=50, q="", status="", app="", card_type="") -> dict:
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(200, max(1, int(size)))
    except (TypeError, ValueError):
        size = 50

    where = ["agent_id=?"]
    args = [agent["id"]]
    if q:
        like = "%" + str(q).strip().upper() + "%"
        where.append("(code LIKE ? OR note LIKE ? OR batch LIKE ?)")
        args += [like, "%" + str(q).strip() + "%", "%" + str(q).strip() + "%"]
    if status:
        where.append("status=?")
        args.append(status)
    if app:
        where.append("app_id=?")
        args.append(app)
    if card_type:
        where.append("card_type=?")
        args.append(card_type)
    w = "WHERE " + " AND ".join(where)

    total = db.scalar("SELECT COUNT(*) FROM cards %s" % w, args)
    rows = db.query("SELECT * FROM cards %s ORDER BY created_at DESC, code DESC"
                    " LIMIT ? OFFSET ?" % w, args + [size, (page - 1) * size])
    dev = {r["code"]: r["n"] for r in db.query(
        "SELECT code, COUNT(*) AS n FROM binds GROUP BY code")}
    apps = {r["app_id"]: r["name"] for r in db.query("SELECT app_id, name FROM apps")}
    t = now()

    items = []
    for r in rows:
        expired = bool(r["expires_at"] and r["expires_at"] < t)
        items.append({
            "code": r["code"],
            "app_name": apps.get(r["app_id"]) or r["app_id"],
            "card_type": r["card_type"],
            "card_type_text": service.CARD_TYPES.get(r["card_type"], r["card_type"]),
            "status": r["status"],
            "expired": expired,
            "devices": dev.get(r["code"], 0),
            "max_devices": r["max_devices"],
            "unbind_left": max(0, r["unbind_limit"] - r["unbind_used"]),
            "note": r["note"],
            "batch": r["batch"],
            "created_text": fmt_time(r["created_at"]),
            "expires_text": (
                fmt_time(r["expires_at"]) if r["expires_at"] is not None
                else ("未激活 · %d天" % r["duration_days"]
                      if (r["card_type"] == "time" and r["duration_days"] > 0)
                      else ("未激活 · %d小时" % r["duration_days"]
                            if (r["card_type"] == "hour" and r["duration_days"] > 0)
                            else "永久"))),
        })
    return {"ok": True, "items": items, "total": total, "page": page, "size": size}


def card_action(agent: dict, codes, action: str, ip: str = "") -> dict:
    """代理商操作自己制的卡。动作白名单见 AGENT_ACTIONS，delete 永远进不来。"""
    if isinstance(codes, str):
        codes = [codes]
    codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
    if not codes:
        return {"ok": False, "err": "BAD_PARAM", "msg": "没有选中卡密"}
    if action not in AGENT_ACTIONS:
        return {"ok": False, "err": "FORBIDDEN",
                "msg": "无此权限：%s" % action}

    n = 0
    skipped = 0
    for code in codes:
        row = db.one("SELECT * FROM cards WHERE code=?", (code,))
        if not row:
            skipped += 1
            continue
        if int(row["agent_id"] or 0) != int(agent["id"]):
            skipped += 1          # 不是自己的卡，静默跳过
            continue
        if action == "ban":
            db.execute("UPDATE cards SET status='banned' WHERE code=?", (code,))
        elif action == "unban":
            # 解封要还原成「按到期时间该是什么状态」，不能一律 activate
            t = now()
            if row["expires_at"] and row["expires_at"] < t:
                db.execute("UPDATE cards SET status='expired' WHERE code=?", (code,))
            elif row["activated_at"]:
                db.execute("UPDATE cards SET status='active' WHERE code=?", (code,))
            else:
                db.execute("UPDATE cards SET status='unused' WHERE code=?", (code,))
        elif action == "unbind":
            db.execute("DELETE FROM binds WHERE code=?", (code,))
        elif action == "unbind_reset":
            db.execute("UPDATE cards SET unbind_used=0 WHERE code=?", (code,))
        elif action == "reset":
            db.execute("UPDATE cards SET status='unused', activated_at=NULL,"
                       " expires_at=NULL, last_used_at=NULL WHERE code=?", (code,))
            db.execute("DELETE FROM binds WHERE code=?", (code,))
        n += 1

    audit(agent, "agent.card." + action, ",".join(codes[:5]),
          "成功 %d / 跳过 %d" % (n, skipped), ip)
    return {"ok": True, "affected": n, "skipped": skipped}
