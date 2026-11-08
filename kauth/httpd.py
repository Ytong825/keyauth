#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 服务与路由分发"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import admin, agent, config, db, security, service, staff
from .util import dumps, now

# ------------------------------------------------------------ 请求体护栏
MAX_BODY = 64 * 1024      # 64KB：批量制卡几百张也够，挡住超大请求打内存
MAX_FIELD = 4096          # 单个字符串字段上限：卡密/机器码/备注都不该超长
MAX_DEPTH = 6             # JSON 嵌套深度上限
MAX_LIST = 500            # 单个数组的元素上限


def _check_fields(data, depth: int = 0) -> bool:
    """递归校验：字段长度、嵌套深度、数组长度。

    没有这道护栏时，超长备注 / 深层嵌套 JSON 会被原样写进数据库。"""
    if depth > MAX_DEPTH:
        return False
    if isinstance(data, dict):
        for k, v in data.items():
            if len(str(k)) > 128:
                return False
            if not _check_fields(v, depth + 1):
                return False
    elif isinstance(data, list):
        if len(data) > MAX_LIST:
            return False
        for v in data:
            if not _check_fields(v, depth + 1):
                return False
    elif isinstance(data, str):
        if len(data) > MAX_FIELD:
            return False
    return True


class _RateLimiter:
    """HTTP 层粗粒度兜底限流（60 秒滑动窗口，按 IP + 接口组）。

    与 security.rate_ok 的分工 —— 别把这两个叠成双倍：
      · security.rate_ok  是**业务层**限流，只作用于 /api/v1/*，
        阈值可在后台「系统设置」里调（默认 120/min），管的是"卡密爆破"。
      · 这里的 _RateLimiter 是**传输层**兜底，阈值故意开得高很多
        （客户端接口 1200/min），只在突发洪水 / 直连端口时起作用。
        管理接口没有业务层限流，所以它那组用 120/min。
    Nginx 层也有限流（deploy/nginx.conf），但那只在走 Nginx 时生效。
    """

    GROUPS = (("/api/v1/", 1200), ("/api/admin/", 120), ("/api/", 120))

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}
        self._sweep = 0.0

    def check(self, ip: str, path: str) -> bool:
        # 测试 / 压测时用 KEYAUTH_RATE_LIMIT=0 豁免，否则跑几百个用例
        # 会被自己的限流打断，测试变成"看谁快"
        if os.environ.get("KEYAUTH_RATE_LIMIT", "1") == "0":
            return True
        t = time.time()
        group = "/api/"
        for pref, _ in self.GROUPS:
            if path.startswith(pref):
                group = pref
                break
        limit = dict(self.GROUPS)[group]
        with self._lock:
            if t - self._sweep > 300:          # 5 分钟清一次空桶
                self._sweep = t
                for k in [k for k, v in self._hits.items()
                          if not v or t - v[-1] > 300]:
                    self._hits.pop(k, None)
            q = self._hits.setdefault((ip, group), [])
            while q and t - q[0] > 60:
                q.pop(0)
            if len(q) >= limit:
                return False
            q.append(t)
            return True


RATE = _RateLimiter()

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "KeyAuth"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ 基础
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, status, body: bytes, ctype="application/json; charset=utf-8",
              extra: dict = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # 安全响应头：防点击劫持 / MIME 嗅探 / 引用泄露
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # CORS 只对客户端接口开放。管理接口发 ACAO:* 等于任何网页都能带着
        # 令牌去打 /api/admin/*，虽然还要 X-Admin-Token，但白白扩大攻击面。
        # 代理商接口同理：只用自定义头，不给通配。
        if not self.path.startswith(("/api/admin/", "/api/agent/")):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-Admin-Token, X-Agent-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    def json(self, obj, status=200):
        self._send(status, dumps(obj).encode("utf-8"))

    def body(self) -> dict:
        """读 JSON 请求体。超限 / 字段过长时直接回错误响应并置标记，
        调用方要检查 _body_error，避免一个请求发两次响应。"""
        self._body_error = False
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        if n > MAX_BODY:
            self._body_error = True
            return self.json({"ok": False, "err": "TOO_LARGE",
                              "msg": "请求体过大（上限 %d KB）" % (MAX_BODY // 1024)}, 413)
        try:
            raw = self.rfile.read(n)
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        if not _check_fields(data):
            self._body_error = True
            return self.json({"ok": False, "err": "BAD_PARAM",
                              "msg": "参数过长或嵌套过深"}, 400)
        return data

    def ip(self) -> str:
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

    def is_admin(self) -> bool:
        return security.token_ok(self.headers.get("X-Admin-Token"))

    def no_auth(self):
        self.json({"ok": False, "err": "NO_AUTH", "msg": "管理令牌不正确"}, 401)

    def forbidden(self, msg: str):
        self.json({"ok": False, "err": "FORBIDDEN", "msg": msg}, 403)

    # ------------------------------------------------------------ 管理员身份
    def admin_ctx(self):
        """返回当前管理员上下文；同时把 actor 写进 thread-local，审计自动带上。

        超级令牌（config.admin_token）等同 owner，脚本和监控继续用它；
        账号登录拿到的会话令牌走 admins 表。
        """
        tok = self.headers.get("X-Admin-Token")
        if security.token_ok(tok):
            admin.set_actor("admin")
            return {"id": 0, "username": "root", "name": "超级令牌",
                    "role": "owner", "is_super": True}
        row = staff.check_token(tok)
        if not row:
            return None
        admin.set_actor("admin:" + row["username"])
        return {"id": row["id"], "username": row["username"],
                "name": row["name"] or row["username"],
                "role": row["role"], "is_super": False}

    # ------------------------------------------------------------ 代理商鉴权
    def agent_me(self):
        """取当前代理商记录；没有/过期/停用都返回 None。"""
        return agent.check(self.headers.get("X-Agent-Token"))

    def no_agent(self):
        self.json({"ok": False, "err": "AGENT_NO_AUTH",
                   "msg": "代理商登录已失效，请重新登录"}, 401)

    def agent_get(self, p: str, qs) -> None:
        me = self.agent_me()
        if not me:
            return self.no_agent()
        g = self.q1
        if p == "/api/agent/me":
            return self.json(agent.me(me))
        if p == "/api/agent/cards":
            return self.json(agent.cards(
                me, page=g(qs, "page", "1"), size=g(qs, "size", "50"),
                q=g(qs, "q"), status=g(qs, "status"), app=g(qs, "app"),
                card_type=g(qs, "card_type")))
        if p == "/api/agent/quotas":
            return self.json(agent.me(me))
        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)

    def agent_post(self, p: str, data: dict, ip: str) -> None:
        # 登录是唯一不需要令牌的代理商接口
        if p == "/api/agent/login":
            r = agent.login(str(data.get("username") or ""),
                            str(data.get("password") or ""), ip)
            if not r.get("ok") and r.get("err") in ("BAD_LOGIN", "LOCKED"):
                # 登录失败也进审计，方便发现撞库
                admin.audit("agent.login_failed",
                            str(data.get("username") or "")[:32],
                            str(r.get("msg") or "密码错误")[:60], ip)
            if r.get("err") == "LOCKED":
                self._send(429, json.dumps(r, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8",
                           {"Retry-After": str(int(r.get("retry_after") or 60))})
                return
            return self.json(r)

        me = self.agent_me()
        if not me:
            return self.no_agent()

        if p == "/api/agent/logout":
            return self.json(agent.logout(me))
        if p == "/api/agent/cards":
            return self.json(agent.gen_cards(me, data, ip))
        if p == "/api/agent/cards/action":
            return self.json(agent.card_action(me, data.get("codes"),
                                               data.get("action", ""), ip))
        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)

    @staticmethod
    def q1(qs, key, default=""):
        v = qs.get(key)
        return v[0] if v else default

    # ------------------------------------------------------------ 静态资源
    def serve_file(self, rel: str, ctype: str = None):
        full = os.path.abspath(os.path.join(config.STATIC_DIR, rel))
        if not full.startswith(os.path.abspath(config.STATIC_DIR)):
            return self.json({"ok": False, "err": "FORBIDDEN"}, 403)
        if not os.path.isfile(full):
            return self._send(404, b"Not Found", "text/plain; charset=utf-8")
        ctype = ctype or MIME.get(os.path.splitext(full)[1].lower(),
                                  "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        # 静态资源一律协商缓存：改完文件刷新即生效，不会被浏览器旧缓存挡住。
        # 上生产后可以把这层缓存交给前置的 Nginx 处理。
        self._send(200, body, ctype, {"Cache-Control": "no-cache, must-revalidate"})

    # ------------------------------------------------------------ GET
    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        u = urlparse(self.path)
        p, qs = unquote(u.path), parse_qs(u.query)

        if p.startswith("/api/") and not RATE.check(self.ip(), p):
            return self.json({"ok": False, "err": "RATE_LIMIT",
                              "msg": "请求过于频繁，请稍后再试"}, 429)

        if p in ("/", "/admin", "/admin/"):
            return self.serve_file("index.html", "text/html; charset=utf-8")
        if p in ("/agent", "/agent/", "/agent.html"):
            return self.serve_file("agent.html", "text/html; charset=utf-8")
        if p.startswith("/static/"):
            return self.serve_file(p[len("/static/"):])
        # 根路径下的静态资源。
        # index.html 挂在 /admin，它里面的相对引用会解析成 /app.css 这种；
        # 而 login.css 自己挂在 /login.css，于是它里面的 url(bg-g1.svg)
        # 会解析成 /bg-g1.svg —— 都不以 /static/ 开头，得在这里兜住。
        # 限定"单层文件名 + 文件确实存在"，免得抢到 /api/... 的路由。
        rel = p.lstrip("/")
        if rel and "/" not in rel and os.path.isfile(
                os.path.join(config.STATIC_DIR, rel)):
            return self.serve_file(rel)
        if p == "/favicon.ico":
            return self.serve_file("favicon.svg") if \
                os.path.isfile(os.path.join(config.STATIC_DIR, "favicon.svg")) \
                else self._send(204, b"")
        if p == "/api/health":
            return self.json({"ok": True, "name": "keyauth",
                              "server_time": now(), "version": "1.3.0"})

        if p.startswith("/api/agent/"):
            return self.agent_get(p, qs)

        if p.startswith("/api/admin/"):
            ctx = self.admin_ctx()
            if not ctx:
                return self.no_auth()
            if p.startswith(staff.OWNER_ONLY) and ctx["role"] != "owner":
                return self.forbidden("只有拥有者能查看管理员账号")
            return self.admin_get(p, qs)

        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)

    def admin_get(self, p: str, qs):
        g = self.q1
        if p == "/api/admin/overview":
            return self.json(admin.overview())
        if p == "/api/admin/cards":
            return self.json(admin.cards(
                q=g(qs, "q"), status=g(qs, "status"), app=g(qs, "app"),
                plan=g(qs, "plan"), card_type=g(qs, "card_type"),
                batch=g(qs, "batch"), page=g(qs, "page", "1"),
                size=g(qs, "size", "50"), agent=g(qs, "agent", "")))
        if p == "/api/admin/cards/export":
            body = admin.export_cards(app=g(qs, "app"), status=g(qs, "status"),
                                      batch=g(qs, "batch")).encode("utf-8-sig")
            return self._send(200, body, "text/csv; charset=utf-8", {
                "Content-Disposition": 'attachment; filename="cards.csv"'})
        if p == "/api/admin/apps":
            return self.json(admin.list_apps())
        if p == "/api/admin/plans":
            return self.json(admin.list_plans())
        if p == "/api/admin/logs":
            return self.json(admin.logs(
                page=g(qs, "page", "1"), size=g(qs, "size", "50"),
                q=g(qs, "q"), result=g(qs, "result"), action=g(qs, "action"),
                app=g(qs, "app"), ts_from=g(qs, "from", ""), ts_to=g(qs, "to", ""),
                limit=g(qs, "limit", "0")))
        if p == "/api/admin/audits":
            return self.json(admin.audits(
                page=g(qs, "page", "1"), size=g(qs, "size", "50"),
                q=g(qs, "q"), action=g(qs, "action"),
                ts_from=g(qs, "from", ""), ts_to=g(qs, "to", ""),
                limit=g(qs, "limit", "0")))
        if p == "/api/admin/webhooks":
            return self.json(admin.list_webhooks())
        if p == "/api/admin/notices":
            return self.json(admin.list_notices())
        if p == "/api/admin/settings":
            return self.json(admin.get_settings())
        if p == "/api/admin/agents":
            return self.json(agent.list_agents())
        if p == "/api/admin/admins":
            return self.json(staff.list_admins())
        if p == "/api/admin/me":
            ctx = self.admin_ctx()
            row = staff._my_row(ctx)
            return self.json({
                "ok": True,
                "admin": dict(ctx, totp_enabled=bool(row and int(
                    row["totp_enabled"] or 0))),
                "roles": staff.ROLES,
            })
        if p == "/api/admin/me/totp":
            return self.json(staff.totp_self(self.admin_ctx(), {}, self.ip()))
        if p == "/api/admin/backups":
            return self.json(admin.backup_info())
        if p.startswith("/api/admin/backups/"):
            name = p[len("/api/admin/backups/"):]
            full = db.backup_path(name)
            if not full:
                return self.json({"ok": False, "err": "NOT_FOUND",
                                  "msg": "备份不存在"}, 404)
            try:
                with open(full, "rb") as f:
                    body = f.read()
            except OSError as e:
                return self.json({"ok": False, "err": "READ_FAIL", "msg": str(e)})
            return self._send(200, body, "application/octet-stream", {
                "Content-Disposition":
                    'attachment; filename="%s"' % os.path.basename(full)})
        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        p = unquote(urlparse(self.path).path)
        ip = self.ip()

        if p.startswith("/api/") and not RATE.check(ip, p):
            return self.json({"ok": False, "err": "RATE_LIMIT",
                              "msg": "请求过于频繁，请稍后再试"}, 429)

        data = self.body()
        if getattr(self, "_body_error", False):
            return None          # body() 已经回过响应了，别再发第二次

        # ---- 客户端接口 ----
        if p == "/api/v1/client-event":
            # 客户端持续上报自定义事件，但服务端没有落库需求，先返回成功占位。
            # 2026-11-06 上线：客户端此前打这个接口一直 404，加桩后恢复 200。
            return self.json({"ok": True, "data": {}})

        if p == "/api/v1/verify":
            return self.json(service.api_verify(data, ip))
        if p == "/api/v1/heartbeat":
            return self.json(service.api_heartbeat(data, ip))
        if p == "/api/v1/query":
            return self.json(service.api_query(data, ip))
        if p == "/api/v1/unbind":
            return self.json(service.api_unbind(data, ip))
        if p == "/api/v1/notices":
            app, err = service.check_request(data, ip, "query")
            if err and err.get("err") not in ("", "BAD_PARAM"):
                return self.json(err)
            return self.json(self.client_notices(data))

        # ---- 代理商接口 ----
        if p.startswith("/api/agent/"):
            return self.agent_post(p, data, ip)

        # ---- 管理接口 ----
        if p.startswith("/api/admin/"):
            # 账号登录是唯一不需要已有令牌的管理接口
            if p == "/api/admin/auth":
                r = staff.login(str(data.get("username") or ""),
                                str(data.get("password") or ""), ip,
                                code=str(data.get("code") or ""))
                if not r.get("ok") and r.get("err") in ("BAD_LOGIN", "ADMIN_DISABLED",
                                                        "BAD_TOTP", "LOCKED"):
                    admin.audit("admin.login_failed",
                                str(data.get("username") or "")[:32],
                                str(r.get("msg") or r.get("err"))[:60], ip)
                # 锁定要给出 429 + Retry-After，脚本和监控才认得出是被挡了
                if r.get("err") == "LOCKED":
                    self._send(429, json.dumps(r, ensure_ascii=False).encode("utf-8"),
                               "application/json; charset=utf-8",
                               {"Retry-After": str(int(r.get("retry_after") or 60))})
                    return
                return self.json(r)

            ctx = self.admin_ctx()
            if not ctx:
                return self.no_auth()
            # 退出登录任何角色都要能做，放在只读拦截之前
            if p == "/api/admin/logout":
                return self.json(staff.logout(ctx))
            # 自己的两步验证任何角色都能管（只读账号也得能给自己加锁）
            if p == "/api/admin/me/totp":
                return self.json(staff.totp_self(ctx, data, ip))
            # 只读账号不能执行任何写操作
            if ctx["role"] == "viewer":
                return self.forbidden("只读账号不能执行写操作")
            if p.startswith(staff.OWNER_ONLY) and ctx["role"] != "owner":
                return self.forbidden("只有拥有者能管理管理员账号")
            if p == "/api/admin/admins":
                return self.json(staff.admin_action(data, ip, ctx))
            return self.admin_post(p, data, ip)

        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)

    def client_notices(self, data: dict) -> dict:
        app_id = str(data.get("app_id") or "").strip()
        rows = db.query(
            "SELECT id,title,content,level FROM notices WHERE enabled=1"
            " AND (app_id='' OR app_id=?) ORDER BY id DESC LIMIT 10", (app_id,))
        return {"ok": True, "data": {
            "announcement": config.CFG.get("announcement", ""),
            "notices": rows,
            "server_time": now(),
        }}

    def admin_post(self, p: str, data: dict, ip: str):
        if p == "/api/admin/login":
            return self.json({"ok": True, "server_time": now()})
        if p == "/api/admin/cards":
            return self.json(admin.gen_cards(data))
        if p == "/api/admin/cards/action":
            return self.json(admin.card_action(data.get("codes"), data.get("action", ""),
                                               data.get("amount", data.get("days", 0)), ip))
        if p == "/api/admin/apps":
            return self.json(admin.app_action(data, ip))
        if p == "/api/admin/plans":
            return self.json(admin.plan_action(data, ip))
        if p == "/api/admin/webhooks":
            return self.json(admin.webhook_action(data, ip))
        if p == "/api/admin/notices":
            return self.json(admin.notice_action(data, ip))
        if p == "/api/admin/settings":
            return self.json(admin.save_settings(data, ip))
        if p == "/api/admin/token/rotate":
            r = admin.rotate_admin_token(ip)
            return self.json(r)
        if p == "/api/admin/agents":
            return self.json(agent.agent_action(data, ip))
        if p == "/api/admin/agents/quota":
            return self.json(agent.topup_quota(data, ip))
        if p == "/api/admin/logs/cleanup":
            return self.json(admin.cleanup_logs(data.get("days"), ip))
        if p == "/api/admin/backup":
            try:
                path = db.backup()
                admin.audit("system.backup", path, "", ip)
                return self.json({"ok": True, "path": os.path.basename(path)})
            except Exception as e:
                return self.json({"ok": False, "err": "BACKUP_FAIL", "msg": str(e)})
        return self.json({"ok": False, "err": "NOT_FOUND", "msg": "无此接口"}, 404)


def serve(host: str, port: int) -> None:
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.serve_forever()
