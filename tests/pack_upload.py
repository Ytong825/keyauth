"""把项目打成"直接拖进 FinalShell 就能用"的 zip。

排除：本地 data/（含本机令牌与测试数据）、__pycache__、临时文件
包含：install.sh / update.sh / server.py / kauth / static / client_demo.py / README / deploy
"""
import zipfile
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "keyauth-上传服务器.zip"

SKIP_TOP = {"data", "__pycache__", ".git", "_smoke", "_testdata"}
SKIP_EXT = (".pyc", ".db", ".db-wal", ".db-shm", ".log")
SKIP_FILE = {".DS_Store", "Thumbs.db"}


def main():
    if OUT.exists():
        OUT.unlink()
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(ROOT.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(ROOT)
            if rel.parts[0] in SKIP_TOP:
                continue
            if any(x in SKIP_TOP for x in rel.parts):
                continue
            if p.name in SKIP_FILE or p.suffix in SKIP_EXT:
                continue
            if rel.parts[0] == "tests" and p.name != "selftest.py":
                continue
            z.write(p, str(pathlib.Path("keyauth") / rel))
            n += 1

    print(f"已打包 {n} 个文件 -> {OUT}")
    print(f"大小 {OUT.stat().st_size/1024:.0f} KB\n")

    # 校验：包内必须有的文件
    must = ["keyauth/install.sh", "keyauth/update.sh", "keyauth/server.py",
            "keyauth/kauth/httpd.py", "keyauth/static/index.html",
            "keyauth/static/app.js", "keyauth/static/app.css",
            "keyauth/static/login.css", "keyauth/static/favicon.svg",
            "keyauth/client_demo.py"]
    with zipfile.ZipFile(OUT) as z:
        names = set(z.namelist())
        missing = [m for m in must if m not in names]
        leaked = [x for x in names if "/data/" in x or x.endswith((".db", ".pyc"))]
    print("必需文件缺失:", missing or "无")
    print("不该出现的（本地数据/缓存）:", leaked or "无")
    if missing or leaked:
        sys.exit(1)

    # 语法校验（Git Bash）
    print("\n包内文件：")
    for i in sorted(names):
        print("  ", i)


if __name__ == "__main__":
    main()
