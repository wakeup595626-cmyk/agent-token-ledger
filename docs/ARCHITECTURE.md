# 架构说明

## 目标

本软件把当前电脑上多个智能体工具留下的 Token 记录，统一转换为只读事件，再按同一口径去重、校验和展示。

它不是一个云端账号面板，也不会把不同电脑的数据合并到一个服务端。

## 运行链路

```text
AgentTokenLedger.exe
  -> agent_token_ledger.app
  -> agent_token_ledger.webapp
  -> LedgerService 后台扫描线程
  -> pipeline.default_context 读取当前用户环境
  -> 各 SourceAdapter 只读扫描
  -> reconcile 去重
  -> validate_snapshot 校验
  -> reporting.report 生成界面和报告数据
  -> 本机 127.0.0.1 Web 服务
  -> pywebview / Edge 应用窗口 / 默认浏览器
```

## 主要模块

| 模块 | 职责 |
| --- | --- |
| `app.py` | 桌面程序入口，解析参数并启动应用窗口 |
| `desktop.py` | 原生 WebView、Edge 应用窗口和浏览器回退 |
| `webapp.py` | 本机 HTTP 服务、后台扫描循环和界面状态 |
| `pipeline.py` | 组装扫描上下文、来源适配器和去重 |
| `sources/` | 每个智能体工具一套只读解析逻辑 |
| `inventory.py` | 当前电脑的来源发现和四态检测 |
| `reporting.py` | 统一聚合、文本/JSON/CSV 报表 |
| `delivery.py` | 导出完整报告和 SHA-256 清单 |
| `web/` | 全中文应用界面，无外部 CDN 依赖 |

## 平台与数据目录

- Windows（当前发布与实测平台）：数据目录为 `%LOCALAPPDATA%\AgentTokenLedger`；扫描上下文解析 `%USERPROFILE%`、`%APPDATA%`、`%LOCALAPPDATA%`；窗口优先使用 Edge WebView2（`edgechromium`）。
- Linux（兼容启动，未实测）：数据目录为 `~/.local/share/AgentTokenLedger`；`appdata` 解析为 `~/.config`，`local_appdata` 解析为 `~/.local/share`；窗口使用系统默认 WebView 后端。
- macOS（兼容启动，未实测）：数据目录为 `~/Library/Application Support/AgentTokenLedger`；`appdata` 与 `local_appdata` 均解析为 `~/Library/Application Support`；窗口使用系统默认 WebView 后端。

开机自启仅由软件内开关写入 Windows 当前用户启动项实现，默认关闭；非 Windows 平台不提供该能力并在设置中显示不可用。

## 界面语言

界面翻译目录内置在 `web/app.js`，该文件只承载翻译目录；应用运行时统一由 `web/runtime.js` 提供。当前提供八种语言：zh-CN、zh-TW、en-US、ja-JP、ko-KR、de-DE、fr-FR、es-ES。`preferences.py` 的 `SUPPORTED_LANGUAGES` 与之对应，非法语言码回退为 zh-CN。设置页的“界面语言”下拉框在 `web/index.html` 内直接渲染这八种选项，`runtime.js` 负责保存选择、切换整页文案，并本地化金额、数字与星期标签。

应用启动时会对“界面语言”下拉框做一次前端自检：比对下拉框选项与翻译目录覆盖的语言是否完全一致，缺失或多余时给出警告，避免再次出现选项与目录脱节导致下拉框为空。

## 本地账本存储

命令行流程（`scan` / `export` 等子命令）把扫描批次写入开发数据库 `var\ledger.sqlite`，与桌面程序的内存统计互不影响。`persist_scan` 落库成功后默认只保留最近 10 次完成的扫描批次，更早的整批历史（events、来源快照、问题记录，均带级联删除）会被清掉并 VACUUM 回收磁盘；始终至少保留最新一次完成的扫描。`keep_scans=0` 可关闭自动清理。

## 统计口径

界面重点展示三项：

- 总输入 Token：普通输入和缓存输入的总和。
- 总输出 Token：模型生成的输出。
- 缓存命中 Token：已包含在总输入中的缓存读取量。

处理量 `processed_tokens` 用于去重和整体比较，不能替代上面三项。

去重顺序如下：

1. 同一来源相同事件键只保留一条。
2. Codex 原生记录优先于 Cockpit 会话镜像。
3. Cockpit 镜像只有在文件标识、会话序号和用量完全匹配时才从原生记录中扣除。
4. 网关日志、代理统计和汇总账本按独立来源处理，避免和原始请求混在一起。

## 扫描失败隔离

每个来源适配器单独捕获异常。一个来源读取失败时会进入“读取异常”，其他来源仍可完成扫描。界面不会把失败结果猜测成零用量。

## 界面状态

服务每秒提供只读状态，界面约每两秒拉取一次。后台每 30 秒重新扫描一次，也可以手动刷新或暂停自动刷新。

关闭原生应用窗口后，服务线程和本机 HTTP 服务一起退出。
