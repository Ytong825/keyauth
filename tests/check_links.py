#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档死链检查：所有 Markdown 里的相对链接必须指向真实文件。

只查仓库内相对路径。http(s)、mailto、纯锚点（#xxx）跳过。
锚点不校验——GitHub 的标题 slug 规则和本地不一致，硬查会误报。

用法：
    python tests/check_links.py          # 有问题退出码 1
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "data", "__pycache__", "node_modules", ".github/workflows"}
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_FENCE = re.compile(r"```.*?```", re.S)
# HTML 注释里的占位内容不算文档内容（比如还没放图的 <img>）
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
# HTML 里的 src="./x.png" / href='x'
ATTR = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)


def md_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel != "." and any(p in SKIP_DIRS for p in rel.split(os.sep)):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower().endswith((".md", ".markdown")):
                yield os.path.join(dirpath, fn)


def strip_noise(text: str) -> str:
    """去掉注释、代码块和行内代码，避免把示例 / 占位里的链接当真链接。"""
    text = HTML_COMMENT.sub("", text)
    text = CODE_FENCE.sub("", text)
    return INLINE_CODE.sub("", text)


def check_one(path: str):
    bad = []
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    text = strip_noise(raw)
    targets = [m.group(1) for m in LINK.finditer(text)]
    targets += [m.group(1) for m in ATTR.finditer(text)]
    base = os.path.dirname(path)
    for t in targets:
        t = t.strip()
        if not t or t.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
            continue
        target = t.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        full = os.path.normpath(os.path.join(base, target))
        if not os.path.exists(full):
            bad.append((os.path.relpath(path, ROOT), t))
    return bad


def main() -> int:
    files = sorted(md_files(ROOT))
    total_links = 0
    problems = []
    for f in files:
        bad = check_one(f)
        problems += bad
        total_links += 1
    if problems:
        print("发现 %d 处死链：" % len(problems))
        for src, target in problems:
            print("  %-28s -> %s" % (src, target))
        return 1
    print("文档死链检查：%d 个 Markdown 文件，相对链接全部有效" % total_links)
    return 0


if __name__ == "__main__":
    sys.exit(main())
