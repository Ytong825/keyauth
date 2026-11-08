## 这个 PR 做了什么

<!-- 一句话说清。不要只写「优化代码」 -->

## 为什么

<!-- 解决什么问题？关联的 issue：Closes #12 -->

## 改动类型

- [ ] 修 Bug
- [ ] 新功能
- [ ] 重构（不改变行为）
- [ ] 文档
- [ ] 其他：

## 怎么验证的

<!-- 跑过的命令、看过的页面、贴截图 -->

```bash
python tests/selftest.py
```

## 自查

- [ ] 没有引入第三方依赖
- [ ] `python -m py_compile kauth/*.py server.py` 通过
- [ ] `node --check static/app.js` 通过（改了前端的话）
- [ ] `python tests/selftest.py` 全绿
- [ ] 改了接口就同步更新了 `docs/API.md`
- [ ] 新错误码已加进 `service.RESULT_TEXT`
- [ ] 没有把 `data/`、数据库、令牌、真实卡密带进提交
- [ ] 破坏性改动已在 `CHANGELOG.md` 的 Unreleased 里说明

## 截图（界面改动必填）

<!-- 拖图进来 -->
