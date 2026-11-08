# 遇到问题去哪儿

按下面的顺序走，比直接开 issue 快得多。

## 1. 先翻文档

| 你的问题 | 看这里 |
|---|---|
| 装不上、起不来、502 | [docs/DEPLOY.md](docs/DEPLOY.md) 的「排错」 |
| 客户端签名不过、`BAD_SIGN` / `TIME_SKEW` | [docs/CLIENT.md](docs/CLIENT.md) 的错误码表 |
| 接口参数、返回结构 | [docs/API.md](docs/API.md) |
| 「为什么不用 FastAPI / 能撑多少量」 | [docs/FAQ.md](docs/FAQ.md) |
| 想加功能、想知道排期 | [ROADMAP.md](ROADMAP.md) |

## 2. 用 Issues 报 bug

开 issue 前请带上这四样，缺一样我大概率要来回问：

1. **版本**：`curl http://127.0.0.1:8787/api/health` 返回的 `version`
2. **环境**：Python 版本、系统发行版、是否走 Nginx
3. **现象**：完整报错或截图，不要只说「用不了」
4. **复现步骤**：从哪一步开始不对

模板已经填好，直接选「Bug report」即可。

## 3. 安全漏洞不要开 issue

见 [SECURITY.md](SECURITY.md)，走私信，我确认后再公开。

## 4. 想加功能

先看 [ROADMAP.md](ROADMAP.md) 里「明确不做」那几条——列进去的说明我想过了，讨论成本高。
不在列表里的，开 issue 描述**使用场景**（你要解决什么问题），比「加个 XX 功能」有用。

## 5. 其他

- 想自己动手改：见 [CONTRIBUTING.md](CONTRIBUTING.md)
- 商业授权 / 定制开发：见 [docs/SPONSOR.md](docs/SPONSOR.md) 末尾的联系方式
