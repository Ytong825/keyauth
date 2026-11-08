#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置加载与持久化。

配置优先级：环境变量 KEYAUTH_DATA 指定的数据目录 > 项目内的 data/ 目录
"""
from __future__ import annotations

import json
import os
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.environ.get("KEYAUTH_DATA") or os.path.join(BASE_DIR, "data"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

CONF_FILE = os.path.join(DATA_DIR, "config.json")
DB_FILE = os.path.join(DATA_DIR, "keyauth.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")


def _defaults() -> dict:
    return {
        "admin_token": secrets.token_urlsafe(32),
        "clock_skew": 300,            # 客户端时间戳允许偏差（秒）
        "nonce_ttl": 600,             # nonce 去重窗口（秒）
        "rate_limit": 120,            # 单 IP 每分钟最大请求数
        "require_sign": True,         # 是否强制签名
        "site_name": "KeyAuth",
        "site_desc": "卡密授权验证系统",
        "announcement": "",           # 客户端登录时下发的公告
        "maintenance": False,         # 维护模式
        "min_client_version": "",     # 最低客户端版本，留空不校验
        # 对外访问地址，如 https://auth.example.com。留空则接入文档按当前浏览器地址显示。
        # 反向代理 / 换端口 / 内网访问时靠它固定，不然文档里的地址会跟着变。
        "public_base_url": "",
        # 校验日志保留天数。0 = 永久保留（日志表会一直长）。
        # 客户端每 3 分钟一次心跳，一台机器一天就是 480 条，必须有个回收机制。
        "log_retention_days": 90,
    }


def load() -> dict:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except OSError as e:
        raise SystemExit("无法创建数据目录 %s：%s" % (DATA_DIR, e))

    cfg: dict = {}
    if os.path.exists(CONF_FILE):
        try:
            with open(CONF_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except Exception:
            cfg = {}

    changed = False
    for k, v in _defaults().items():
        if k not in cfg or cfg[k] is None or cfg[k] == "":
            # 布尔值允许 False，不要被上面这个判断重置
            if k in cfg and isinstance(cfg[k], bool):
                continue
            cfg[k] = v
            changed = True
    if changed or not os.path.exists(CONF_FILE):
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CONF_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONF_FILE)


CFG = load()
