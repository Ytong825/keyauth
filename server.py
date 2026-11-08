#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KeyAuth —— 卡密授权与发卡系统

启动：
    python server.py                     # 默认 0.0.0.0:8787
    python server.py -p 9000
    python server.py --host 127.0.0.1 -p 8787

首次启动会在 data/ 目录生成 config.json（管理令牌、密钥）与 keyauth.db。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kauth import config, db, httpd          # noqa: E402
from kauth.util import now                  # noqa: E402


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检测端口是否已被占用。

    Windows 的 SO_REUSEADDR 允许两个进程绑同一个端口，于是会出现
    「两个实例争抢请求、管理令牌随机对不上」这种极难排查的现象，
    所以启动前必须先确认端口是干净的。
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="KeyAuth 卡密授权服务")
    ap.add_argument("-p", "--port", type=int,
                    default=int(os.environ.get("PORT", "8787")))
    ap.add_argument("--host", default=os.environ.get("BIND", "0.0.0.0"))
    args = ap.parse_args()

    if port_in_use(args.port):
        sys.stderr.write(
            "\n[x] 端口 %d 已被占用。\n"
            "    最常见的原因是上一次启动的实例还在运行，或者旧进程没退干净。\n"
            "    此时两个实例会同时绑定该端口，请求被随机分发，\n"
            "    表现为「管理令牌时对时错」这种很难查的问题。\n\n"
            "    处理办法：先停掉旧进程，或者换个端口：\n"
            "        python server.py -p 9000\n\n" % args.port)
        sys.exit(1)

    db.init()

    # 启动时回收一次过期日志。心跳 3 分钟一条，不回收日志表会无限长。
    try:
        from kauth.admin import cleanup_logs
        n = cleanup_logs()
        if n.get("deleted"):
            print("  [清理] 删除 %d 条超过 %d 天的校验日志"
                  % (n["deleted"], n["days"]))
    except Exception:
        pass

    line = "═" * 66
    cfg = config.CFG
    print(line)
    print("  KeyAuth 卡密授权系统 v1.3.0")
    print(line)
    print("  管理后台   http://127.0.0.1:%d/admin" % args.port)
    print("  验证接口   http://127.0.0.1:%d/api/v1/verify" % args.port)
    print("  心跳接口   http://127.0.0.1:%d/api/v1/heartbeat" % args.port)
    print("  管理令牌   %s" % cfg["admin_token"])
    print("  数据目录   %s" % config.DATA_DIR)
    print(line)

    app = db.query("SELECT app_id, name FROM apps ORDER BY id LIMIT 1")
    if app:
        print("  默认应用   %s（%s）" % (app[0]["name"], app[0]["app_id"]))
        print("             AppSecret 请在「应用」页复制")
        print(line)

    try:
        httpd.serve(args.host, args.port)
    except KeyboardInterrupt:
        print("\n已停止")
    except OSError as e:
        sys.stderr.write("启动失败：%s\n" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
