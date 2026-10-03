# 参与贡献

感谢你愿意改进本机智能体 Token 用量账本。

## 提交问题

提交 Issue 时请说明：

- Windows 版本和 Python 版本。
- 智能体工具名称、版本和本机数据目录。
- 是“未发现”“读取异常”还是“不支持可靠采集”。
- 可复现步骤，以及去除账号、密钥和私人内容后的最小日志片段。

不要把真实 API Key、访问令牌、账号 Cookie、完整会话正文或未经处理的私密日志上传到公开 Issue。

## 提交代码

1. 阅读 `docs/ARCHITECTURE.md` 和 `docs/AUTO_DETECTION.md`。
2. 为新来源增加独立的 `SourceAdapter`，不要把解析逻辑塞进界面代码。
3. 保持只读边界，不修改其他软件的数据目录。
4. 为新增格式补充单元测试和最小匿名样例。
5. 运行：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

6. 更新 `docs/SUPPORTED_SOURCES.md` 和 `CHANGELOG.md`。

## 新增来源的验收标准

- 能明确说明 Token 字段的语义和单位。
- 能说明是否会与已有来源重复，以及如何去重。
- 无法可靠取得 Token 时返回“不支持可靠采集”，不能猜测数字。
- 扫描失败时只影响该来源，不能破坏其他来源的统计。
- 不发送网络请求，不写回原始来源。

## 提交标题

建议使用以下前缀：

- `feat:` 新功能
- `fix:` 缺陷修复
- `docs:` 文档
- `test:` 测试
- `build:` 构建和发布
- `refactor:` 不改变行为的重构
