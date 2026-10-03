# 本机智能体 Token 用量账本

[![CI](https://github.com/wakeup595626-cmyk/agent-token-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/wakeup595626-cmyk/agent-token-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/wakeup595626-cmyk/agent-token-ledger)](https://github.com/wakeup595626-cmyk/agent-token-ledger/releases)

本机智能体 Token 用量账本是一个只在本机运行的 Windows 桌面应用。它不是一张静态网页，也不需要把数据上传到服务器。双击 `AgentTokenLedger.exe` 后，程序会打开一个独立应用窗口，自动检测当前电脑上的智能体工具记录，并用全中文界面展示 Token 用量。

程序重点展示本机用量总量和费用：

- 总 Token（输入处理量与输出量合计）
- 总输入 Token
- 总输出 Token
- 缓存命中 Token
- 参考总费用（实采金额与未采集部分的估算值，美元与人民币）

统计图固定占用同一个区域，可以通过工具栏自由切换图形类型和统计对象：

- 柱状图：可细分为“Agent 工具”或“模型”，比较各分项的 Token 用量。
- 折线图：可细分为“Agent 工具”或“模型”，比较各分项的 Token 用量。
- 贡献图：使用类似 GitHub 的方格展示每天的使用量，范围跟随页面顶部的统计范围。

左侧导航只负责切换一级页面，图表内部只负责切换当前页面的图形类型和统计对象；程序不会同时堆放三张图，也不会修改 Codex、Cockpit、DeepSeek Harness、WorkBuddy、Trae 或 Antigravity 的原始数据。

## 普通用户使用

### 运行环境

- Windows 10 或 Windows 11，64 位。
- 发布版 `AgentTokenLedger.exe` 已包含运行环境，不需要另行安装 Python。
- 优先使用 Microsoft Edge WebView2 打开原生应用窗口。
- 如果当前电脑没有可用的 WebView2，程序会自动尝试 Microsoft Edge 应用窗口；两者都不可用时才回退到默认浏览器。

### 安装和启动

1. 从 GitHub Releases 下载 `AgentTokenLedger-windows-x64-v1.0.0.zip`。
2. 将压缩包解压到任意可写目录，例如桌面上的独立文件夹。
3. 双击 `AgentTokenLedger.exe`。
4. 程序打开应用窗口后即可查看统计结果。

也可以把 `AgentTokenLedger.exe` 单独放到桌面使用。程序自己的日志和 WebView 缓存会写入：

```text
%LOCALAPPDATA%\AgentTokenLedger
```

这些运行数据与来源工具的原始日志分开保存。

### 关闭和停止

- 关闭应用窗口会停止后台扫描服务并退出程序。
- 如果程序已经运行，再次双击同一个 EXE 会打开已有服务对应的应用窗口。
- “设置 → 运行控制”中有“停止本机服务”按钮，可确认后主动停止后台服务。
- “设置 → 运行控制 → 开机自动启动”默认关闭；只有在用户主动开启后，程序才会把当前 EXE 写入当前 Windows 用户的启动项。
- 暂停按钮只暂停自动刷新，不影响手动刷新。

程序默认每 30 秒重新扫描一次本机来源。

## 界面说明

应用窗口左侧是固定导航，右侧是当前页面内容。当前版本有五个一级页面：

| 页面 | 内容 |
| --- | --- |
| 总览 | 总 Token、输入、输出、缓存、参考总费用、三种可切换统计图和快速明细 |
| 用量明细 | 按 Agent 工具、模型、来源、账号、日期或记录类型查看 Token 与费用 |
| 本机来源检测 | 当前电脑的检测结果和明细 |
| 数据质量 | 数据校验、扫描问题和统计说明 |
| 设置 | 语言、主题、币种、汇率、刷新间隔、开机自动启动、运行控制和数据位置 |

总览顶部固定显示总 Token、总输入、总输出、缓存命中和参考总费用。扫描状态栏显示最近扫描时间、下次刷新时间、扫描耗时和去重后的事件数。

### 界面语言

程序内置八种主流语言，可在“设置 → 界面语言”切换并即时生效：简体中文、繁體中文、English、日本語、한국어、Deutsch、Français、Español。金额、数字与星期标签会跟随所选语言本地化。默认为简体中文。

### 运行平台

当前发布与实测平台为 Windows 10 / 11（64 位）。程序的启动逻辑对 Linux 与 macOS 做了兼容解析（数据目录使用 XDG 与 macOS 惯例路径、窗口使用系统默认 WebView 后端），可在这些平台上从源码运行；但 Linux 与 macOS 本轮尚未在真实机器上实测，开机自启等 Windows 专属能力在非 Windows 平台会自动显示不可用。

### 总量与费用口径

| 指标 | 含义 |
| --- | --- |
| 总 Token | 输入处理量与输出量的合计 |
| 总输入 Token | 普通输入与缓存输入的总和 |
| 总输出 Token | 模型生成的输出 Token |
| 缓存命中 Token | 从缓存中直接读取的输入，已经包含在总输入中 |
| 参考总费用 | 优先保留来源明确提供的实采金额；没有费用字段的部分，用已实采样本推导的单价估算；人民币按用户在设置中填写的汇率换算 |

页面中的总量、图表和明细表使用同一套去重后的数据。程序不会用字符数、消息长度或猜测值补足缺失 Token。费用部分只在存在实采样本时使用加权单价估算，并以 `≈` 和“参考估算”明确标识；没有实采费用样本时显示“无法估算”，不会把估算值冒充实际账单。实采记录显示“已采集”，实采与估算混合的记录显示“部分估算”，完全依赖估算的记录显示“参考估算”。

估算单价按“实采金额 ÷ 对应的已处理 Token”计算，再乘未采集部分的已处理 Token。由于不同模型和账号的真实价格可能不同，该金额只适合用于快速了解大致成本，不应作为财务账单。

因此，费用口径是“来源实采金额 + 未采集部分的参考估算”，不是 OpenAI、Anthropic 或其他云服务商账单的原始金额。人民币金额还会使用用户在设置页填写的汇率换算。

### 统计图切换

图表区提供两个互斥切换组，同一时间只显示一张图。

| 图形类型 | 统计对象 | 说明 |
| --- | --- | --- |
| 柱状图 | Agent 工具或模型 | 比较各分项的总 Token 用量 |
| 折线图 | Agent 工具或模型 | 用折线比较各分项的 Token 用量差异 |
| 贡献图 | 按天汇总 | 类似 GitHub 贡献图，范围跟随页面顶部的统计范围 |

鼠标移到柱子、折线点或日期方格上，可以查看输入、输出和缓存明细。模型数量较多时，折线图支持在图内横向滚动，不会把剩余模型合并成“其他模型”。

## 不同电脑如何自动检测

程序不会保存或复用开发电脑的用户名和目录。每次启动和刷新时，它都会重新读取运行它的当前 Windows 用户环境：

- `%USERPROFILE%`
- `%APPDATA%`
- `%LOCALAPPDATA%`

随后程序检查已支持工具的标准目录，并由对应适配器判断是否能读取可靠 Token。因此，同一个 EXE 复制到不同电脑后，会自动检测那台电脑上的当前用户数据，不需要手工修改配置。

这不是演示数据，也不是随机生成的模拟数字。程序只读取运行它的电脑上真实存在的本机日志；没有日志时不会凭消息长度或字符数猜测 Token。不同用户运行同一个 EXE 时，读取的是各自电脑的 `%USERPROFILE%`、`%APPDATA%` 和 `%LOCALAPPDATA%`，不会读到开发电脑的数据，也不会把开发电脑的数据打进发布包。

可读取范围受三个现实条件限制：

- 当前电脑安装了对应智能体工具。
- 该工具已经生成受支持的日志或数据库。
- 该工具版本仍使用本文列出的已知格式。

任一条件不满足时，界面会显示“本机未发现”“读取异常”或“不支持可靠采集”，而不是填造数据。

更完整的口径见 [数据真实性与跨电脑读取边界](docs/DATA_AUTHENTICITY.md)。

检测结果分为四种：

| 状态 | 含义 | 是否计入统计 |
| --- | --- | --- |
| 已发现 | 至少一个已知路径存在，读取正常 | 计入 |
| 本机未发现 | 支持该来源，但当前电脑没有已知路径 | 不计入 |
| 不支持可靠采集 | 已复核，但数据被加密、只有配置或没有 Token 字段 | 不计入，也不猜测 |
| 读取异常 | 路径存在，但适配器读取失败 | 不计入，并显示错误原因 |

“本机未发现”通常表示当前电脑没有安装对应工具，或者该工具还没有生成记录。它不代表统计程序崩溃。

自动检测只覆盖下列已知格式。第三方工具升级后如果改变目录或数据结构，界面会显示“读取异常”或“不支持可靠采集”，以便及时发现兼容问题。

### 可采集来源

| 智能体工具 | 默认读取位置 | 精度 |
| --- | --- | --- |
| Codex | `%USERPROFILE%\.codex\sessions`、`archived_sessions` | 请求级 |
| Codex Cockpit 会话镜像 | `%USERPROFILE%\.antigravity_cockpit\codex_session_usage.sqlite` | 请求级 |
| Cockpit Gateway | `%USERPROFILE%\.antigravity_cockpit\codex_local_access_logs.sqlite` | 请求级 |
| DeepSeek Harness | `%USERPROFILE%\.dsh\token-ledger\ledger.json` | 日/路由汇总 |
| WorkBuddy | `%USERPROFILE%\.workbuddy\projects` | 请求级 |
| WorkBuddy AI | `%USERPROFILE%\.workbuddy-ai\projects` | 请求级 |
| Trae | `%APPDATA%\TraeTools\data\usage_*.jsonl` | 导出请求行 |
| Antigravity Tools | `%USERPROFILE%\.antigravity_tools\token_stats.db` | 代理请求 |

### 已复核但不支持可靠采集

- Antigravity 原生会话
- TraeWork / TraeWork CN
- Trae SOLO / Trae SOLO CN
- TeleAgent
- CodeBuddy / CodeBuddy CN
- SheetAgent
- GitHub Copilot 本机会话

这些来源会保留在“本机来源检测”页面中，明确显示状态和原因，避免用户误以为程序漏掉了可用数据。

## 隐私与只读边界

- 程序不登录云端账号。
- 程序不上传统计、会话或报告。
- 程序不调用云端模型。
- 程序只监听本机回环地址 `127.0.0.1`。
- 来源 SQLite 数据库使用只读方式打开。
- JSON、JSONL 和导出文件按只读方式解析。
- 程序不会写入、重命名、移动或删除其他工具的数据。

报告包含本机来源路径、扫描时间和用量证据，适合本机查看和本地交付，不应直接上传到公开 GitHub 仓库。公共源码包不会包含本机数据库、报告、WebView 缓存或其他工具的原始日志。

## 从源码运行

需要 Python 3.11 或更高版本。

```powershell
python -m pip install -e ".[desktop]"
$env:PYTHONPATH = "src"
python -m agent_token_ledger
```

不加参数时会启动本机应用窗口。也可以只启动本地服务：

```powershell
$env:PYTHONPATH = "src"
python -m agent_token_ledger --no-browser
```

默认地址为 `http://127.0.0.1:8765/`。如果首选端口被占用，程序会在后续端口中寻找可用端口。

## 一键扫描与生成报告

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all.ps1
```

脚本会依次：

1. 运行自动测试；
2. 重新扫描当前电脑的来源；
3. 校验最新快照；
4. 生成 TXT、JSON、CSV 和 SHA-256 清单。

报告写入项目自己的 `reports` 目录。

## 构建 Windows 桌面程序

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-app.ps1
```

脚本会：

1. 运行测试；
2. 检查并安装固定版本的 PyInstaller 和 pywebview；
3. 构建单文件 `AgentTokenLedger.exe`；
4. 将 EXE 复制到当前用户桌面；
5. 默认停止，不生成 ZIP、源码包或任何发布资源包。

如果只构建、不复制到桌面：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-app.ps1 -NoDesktop
```

只有明确准备制作发布 ZIP 时，才显式添加 `-Package`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-app.ps1 -Package
```

默认桌面目录由 Windows 当前用户自动解析。自动化或自定义环境可以使用 `-DesktopDir` 和 `-OutputsRoot` 显式指定。当前版本的默认构建命令不会创建任何发布包。

## 生成开源和交付压缩包

发布包脚本只在确认版本为最终版后运行。当前版本不要执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package.ps1
```

脚本会生成：

| 文件 | 用途 | 是否适合公开上传 |
| --- | --- | --- |
| `agent-token-ledger-v1.0.0-source.zip` | 公共源码、测试、脚本、文档和配置 | 是 |
| `agent-token-ledger-v1.0.0-reports.zip` | 当前电脑生成的本地报告 | 否 |
| `agent-token-ledger-v1.0.0-delivery.zip` | 源码、文档和本地报告的完整交付 | 否 |
| `AgentTokenLedger-windows-x64-v1.0.0.zip` | Windows 可执行程序和发布文档 | 是 |

每个 ZIP 都会同时生成 `.sha256` 校验文件。

公共源码包和 Windows 发布包都会排除：

- `var\ledger.sqlite`
- `reports`
- WebView 用户缓存
- 日志、临时文件和 Python 缓存
- 其他智能体工具的原始数据库或日志

## 项目结构

```text
.
├─ src\agent_token_ledger\        应用、扫描器、Web 服务和静态界面
├─ src\agent_token_ledger\sources 各智能体工具的只读适配器
├─ tests\                         自动测试
├─ scripts\                       测试、扫描、报告、构建和打包脚本
├─ docs\                          架构、自动检测、来源、隐私和发布文档
├─ assets\                        应用图标
├─ .github\                       CI、Release 和 Issue 模板
├─ pyproject.toml                 Python 包配置
└─ README.md                      中文使用和构建说明
```

更详细的设计和发布说明见 `docs` 目录。

## 开源发布

项目使用 MIT 许可证。准备上传 GitHub 时：

1. 只提交源码目录和公开文档。
2. 不要提交 `var`、`reports`、数据库、日志或本机 WebView 缓存。
3. 在 GitHub Releases 中上传 `-source.zip`、Windows 发布 ZIP 和对应 `.sha256`。
4. 不要把 `-reports.zip` 或 `-delivery.zip` 发布到公开仓库。

`.gitignore` 已覆盖常见本机运行数据。GitHub Actions 工作流会运行测试，并在发布标签中构建 Windows 程序。

## 当前版本

版本：`1.0.0`

更新内容见 `CHANGELOG.md`。
