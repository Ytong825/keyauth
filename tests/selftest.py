# -*- coding: utf-8 -*-
"""KeyAuth 端到端自测：覆盖制卡、激活、心跳、签名、防重放、设备绑定、额度扣减等"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
# 注意：真正生效的是下面 env["KEYAUTH_RATE_LIMIT"]（传给子进程）
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DATA = os.path.join(ROOT, "_testdata")
PORT = 8799
BASE = "http://127.0.0.1:%d" % PORT
PY = sys.executable

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print("%s  %-34s %s" % ("PASS" if cond else "FAIL", name, detail))


def call(method, path, obj=None, token=None, raw_body=None):
    data = raw_body if raw_body is not None else (
        json.dumps(obj).encode() if obj is not None else None)
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Admin-Token"] = token
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8")
            return r.status, (json.loads(body) if body.strip().startswith(("{", "[")) else body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def sign_of(secret, params):
    raw = "&".join("%s=%s" % (k, params[k]) for k in sorted(params) if k != "sign")
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def client(path, app_id, code, machine, secret, ts=None, nonce=None, cost=None,
           bad_sign=False, no_sign=False, extra=None):
    p = {
        "app_id": app_id,
        "code": code,
        "machine_id": machine,
        "ts": int(ts if ts is not None else time.time()),
        "nonce": nonce or os.urandom(8).hex(),
    }
    if cost is not None:
        p["cost"] = str(cost)
    if extra:
        p.update(extra)
    if not no_sign:
        p["sign"] = "deadbeef" if bad_sign else sign_of(secret, p)
    return call("POST", path, p)[1]


def main():
    if os.path.isdir(TMP_DATA):
        shutil.rmtree(TMP_DATA)
    # 读后端源码做静态断言（安全头这类不适合用 HTTP 往返验）
    def _src(name):
        with open(os.path.join(ROOT, "kauth", name), encoding="utf-8") as f:
            return f.read()

    SRC_HTTPD = _src("httpd.py")
    SRC_SERVICE = _src("service.py")
    SRC_SECURITY = _src("security.py")

    env = os.environ.copy()
    env["KEYAUTH_DATA"] = TMP_DATA
    # 服务是 subprocess 独立进程，限流豁免必须经 env 传过去；
    # 只设 os.environ 只作用于本进程，拦不住子进程的限流。
    env["KEYAUTH_RATE_LIMIT"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        [PY, os.path.join(ROOT, "server.py"), "-p", str(PORT), "--host", "127.0.0.1"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace")
    out = ""
    try:
        ok = False
        for _ in range(50):
            try:
                with urllib.request.urlopen(BASE + "/api/health", timeout=2) as r:
                    if json.loads(r.read().decode())["ok"]:
                        ok = True
                        break
            except Exception:
                time.sleep(0.25)
        check("服务启动 / 健康检查", ok)
        if not ok:
            return 1

        with open(os.path.join(TMP_DATA, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        TK = cfg["admin_token"]

        # ---------------- 鉴权 ----------------
        st, _ = call("GET", "/api/admin/overview")
        check("无令牌访问被拒", st == 401, "HTTP %s" % st)

        st, d = call("GET", "/api/admin/overview", token=TK)
        check("概览接口可用", st == 200 and d["ok"] and d["stats"]["cards_total"] == 0,
              "卡密 %s / 应用 %s" % (d["stats"]["cards_total"], d["stats"]["apps"]))

        # ---------------- 应用 ----------------
        st, d = call("GET", "/api/admin/apps", token=TK)
        check("默认应用自动创建", d["ok"] and len(d["items"]) == 1,
              d["items"][0]["name"] if d["ok"] else "")

        st, d = call("POST", "/api/admin/apps",
                     {"action": "create", "name": "测试软件", "note": "自测"}, token=TK)
        check("新建应用", d.get("ok") and d["app_id"].startswith("app_"), d.get("app_id", ""))
        APP, SECRET = d["app_id"], d["app_secret"]

        # ---------------- 套餐 ----------------
        st, d = call("POST", "/api/admin/plans",
                     {"action": "create", "name": "月卡", "app_id": APP, "card_type": "time",
                      "duration_days": 30, "max_devices": 1, "unbind_limit": 1, "price": 9.9},
                     token=TK)
        check("新建时间套餐并返回 id（建套餐→拿 id→制卡带 plan_id 这条链要能走通）",
              d.get("ok") and isinstance(d.get("id"), int) and d["id"] > 0,
              "id=%s" % d.get("id"))
        check("套餐创建返回完整字段", bool(d.get("data", {}).get("unbind_limit") == 1),
              json.dumps(d.get("data", {}), ensure_ascii=False))
        plan_time = d["id"]

        st, d = call("POST", "/api/admin/plans",
                     {"action": "create", "name": "3次卡", "app_id": APP, "card_type": "count",
                      "total_value": 3, "max_devices": 2, "unbind_limit": 2}, token=TK)
        check("新建次数套餐", d.get("ok"))

        st, d = call("POST", "/api/admin/plans",
                     {"action": "create", "name": "100点卡", "app_id": APP, "card_type": "point",
                      "total_value": 100, "max_devices": 1, "unbind_limit": 0}, token=TK)
        check("新建点数套餐", d.get("ok"))

        st, d = call("GET", "/api/admin/plans", token=TK)
        plan_cnt = [x for x in d["items"] if x["name"] == "3次卡"][0]["id"]
        plan_pt = [x for x in d["items"] if x["name"] == "100点卡"][0]["id"]

        # ---------------- 制卡 ----------------
        st, d = call("POST", "/api/admin/cards",
                     {"app_id": APP, "plan_id": plan_time, "count": 3, "note": "自测"}, token=TK)
        check("按套餐批量制卡", d.get("ok") and len(d["codes"]) == 3, str(d.get("codes")))
        c1, c2, c3 = d["codes"]

        st, d = call("GET", "/api/admin/cards?" + urllib.parse.urlencode({"q": "自测"}), token=TK)
        it = d["items"][0]
        check("卡密继承套餐参数",
              it["duration_days"] == 30 and it["max_devices"] == 1 and it["plan"] == "月卡")

        st, d = call("POST", "/api/admin/cards",
                     {"app_id": APP, "plan_id": plan_cnt, "count": 1, "prefix": "VIP"}, token=TK)
        cn = d["codes"][0]
        check("制卡支持前缀", cn.startswith("VIP-"), cn)

        st, d = call("POST", "/api/admin/cards",
                     {"app_id": APP, "plan_id": plan_pt, "count": 1}, token=TK)
        cp = d["codes"][0]
        check("点数卡制卡", bool(cp) and len(cp) == 19, cp)

        # ---------------- 激活与心跳 ----------------
        r = client("/api/v1/verify", APP, c1, "PC-A", SECRET)
        check("首次校验自动激活", r.get("ok"), r.get("msg", ""))
        dta = r.get("data", {})
        check("返回完整授权信息",
              dta.get("plan") == "月卡" and dta.get("remaining_seconds", 0) > 29 * 86400
              and dta.get("devices") == 1 and dta.get("unbind_left") == 1,
              "剩余 %.0f 天" % (dta.get("remaining_seconds", 0) / 86400))

        r = client("/api/v1/heartbeat", APP, c1, "PC-A", SECRET)
        check("同机心跳通过", r.get("ok"))

        r = client("/api/v1/query", APP, c1, "PC-A", SECRET)
        check("状态查询通过", r.get("ok") and r["data"]["card_type"] == "time")

        r = client("/api/v1/heartbeat", APP, c1, "PC-B", SECRET)
        check("未绑定设备心跳被拒", r.get("err") == "DEVICE_MISMATCH", r.get("err", ""))

        r = client("/api/v1/verify", APP, c1, "PC-B", SECRET)
        check("超设备数校验被拒", r.get("err") == "DEVICE_LIMIT", r.get("msg", ""))

        # ---------------- 签名与防重放 ----------------
        r = client("/api/v1/verify", APP, c2, "PC-A", SECRET, bad_sign=True)
        check("错误签名被拒", r.get("err") == "BAD_SIGN")

        r = client("/api/v1/verify", APP, c2, "PC-A", SECRET, no_sign=True)
        check("缺少签名被拒", r.get("err") == "BAD_SIGN")

        r = client("/api/v1/verify", APP, c2, "PC-A", SECRET, ts=time.time() - 9999)
        check("过期时间戳被拒", r.get("err") == "BAD_TS")

        fx = "nonce-fixed-0001"
        r1 = client("/api/v1/verify", APP, c2, "PC-A", SECRET, nonce=fx)
        r2 = client("/api/v1/verify", APP, c2, "PC-A", SECRET, nonce=fx)
        check("首次请求通过", r1.get("ok"))
        check("重复 nonce 判重放", r2.get("err") == "REPLAY", r2.get("err", ""))

        r = client("/api/v1/verify", APP, "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "PC-A", SECRET)
        check("卡密不存在", r.get("err") == "CARD_NOT_FOUND")

        r = client("/api/v1/verify", APP, c3, "", SECRET)
        check("缺少机器码被拒", r.get("err") == "BAD_PARAM")

        r = client("/api/v1/verify", "app_not_exist", c3, "PC-A", SECRET)
        check("应用不存在", r.get("err") == "BAD_APP")

        # ---------------- 次数卡：每次固定扣 1 ----------------
        r = client("/api/v1/verify", APP, cn, "PC-A", SECRET)
        check("次数卡首次校验扣 1 次",
              r.get("ok") and r["data"]["used_value"] == 1 and r["data"]["remaining_value"] == 2,
              "已用 1 / 剩 %s" % r.get("data", {}).get("remaining_value"))

        r = client("/api/v1/verify", APP, cn, "PC-A", SECRET)
        check("次数卡逐次扣减", r["data"]["used_value"] == 2,
              "已用 %s" % r.get("data", {}).get("used_value"))

        r = client("/api/v1/heartbeat", APP, cn, "PC-A", SECRET)
        check("心跳不扣次数", r["data"]["used_value"] == 2)

        r = client("/api/v1/verify", APP, cn, "PC-A", SECRET)
        check("用尽后转 used_up", r.get("ok") and r["data"]["status"] == "used_up",
              "状态 %s" % r.get("data", {}).get("status"))

        r = client("/api/v1/verify", APP, cn, "PC-A", SECRET)
        check("额度用尽被拒", r.get("err") == "CARD_USED_UP", r.get("err", ""))

        # ---------------- 点数卡：按 cost 扣减 ----------------
        r = client("/api/v1/verify", APP, cp, "PC-A", SECRET)
        check("点数卡首次扣 1 点", r["data"]["used_value"] == 1,
              "已用 %s" % r.get("data", {}).get("used_value"))

        r = client("/api/v1/verify", APP, cp, "PC-A", SECRET, cost=0)
        check("cost=0 只校验不扣减", r.get("ok") and r["data"]["used_value"] == 1)

        r = client("/api/v1/verify", APP, cp, "PC-A", SECRET, cost=50)
        check("按 cost 扣减点数", r["data"]["used_value"] == 51,
              "已用 %s" % r.get("data", {}).get("used_value"))

        r = client("/api/v1/verify", APP, cp, "PC-A", SECRET, cost=60)
        check("余额不足被拒", r.get("err") == "CARD_USED_UP", r.get("msg", ""))

        r = client("/api/v1/verify", APP, cp, "PC-A", SECRET, cost=49)
        check("恰好用完转 used_up", r.get("ok") and r["data"]["status"] == "used_up",
              "状态 %s" % r.get("data", {}).get("status"))

        # ---------------- 封禁 / 解绑 ----------------
        st, d = call("POST", "/api/admin/cards/action",
                     {"codes": [c1], "action": "ban"}, token=TK)
        check("后台封禁", d.get("ok") and d["affected"] == 1)
        r = client("/api/v1/verify", APP, c1, "PC-A", SECRET)
        check("封禁后校验被拒", r.get("err") == "CARD_BANNED")

        call("POST", "/api/admin/cards/action", {"codes": [c1], "action": "unban"}, token=TK)
        r = client("/api/v1/verify", APP, c1, "PC-A", SECRET)
        check("解封后恢复", r.get("ok"))

        r = client("/api/v1/unbind", APP, c1, "PC-A", SECRET)
        check("自助解绑成功", r.get("ok") and r["data"]["unbind_left"] == 0, r.get("msg", ""))
        r = client("/api/v1/unbind", APP, c1, "PC-A", SECRET)
        check("超换绑次数被拒", r.get("err") == "UNBIND_LIMIT", r.get("msg", ""))
        r = client("/api/v1/verify", APP, c1, "PC-B", SECRET)
        check("解绑后新设备可绑", r.get("ok"))

        # ---------------- 续期 ----------------
        st, d = call("POST", "/api/admin/cards/action",
                     {"codes": [c1], "action": "renew", "days": 365}, token=TK)
        check("时间卡续期", d.get("ok"))
        st, d = call("GET", "/api/admin/cards?" + urllib.parse.urlencode({"q": c1}), token=TK)
        check("续期后到期时间延长", d["items"][0]["expires_text"] != "-")

        # ---------------- 列表 / 筛选 / 分页 ----------------
        st, d = call("GET", "/api/admin/cards?" + urllib.parse.urlencode(
            {"status": "unused", "app": APP}), token=TK)
        check("按状态+应用筛选", d["ok"] and d["total"] == 1, "未使用 %s" % d.get("total"))

        st, d = call("GET", "/api/admin/cards?page=1&size=2", token=TK)
        check("分页生效", len(d["items"]) == 2 and d["total"] == 5,
              "返回 %s 条 / 共 %s 条" % (len(d["items"]), d["total"]))

        st, d = call("GET", "/api/admin/cards?" + urllib.parse.urlencode(
            {"card_type": "count"}), token=TK)
        check("按卡密类型筛选", d["total"] == 1)

        # ---------------- 日志 / 审计 ----------------
        st, d = call("GET", "/api/admin/logs?limit=300", token=TK)
        kinds = set(x["result"] for x in d["items"])
        want = {"OK", "CARD_BANNED", "DEVICE_LIMIT", "DEVICE_MISMATCH", "BAD_SIGN",
                "BAD_TS", "REPLAY", "CARD_NOT_FOUND", "BAD_PARAM", "BAD_APP",
                "UNBIND_LIMIT", "CARD_USED_UP"}
        check("日志覆盖全部结果码", want <= kinds, "缺 %s" % sorted(want - kinds))
        acts = set(x["action"] for x in d["items"])
        check("日志区分动作类型", {"verify", "heartbeat", "query", "unbind"} <= acts,
              str(sorted(acts)))

        st, d = call("GET", "/api/admin/audits", token=TK)
        check("后台操作审计", d["ok"] and len(d["items"]) > 0,
              "记录 %d 条" % len(d["items"]))

        # ---------------- 导出 ----------------
        st, body = call("GET", "/api/admin/cards/export?app=" + APP, token=TK)
        check("导出 CSV", st == 200 and "卡密,应用,套餐" in body,
              "%d 字节" % (len(body) if isinstance(body, str) else 0))

        # ---------------- WebHook / 公告 / 设置 ----------------
        st, d = call("POST", "/api/admin/webhooks",
                     {"action": "create", "url": "http://127.0.0.1:9/hook",
                      "events": ["card.activated"]}, token=TK)
        check("创建 WebHook", d.get("ok"))
        st, d = call("POST", "/api/admin/webhooks",
                     {"action": "create", "url": "ftp://bad"}, token=TK)
        check("WebHook 地址校验", d.get("err") == "BAD_PARAM")

        st, d = call("POST", "/api/admin/notices",
                     {"action": "create", "title": "维护通知", "content": "今晚升级",
                      "level": "warn"}, token=TK)
        check("发布公告", d.get("ok"))
        r = client("/api/v1/notices", APP, c1, "PC-B", SECRET)
        check("客户端可拉取公告", r.get("ok") and len(r["data"]["notices"]) == 1)

        st, d = call("POST", "/api/admin/settings",
                     {"site_name": "我的发卡站", "announcement": "欢迎",
                      "rate_limit": 60, "clock_skew": 120}, token=TK)
        check("保存系统设置", d.get("ok") and d["settings"]["site_name"] == "我的发卡站")
        st, d = call("GET", "/api/admin/settings", token=TK)
        check("设置持久化生效", d["settings"]["announcement"] == "欢迎"
              and d["settings"]["clock_skew"] == 120)

        # ---------------- 批量操作 ----------------
        st, d = call("POST", "/api/admin/cards/action",
                     {"codes": [c2, c3], "action": "delete"}, token=TK)
        check("批量删除", d.get("ok") and d["affected"] == 2)
        st, d = call("GET", "/api/admin/cards", token=TK)
        check("删除后总数正确", d["total"] == 3, "total=%s" % d["total"])

        # ---------------- 管理界面 ----------------
        st, html = call("GET", "/admin")
        check("管理后台页面可访问",
              st == 200 and "接入文档" in html and "login.css" in html,
              "%d 字节" % (len(html) if isinstance(html, str) else 0))

        st, css = call("GET", "/static/app.css")
        check("样式表可加载", st == 200 and "--primary" in css,
              "%d 字节" % (len(css) if isinstance(css, str) else 0))

        st, css2 = call("GET", "/static/login.css")
        check("登录页样式可加载",
              st == 200 and ".lg-panel" in css2 and ".lg-bg" in css2
              and ".lg-input" in css2,
              "%d 字节" % (len(css2) if isinstance(css2, str) else 0))
        check("登录页三套配色齐全",
              'data-skin="paper"' in css2 and 'data-skin="ink"' in css2
              and 'data-skin="postal"' in css2)
        check("登录页无 AI 默认配方残留",
              all(k not in css2 for k in
                  ("backdrop-filter", "linear-gradient(118deg)")))
        check("登录页已去掉卡片盒子与发光层",
              all(k not in css2 for k in
                  (".lg-card", ".lg-stamp", ".lg-crop", ".lg-rules",
                   ".lg-grain", ".lg-vig", ".lg-wm")))
        check("登录页采用大圆角填充式控件",
              "border-radius: 10px" in css2 and "--l-field" in css2
              and "--l-btn-fg" in css2)
        check("风格已固化为单一（选型期候选风格全部移除）",
              'data-bg="pearl"' in css2
              and all(('data-bg="%s"' % v) not in css2
                      for v in ("aurora", "grainy", "brutal", "retro", "mesh")))
        check("背景为珠光白：近白底 + 极淡冷暖柔光 + 对角渐变兜底",
              "#FCFCFE 0%, #F6F7FB 46%, #FBF7F3 100%" in css2
              and "@keyframes lgPearl" in css2
              and "rgba(203, 213, 246, .55)" in css2
              and "rgba(253, 230, 214, .50)" in css2)
        check("图案为双层视差点阵：大间距 + 低对比 + 必带渐隐 mask",
              "lgDotsNear" in css2 and "lgDotsFar" in css2
              and "background-size: 46px 46px" in css2
              and "background-size: 92px 92px" in css2
              and "background-position: 0 -46px" in css2
              and "background-position: 0 -92px" in css2
              and "lgDotsBreath" in css2
              and "radial-gradient(ellipse 90% 84% at 50% 44%" in css2)
        check("图案候选已收敛为单一（弧/网格/斜纹/图案开关全移除）",
              "data-pat" not in css2
              and "repeating-radial-gradient" not in css2
              and "lgFigWeave" not in css2 and "lgGridDrift" not in css2)
        check("卡片吃风格变量：阴影 / 描边宽 / 圆角都可被覆盖",
              "var(--l-card-w, 1px)" in css2
              and "var(--l-card-r, 16px)" in css2
              and "box-shadow: var(--l-shadow)" in css2
              and "0 1px 2px rgba(0, 0, 0, .04)" in css2)

        st, js = call("GET", "/static/app.js")
        check("前端脚本可加载",
              st == 200 and "loadOverview" in js and "cloud_init" in js
              and "loadBackups" in js,
              "%d 字节" % (len(js) if isinstance(js, str) else 0))
        check("前端：风格写死为 pearl，无选型开关与死代码",
              "function lgStyle() { return 'pearl'; }" in js
              and "LG_STYLES" not in js and "LG_DARK" not in js
              and "LG_PATS" not in js and "lgPat" not in js
              and "lgSkin" not in js
              and 'data-skin="paper" data-bg="pearl"' in js
              and "lg-pattern" not in js)
        st, css3 = call("GET", "/app.css")
        check("相对路径资源路由可用（index.html 在 /admin 也能取到 app.css）",
              st == 200 and "--primary" in css3,
              "%d 字节" % (len(css3) if isinstance(css3, str) else 0))
        check("登录页为单屏：输入框与按钮同屏，无第二步弹窗",
              "'lgTok'" in js and "'lgBtn'" in js and "lg-fig" in js
              and "lg-bg" in js and "欢迎回来" in js
              and all(k not in js for k in
                      ("lgModal", "openAsk", "closeAsk", "lg-dots", "LG_ESC")))
        check("登录页已移除服务状态块（个人使用无意义）",
              all(k not in css2 for k in (".lg-sep", ".lg-status", ".lg-dot "))
              and "'lgDot'" not in js and "lg-status" not in js
              and "服务状态" not in js)
        check("控件为白底细描边，聚焦只加强描边 + 极淡 ring",
              "--l-line: rgba(0, 0, 0, .10)" in css2
              and "box-shadow: 0 0 0 3px var(--l-focus-ring)" in css2)
        check("动效可被系统「减弱动态效果」关掉",
              "prefers-reduced-motion" in css2)
        check("输入框样式已提权，不怕 app.css 通用规则覆盖",
              ".lg .lg-input input" in css2 and "-webkit-autofill" in css2
              and "credentials-auto-fill-button" in css2)
        check("入场动画不再抢 transform（否则鼠标视差被顶掉）",
              "@keyframes lgFadeIn { from { opacity: 0 } }" in css2
              and ".lg-panel.shake" in css2)
        check("早期的满屏纹理方案（点阵背景/波纹/扭索纹）已彻底移除",
              all(k not in css2 for k in
                  (".lg-bokeh", ".lg-rings", ".lg-guilloche", ".lg-pattern",
                   "bg-g1.svg", "lgGridDrift", "lgFigWeave", "lgFigSlide")))
        check("没有用 color-mix（不支持时整条 background-image 会失效）",
              "color-mix" not in css2)
        check("登录页含自绘标识与按钮图标",
              "SVG_MARK" in js and "SVG_LOCK" in js and "SVG_EYE_OFF" in js
              and "lgRing" in js)
        check("标识为圆头描边钥匙（非填充块）",
              'stroke-linecap="round"' in js and "11.9 12.1" in js
              and 'd="M8.5 3H15.5' not in js)
        check("密码默认明文可见，眼睛按钮可切回遮罩",
              'type="text" id="lgTok"' in js and "masked = !masked" in js)
        check("背景为纯 CSS，页面上没有常驻动画循环",
              "getContext" not in js and "requestAnimationFrame" not in js)
        check("登录页已移除多余文案与装饰",
              all(k not in js for k in (
                  "lgSerial", "lg-spine", "lg-feat",
                  "授权签发中心", "签发通行证", "卡密生成、机器码绑定",
                  "令牌在服务器上", "输入管理令牌，换取控制台通行权限")))
        # 两步验证的验证码框默认收起，服务端回 NEED_TOTP 才展开
        check("登录页有两个验证码输入框且默认隐藏",
              'id="lgCodeField" style="display:none"' in js
              and 'id="lgCode"' in js and "NEED_TOTP" in js)
        check("登录页文案为口语化措辞",
              "请输入密码" in js and "密码不正确" in js
              and all(k not in js for k in ("输入管理令牌", "data/config.json",
                                            "粘贴或输入管理令牌",
                                            '<label for="lgTok"'))
              and ".lg-dsub" not in css2
              and ".lg-modal" not in css2)

        st, svg = call("GET", "/static/favicon.svg")
        check("站点图标可加载", st == 200 and "<svg" in svg)

        st, _ = call("GET", "/api/health")
        # ---- 本次加固 / 修复的回归 ----
        st, d = call("POST", "/api/v1/verify",
                     {"app_id": "x" * 70000})
        check("超大请求体被拒（413）", st == 413 and d.get("err") == "TOO_LARGE", str(st))
        st, d = call("POST", "/api/v1/verify",
                     {"app_id": APP, "code": "C" * 5000})
        check("超长字段被拒（400）", st == 400 and d.get("err") == "BAD_PARAM", str(st))
        check("安全响应头齐备（防点击劫持 / MIME 嗅探 / 引用泄露）",
              all(h in SRC_HTTPD for h in
                  ('send_header("X-Content-Type-Options", "nosniff")',
                   'send_header("X-Frame-Options", "SAMEORIGIN")',
                   'send_header("Referrer-Policy"')))
        check("CORS 只对客户端接口开放，管理/代理商接口都不发 ACAO:*",
              'if not self.path.startswith(("/api/admin/", "/api/agent/")):' in SRC_HTTPD
              and 'send_header("Access-Control-Allow-Origin", "*")' in SRC_HTTPD)
        check("请求体护栏 + 两层限流就位（业务层可配 / 传输层兜底）",
              "MAX_BODY = 64 * 1024" in SRC_HTTPD
              and "def _check_fields" in SRC_HTTPD
              and "class _RateLimiter" in SRC_HTTPD
              and 'os.environ.get("KEYAUTH_RATE_LIMIT", "1") == "0"' in SRC_HTTPD
              and "def rate_ok" in SRC_SECURITY)
        check("换绑语义：新机器可自助解绑旧设备",
              "ORDER BY bind_at" in SRC_SERVICE
              and "unbound_machine" in SRC_SERVICE
              and "DEVICE_MISMATCH" in SRC_SERVICE)

        # 注意：这条依赖上面那次 health 调用的 st，我插入新断言后必须重新取一次
        st, _ = call("GET", "/api/health")
        # 注意：这条依赖上面那次 health 调用的 st，我插入新断言后必须重新取一次
        st, _ = call("GET", "/api/health")
        check("健康检查免鉴权", st == 200)

        st, _ = call("GET", "/static/%2e%2e/kauth/config.py")
        check("静态目录穿越被拦截", st in (403, 404), "HTTP %s" % st)

        # ---------------- 备份 ----------------
        st, d = call("POST", "/api/admin/backup", {}, token=TK)
        check("数据库热备份", d.get("ok") and d["path"].endswith(".db"), d.get("path", ""))

    finally:
        proc.terminate()
        try:
            out = proc.communicate(timeout=5)[0] or ""
        except Exception:
            proc.kill()
            out = ""
        shutil.rmtree(TMP_DATA, ignore_errors=True)

    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 60)
    print("总计 %d 项，通过 %d 项，失败 %d 项"
          % (len(results), len(results) - len(failed), len(failed)))
    print("=" * 60)
    if failed:
        print("\n--- 服务端输出 ---")
        print(out[-2500:])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
