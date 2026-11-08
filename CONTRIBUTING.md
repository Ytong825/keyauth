# 贡献指南

先谢谢你看这份文件。下面的规矩不多，但请读完再动手，能省掉来回沟通。

## 开发环境

```bash
git clone https://github.com/Ytong825/keyauth.git
cd keyauth
python server.py            # 起在 127.0.0.1:8787，终端打印管理令牌
python tests/selftest.py    # 99 项端到端自测，提交前必须全绿
```

- Python 3.8+，**不引入任何第三方依赖**（这是项目的核心约束，PR 里出现 `requirements.txt` 会被拒）
- 数据库用临时目录，别碰 `data/`：

  ```bash
  KEYAUTH_DATA=/tmp/ka-dev python server.py
  ```

- 前端是手写 HTML/CSS/JS，没有构建步骤，没有 npm。改完刷新浏览器即可。

## 提交前自查

```bash
python -m py_compile kauth/*.py server.py    # 后端语法
node --check static/app.js                    # 前端语法（如装了 node）
python tests/selftest.py                      # 回归
```

改动涉及界面时，附一张截图或 GIF。

## 代码约定

**后端**

- 只用标准库。需要新能力时先问「标准库能不能凑合」，能凑合就别引依赖
- SQL 一律参数化，禁止字符串拼参数
- 涉及比较敏感值（签名、令牌、哈希）时用 `hmac.compare_digest`
- 新增接口要同时更新 [docs/API.md](docs/API.md)
- 新增错误码要加进 `kauth/service.py` 的 `RESULT_TEXT`，否则界面会显示原始码

**前端**

- 不引框架、不引 CDN。所有资源本地化
- 事件绑定时注意作用域：`app.js` 是 IIFE，**内联 `onclick` 只能访问 `window` 上的东西**。
  需要在 HTML 里调的函数据必须显式挂到 `window`
- 列表渲染用 `esc()` 转义，别直接拼用户数据

## 提交信息

用 Conventional Commits 前缀，中文描述即可：

```
feat: 卡密库支持按批次导出
fix: 未激活的时间卡被显示成「永久」
docs: 补充 HTTPS 部署说明
refactor: 把签名校验抽到 security.py
test: 补 3 个换绑次数用尽的用例
```

一次提交只做一件事。格式化改动单独一个 commit，别和逻辑改动混在一起。

## Pull Request

1. 从 `main` 切分支：`git checkout -b feat/xxx`
2. 写清楚**为什么改**，而不只是改了什么
3. 关联 issue（如果有）：`Closes #12`
4. 确认 CI 绿了再请求 review

会被拒的情况：

- 引入第三方依赖（除非有充分理由并在 PR 里说明）
- 改动 `data/` 或把数据库、令牌、真实卡密带进仓库
- 只改格式的大 diff（会淹没实际改动）
- 破坏向后兼容却没在 CHANGELOG 里说明

## 报告问题

用 [issue 模板](https://github.com/Ytong825/keyauth/issues/new/choose)，附上：

- 版本 / commit
- Python 版本、操作系统
- 复现步骤，以及 `journalctl -u keyauth -n 50` 的相关片段
- **把卡密、AppSecret、管理令牌、真实 IP 打码**

安全问题不要开公开 issue，走 [SECURITY.md](SECURITY.md)。

## 行为准则

参与本项目即表示同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
