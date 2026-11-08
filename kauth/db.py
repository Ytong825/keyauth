#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 访问层：连接管理、表结构、初始化与轻量迁移"""
from __future__ import annotations

import sqlite3
import threading

from . import config
from .util import gen_hex, now

_local = threading.local()


# ---------------------------------------------------------------- 表结构
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 应用：每个软件一套独立密钥
CREATE TABLE IF NOT EXISTS apps (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT    NOT NULL,
    app_id             TEXT    NOT NULL UNIQUE,
    app_secret         TEXT    NOT NULL,
    status             TEXT    NOT NULL DEFAULT 'active',   -- active / disabled
    require_sign       INTEGER NOT NULL DEFAULT 1,
    heartbeat_interval INTEGER NOT NULL DEFAULT 180,        -- 建议心跳间隔（秒）
    webhook_url        TEXT    NOT NULL DEFAULT '',
    note               TEXT    NOT NULL DEFAULT '',
    created_at         INTEGER NOT NULL
);

-- 套餐：制卡预设
CREATE TABLE IF NOT EXISTS plans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id        TEXT    NOT NULL DEFAULT '',
    name          TEXT    NOT NULL,
    card_type     TEXT    NOT NULL DEFAULT 'time',   -- time / count / point
    duration_days INTEGER NOT NULL DEFAULT 30,       -- 时间卡有效天数，0 = 永久
    total_value   INTEGER NOT NULL DEFAULT 0,        -- 次数卡/点数卡的初始额度
    max_devices   INTEGER NOT NULL DEFAULT 1,
    unbind_limit  INTEGER NOT NULL DEFAULT 1,
    price         REAL    NOT NULL DEFAULT 0,
    note          TEXT    NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL
);

-- 卡密
CREATE TABLE IF NOT EXISTS cards (
    code          TEXT PRIMARY KEY,
    app_id        TEXT    NOT NULL DEFAULT '',
    plan_id       INTEGER,
    plan          TEXT    NOT NULL DEFAULT '',
    card_type     TEXT    NOT NULL DEFAULT 'time',
    duration_days INTEGER NOT NULL DEFAULT 0,
    total_value   INTEGER NOT NULL DEFAULT 0,
    used_value    INTEGER NOT NULL DEFAULT 0,
    max_devices   INTEGER NOT NULL DEFAULT 1,
    unbind_limit  INTEGER NOT NULL DEFAULT 1,
    unbind_used   INTEGER NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'unused',  -- unused/active/expired/used_up/banned
    note          TEXT    NOT NULL DEFAULT '',
    batch         TEXT    NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    activated_at  INTEGER,
    expires_at    INTEGER,
    last_used_at  INTEGER
);

-- 设备绑定
CREATE TABLE IF NOT EXISTS binds (
    code       TEXT    NOT NULL,
    machine_id TEXT    NOT NULL,
    bind_at    INTEGER NOT NULL,
    last_seen  INTEGER NOT NULL,
    PRIMARY KEY (code, machine_id)
);

-- 校验日志
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         INTEGER NOT NULL,
    app_id     TEXT    NOT NULL DEFAULT '',
    code       TEXT    NOT NULL DEFAULT '',
    machine_id TEXT    NOT NULL DEFAULT '',
    ip         TEXT    NOT NULL DEFAULT '',
    action     TEXT    NOT NULL DEFAULT 'verify',
    result     TEXT    NOT NULL DEFAULT '',
    detail     TEXT    NOT NULL DEFAULT ''
);

-- 后台操作审计
CREATE TABLE IF NOT EXISTS audits (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     INTEGER NOT NULL,
    actor  TEXT    NOT NULL DEFAULT 'admin',
    ip     TEXT    NOT NULL DEFAULT '',
    action TEXT    NOT NULL,
    target TEXT    NOT NULL DEFAULT '',
    detail TEXT    NOT NULL DEFAULT ''
);

-- WebHook 订阅
CREATE TABLE IF NOT EXISTS webhooks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id     TEXT    NOT NULL DEFAULT '',
    url        TEXT    NOT NULL,
    events     TEXT    NOT NULL DEFAULT 'card.activated',
    secret     TEXT    NOT NULL DEFAULT '',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

-- 公告（下发给客户端）
CREATE TABLE IF NOT EXISTS notices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id     TEXT    NOT NULL DEFAULT '',
    title      TEXT    NOT NULL,
    content    TEXT    NOT NULL DEFAULT '',
    level      TEXT    NOT NULL DEFAULT 'info',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

-- 管理员账号（多账号 + 角色）。config 里的 admin_token 仍是 owner 级超级令牌，
-- 这套是给人用的：有用户名、能分级、能单独停用。
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    pwd_hash      TEXT    NOT NULL,
    pwd_salt      TEXT    NOT NULL,
    name          TEXT    NOT NULL DEFAULT '',
    role          TEXT    NOT NULL DEFAULT 'admin',      -- owner / admin / viewer
    status        TEXT    NOT NULL DEFAULT 'active',
    token         TEXT    NOT NULL DEFAULT '',
    token_exp     INTEGER NOT NULL DEFAULT 0,
    last_login_at INTEGER,
    last_login_ip TEXT    NOT NULL DEFAULT '',
    totp_secret   TEXT    NOT NULL DEFAULT '',          -- base32 密钥，只在绑定时写
    totp_enabled  INTEGER NOT NULL DEFAULT 0,
    totp_last_step INTEGER NOT NULL DEFAULT 0,          -- 用过的时间步，防同码重放
    totp_recovery TEXT    NOT NULL DEFAULT '[]',        -- 恢复码哈希列表
    created_at    INTEGER NOT NULL
);

-- 代理商（分销）：只有制卡与操作卡权限，没有删除权
CREATE TABLE IF NOT EXISTS agents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    pwd_hash      TEXT    NOT NULL,
    pwd_salt      TEXT    NOT NULL,
    name          TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'active',      -- active / disabled
    note          TEXT    NOT NULL DEFAULT '',
    token         TEXT    NOT NULL DEFAULT '',            -- 当前会话令牌
    token_exp     INTEGER NOT NULL DEFAULT 0,
    last_login_at INTEGER,
    last_login_ip TEXT    NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL
);

-- 代理商能制卡的应用
CREATE TABLE IF NOT EXISTS agent_apps (
    agent_id INTEGER NOT NULL,
    app_id   TEXT    NOT NULL,
    PRIMARY KEY (agent_id, app_id)
);

-- 代理商配额：一个应用 × 一种卡规格一条记录
CREATE TABLE IF NOT EXISTS agent_quotas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      INTEGER NOT NULL,
    app_id        TEXT    NOT NULL,
    card_type     TEXT    NOT NULL DEFAULT 'time',        -- time / hour
    duration_days INTEGER NOT NULL DEFAULT 30,
    max_devices   INTEGER NOT NULL DEFAULT 1,
    unbind_limit  INTEGER NOT NULL DEFAULT 1,
    quota_total   INTEGER NOT NULL DEFAULT 0,
    quota_used    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (agent_id, app_id, card_type, duration_days, max_devices, unbind_limit)
);

CREATE INDEX IF NOT EXISTS idx_cards_status  ON cards(status);
CREATE INDEX IF NOT EXISTS idx_cards_app     ON cards(app_id);
CREATE INDEX IF NOT EXISTS idx_cards_batch   ON cards(batch);
CREATE INDEX IF NOT EXISTS idx_cards_plan    ON cards(plan_id);
CREATE INDEX IF NOT EXISTS idx_binds_code    ON binds(code);
CREATE INDEX IF NOT EXISTS idx_binds_seen    ON binds(last_seen);
CREATE INDEX IF NOT EXISTS idx_logs_ts       ON logs(ts);
CREATE INDEX IF NOT EXISTS idx_logs_result   ON logs(result);
CREATE INDEX IF NOT EXISTS idx_logs_code     ON logs(code);
CREATE INDEX IF NOT EXISTS idx_audits_ts     ON audits(ts);
CREATE INDEX IF NOT EXISTS idx_agent_quotas  ON agent_quotas(agent_id, app_id);
CREATE INDEX IF NOT EXISTS idx_agents_token  ON agents(token);
CREATE INDEX IF NOT EXISTS idx_admins_token  ON admins(token);

-- 登录失败节流：按「类型:账号」计数，撞库锁定用（见 kauth/throttle.py）
CREATE TABLE IF NOT EXISTS login_throttle (
    key          TEXT    PRIMARY KEY,                    -- admin:zhangsan / agent:lisi
    fails        INTEGER NOT NULL DEFAULT 0,
    first_at     INTEGER NOT NULL DEFAULT 0,
    last_at      INTEGER NOT NULL DEFAULT 0,
    locked_until INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_throttle_last ON login_throttle(last_at);
"""

# ---------------------------------------------------------------- 连接
def conn() -> sqlite3.Connection:
    """每线程一个连接"""
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(config.DB_FILE, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=20000")
        _local.conn = c
    return c


def query(sql: str, args=()) -> list:
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql: str, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def scalar(sql: str, args=(), default=0):
    r = conn().execute(sql, args).fetchone()
    if not r:
        return default
    v = r[0]
    return default if v is None else v


def execute(sql: str, args=()) -> int:
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur.rowcount


def insert_id(sql: str, args=()) -> int:
    """执行 INSERT 并返回新行 id。

    execute() 只返回 rowcount（对 INSERT 恒为 1），拿不到主键，
    于是"建套餐 → 拿 id → 制卡时带上"这条链在 API 层串不起来。
    """
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return int(cur.lastrowid or 0)


def executemany(sql: str, rows) -> int:
    c = conn()
    cur = c.executemany(sql, rows)
    c.commit()
    return cur.rowcount


def close() -> None:
    c = getattr(_local, "conn", None)
    if c is not None:
        c.close()
        _local.conn = None


# ---------------------------------------------------------------- 初始化
def _migrate() -> None:
    """老库补列。SQLite 的 ALTER TABLE 只支持加列，够用。"""
    cols = {r["name"] for r in query("PRAGMA table_info(cards)")}
    if "agent_id" not in cols:
        execute("ALTER TABLE cards ADD COLUMN agent_id INTEGER NOT NULL DEFAULT 0")
    if "agent_name" not in cols:
        execute("ALTER TABLE cards ADD COLUMN agent_name TEXT NOT NULL DEFAULT ''")
    execute("CREATE INDEX IF NOT EXISTS idx_cards_agent ON cards(agent_id)")

    # 管理员两步验证
    acols = {r["name"] for r in query("PRAGMA table_info(admins)")}
    for col, ddl in (
        ("totp_secret", "ALTER TABLE admins ADD COLUMN totp_secret TEXT NOT NULL DEFAULT ''"),
        ("totp_enabled", "ALTER TABLE admins ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0"),
        # 已用过的时间步，防同一个验证码在 30 秒内被重放
        ("totp_last_step", "ALTER TABLE admins ADD COLUMN totp_last_step INTEGER NOT NULL DEFAULT 0"),
        ("totp_recovery", "ALTER TABLE admins ADD COLUMN totp_recovery TEXT NOT NULL DEFAULT '[]'"),
    ):
        if col not in acols:
            execute(ddl)


def init() -> None:
    c = conn()
    c.executescript(SCHEMA)
    c.commit()
    _migrate()

    # 登录节流表只在登录失败时写，一天扫一次就够，避免无限长
    try:
        execute("DELETE FROM login_throttle WHERE last_at < ?", (now() - 86400,))
    except Exception:
        pass

    if scalar("SELECT COUNT(*) FROM apps") == 0:
        c.execute(
            "INSERT INTO apps(name,app_id,app_secret,status,require_sign,"
            "heartbeat_interval,note,created_at) VALUES(?,?,?,'active',1,180,?,?)",
            ("默认应用", "app_" + gen_hex(8), gen_hex(24),
             "首次启动自动创建，可改名或删除", now()),
        )
        c.commit()


def list_backups() -> list:
    """列出 data/backup/ 里的备份文件，新的在前。"""
    import os
    if not os.path.isdir(config.BACKUP_DIR):
        return []
    out = []
    for f in sorted(os.listdir(config.BACKUP_DIR), reverse=True):
        if not f.endswith(".db"):
            continue
        p = os.path.join(config.BACKUP_DIR, f)
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append({"name": f, "size": st.st_size,
                    "mtime": int(st.st_mtime)})
    return out


def backup_path(name: str):
    """只允许 data/backup/ 下的 .db 文件，防目录穿越。"""
    import os
    safe = os.path.basename(str(name or ""))
    if not safe.endswith(".db"):
        return None
    p = os.path.join(config.BACKUP_DIR, safe)
    return p if os.path.isfile(p) else None


def backup() -> str:
    """把数据库热备份到 data/backup/"""
    import os
    import time
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    name = "keyauth-%s.db" % time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(config.BACKUP_DIR, name)
    dst = sqlite3.connect(path)
    with dst:
        conn().backup(dst)
    dst.close()

    # 只保留最近 20 份
    files = sorted(f for f in os.listdir(config.BACKUP_DIR) if f.endswith(".db"))
    for old in files[:-20]:
        try:
            os.remove(os.path.join(config.BACKUP_DIR, old))
        except OSError:
            pass
    return path
