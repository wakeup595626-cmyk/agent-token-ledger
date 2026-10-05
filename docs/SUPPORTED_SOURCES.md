# 支持的来源

## 可采集来源

| 智能体 | 来源类型 | 默认读取位置 | 精度 |
| --- | --- | --- | --- |
| Codex | 本机原始记录 | `%USERPROFILE%\.codex\sessions`、`archived_sessions` | 请求级 |
| Codex | Cockpit 会话镜像 | `%USERPROFILE%\.antigravity_cockpit\codex_session_usage.sqlite` | 请求级 |
| Cockpit Gateway | 网关日志 | `%USERPROFILE%\.antigravity_cockpit\codex_local_access_logs.sqlite` | 请求级 |
| DeepSeek Harness | 本机原生日志（插件账本兜底） | `%DSH_HOME%\sessions`（未设置时为 `%USERPROFILE%\.dsh\sessions`） | 请求级 |
| WorkBuddy | 本机记录 | `%USERPROFILE%\.workbuddy\projects` | 请求级 |
| WorkBuddy AI | 本机记录 | `%USERPROFILE%\.workbuddy-ai\projects` | 请求级 |
| Trae | TraeTools 导出 | `%APPDATA%\TraeTools\data\usage_*.jsonl` | 请求级 |
| Antigravity Tools | 代理统计 | `%USERPROFILE%\.antigravity_tools\token_stats.db` | 代理请求 |

DeepSeek Harness 优先解析 `sessions` 目录下的原生日志；数据目录由 `DSH_HOME` 决定，未设置时回退 `%USERPROFILE%\.dsh`。程序还会浅层检查其它固定盘符的 `\.dsh` 与 `X:\Users\*\.dsh`，以便读取用户目录在 D 盘等其它盘符的机器，整个过程只读、不做全盘递归。
## 已复核但不支持可靠采集

以下来源在当前复核中没有稳定、可解释的 Token 字段，或者数据会被加密、只有额度状态：

- Antigravity 原生会话
- TraeWork / TraeWork CN
- Trae SOLO / Trae SOLO CN
- TeleAgent
- CodeBuddy / CodeBuddy CN
- SheetAgent
- GitHub Copilot 本机会话

这些项目保留在“本机来源检测”中，以避免用户误以为程序漏掉了可用数据。无法可靠还原时，界面明确显示“不支持可靠采集”，不会估算 Token。

## 口径原则

- 输入、输出和缓存命中分开保存。
- 不把网关统计自动并入 Codex 原始请求。
- 不用字符数或消息长度猜测 Token。
- 同一请求重复出现时优先保留可验证的原始记录。
- 来源格式变化时以错误或复核状态暴露问题，不静默修改数据。
