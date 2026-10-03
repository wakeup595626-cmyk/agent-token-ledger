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
