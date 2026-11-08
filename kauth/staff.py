#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理员账号（多账号 + 角色）。

和 `config.admin_token` 的关系：

- `admin_token` 是**超级令牌**，写死在配置文件里，等同 owner，永远有效。
  脚本、监控、自动化都用它，不受账号体系影响。
- 这个模块管的是**给人用的账号**：有用户名、有角色、能单独停用、能各自登录。

角色：

| role | 能做什么 |
|---|---|
| owner  | 全部，包含管理管理员账号 |
| admin  | 除「管理员账号管理」外的全部 |
| viewer | 只读，所有 POST 一律 403 |

写操作被拒的判定放在 httpd 层（`admin_guard`），这里只负责身份。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from . import db, throttle, totp
from .util import fmt_time, now

TOKEN_TTL = 3 * 86400          # 管理员会话 3 天（比代理商的 7 天短，权限更大）
PBKDF2_ROUNDS = 150000

ROLES = {
    "owner": "拥有者",
    "admin": "管理员",
    "viewer": "只读",
}

# 只有 owner 能调的管理接口前缀
OWNER_ONLY = ("/api/admin/admins",)

# 关于「最后一个 owner」：配置文件里的 admin_token 永远是一个 owner 且不受这里管，
# 所以把账号表里的 owner 全删/全降级也不会锁死系统——随时能用超级令牌登进来重建。
# 因此这里不做「最后一个 owner 不能动」的拦截，只拦「删自己」。
# （最早做过这个拦截，结果是账号表里唯一的 owner 永远删不掉，反而成了坑。）


def hash_password(pwd: str, salt: str = "") -> tuple:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"),
                            salt.encode("utf-8"), PBKDF2_ROUNDS)
    return h.hex(), salt


def check_password(pwd: str, pwd_hash: str, salt: str) -> bool:
    h, _ = hash_password(pwd, salt)
    return hmac.compare_digest(h, pwd_hash or "")


# ---------------------------------------------------------------- 身份
def public(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row["name"] or row["username"],
        "role": row["role"],
        "role_text": ROLES.get(row["role"], row["role"]),
        "status": row["status"],
        "totp_enabled": bool(row.get("totp_enabled")),
        "totp_recovery_left": totp.recovery_left(row.get("totp_recovery") or "[]"),
        "created_text": fmt_time(row["created_at"]),
        "last_login_text": fmt_time(row["last_login_at"]) if row["last_login_at"] else "-",
        "last_login_ip": row["last_login_ip"] or "-",
        "is_super": bool(row.get("is_super")),
    }


def check_token(token: str):
    """用会话令牌换管理员记录。无效/过期/停用返回 None。"""
    t = str(token or "").strip()
    if not t:
        return None
    row = db.one("SELECT * FROM admins WHERE token=?", (t,))
    if not row:
        return None
    if row["status"] != "active" or int(row["token_exp"] or 0) < now():
        return None
    return row


def _locked_msg(sec: int) -> str:
    m = max(1, int((sec + 59) // 60))
    return "密码错误次数过多，请 %d 分钟后再试" % m


def login(username: str, password: str, ip: str = "",
          code: str = "", otp: str = "") -> dict:
    """账号密码登录，可带两步验证码。

    返回的 err 里这三条前端要单独处理：
      · LOCKED     连错太多次，retry_after 是剩余秒数
      · NEED_TOTP  密码对了但缺验证码，前端要展开验证码输入框
      · BAD_TOTP   验证码不对（恢复码也认，用掉的会作废）
    """
    u = str(username or "").strip()
    p = str(password or "")
    if not u or not p:
        return {"ok": False, "err": "BAD_PARAM", "msg": "请输入账号和密码"}

    # 锁定检查放在验密码之前：锁住期间连密码都不验，避免边猜边试
    st = throttle.status("admin", u)
    if st["locked"]:
        return {"ok": False, "err": "LOCKED", "retry_after": st["retry_after"],
                "msg": _locked_msg(st["retry_after"])}

    row = db.one("SELECT * FROM admins WHERE username=?", (u,))
    if not row or not check_password(p, row["pwd_hash"], row["pwd_salt"]):
        throttle.fail("admin", u)
        return {"ok": False, "err": "BAD_LOGIN", "msg": "账号或密码错误"}
    if row["status"] != "active":
        return {"ok": False, "err": "ADMIN_DISABLED", "msg": "该账号已被停用"}

    # ---- 两步验证 ----
    if int(row["totp_enabled"] or 0):
        c = str(code or otp or "").strip()
        if not c:
            return {"ok": False, "err": "NEED_TOTP", "msg": "请输入两步验证码"}
        ok, step = totp.verify(row["totp_secret"], c,
                               last_step=int(row["totp_last_step"] or 0))
        if ok:
            db.execute("UPDATE admins SET totp_last_step=? WHERE id=?", (step, row["id"]))
        else:
            # 验证码不对时再试恢复码，命中就作废该码
            hit, left = totp.recovery_consume(row["totp_recovery"] or "[]", c)
            if not hit:
                throttle.fail("admin", u)
                return {"ok": False, "err": "BAD_TOTP", "msg": "验证码不正确"}
            db.execute("UPDATE admins SET totp_recovery=? WHERE id=?", (left, row["id"]))
            from .admin import audit as _audit
            _audit("admin.login_recovery", u,
                   "恢复码登录，剩余 %d 个" % totp.recovery_left(left), ip,
                   actor="admin:" + u)

    throttle.reset("admin", u)
    tok = secrets.token_urlsafe(32)
    exp = now() + TOKEN_TTL
    db.execute("UPDATE admins SET token=?, token_exp=?, last_login_at=?,"
               " last_login_ip=? WHERE id=?", (tok, exp, now(), ip, row["id"]))
    from .admin import audit as _audit
    _audit("admin.login", u, "", ip, actor="admin:" + u)
    return {"ok": True, "token": tok, "expires_at": exp, "admin": public(dict(row))}


def logout(row: dict) -> dict:
    if row.get("id"):
        db.execute("UPDATE admins SET token='', token_exp=0 WHERE id=?", (row["id"],))
    return {"ok": True}


# ---------------------------------------------------------------- 两步验证
def _my_row(me: dict):
    """当前登录者对应的 admins 行。超级令牌（id=0）没有行。"""
    aid = int((me or {}).get("id") or 0)
    if aid <= 0:
        return None
    return db.one("SELECT * FROM admins WHERE id=?", (aid,))


SUPER_NO_TOTP = {
    "ok": False, "err": "SUPER_NO_TOTP",
    "msg": "超级令牌本身就是一把密钥，不支持两步验证。请用账号密码登录后再绑定。",
}


def totp_self(me: dict, data: dict, ip: str = "") -> dict:
    """自助管理自己的两步验证：status / setup / enable / disable / recovery。

    绑定分两步：先 setup 拿密钥，用户把它敲进认证器 App（或扫 otpauth 链接），
    再拿 App 上显示的一次性码 enable。中间那步不能省——不然密钥存了但用户没存，
    一登录就把自己锁在外面。
    """
    row = _my_row(me)
    if not row:
        return SUPER_NO_TOTP
    from .admin import audit as _audit

    action = str(data.get("action") or "status")
    enabled = bool(int(row["totp_enabled"] or 0))

    if action == "status":
        return {"ok": True, "enabled": enabled,
                "recovery_left": totp.recovery_left(row["totp_recovery"] or "[]")}

    if action == "setup":
        if enabled:
            return {"ok": False, "err": "ALREADY_ON",
                    "msg": "两步验证已开启，要换密钥请先关闭再重新绑定"}
        secret = totp.new_secret()
        db.execute("UPDATE admins SET totp_secret=?, totp_enabled=0, totp_last_step=0"
                   " WHERE id=?", (secret, row["id"]))
        return {"ok": True, "secret": secret, "secret_grouped": totp.group(secret),
                "uri": totp.uri(secret, row["username"]), "digits": totp.DIGITS,
                "period": totp.STEP}

    if action == "enable":
        secret = row["totp_secret"] or ""
        if not secret:
            return {"ok": False, "err": "NOT_SETUP", "msg": "请先生成密钥"}
        ok, _step = totp.verify(secret, data.get("code"), last_step=0)
        if not ok:
            return {"ok": False, "err": "BAD_TOTP",
                    "msg": "验证码不正确。确认手机时间已自动同步，再输一次当前显示的码。"}
        codes = totp.new_recovery()
        # 这里刻意不写 totp_last_step：绑定用的那个码若也记成「已用」，
        # 用户刚开完两步验证、马上退出再登录时，30 秒内同一个码会被拒，
        # 看着像绑定失败。绑定时会话本来就是已认证的，重放风险可以忽略。
        db.execute("UPDATE admins SET totp_enabled=1, totp_last_step=0, totp_recovery=?"
                   " WHERE id=?", (totp.recovery_store(codes), row["id"]))
        _audit("admin.totp.enable", row["username"], "开启两步验证", ip,
               actor="admin:" + row["username"])
        return {"ok": True, "recovery": codes}

    if action == "disable":
        # 关掉第二道锁必须验当前密码，不能只靠一个已登录会话
        if not check_password(str(data.get("password") or ""),
                              row["pwd_hash"], row["pwd_salt"]):
            return {"ok": False, "err": "BAD_LOGIN", "msg": "当前密码不正确"}
        db.execute("UPDATE admins SET totp_enabled=0, totp_secret='', totp_last_step=0,"
                   " totp_recovery='[]' WHERE id=?", (row["id"],))
        _audit("admin.totp.disable", row["username"], "关闭两步验证", ip,
               actor="admin:" + row["username"])
        return {"ok": True}

    if action == "recovery":
        if not enabled:
            return {"ok": False, "err": "NOT_ENABLED", "msg": "两步验证还没开启"}
        if not check_password(str(data.get("password") or ""),
                              row["pwd_hash"], row["pwd_salt"]):
            return {"ok": False, "err": "BAD_LOGIN", "msg": "当前密码不正确"}
        codes = totp.new_recovery()
        db.execute("UPDATE admins SET totp_recovery=? WHERE id=?",
                   (totp.recovery_store(codes), row["id"]))
        _audit("admin.totp.recovery", row["username"], "重新生成恢复码", ip,
               actor="admin:" + row["username"])
        return {"ok": True, "recovery": codes}

    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}


def _confirm_ok(data: dict, row: dict) -> bool:
    """高危操作要求输入目标账号名，防止误点。

    服务端也查，不只是前端弹窗——一个被盗的会话不该能一次请求删掉账号。
    """
    got = str(data.get("confirm") or "").strip().lower()
    return bool(got) and got == str(row["username"] or "").strip().lower()


# ---------------------------------------------------------------- 账号管理（仅 owner）
def list_admins() -> dict:
    rows = db.query("SELECT * FROM admins ORDER BY id")
    items = [public(dict(r)) for r in rows]
    # 超级令牌以虚拟行呈现，让人知道它存在且等同 owner
    items.insert(0, {
        "id": 0, "username": "root", "name": "超级令牌（配置文件）",
        "role": "owner", "role_text": ROLES["owner"], "status": "active",
        "totp_enabled": False, "totp_recovery_left": 0,
        "created_text": "-", "last_login_text": "-", "last_login_ip": "-",
        "is_super": True,
    })
    return {"ok": True, "items": items}


def admin_action(data: dict, ip: str = "", me: dict = None) -> dict:
    from .admin import audit as _audit

    action = str(data.get("action") or "")
    me_id = int((me or {}).get("id") or 0)

    if action == "create":
        u = str(data.get("username") or "").strip()
        p = str(data.get("password") or "").strip()
        role = str(data.get("role") or "admin")
        if not u or not p:
            return {"ok": False, "err": "BAD_PARAM", "msg": "账号和密码都要填"}
        if len(p) < 8:
            return {"ok": False, "err": "BAD_PARAM", "msg": "管理员密码至少 8 位"}
        if role not in ROLES:
            role = "admin"
        if db.one("SELECT 1 AS x FROM admins WHERE username=?", (u,)):
            return {"ok": False, "err": "DUP_USER", "msg": "该账号已存在"}
        h, salt = hash_password(p)
        aid = db.insert_id(
            "INSERT INTO admins(username,pwd_hash,pwd_salt,name,role,status,created_at)"
            " VALUES(?,?,?,?,?,'active',?)",
            (u, h, salt, str(data.get("name") or u).strip(), role, now()))
        _audit("admin.account.create", u, role, ip)
        return {"ok": True, "id": aid}

    if action == "update":
        aid = int(data.get("id") or 0)
        row = db.one("SELECT * FROM admins WHERE id=?", (aid,))
        if not row:
            return {"ok": False, "err": "NOT_FOUND", "msg": "账号不存在"}
        sets, args = [], []
        if "name" in data:
            sets.append("name=?")
            args.append(str(data.get("name") or "").strip())
        if "role" in data:
            role = str(data.get("role") or "")
            if role not in ROLES:
                return {"ok": False, "err": "BAD_PARAM", "msg": "角色不存在"}
            sets.append("role=?")
            args.append(role)
        if "status" in data:
            st = str(data.get("status") or "active")
            sets.append("status=?")
            args.append(st)
            if st != "active":
                sets.append("token=''")
                sets.append("token_exp=0")
        if sets:
            args.append(aid)
            db.execute("UPDATE admins SET %s WHERE id=?" % ",".join(sets), args)
        _audit("admin.account.update", row["username"], ",".join(sets), ip)
        return {"ok": True}

    if action == "reset_password":
        aid = int(data.get("id") or 0)
        p = str(data.get("password") or "").strip()
        if len(p) < 8:
            return {"ok": False, "err": "BAD_PARAM", "msg": "至少 8 位"}
        row = db.one("SELECT * FROM admins WHERE id=?", (aid,))
        if not row:
            return {"ok": False, "err": "NOT_FOUND", "msg": "账号不存在"}
        if not _confirm_ok(data, row):
            return {"ok": False, "err": "CONFIRM_REQUIRED",
                    "msg": "请先输入账号名「%s」确认" % row["username"]}
        h, salt = hash_password(p)
        db.execute("UPDATE admins SET pwd_hash=?, pwd_salt=?, token='', token_exp=0"
                   " WHERE id=?", (h, salt, aid))
        _audit("admin.account.reset_password", row["username"], "重置密码", ip)
        return {"ok": True}

    if action == "kick":
        aid = int(data.get("id") or 0)
        db.execute("UPDATE admins SET token='', token_exp=0 WHERE id=?", (aid,))
        _audit("admin.account.kick", str(aid), "强制下线", ip)
        return {"ok": True}

    if action == "delete":
        aid = int(data.get("id") or 0)
        if aid == me_id:
            return {"ok": False, "err": "BAD_PARAM", "msg": "不能删除自己"}
        row = db.one("SELECT * FROM admins WHERE id=?", (aid,))
        if not row:
            return {"ok": False, "err": "NOT_FOUND", "msg": "账号不存在"}
        if not _confirm_ok(data, row):
            return {"ok": False, "err": "CONFIRM_REQUIRED",
                    "msg": "请先输入账号名「%s」确认" % row["username"]}
        db.execute("DELETE FROM admins WHERE id=?", (aid,))
        _audit("admin.account.delete", row["username"], "", ip)
        return {"ok": True}

    if action == "totp_disable":
        # 别人丢了手机时由拥有者解锁。不验对方的密码，但要输账号名确认
        aid = int(data.get("id") or 0)
        row = db.one("SELECT * FROM admins WHERE id=?", (aid,))
        if not row:
            return {"ok": False, "err": "NOT_FOUND", "msg": "账号不存在"}
        if not _confirm_ok(data, row):
            return {"ok": False, "err": "CONFIRM_REQUIRED",
                    "msg": "请先输入账号名「%s」确认" % row["username"]}
        if not int(row["totp_enabled"] or 0):
            return {"ok": False, "err": "NOT_ENABLED", "msg": "该账号没开两步验证"}
        db.execute("UPDATE admins SET totp_enabled=0, totp_secret='', totp_last_step=0,"
                   " totp_recovery='[]' WHERE id=?", (aid,))
        _audit("admin.account.totp_off", row["username"], "拥有者关闭两步验证", ip)
        return {"ok": True}

    return {"ok": False, "err": "BAD_ACTION", "msg": "未知操作"}
