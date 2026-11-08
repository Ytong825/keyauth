#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebHook 推送：卡密激活 / 封禁 / 额度耗尽时回调业务方"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request

from . import db
from .util import now

TIMEOUT = 6


def emit(app: dict, event: str, card: dict = None, extra: dict = None) -> None:
    """异步推送，绝不阻塞主请求链路"""
    if not app:
        return
    subs = db.query(
        "SELECT * FROM webhooks WHERE enabled=1 AND (app_id='' OR app_id=?)",
        (app.get("app_id", ""),),
    )
    if not subs:
        return

    payload = {
        "event": event,
        "app_id": app.get("app_id", ""),
        "ts": now(),
    }
    if card:
        payload["card"] = {
            "code": card.get("code"),
            "plan": card.get("plan"),
            "card_type": card.get("card_type"),
            "status": card.get("status"),
            "expires_at": card.get("expires_at"),
            "machine_id": (extra or {}).get("machine_id"),
        }
    if extra:
        payload.update({k: v for k, v in extra.items() if k != "machine_id"})

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    for sub in subs:
        if event not in [e.strip() for e in str(sub["events"]).split(",")]:
            continue
        threading.Thread(target=_post, args=(sub, body), daemon=True).start()


def _post(sub: dict, body: bytes) -> None:
    headers = {"Content-Type": "application/json", "User-Agent": "KeyAuth-Webhook/1.0"}
    secret = str(sub.get("secret") or "")
    if secret:
        headers["X-KeyAuth-Signature"] = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    req = urllib.request.Request(sub["url"], data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            resp.read(512)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        pass          # 推送失败不影响主流程，也不重试
