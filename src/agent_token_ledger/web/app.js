(() => {
  const translations = {
    "zh-CN": {
      "app.name": "智能体用量账本",
      "app.localOnly": "本机只读统计",
      "app.privacyTitle": "本地只读运行",
      "app.privacyShort": "数据只保存在当前电脑",
      "app.versionLabel": "版本",
      "nav.main": "主导航",
      "nav.sectionData": "统计中心",
      "nav.overview": "总览",
      "nav.usage": "用量明细",
      "nav.sources": "本机来源检测",
      "nav.quality": "数据质量",
      "nav.settings": "设置",
      "page.overview.title": "总览",
      "page.overview.subtitle": "查看总体令牌、费用和分项趋势",
      "page.usage.title": "用量明细",
      "page.usage.subtitle": "按智能体工具、模型和其他维度查看完整明细",
      "page.sources.title": "本机来源检测",
      "page.sources.subtitle": "每次启动都会重新检测当前电脑",
      "page.quality.title": "数据质量",
      "page.quality.subtitle": "查看校验结果、扫描问题和统计口径",
      "page.settings.title": "设置",
      "page.settings.subtitle": "管理语言、币种、汇率、主题和刷新频率",
      "action.refresh": "立即刷新",
      "action.refreshTitle": "立即扫描全部来源",
      "action.pause": "暂停",
      "action.pauseContinue": "继续",
      "action.pauseTitle": "暂停或继续自动刷新",
      "action.continueTitle": "继续自动刷新",
      "action.stop": "停止",
      "action.stopConfirm": "确定要停止本机服务吗？",
      "action.stopTitle": "停止本机服务",
      "action.exportCsv": "导出 CSV",
      "action.exportJson": "导出 JSON",
      "action.exported": "已导出",
      "action.copied": "已复制",
      "action.copyFailed": "复制失败",
      "action.cleared": "已清除",
      "status.starting": "启动中",
      "status.scanning": "扫描中",
      "status.ready": "运行中",
      "status.paused": "已暂停",
      "status.error": "扫描异常",
      "status.stopping": "停止中",
      "scan.last": "最近扫描",
      "scan.next": "下次刷新",
      "scan.duration": "扫描耗时",
      "scan.events": "事件",
      "scan.waiting": "等待首次扫描",
      "metric.totalTokens": "总令牌",
      "metric.processed": "输入处理量与输出量合计",
      "metric.cost": "参考总费用",
      "metric.costHint": "实采金额与未采集部分的参考估算",
      "metric.input": "总输入令牌",
      "metric.inputHint": "普通输入与缓存输入",
      "metric.output": "总输出令牌",
      "metric.outputHint": "模型生成的输出",
      "metric.cached": "缓存命中令牌",
      "metric.cachedHint": "从缓存直接读取的输入",
      "metric.precise": "精确数量",
      "metric.recordSessions": "{events} 条记录 · {sessions} 个会话",
      "metric.cacheIncluded": "已包含在总输入中",
      "metric.costCoverage": "费用覆盖 {covered}/{events} 条记录",
      "metric.costMissing": "暂无可用于费用估算的已采集样本",
      "metric.costEstimate": "≈{secondary} · 实采 {known} · 费用覆盖 {covered}/{events} 条",
      "metric.costEstimateHint": "参考估算按已采集样本推导，不等同于实际账单",
      "chart.type": "图形类型",
      "chart.subject": "统计对象",
      "chart.range": "时间范围",
      "filter.kicker": "统计范围",
      "filter.start": "开始日期",
      "filter.end": "结束日期",
      "filter.rangeJoin": "{start} 至 {end}",
      "range.7": "最近 7 天",
      "range.30": "最近 30 天",
      "range.90": "最近 90 天",
      "range.month": "本月",
      "range.all": "全部时间",
      "range.custom": "自定义",
      "chart.typeBar": "柱状图",
      "chart.typeLine": "折线图",
      "chart.typeHeatmap": "贡献图",
      "chart.agent": "智能体工具",
      "chart.model": "模型",
      "chart.barAgentTitle": "各智能体工具令牌总量",
      "chart.barAgentDesc": "按智能体工具比较总令牌；悬停可查看输入、输出、缓存和费用",
      "chart.barModelTitle": "各模型令牌总量",
      "chart.barModelDesc": "按模型比较总令牌；模型较多时可横向滚动查看",
      "chart.lineAgentTitle": "各智能体工具令牌趋势",
      "chart.lineAgentDesc": "以折线形式比较智能体工具之间的令牌用量差异",
      "chart.lineModelTitle": "各模型令牌趋势",
      "chart.lineModelDesc": "以折线形式比较模型用量，模型较多时可横向滚动",
      "chart.heatmapTitle": "每日令牌贡献",
      "chart.heatmapDesc": "类似 GitHub 的贡献图，颜色越深表示当天令牌用量越高",
      "chart.totalSubjects": "统计对象",
      "chart.totalValue": "合计用量",
      "chart.highest": "用量最高",
      "chart.estimatedCost": "参考费用",
      "chart.rangeValue": "时间范围",
      "chart.activeDays": "有记录天数",
      "chart.peakDay": "单日最高",
      "chart.subjectCount": "{count} 个",
      "chart.unitCount": "{count} 个",
      "heatmap.less": "少",
      "heatmap.more": "多",
      "overview.quickTitle": "快速明细",
      "overview.quickDesc": "总览只保留关键内容，完整分项可在“用量明细”中查看",
      "overview.openUsage": "查看完整明细",
      "overview.noData": "等待首次扫描",
      "usage.title": "用量明细",
      "usage.desc": "按智能体工具、模型或其他维度查看令牌与费用",
      "usage.search": "筛选当前明细",
      "usage.dimension": "统计维度",
      "dimension.agent": "智能体工具",
      "dimension.model": "模型",
      "dimension.source": "来源",
      "dimension.account": "账号",
      "dimension.date": "日期",
      "dimension.kind": "记录类型",
      "table.name": "名称",
      "table.totalTokens": "总令牌",
      "table.input": "输入",
      "table.output": "输出",
      "table.cached": "缓存命中",
      "table.cnyCost": "人民币费用",
      "table.usdCost": "美元费用",
      "table.costState": "费用状态",
      "table.share": "占比",
      "table.events": "记录数",
      "table.empty": "没有匹配的数据",
      "cost.missing": "无法估算",
      "cost.estimated": "参考估算",
      "cost.partial": "部分估算",
      "cost.complete": "已采集",
      "cost.partialDetail": "部分记录为实采费用，其余按样本单价估算",
      "cost.estimatedDetail": "未找到原始费用，已按已采集样本单价估算",
      "cost.estimateBasis": "估算依据：{rate} / 百万处理令牌",
      "sources.title": "本机检测概览",
      "sources.desc": "每次启动和手动刷新都会重新检测当前电脑",
      "sources.redetect": "重新检测",
      "sources.detailTitle": "来源明细",
      "sources.detailDesc": "明确列出已发现、本机未发现和无法可靠采集的来源",
      "source.supported": "支持采集",
      "source.detected": "已发现",
      "source.missing": "本机未发现",
      "source.unsupported": "不支持可靠采集",
      "source.error": "读取异常",
      "source.noPaths": "没有可用的本机路径",
      "source.runtime": "{events} 条记录 · {tokens}",
      "source.readError": "读取失败",
      "quality.validationTitle": "校验结果",
      "quality.validationDesc": "汇总前会检查数据含义、重复键和总量一致性",
      "quality.issuesTitle": "扫描问题",
      "quality.issuesDesc": "错误和警告会影响统计可信度，提示项用于说明覆盖情况",
      "quality.notesTitle": "统计说明",
      "quality.notesDesc": "口径说明直接来自当前扫描结果",
      "quality.passed": "校验结果",
      "quality.pass": "通过",
      "quality.fail": "未通过",
      "quality.events": "记录数",
      "quality.errors": "错误",
      "quality.warnings": "警告",
      "quality.semantic": "语义未明确",
      "quality.providerMismatch": "服务商总用量差异",
      "quality.noIssues": "当前没有扫描问题",
      "quality.waitingNotes": "等待首次扫描后生成口径说明。",
      "severity.error": "错误",
      "severity.warning": "警告",
      "severity.info": "提示",
      "settings.displayTitle": "显示与语言",
      "settings.displayDesc": "设置会自动保存到当前电脑并立即生效",
      "settings.saved": "已保存",
      "settings.saving": "保存中…",
      "settings.saveFailed": "保存失败",
      "settings.language": "界面语言",
      "settings.languageHint": "默认中文，切换后整个应用界面立即更新",
      "settings.theme": "界面主题",
      "settings.themeLight": "浅色",
      "settings.themeDark": "深色",
      "settings.themeSystem": "跟随系统",
      "settings.themeHint": "深色主题适合夜间查看长期统计",
      "settings.currency": "默认币种",
      "settings.currencyHint": "主显币种，另一币种仍会在明细中显示",
      "settings.currencyCNY": "人民币（元）",
      "settings.currencyUSD": "美元（$）",
      "settings.rate": "美元兑人民币汇率",
      "settings.rateFrom": "1 美元 =",
      "settings.rateHint": "不联网获取汇率，由用户自行修改；默认 7.20",
      "settings.rateTo": "人民币",
      "settings.refresh": "自动刷新间隔",
      "settings.seconds10": "每 10 秒",
      "settings.seconds30": "每 30 秒",
      "settings.seconds60": "每 1 分钟",
      "settings.seconds300": "每 5 分钟",
      "settings.seconds900": "每 15 分钟",
      "settings.refreshHint": "最小 10 秒，修改后后台扫描周期同步更新",
      "settings.save": "保存设置",
      "settings.reset": "恢复默认设置",
      "settings.aboutTitle": "应用信息",
      "settings.aboutDesc": "版本、运行方式和数据位置",
      "settings.version": "软件版本",
      "settings.windowMode": "运行方式",
      "settings.status": "服务状态",
      "settings.dataDir": "数据位置",
      "settings.license": "许可证",
      "settings.runtimeTitle": "运行控制",
      "settings.runtimeDesc": "这些操作不会关闭其他智能体工具",
      "settings.startupTitle": "开机自动启动",
      "settings.startupDesc": "登录 Windows 后自动打开本机账本，可随时关闭。",
      "settings.startupEnabled": "已开启",
      "settings.startupDisabled": "已关闭",
      "settings.startupUnavailable": "发布版可用",
      "settings.startupSaveFailed": "开机启动设置失败",
      "settings.scanNow": "立即重新扫描",
      "settings.pauseAuto": "暂停自动刷新",
      "settings.continueAuto": "继续自动刷新",
      "settings.stopService": "停止本机服务",
      "settings.openData": "打开数据目录",
      "settings.copyDiagnostics": "复制诊断信息",
      "settings.clearCache": "清除临时缓存",
      "settings.priceTitle": "模型价格表",
      "settings.priceDesc": "价格为美元/百万令牌；修改后自动保存并重新估算费用",
      "settings.priceReset": "恢复默认价格",
      "settings.priceModel": "模型",
      "settings.priceInput": "输入价格",
      "settings.priceCached": "缓存命中价格",
      "settings.priceOutput": "输出价格",
      "settings.priceFallback": "其他模型兜底价格",
      "settings.priceSaved": "价格已保存",
      "comparison.title": "较上一周期",
      "comparison.unavailable": "暂时没有可比的上一周期",
      "comparison.current": "本期 {value}",
      "comparison.previous": "上期 {value}",
      "comparison.percent": "{direction}{percent}%",
      "settings.runtimeLocal": "仅监听本机回环地址",
      "settings.runtimeNoUpload": "只读取本机日志，不上传数据",
      "settings.runtimeNoLogin": "无需登录账号",
      "settings.privacy": "程序只读取本机已有日志，不上传数据，不登录账号，不调用云端模型；服务只监听 127.0.0.1。",
      "window.webview": "原生应用窗口",
      "window.edge": "Edge 应用窗口",
      "window.browser": "浏览器窗口",
      "window.service": "后台服务",
      "footer.note": "关闭应用窗口会同时停止后台服务。",
      "stopped.title": "服务已停止",
      "stopped.desc": "可以关闭此窗口。再次双击 AgentTokenLedger.exe 即可重新启动。",
      "time.soon": "即将",
      "time.seconds": "{count} 秒后",
      "time.minutes": "{count} 分钟后",
      "time.ms": "{count} 毫秒",
      "time.paused": "已暂停",
      "sourceKind.native": "本机原始记录",
      "sourceKind.derived": "会话镜像",
      "sourceKind.gateway": "网关统计",
      "sourceKind.aggregate": "汇总记录",
      "sourceKind.proxy": "代理统计",
      "sourceKind.plugin": "插件记录",
      "sourceKind.other": "其他来源",
      "precision.request": "请求级记录",
      "precision.daily-route aggregate": "按天与路由汇总",
      "precision.exported request rows": "导出的请求记录",
      "precision.proxy request": "代理请求记录",
      "precision.local": "本地记录",
      "issueSource.inventory": "来源复核",
      "issueSource.reconcile": "重复对账",
      "issueSource.codex_native": "Codex 日志",
      "issueSource.cockpit_session": "Cockpit 会话镜像",
      "issueSource.cockpit_gateway": "Cockpit 网关日志",
      "issueSource.dsh": "DeepSeek Harness",
      "issueSource.workbuddy": "WorkBuddy",
      "issueSource.workbuddy_ai": "WorkBuddy AI",
      "issueSource.traetools": "Trae",
      "issueSource.antigravity_tools": "Antigravity Tools",
      "issueSource.local": "本机来源",
      "issueCode.source_unavailable": "来源未发现或无法采集",
      "issueCode.source_unsupported": "已复核但没有可靠令牌数据",
      "issueCode.source_read_error": "本机来源读取失败",
      "issueCode.scan_failed": "来源扫描失败",
      "issueCode.root_missing": "来源目录不存在",
      "issueCode.database_missing": "来源数据库不存在",
      "issueCode.ledger_missing": "来源账本不存在",
      "issueCode.data_missing": "来源数据目录不存在",
      "issueCode.database_read_error": "来源数据库读取失败",
      "issueCode.ledger_parse_error": "来源账本解析失败",
      "issueCode.ledger_shape_error": "来源账本结构不完整",
      "issueCode.jsonl_parse_error": "记录文件解析失败",
      "issueCode.duplicate_event_mismatch": "重复记录的用量不一致",
      "issueCode.event_key_collision": "同一条记录的用量前后不一致",
      "issueCode.cockpit_native_overlap": "与原始记录重复，已去重",
      "issueCode.native_duplicate_mismatch": "重复记录的用量不一致",
      "issueCode.provider_total_mismatch": "服务商总用量不一致",
      "issueCode.semantic_unknown": "数据含义未明确",
      "issueCode.other": "其他扫描提示",
    },
    "en-US": {
      "app.name": "Agent Usage Ledger",
      "app.localOnly": "Local read-only statistics",
      "app.privacyTitle": "Local read-only runtime",
      "app.privacyShort": "Data stays on this computer",
      "app.versionLabel": "Version",
      "nav.main": "Main navigation",
      "nav.sectionData": "Statistics",
      "nav.overview": "Overview",
      "nav.usage": "Usage details",
      "nav.sources": "Source detection",
      "nav.quality": "Data quality",
      "nav.settings": "Settings",
      "page.overview.title": "Overview",
      "page.overview.subtitle": "Token totals, known costs, and usage trends",
      "page.usage.title": "Usage details",
      "page.usage.subtitle": "Token and cost details by agent tool, model, and other dimensions",
      "page.sources.title": "Source detection",
      "page.sources.subtitle": "The current computer is rechecked on every launch",
      "page.quality.title": "Data quality",
      "page.quality.subtitle": "Validation, scan issues, and accounting scope",
      "page.settings.title": "Settings",
      "page.settings.subtitle": "Language, currency, exchange rate, theme, and refresh interval",
      "action.refresh": "Refresh",
      "action.refreshTitle": "Scan all local sources now",
      "action.pause": "Pause",
      "action.pauseContinue": "Resume",
      "action.pauseTitle": "Pause or resume automatic refresh",
      "action.continueTitle": "Resume automatic refresh",
      "action.stop": "Stop",
      "action.stopConfirm": "Stop the local service?",
      "action.stopTitle": "Stop the local service",
      "action.exportCsv": "Export CSV",
      "action.exportJson": "Export JSON",
      "action.exported": "Exported",
      "action.copied": "Copied",
      "action.copyFailed": "Copy failed",
      "action.cleared": "Cleared",
      "status.starting": "Starting",
      "status.scanning": "Scanning",
      "status.ready": "Running",
      "status.paused": "Paused",
      "status.error": "Scan error",
      "status.stopping": "Stopping",
      "scan.last": "Last scan",
      "scan.next": "Next refresh",
      "scan.duration": "Scan time",
      "scan.events": "Events",
      "scan.waiting": "Waiting for first scan",
      "metric.totalTokens": "Total tokens",
      "metric.processed": "Input processing plus output",
      "metric.cost": "Estimated total cost",
      "metric.costHint": "Collected charges plus estimates for missing charges",
      "metric.input": "Total input tokens",
      "metric.inputHint": "Regular and cached input",
      "metric.output": "Total output tokens",
      "metric.outputHint": "Model-generated output",
      "metric.cached": "Cache hit tokens",
      "metric.cachedHint": "Input read directly from cache",
      "metric.precise": "Exact count",
      "metric.recordSessions": "{events} records · {sessions} sessions",
      "metric.cacheIncluded": "Included in total input",
      "metric.costCoverage": "Cost coverage {covered}/{events} records",
      "metric.costMissing": "No collected cost sample is available for estimation",
      "metric.costEstimate": "≈{secondary} · collected {known} · coverage {covered}/{events} records",
      "metric.costEstimateHint": "Reference estimate derived from collected samples, not an actual bill",
      "chart.type": "Chart type",
      "chart.subject": "Subject",
      "chart.range": "Range",
      "filter.kicker": "Reporting range",
      "filter.start": "Start date",
      "filter.end": "End date",
      "filter.rangeJoin": "{start} to {end}",
      "range.7": "Last 7 days",
      "range.30": "Last 30 days",
      "range.90": "Last 90 days",
      "range.month": "This month",
      "range.all": "All time",
      "range.custom": "Custom",
      "chart.typeBar": "Bar",
      "chart.typeLine": "Line",
      "chart.typeHeatmap": "Contribution",
      "chart.agent": "Agent tools",
      "chart.model": "Models",
      "chart.barAgentTitle": "Token totals by agent tool",
      "chart.barAgentDesc": "Compare total tokens by agent tool; hover for input, output, cache, and cost",
      "chart.barModelTitle": "Token totals by model",
      "chart.barModelDesc": "Compare total tokens by model; scroll horizontally when many models exist",
      "chart.lineAgentTitle": "Token trend by agent tool",
      "chart.lineAgentDesc": "Compare token usage across agent tools with a line chart",
      "chart.lineModelTitle": "Token trend by model",
      "chart.lineModelDesc": "Compare token usage across models; scroll horizontally when needed",
      "chart.heatmapTitle": "Daily token contribution",
      "chart.heatmapDesc": "A GitHub-style contribution view; darker cells mean higher daily usage",
      "chart.totalSubjects": "Subjects",
      "chart.totalValue": "Total usage",
      "chart.highest": "Highest",
      "chart.estimatedCost": "Reference cost",
      "chart.rangeValue": "Range",
      "chart.activeDays": "Active days",
      "chart.peakDay": "Peak day",
      "chart.subjectCount": "{count}",
      "chart.unitCount": "{count}",
      "heatmap.less": "Less",
      "heatmap.more": "More",
      "overview.quickTitle": "Quick detail",
      "overview.quickDesc": "Overview keeps only essentials; open Usage details for every breakdown",
      "overview.openUsage": "Open full details",
      "overview.noData": "Waiting for the first scan",
      "usage.title": "Usage details",
      "usage.desc": "Token and cost details by agent tool, model, or another dimension",
      "usage.search": "Filter current details",
      "usage.dimension": "Dimension",
      "dimension.agent": "Agent tools",
      "dimension.model": "Models",
      "dimension.source": "Sources",
      "dimension.account": "Accounts",
      "dimension.date": "Dates",
      "dimension.kind": "Record types",
      "table.name": "Name",
      "table.totalTokens": "Total tokens",
      "table.input": "Input",
      "table.output": "Output",
      "table.cached": "Cache hits",
      "table.cnyCost": "CNY cost",
      "table.usdCost": "USD cost",
      "table.costState": "Cost state",
      "table.share": "Share",
      "table.events": "Records",
      "table.empty": "No matching data",
      "cost.missing": "Cannot estimate",
      "cost.estimated": "Reference estimate",
      "cost.partial": "Partly estimated",
      "cost.complete": "Collected",
      "cost.partialDetail": "Some records have collected charges; the rest use the sample rate",
      "cost.estimatedDetail": "No charge field was found, so the collected sample rate is used",
      "cost.estimateBasis": "Estimate basis: {rate} per million processed tokens",
      "sources.title": "Local detection overview",
      "sources.desc": "The current computer is rechecked on every launch and manual refresh",
      "sources.redetect": "Detect again",
      "sources.detailTitle": "Source details",
      "sources.detailDesc": "Detected, missing, and unsupported sources are listed explicitly",
      "source.supported": "Supported",
      "source.detected": "Detected",
      "source.missing": "Not found",
      "source.unsupported": "Not reliably collectable",
      "source.error": "Read error",
      "source.noPaths": "No usable local path",
      "source.runtime": "{events} records · {tokens}",
      "source.readError": "read failed",
      "quality.validationTitle": "Validation",
      "quality.validationDesc": "Semantics, duplicate keys, and totals are checked before aggregation",
      "quality.issuesTitle": "Scan issues",
      "quality.issuesDesc": "Errors and warnings affect confidence; info items explain source coverage",
      "quality.notesTitle": "Accounting notes",
      "quality.notesDesc": "Scope notes generated from the current scan",
      "quality.passed": "Validation",
      "quality.pass": "Passed",
      "quality.fail": "Failed",
      "quality.events": "Records",
      "quality.errors": "Errors",
      "quality.warnings": "Warnings",
      "quality.semantic": "Unknown semantics",
      "quality.providerMismatch": "Provider total mismatches",
      "quality.noIssues": "No scan issues",
      "quality.waitingNotes": "Accounting notes will appear after the first scan.",
      "severity.error": "Error",
      "severity.warning": "Warning",
      "severity.info": "Info",
      "settings.displayTitle": "Appearance and language",
      "settings.displayDesc": "Settings are saved on this computer and applied immediately",
      "settings.saved": "Saved",
      "settings.saving": "Saving…",
      "settings.saveFailed": "Save failed",
      "settings.language": "Interface language",
      "settings.languageHint": "Chinese is the default; the whole interface updates immediately",
      "settings.theme": "Theme",
      "settings.themeLight": "Light",
      "settings.themeDark": "Dark",
      "settings.themeSystem": "Follow system",
      "settings.themeHint": "Dark theme is easier on the eyes at night",
      "settings.currency": "Primary currency",
      "settings.currencyHint": "The other currency remains visible in detail tables",
      "settings.currencyCNY": "Chinese yuan (CNY)",
      "settings.currencyUSD": "US dollar (USD)",
      "settings.rate": "USD to CNY exchange rate",
      "settings.rateFrom": "1 USD =",
      "settings.rateHint": "No network lookup; editable locally, default 7.20",
      "settings.rateTo": "CNY",
      "settings.refresh": "Automatic refresh interval",
      "settings.seconds10": "Every 10 seconds",
      "settings.seconds30": "Every 30 seconds",
      "settings.seconds60": "Every minute",
      "settings.seconds300": "Every 5 minutes",
      "settings.seconds900": "Every 15 minutes",
      "settings.refreshHint": "Minimum 10 seconds; the background scan interval updates too",
      "settings.save": "Save settings",
      "settings.reset": "Restore defaults",
      "settings.aboutTitle": "Application information",
      "settings.aboutDesc": "Version, window mode, and data location",
      "settings.version": "Version",
      "settings.windowMode": "Window mode",
      "settings.status": "Service status",
      "settings.dataDir": "Data location",
      "settings.license": "License",
      "settings.runtimeTitle": "Runtime controls",
      "settings.runtimeDesc": "These controls never close other agent tools",
      "settings.startupTitle": "Launch at sign-in",
      "settings.startupDesc": "Open the local ledger after Windows sign-in. You can turn this off at any time.",
      "settings.startupEnabled": "Enabled",
      "settings.startupDisabled": "Disabled",
      "settings.startupUnavailable": "Available in the packaged app",
      "settings.startupSaveFailed": "Could not update startup settings",
      "settings.scanNow": "Scan again now",
      "settings.pauseAuto": "Pause automatic refresh",
      "settings.continueAuto": "Resume automatic refresh",
      "settings.stopService": "Stop local service",
      "settings.openData": "Open data folder",
      "settings.copyDiagnostics": "Copy diagnostics",
      "settings.clearCache": "Clear temporary cache",
      "settings.priceTitle": "Model price table",
      "settings.priceDesc": "USD per million tokens; edits are saved automatically and costs are recalculated",
      "settings.priceReset": "Restore default prices",
      "settings.priceModel": "Model",
      "settings.priceInput": "Input price",
      "settings.priceCached": "Cache-hit price",
      "settings.priceOutput": "Output price",
      "settings.priceFallback": "Fallback price for other models",
      "settings.priceSaved": "Prices saved",
      "comparison.title": "Compared with previous period",
      "comparison.unavailable": "No comparable previous period",
      "comparison.current": "Current {value}",
      "comparison.previous": "Previous {value}",
      "comparison.percent": "{direction}{percent}%",
      "settings.runtimeLocal": "Listens only on the local loopback address",
      "settings.runtimeNoUpload": "Reads local logs only and never uploads data",
      "settings.runtimeNoLogin": "No account or sign-in required",
      "settings.privacy": "The application only reads existing local logs. It does not upload data, sign in, or call cloud models; the service listens only on 127.0.0.1.",
      "window.webview": "Native app window",
      "window.edge": "Edge app window",
      "window.browser": "Browser window",
      "window.service": "Background service",
      "footer.note": "Closing the application window also stops the background service.",
      "stopped.title": "Service stopped",
      "stopped.desc": "You can close this window. Double-click AgentTokenLedger.exe to start again.",
      "time.soon": "Soon",
      "time.seconds": "in {count} seconds",
      "time.minutes": "in {count} minutes",
      "time.ms": "{count} ms",
      "time.paused": "Paused",
      "sourceKind.native": "Native local record",
      "sourceKind.derived": "Session mirror",
      "sourceKind.gateway": "Gateway record",
      "sourceKind.aggregate": "Aggregate record",
      "sourceKind.proxy": "Proxy record",
      "sourceKind.plugin": "Plugin record",
      "sourceKind.other": "Other source",
      "precision.request": "Request-level",
      "precision.daily-route aggregate": "Daily route aggregate",
      "precision.exported request rows": "Exported request rows",
      "precision.proxy request": "Proxy request",
      "precision.local": "Local record",
      "issueSource.inventory": "Source review",
      "issueSource.reconcile": "Deduplication",
      "issueSource.codex_native": "Codex logs",
      "issueSource.cockpit_session": "Cockpit session mirror",
      "issueSource.cockpit_gateway": "Cockpit gateway logs",
      "issueSource.dsh": "DeepSeek Harness",
      "issueSource.workbuddy": "WorkBuddy",
      "issueSource.workbuddy_ai": "WorkBuddy AI",
      "issueSource.traetools": "Trae",
      "issueSource.antigravity_tools": "Antigravity Tools",
      "issueSource.local": "Local source",
      "issueCode.source_unavailable": "Source unavailable",
      "issueCode.source_unsupported": "Reviewed but no reliable token ledger",
      "issueCode.source_read_error": "Local source read failed",
      "issueCode.scan_failed": "Source scan failed",
      "issueCode.root_missing": "Source directory missing",
      "issueCode.database_missing": "Source database missing",
      "issueCode.ledger_missing": "Source ledger missing",
      "issueCode.data_missing": "Source data directory missing",
      "issueCode.database_read_error": "Source database read failed",
      "issueCode.ledger_parse_error": "Source ledger parse failed",
      "issueCode.ledger_shape_error": "Source ledger shape is incomplete",
      "issueCode.jsonl_parse_error": "Record file parse failed",
      "issueCode.duplicate_event_mismatch": "Duplicate record usage mismatch",
      "issueCode.event_key_collision": "Same event key has different usage",
      "issueCode.cockpit_native_overlap": "Duplicate of native record, skipped",
      "issueCode.native_duplicate_mismatch": "Duplicate record usage mismatch",
      "issueCode.provider_total_mismatch": "Provider total mismatch",
      "issueCode.semantic_unknown": "Unknown data semantics",
      "issueCode.other": "Other scan notice",
    },
  };

  // The translation catalog stays in this file. The active dashboard runtime
  // lives in runtime.js so a stale renderer cannot bind to removed controls.
  window.AgentTokenLedgerTranslations = translations;
  return;

  const dimensionOptions = ["agent", "model", "source", "account", "date", "kind"];
  const chartTypeOptions = ["bar", "line", "heatmap"];
  const chartMetricOptions = ["agent", "model"];
  const reportRangeOptions = ["7", "30", "90", "month", "all", "custom"];
  const CHART_HEIGHT = 360;
  const defaultPreferences = {
    language: "zh-CN",
    currency: "CNY",
    exchange_rate: 7.2,
    refresh_seconds: 30,
    theme: "light",
  };

  let state = null;
  let currentPage = "overview";
  let currentDimension = "agent";
  let currentChartType = "bar";
  let currentChartMetric = "agent";
  let currentReportRange = "all";
  let customStartDate = "";
  let customEndDate = "";
  let currentReport = null;
  let reportRequestId = 0;
  let priceSaveTimer = null;
  let currentChartPoints = [];
  let currentHeatmapPoints = new Map();
  let searchText = "";
  let lastVersion = -1;
  let lastReportKey = "";
  let systemThemeQuery = null;

  const byId = (id) => document.getElementById(id);
  const number = (value) => {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const preferences = () => ({
    ...defaultPreferences,
    ...(state?.preferences || {}),
  });
  const locale = () => preferences().language || "zh-CN";
  const t = (key, values = {}) => {
    const activeLocale = locale();
    const template =
      translations[activeLocale]?.[key] ??
      translations["zh-CN"][key] ??
      key;
    return String(template).replace(/\{(\w+)\}/g, (_, name) =>
      Object.prototype.hasOwnProperty.call(values, name)
        ? String(values[name])
        : `{${name}}`,
    );
  };
  const integer = (value) =>
    number(value).toLocaleString(locale(), { maximumFractionDigits: 0 });
  const fixed = (value, digits = 2) =>
    number(value).toLocaleString(locale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  const yi = (value) => {
    const numeric = number(value);
    if (locale().startsWith("en")) {
      if (Math.abs(numeric) >= 1_000_000_000) {
        return `${fixed(numeric / 1_000_000_000, numeric >= 10_000_000_000 ? 1 : 2)}B`;
      }
      if (Math.abs(numeric) >= 1_000_000) {
        return `${fixed(numeric / 1_000_000, numeric >= 10_000_000 ? 1 : 2)}M`;
      }
      if (Math.abs(numeric) >= 1_000) {
        return `${fixed(numeric / 1_000, numeric >= 100_000 ? 1 : 2)}K`;
      }
      return integer(numeric);
    }
    return `${fixed(numeric / 100_000_000, 4)} 亿`;
  };
  const compactNumber = (value) => {
    const numeric = number(value);
    if (locale().startsWith("en")) {
      return yi(numeric);
    }
    if (numeric >= 100_000_000) {
      return `${fixed(numeric / 100_000_000, numeric >= 1_000_000_000 ? 2 : 3)} 亿`;
    }
    if (numeric >= 10_000) {
      return `${fixed(numeric / 10_000, numeric >= 1_000_000 ? 1 : 2)} 万`;
    }
    return integer(numeric);
  };
  const money = (usd, currency = preferences().currency) => {
    const rate = number(preferences().exchange_rate) || 7.2;
    if (currency === "CNY") {
      return `¥${fixed(number(usd) * rate, 2)}`;
    }
    return `$${fixed(usd, 4)}`;
  };
  const fullTime = (ms) =>
    ms
      ? new Date(number(ms)).toLocaleString(locale(), { hour12: false })
      : "—";
  const parseDay = (value) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!match) return null;
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  };
  const dayKey = (value) => {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };
  const addDays = (value, count) => {
    const next = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    next.setDate(next.getDate() + count);
    return next;
  };
  const shortDay = (value) => {
    if (locale().startsWith("en")) {
      return value.toLocaleDateString(locale(), {
        month: "short",
        day: "numeric",
      });
    }
    return `${value.getMonth() + 1}月${value.getDate()}日`;
  };
  const fullDay = (value) =>
    value.toLocaleDateString(locale(), {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  const niceMaximum = (value) => {
    if (!(value > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(value));
    const normalized = value / power;
    const factor =
      [1, 1.5, 2, 2.5, 5, 10].find((item) => normalized <= item) || 10;
    return factor * power;
  };
  const relativeTime = (ms) => {
    if (!ms) return "—";
    const seconds = Math.max(0, Math.round((number(ms) - Date.now()) / 1000));
    if (seconds <= 1) return t("time.soon");
    if (seconds < 60) return t("time.seconds", { count: seconds });
    return t("time.minutes", { count: Math.ceil(seconds / 60) });
  };
  const text = (element, value) => {
    if (element) element.textContent = value;
  };
  const escapeHtml = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character],
    );
  const sourceKindLabel = (value) =>
    t(`sourceKind.${value}`) === `sourceKind.${value}`
      ? t("sourceKind.other")
      : t(`sourceKind.${value}`);
  const precisionLabel = (value) =>
    t(`precision.${value}`) === `precision.${value}`
      ? t("precision.local")
      : t(`precision.${value}`);
  const sourceStatusLabel = (value) =>
    t(`source.${value}`) === `source.${value}` ? value || "—" : t(`source.${value}`);
  const issueSourceLabel = (value) =>
    t(`issueSource.${value}`) === `issueSource.${value}`
      ? t("issueSource.local")
      : t(`issueSource.${value}`);
  const issueCodeLabel = (value) =>
    t(`issueCode.${value}`) === `issueCode.${value}`
      ? t("issueCode.other")
      : t(`issueCode.${value}`);
  const severityLabel = (value) => t(`severity.${value}`) || value;
  const windowModeLabel = (value) =>
    t(`window.${value}`) === `window.${value}`
      ? t("window.webview")
      : t(`window.${value}`);
  const costProfile = () => {
    const primaryGroups = state?.reports?.primary?.agent?.groups || [];
    const fallbackGroups = state?.reports?.primary?.model?.groups || [];
    const groups = primaryGroups.length ? primaryGroups : fallbackGroups;
    let weightedCostUsd = 0;
    let weightedTokens = 0;
    let knownCostUsd = 0;
    let costedEvents = 0;
    let events = 0;
    let sampleGroups = 0;

    groups.forEach((group) => {
      const groupEvents = number(group?.events);
      const groupCostedEvents = Math.min(
        groupEvents,
        number(group?.costed_events),
      );
      const groupTokens = number(group?.processed_tokens);
      knownCostUsd += number(group?.cost_usd);
      costedEvents += groupCostedEvents;
      events += groupEvents;
      if (!groupEvents || !groupCostedEvents || !groupTokens) return;
      const coveredTokens = groupTokens * (groupCostedEvents / groupEvents);
      if (coveredTokens <= 0) return;
      weightedCostUsd += number(group?.cost_usd);
      weightedTokens += coveredTokens;
      sampleGroups += 1;
    });

    return {
      rateUsdPerToken: weightedTokens ? weightedCostUsd / weightedTokens : 0,
      knownCostUsd,
      costedEvents,
      events,
      sampleGroups,
    };
  };

  const costCoverage = (group) => {
    const events = number(group?.events);
    const covered = Math.min(events, number(group?.costed_events));
    if (!events) return "missing";
    if (covered >= events) return "complete";
    if (covered > 0) return "partial";
    return costProfile().rateUsdPerToken > 0 ? "estimated" : "missing";
  };

  const estimatedCostForGroup = (group) => {
    const events = number(group?.events);
    const covered = Math.min(events, number(group?.costed_events));
    const tokens = number(group?.processed_tokens);
    const knownCost = number(group?.cost_usd);
    const rate = costProfile().rateUsdPerToken;
    if (!tokens) return knownCost;
    if (covered >= events && events > 0) return knownCost;
    if (!covered) return rate > 0 ? tokens * rate : 0;
    const coveredTokens = tokens * (covered / events);
    return knownCost + Math.max(0, tokens - coveredTokens) * rate;
  };

  const estimatedPrimaryCost = () => {
    const groups = state?.reports?.primary?.agent?.groups?.length
      ? state.reports.primary.agent.groups
      : state?.reports?.primary?.model?.groups || [];
    const profile = costProfile();
    return {
      ...profile,
      estimatedCostUsd: groups.reduce(
        (sum, group) => sum + estimatedCostForGroup(group),
        0,
      ),
    };
  };

  const costStateLabel = (group) => {
    const status = costCoverage(group);
    return t(`cost.${status}`);
  };
  const costStateDetail = (group) => {
    const status = costCoverage(group);
    if (status === "complete") return "";
    return status === "estimated"
      ? t("cost.estimatedDetail")
      : t("cost.partialDetail");
  };
  const costCell = (group, currency = preferences().currency) => {
    const status = costCoverage(group);
    if (status === "missing") return t("cost.missing");
    const value = money(estimatedCostForGroup(group), currency);
    return status === "complete" ? value : `≈${value}`;
  };

  function applyStaticTranslations() {
    document.documentElement.lang = locale();
    document.title = t("app.name");
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.title = t(element.dataset.i18nTitle);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
  }

  function resolvedTheme(theme) {
    if (theme === "system") {
      return systemThemeQuery?.matches ? "dark" : "light";
    }
    return theme === "dark" ? "dark" : "light";
  }

  function applyTheme() {
    document.documentElement.dataset.theme = resolvedTheme(preferences().theme);
  }

  function renderNavigation() {
    document.querySelectorAll(".nav-item").forEach((button) => {
      const active = button.dataset.page === currentPage;
      button.classList.toggle("active", active);
      button.setAttribute("aria-current", active ? "page" : "false");
    });
  }

  function renderPage() {
    const page = t(`page.${currentPage}.title`);
    text(byId("pageTitle"), page);
    text(byId("pageSubtitle"), t(`page.${currentPage}.subtitle`));
    document.querySelectorAll("[data-page-view]").forEach((view) => {
      view.hidden = view.dataset.pageView !== currentPage;
    });
    byId("chartTooltip").style.display = "none";
  }

  function renderStatus() {
    const status = state?.status || "starting";
    const pill = byId("statusPill");
    pill.className = `status-pill ${status}`;
    text(pill, t(`status.${status}`) === `status.${status}` ? status : t(`status.${status}`));
    byId("progressTrack").classList.toggle("active", status === "scanning");
    byId("progressTrack").closest(".scan-band")?.classList.toggle(
      "paused",
      Boolean(state?.paused),
    );
    byId("refreshButton").disabled = status === "scanning" || status === "stopping";
    const pauseButton = byId("pauseButton");
    const pauseLabel = state?.paused
      ? t("action.pauseContinue")
      : t("action.pause");
    pauseButton.querySelector(".btn-label").textContent = pauseLabel;
    pauseButton.title = state?.paused ? t("action.continueTitle") : t("action.pauseTitle");
    pauseButton.setAttribute("aria-label", pauseButton.title);
    pauseButton.classList.toggle("pause-active", Boolean(state?.paused));
    pauseButton.setAttribute("aria-pressed", state?.paused ? "true" : "false");
    pauseButton.disabled = status === "stopping";
    const settingsPauseButton = byId("settingsPauseButton");
    settingsPauseButton.classList.toggle("pause-active", Boolean(state?.paused));
    settingsPauseButton.setAttribute(
      "aria-pressed",
      state?.paused ? "true" : "false",
    );
    byId("stopButton").disabled = status === "stopping";
    const error = state?.last_error || "";
    const banner = byId("errorBanner");
    banner.textContent = error ? `${t("status.error")}: ${error}` : "";
    banner.classList.toggle("visible", Boolean(error));
  }

  function renderTotals() {
    const overall = state?.scopes?.primary;
    const recordText = overall
      ? t("metric.recordSessions", {
          events: integer(overall.events),
          sessions: integer(overall.sessions),
        })
      : t("scan.waiting");
    text(byId("totalTokensValue"), overall ? yi(overall.processed_tokens) : "—");
    text(
      byId("totalTokensSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.processed_tokens)} · ${recordText}`
        : recordText,
    );

    const costSummary = estimatedPrimaryCost();
    const costedEvents = costSummary.costedEvents;
    const events = costSummary.events;
    const selectedCurrency = preferences().currency;
    const secondaryCurrency = selectedCurrency === "CNY" ? "USD" : "CNY";
    text(
      byId("totalCostValue"),
      costSummary.estimatedCostUsd
        ? `≈${money(costSummary.estimatedCostUsd, selectedCurrency)}`
        : t("cost.missing"),
    );
    text(
      byId("totalCostSub"),
      costSummary.estimatedCostUsd
        ? t("metric.costEstimate", {
            secondary: money(costSummary.estimatedCostUsd, secondaryCurrency),
            known: money(costSummary.knownCostUsd, selectedCurrency),
            covered: integer(costedEvents),
            events: integer(events),
          })
        : t("metric.costMissing"),
    );
    byId("totalCostValue").title = t("metric.costEstimateHint");
    byId("totalCostSub").title = costSummary.rateUsdPerToken
      ? t("cost.estimateBasis", {
          rate: money(costSummary.rateUsdPerToken * 1_000_000),
        })
      : "";

    text(byId("totalInputValue"), overall ? yi(overall.input_tokens_total) : "—");
    text(
      byId("totalInputSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.input_tokens_total)}`
        : recordText,
    );
    text(byId("totalOutputValue"), overall ? yi(overall.output_tokens) : "—");
    text(
      byId("totalOutputSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.output_tokens)}`
        : recordText,
    );
    text(
      byId("totalCachedValue"),
      overall ? yi(overall.cached_input_tokens) : "—",
    );
    text(
      byId("totalCachedSub"),
      overall
        ? `${t("metric.precise")} ${integer(overall.cached_input_tokens)} · ${t("metric.cacheIncluded")}`
        : recordText,
    );
  }

  function renderScanFacts() {
    text(
      byId("lastScan"),
      state?.last_scan_finished_at
        ? fullTime(state.last_scan_finished_at_ms)
        : t("scan.waiting"),
    );
    text(
      byId("nextScan"),
      state?.paused ? t("time.paused") : relativeTime(state?.next_scan_ms),
    );
    text(
      byId("duration"),
      state?.last_scan_duration_ms == null
        ? "—"
        : t("time.ms", { count: integer(state.last_scan_duration_ms) }),
    );
    const primaryEvents = state?.scopes?.primary?.events;
    text(byId("eventCount"), primaryEvents == null ? "—" : integer(primaryEvents));
  }

  function makeSegmented(container, values, active, labelFor, onSelect) {
    if (!container) return;
    container.replaceChildren();
    values.forEach((value) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.value = value;
      button.textContent = labelFor(value);
      button.classList.toggle("active", value === active);
      button.setAttribute("aria-pressed", value === active ? "true" : "false");
      button.addEventListener("click", () => onSelect(value));
      container.appendChild(button);
    });
  }

  function renderChartToolbar() {
    makeSegmented(
      byId("chartTypeTabs"),
      chartTypeOptions,
      currentChartType,
      (value) => t(`chart.type${value[0].toUpperCase()}${value.slice(1)}`),
      (value) => {
        currentChartType = value;
        renderChartPanel();
      },
    );
    makeSegmented(
      byId("chartMetricTabs"),
      chartMetricOptions,
      currentChartMetric,
      (value) => t(`chart.${value}`),
      (value) => {
        currentChartMetric = value;
        renderChartPanel();
      },
    );
    makeSegmented(
      byId("heatmapRangeTabs"),
      chartRangeOptions,
      currentChartRange,
      (value) => t(`range.${value}`),
      (value) => {
        currentChartRange = value;
        renderChartPanel();
      },
    );
    byId("chartMetricGroup").hidden = currentChartType === "heatmap";
    byId("heatmapRangeGroup").hidden = currentChartType !== "heatmap";
    byId("heatmapLegend").hidden = true;

    const titleKey =
      currentChartType === "heatmap"
        ? "chart.heatmapTitle"
        : currentChartType === "line"
          ? `chart.line${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Title`
          : `chart.bar${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Title`;
    const descKey =
      currentChartType === "heatmap"
        ? "chart.heatmapDesc"
        : currentChartType === "line"
          ? `chart.line${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Desc`
          : `chart.bar${currentChartMetric[0].toUpperCase()}${currentChartMetric.slice(1)}Desc`;
    text(byId("chartPanelTitle"), t(titleKey));
    text(byId("chartPanelDescription"), t(descKey));
  }

  function renderChartPanel() {
    renderChartToolbar();
    if (currentChartType === "heatmap") {
      renderHeatmapChart();
    } else {
      renderUsageChart();
    }
  }

  function chartGroups() {
    return (state?.reports?.primary?.[currentChartMetric]?.groups || [])
      .filter((item) => number(item.processed_tokens) > 0)
      .sort(
        (left, right) =>
          number(right.processed_tokens) - number(left.processed_tokens),
      );
  }

  function pointFromGroup(group) {
    return {
      name: group.group || "—",
      value: number(group.processed_tokens),
      events: number(group.events),
      input: number(group.input_tokens_total),
      cached: number(group.cached_input_tokens),
      output: number(group.output_tokens),
      cost: number(group.cost_usd),
      estimatedCost: estimatedCostForGroup(group),
      costedEvents: number(group.costed_events),
    };
  }

  function summaryValues(values) {
    const container = byId("chartSummary");
    container.innerHTML = values
      .map(
        ([label, value]) =>
          `<div class="chart-summary-item"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`,
      )
      .join("");
  }

  function makeSvg(svg, width, height) {
    const namespace = "http://www.w3.org/2000/svg";
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.style.height = `${height}px`;
    svg.replaceChildren();
    const scroll = byId("chartScroll");
    scroll.scrollLeft = 0;
    return (name, attributes = {}) => {
      const node = document.createElementNS(namespace, name);
      Object.entries(attributes).forEach(([key, value]) =>
        node.setAttribute(key, value),
      );
      svg.appendChild(node);
      return node;
    };
  }

  function clipLabel(value, maximum = 14) {
    const textValue = String(value || "—");
    return textValue.length > maximum
      ? `${textValue.slice(0, maximum - 1)}…`
      : textValue;
  }

  function renderUsageChart() {
    const groups = chartGroups();
    currentChartPoints = groups.map(pointFromGroup);
    const empty = byId("chartEmpty");
    empty.hidden = currentChartPoints.length > 0;
    const svg = byId("usageChart");
    const total = currentChartPoints.reduce((sum, item) => sum + item.value, 0);
    const top = currentChartPoints[0];
    const estimatedCost = currentChartPoints.reduce(
      (sum, item) => sum + item.estimatedCost,
      0,
    );
    summaryValues([
      [t("chart.totalSubjects"), t("chart.subjectCount", { count: integer(groups.length) })],
      [t("chart.totalValue"), yi(total)],
      [
        t("chart.highest"),
        top ? `${clipLabel(top.name, 18)} · ${yi(top.value)}` : "—",
      ],
      [
        t("chart.estimatedCost"),
        estimatedCost ? `≈${money(estimatedCost)}` : t("cost.missing"),
      ],
    ]);
    if (!currentChartPoints.length) {
      svg.replaceChildren();
      return;
    }
    if (currentChartType === "line") {
      renderLineChart(svg, currentChartPoints);
    } else {
      renderBarChart(svg, currentChartPoints);
    }
  }

  function renderBarChart(svg, points) {
    const width = Math.max(1000, 104 + points.length * 84);
    const height = 330;
    const make = makeSvg(svg, width, height);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const padding = { left: 82, right: 30, top: 26, bottom: 82 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const bottom = padding.top + plotHeight;
    const maximum = niceMaximum(Math.max(...points.map((item) => item.value), 1));
    const step = plotWidth / points.length;
    const barWidth = Math.max(28, Math.min(72, step * 0.58));

    drawGrid(make, padding, width, plotHeight, maximum);
    points.forEach((point, index) => {
      const x = padding.left + step * index + step / 2;
      const barHeight = Math.max(2, (point.value / maximum) * plotHeight);
      make("rect", {
        x: x - barWidth / 2,
        y: bottom - barHeight,
        width: barWidth,
        height: barHeight,
        rx: 4,
        class: "chart-bar",
        "data-chart-index": index,
      });
      const valueLabel = make("text", {
        x,
        y: Math.max(padding.top, bottom - barHeight - 7),
        "text-anchor": "middle",
        class: "chart-axis-text value",
      });
      valueLabel.textContent = compactNumber(point.value);
      const nameLabel = make("text", {
        x,
        y: height - 46,
        "text-anchor": "end",
        class: "chart-axis-text",
        transform: `rotate(-32 ${x} ${height - 46})`,
      });
      nameLabel.textContent = clipLabel(point.name, points.length > 12 ? 13 : 17);
    });
  }

  function renderLineChart(svg, points) {
    const width = Math.max(1000, 104 + points.length * 84);
    const height = 330;
    const make = makeSvg(svg, width, height);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const padding = { left: 82, right: 30, top: 36, bottom: 82 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const bottom = padding.top + plotHeight;
    const maximum = niceMaximum(Math.max(...points.map((item) => item.value), 1));
    const step = points.length > 1 ? plotWidth / (points.length - 1) : 0;

    drawGrid(make, padding, width, plotHeight, maximum);
    const linePoints = points.map((point, index) => ({
      x:
        points.length > 1
          ? padding.left + step * index
          : padding.left + plotWidth / 2,
      y: bottom - (point.value / maximum) * plotHeight,
      point,
    }));
    if (linePoints.length > 1) {
      make("path", {
        d: linePoints
          .map(
            (item, index) =>
              `${index ? "L" : "M"} ${item.x.toFixed(2)} ${item.y.toFixed(2)}`,
          )
          .join(" "),
        class: "chart-line",
      });
    }
    linePoints.forEach((item, index) => {
      make("circle", {
        cx: item.x,
        cy: item.y,
        r: 4.2,
        class: "chart-line-point",
        "data-chart-index": index,
      });
      make("rect", {
        x: item.x - Math.max(18, step / 2),
        y: padding.top,
        width: Math.max(36, step),
        height: plotHeight,
        class: "chart-hit-area",
        "data-chart-index": index,
      });
      const nameLabel = make("text", {
        x: item.x,
        y: height - 46,
        "text-anchor": "end",
        class: "chart-axis-text",
        transform: `rotate(-32 ${item.x} ${height - 46})`,
      });
      nameLabel.textContent = clipLabel(item.point.name, points.length > 12 ? 13 : 17);
      const valueLabel = make("text", {
        x: item.x,
        y: Math.max(padding.top - 8, item.y - 10),
        "text-anchor": "middle",
        class: "chart-axis-text value",
      });
      valueLabel.textContent = compactNumber(item.point.value);
    });
  }

  function drawGrid(make, padding, width, plotHeight, maximum) {
    for (let tick = 0; tick <= 4; tick += 1) {
      const ratio = tick / 4;
      const y = padding.top + plotHeight * ratio;
      make("line", {
        x1: padding.left,
        x2: width - padding.right,
        y1: y,
        y2: y,
        class: "chart-grid-line",
      });
      const label = make("text", {
        x: padding.left - 10,
        y: y + 4,
        "text-anchor": "end",
        class: "chart-axis-text",
      });
      label.textContent = compactNumber(maximum * (1 - ratio));
    }
  }

  function buildDatePoints() {
    const groups = state?.reports?.primary?.date?.groups || [];
    const byDate = new Map();
    const dates = [];
    groups.forEach((group) => {
      const parsed = parseDay(group.group);
      if (!parsed) return;
      byDate.set(dayKey(parsed), group);
      dates.push(parsed);
    });
    if (!dates.length) return [];

    dates.sort((left, right) => left - right);
    const firstDate = dates[0];
    const lastDate = dates[dates.length - 1];
    let startDate = firstDate;
    if (currentChartRange !== "all") {
      const requestedDays = Math.max(1, Number(currentChartRange));
      const requestedStart = addDays(lastDate, -(requestedDays - 1));
      startDate = requestedStart > firstDate ? requestedStart : firstDate;
    }

    const points = [];
    for (
      let cursor = startDate;
      cursor.getTime() <= lastDate.getTime();
      cursor = addDays(cursor, 1)
    ) {
      const key = dayKey(cursor);
      const group = byDate.get(key);
      points.push({
        date: new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()),
        key,
        value: number(group?.processed_tokens),
        events: number(group?.events),
        input: number(group?.input_tokens_total),
        cached: number(group?.cached_input_tokens),
        output: number(group?.output_tokens),
        cost: number(group?.cost_usd),
        estimatedCost: estimatedCostForGroup(group),
        costedEvents: number(group?.costed_events),
      });
    }
    return points;
  }

  function renderHeatmapChart() {
    const points = buildDatePoints();
    currentHeatmapPoints = new Map();
    const svg = byId("usageChart");
    const empty = byId("chartEmpty");
    empty.hidden = points.length > 0;
    const total = points.reduce((sum, item) => sum + item.value, 0);
    const active = points.filter((item) => item.value > 0);
    const peak = points.reduce(
      (best, item) => (item.value > best.value ? item : best),
      points[0] || { value: 0, date: null },
    );
    summaryValues([
      [
        t("chart.rangeValue"),
        points.length
          ? `${fullDay(points[0].date)} – ${fullDay(points[points.length - 1].date)}`
          : "—",
      ],
      [t("chart.totalValue"), yi(total)],
      [t("chart.activeDays"), t("chart.unitCount", { count: integer(active.length) })],
      [t("chart.peakDay"), peak.date ? `${shortDay(peak.date)} · ${yi(peak.value)}` : "—"],
    ]);
    if (!points.length) {
      svg.replaceChildren();
      return;
    }

    const firstDate = new Date(points[0].date);
    const mondayOffset = (firstDate.getDay() + 6) % 7;
    const gridStart = addDays(firstDate, -mondayOffset);
    const lastDate = new Date(points[points.length - 1].date);
    const totalDays = Math.round((lastDate - gridStart) / 86400000) + 1;
    const weeks = Math.ceil(totalDays / 7);
    const cell = 27;
    const gap = 6;
    const step = cell + gap;
    const gridWidth = weeks * step - gap;
    const width = Math.max(1000, 48 + gridWidth + 40);
    const height = 330;
    const make = makeSvg(svg, width, height);
    svg.style.width = `${width}px`;
    svg.style.minWidth = `${width}px`;
    const startX =
      gridWidth + 116 <= width ? Math.max(48, (width - gridWidth) / 2) : 48;
    const startY = 52;
    const maximum = Math.max(...points.map((item) => item.value), 1);
    const byKey = new Map(points.map((item) => [item.key, item]));
    const weekdays = locale().startsWith("en")
      ? ["M", "T", "W", "T", "F", "S", "S"]
      : ["一", "二", "三", "四", "五", "六", "日"];

    weekdays.forEach((label, index) => {
      if (index % 2 !== 0) return;
      const textNode = make("text", {
        x: startX - 9,
        y: startY + index * step + 19,
        "text-anchor": "end",
        class: "heatmap-weekday",
      });
      textNode.textContent = label;
    });

    let previousMonth = -1;
    for (let dayIndex = 0; dayIndex < totalDays; dayIndex += 1) {
      const date = addDays(gridStart, dayIndex);
      const week = Math.floor(dayIndex / 7);
      const weekday = dayIndex % 7;
      if (date > lastDate || date < firstDate) continue;
      if (date.getDate() <= 7 && date.getMonth() !== previousMonth) {
        previousMonth = date.getMonth();
        const monthLabel = make("text", {
          x: startX + week * step,
          y: 27,
          class: "heatmap-month",
        });
        monthLabel.textContent = date.toLocaleDateString(locale(), { month: "short" });
      }
      const item = byKey.get(dayKey(date)) || {
        value: 0,
        events: 0,
        input: 0,
        cached: 0,
        output: 0,
        cost: 0,
        costedEvents: 0,
      };
      const ratio = item.value / maximum;
      const level = !item.value
        ? 0
        : ratio <= 0.25
          ? 1
          : ratio <= 0.5
            ? 2
            : ratio <= 0.75
              ? 3
              : 4;
      make("rect", {
        x: startX + week * step,
        y: startY + weekday * step,
        width: cell,
        height: cell,
        rx: 5,
        class: `heatmap-cell level-${level}`,
        "data-chart-index": dayIndex,
      });
      item.date = date;
      currentHeatmapPoints.set(dayIndex, item);
    }

    const legendY = height - 26;
    const legendX = width - 214;
    const legendText = make("text", {
      x: legendX,
      y: legendY + 12,
      class: "heatmap-weekday",
    });
    legendText.textContent = t("heatmap.less");
    for (let level = 0; level < 5; level += 1) {
      make("rect", {
        x: legendX + 26 + level * 20,
        y: legendY,
        width: 15,
        height: 15,
        rx: 3,
        class: `heatmap-cell level-${level}`,
      });
    }
    const moreText = make("text", {
      x: legendX + 134,
      y: legendY + 12,
      class: "heatmap-weekday",
    });
    moreText.textContent = t("heatmap.more");
  }

  function renderOverviewTopList() {
    const container = byId("overviewTopList");
    const groups = (state?.reports?.primary?.agent?.groups || []).slice(0, 5);
    if (!groups.length) {
      container.innerHTML = `<div class="empty">${escapeHtml(t("overview.noData"))}</div>`;
      return;
    }
    container.innerHTML = groups
      .map(
        (group, index) => `
          <div class="top-list-row">
            <span class="rank">${index + 1}</span>
            <strong title="${escapeHtml(group.group)}">${escapeHtml(group.group || "—")}</strong>
            <span>${escapeHtml(yi(group.processed_tokens))}</span>
            <span>${escapeHtml(costCell(group))}</span>
            <span class="cost-state ${escapeHtml(costCoverage(group))}" title="${escapeHtml(costStateDetail(group))}">${escapeHtml(costStateLabel(group))}</span>
          </div>`,
      )
      .join("");
  }

  function renderDimensionTabs() {
    makeSegmented(
      byId("dimensionTabs"),
      dimensionOptions,
      currentDimension,
      (value) => t(`dimension.${value}`),
      (value) => {
        currentDimension = value;
        renderReport();
        renderDimensionTabs();
      },
    );
  }

  function renderReport() {
    const reportData = state?.reports?.primary?.[currentDimension];
    const groups = reportData?.groups || [];
    const normalizedSearch = searchText.trim().toLowerCase();
    const filtered = groups.filter(
      (group) =>
        !normalizedSearch ||
        String(group.group || "")
          .toLowerCase()
          .includes(normalizedSearch),
    );
    const total = number(reportData?.overall?.processed_tokens);
    const body = byId("reportBody");
    body.replaceChildren();
    const empty = byId("reportEmpty");
    empty.hidden = filtered.length !== 0;
    text(empty, t("table.empty"));

    filtered.slice(0, 500).forEach((group) => {
      const row = document.createElement("tr");
      const share =
        total > 0 ? (number(group.processed_tokens) / total) * 100 : 0;
      const costState = costCoverage(group);
      row.innerHTML = `
        <td class="group-name" title="${escapeHtml(group.group)}">${escapeHtml(group.group || "—")}</td>
        <td class="num">${escapeHtml(yi(group.processed_tokens))}</td>
        <td class="num">${escapeHtml(yi(group.input_tokens_total))}</td>
        <td class="num">${escapeHtml(yi(group.output_tokens))}</td>
        <td class="num">${escapeHtml(yi(group.cached_input_tokens))}</td>
        <td class="num cost-cell">${escapeHtml(costCell(group, "CNY"))}</td>
        <td class="num cost-cell">${escapeHtml(costCell(group, "USD"))}</td>
        <td><span class="cost-state ${escapeHtml(costState)}" title="${escapeHtml(costStateDetail(group))}">${escapeHtml(costStateLabel(group))}</span></td>
        <td class="num"><span class="bar"><span style="width:${Math.min(100, share).toFixed(2)}%"></span></span>${fixed(share, 1)}%</td>
        <td class="num">${escapeHtml(integer(group.events))}</td>`;
      body.appendChild(row);
    });
  }

  function renderSourceSummary() {
    const summary = state?.source_summary || {};
    const values = [
      ["source.supported", number(summary.supported), "supported"],
      ["source.detected", number(summary.detected), "detected"],
      ["source.missing", number(summary.missing), "missing"],
      ["source.unsupported", number(summary.unsupported), "unsupported"],
      ["source.error", number(summary.error), "error"],
    ];
    byId("sourceSummaryGrid").innerHTML = values
      .map(
        ([labelKey, value, className]) =>
          `<div class="detection-item ${className}"><span>${escapeHtml(t(labelKey))}</span><strong>${escapeHtml(integer(value))}</strong></div>`,
      )
      .join("");
  }

  function renderSources() {
    renderSourceSummary();
    const container = byId("sourceList");
    container.replaceChildren();
    const runtimeByAgent = {};
    for (const row of state?.source_runtime || []) {
      const current = runtimeByAgent[row.agent] || {
        events: 0,
        processed_tokens: 0,
      };
      current.events += number(row.events);
      current.processed_tokens += number(row.processed_tokens);
      runtimeByAgent[row.agent] = current;
    }
    const sources = state?.sources || [];
    if (!sources.length) {
      container.innerHTML = `<div class="empty">${escapeHtml(t("overview.noData"))}</div>`;
      return;
    }
    sources.forEach((source) => {
      const row = document.createElement("div");
      row.className = "source-row";
      const runtime = runtimeByAgent[source.agent] || {
        events: 0,
        processed_tokens: 0,
      };
      const status = source.status || "missing";
      const paths = source.existing_paths?.length
        ? source.existing_paths
        : source.paths || [];
      const pathText = paths.length ? paths.join("; ") : t("source.noPaths");
      const precision = precisionLabel(source.metadata?.precision);
      const errorText = source.metadata?.error
        ? `; ${t("source.readError")}: ${source.metadata.error}`
        : "";
      row.innerHTML = `
        <div>
          <div class="source-name">${escapeHtml(source.agent)}</div>
          <div class="source-meta">${escapeHtml(sourceKindLabel(source.kind))} · ${escapeHtml(precision)} · ${escapeHtml(source.note || "")}${escapeHtml(errorText)}</div>
        </div>
        <div class="source-meta" title="${escapeHtml(pathText)}">${escapeHtml(pathText)}</div>
        <div class="source-status ${escapeHtml(status)}">${escapeHtml(sourceStatusLabel(status))} · ${escapeHtml(
          t("source.runtime", {
            events: integer(runtime.events),
            tokens: yi(runtime.processed_tokens),
          }),
        )}</div>`;
      container.appendChild(row);
    });
  }

  function renderValidation() {
    const validation = state?.validation || {};
    const values = [
      [
        t("quality.passed"),
        validation.passed ? t("quality.pass") : t("quality.fail"),
        validation.passed ? "validation-pass" : "validation-fail",
      ],
      [t("quality.events"), integer(validation.events), ""],
      [t("quality.errors"), integer(validation.errors), validation.errors ? "validation-fail" : ""],
      [t("quality.warnings"), integer(validation.warnings), validation.warnings ? "validation-warn" : ""],
      [t("quality.semantic"), integer(validation.semantic_unknown), ""],
      [t("quality.providerMismatch"), integer(validation.provider_total_mismatches), ""],
    ];
    byId("validationGrid").innerHTML = values
      .map(
        ([label, value, className]) =>
          `<div class="validation-item ${escapeHtml(className)}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`,
      )
      .join("");

    const list = byId("issueList");
    list.replaceChildren();
    const issues = (state?.issues || []).slice(0, 20);
    if (!issues.length) {
      list.innerHTML = `<div class="empty">${escapeHtml(t("quality.noIssues"))}</div>`;
      return;
    }
    issues.forEach((issue) => {
      const row = document.createElement("div");
      row.className = "issue-row";
      row.innerHTML = `
        <div><span class="issue-severity ${escapeHtml(issue.severity)}">${escapeHtml(severityLabel(issue.severity))}</span> <span class="issue-source">${escapeHtml(issueSourceLabel(issue.source))}</span></div>
        <div class="issue-message">${escapeHtml(issue.message)}</div>
        <div class="source-meta" title="${escapeHtml(issue.code)}">${escapeHtml(issueCodeLabel(issue.code))}</div>`;
      list.appendChild(row);
    });
  }

  function renderNotes() {
    const notes = state?.notes || [];
    byId("notes").innerHTML = notes.length
      ? notes.map((note) => `<p>${escapeHtml(note)}</p>`).join("")
      : `<p>${escapeHtml(t("quality.waitingNotes"))}</p>`;
  }

  function renderSettings() {
    const prefs = preferences();
    byId("languageSelect").value = prefs.language;
    byId("themeSelect").value = prefs.theme;
    byId("currencySelect").value = prefs.currency;
    byId("exchangeRateInput").value = String(prefs.exchange_rate);
    const refreshValue = String(prefs.refresh_seconds);
    const refreshSelect = byId("refreshSelect");
    if (![...refreshSelect.options].some((option) => option.value === refreshValue)) {
      const option = document.createElement("option");
      option.value = refreshValue;
      option.textContent = t("settings.refreshHint");
      refreshSelect.appendChild(option);
    }
    refreshSelect.value = refreshValue;
  }

  function renderAbout() {
    const version = state?.version || "—";
    text(byId("sidebarVersion"), `${version}`);
    text(byId("aboutVersion"), version);
    text(byId("aboutWindowMode"), windowModeLabel(state?.window_mode));
    const aboutStatus = byId("aboutStatus");
    text(aboutStatus, byId("statusPill").textContent || t("status.starting"));
    aboutStatus.className = `about-status ${state?.status || "starting"}`;
    text(byId("aboutDataDir"), state?.work_dir || "—");
    const settingsPauseLabel = state?.paused
      ? t("settings.continueAuto")
      : t("settings.pauseAuto");
    text(byId("settingsPauseTitle"), settingsPauseLabel);
    const settingsPauseButton = byId("settingsPauseButton");
    settingsPauseButton.title = settingsPauseLabel;
    settingsPauseButton.setAttribute("aria-label", settingsPauseLabel);
    settingsPauseButton.disabled = state?.status === "stopping";
    byId("settingsRefreshButton").disabled =
      state?.status === "scanning" || state?.status === "stopping";
    byId("settingsStopButton").disabled = state?.status === "stopping";
  }

  function render() {
    applyTheme();
    applyStaticTranslations();
    renderNavigation();
    renderPage();
    renderStatus();
    renderScanFacts();
    renderTotals();
    renderChartPanel();
    renderOverviewTopList();
    renderDimensionTabs();
    renderReport();
    renderSources();
    renderValidation();
    renderNotes();
    renderSettings();
    renderAbout();
  }

  async function loadState(force = false) {
    try {
      const response = await fetch("/api/state", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json();
      if (
        !force &&
        next.scan_id === lastVersion &&
        next.scanning === state?.scanning &&
        next.paused === state?.paused &&
        next.status === state?.status &&
        JSON.stringify(next.preferences) === JSON.stringify(state?.preferences)
      ) {
        return;
      }
      lastVersion = next.scan_id;
      state = next;
      render();
    } catch (error) {
      // A stopped service intentionally drops the connection; keep the last view.
    }
  }

  async function post(path, body = {}) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function action(path, body = {}) {
    try {
      const next = await post(path, body);
      state = next;
      lastVersion = next.scan_id;
      render();
      return next;
    } catch (error) {
      return null;
    }
  }

  async function togglePaused() {
    const nextPaused = !Boolean(state?.paused);
    if (state) {
      state = {
        ...state,
        paused: nextPaused,
        status: nextPaused
          ? "paused"
          : state.scanning
            ? "scanning"
            : "ready",
        next_scan_ms: null,
        next_scan_at: "",
      };
      render();
    }
    const result = await action("/api/pause", { paused: nextPaused });
    if (!result) {
      await loadState(true);
    }
  }

  async function saveSettings() {
    const saved = byId("settingsSaved");
    saved.className = "save-state saving";
    text(saved, t("settings.saving"));
    try {
      const next = await post("/api/preferences", {
        language: byId("languageSelect").value,
        theme: byId("themeSelect").value,
        currency: byId("currencySelect").value,
        exchange_rate: Number(byId("exchangeRateInput").value),
        refresh_seconds: Number(byId("refreshSelect").value),
      });
      state = next;
      lastVersion = next.scan_id;
      render();
      saved.className = "save-state";
      text(saved, t("settings.saved"));
    } catch (error) {
      saved.className = "save-state error";
      text(saved, t("settings.saveFailed"));
    }
  }

  async function resetSettings() {
    byId("languageSelect").value = defaultPreferences.language;
    byId("themeSelect").value = defaultPreferences.theme;
    byId("currencySelect").value = defaultPreferences.currency;
    byId("exchangeRateInput").value = String(defaultPreferences.exchange_rate);
    byId("refreshSelect").value = String(defaultPreferences.refresh_seconds);
    await saveSettings();
  }

  async function stopService() {
    if (!window.confirm(t("action.stopConfirm"))) return;
    await action("/api/stop");
    byId("stoppedOverlay").classList.add("visible");
  }

  function bindChartTooltip() {
    const svg = byId("usageChart");
    svg.addEventListener("mousemove", (event) => {
      const target = event.target.closest?.("[data-chart-index]");
      const tooltip = byId("chartTooltip");
      if (!target) {
        tooltip.style.display = "none";
        return;
      }
      const index = Number(target.dataset.chartIndex);
      let lines = [];
      if (currentChartType === "heatmap") {
        const point = currentHeatmapPoints.get(index);
        if (!point) return;
        lines = [
          `<strong>${escapeHtml(fullDay(point.date))}</strong>`,
          `${escapeHtml(t("chart.totalValue"))}: ${escapeHtml(yi(point.value))}`,
          `${escapeHtml(t("table.input"))}: ${escapeHtml(yi(point.input))}`,
          `${escapeHtml(t("table.output"))}: ${escapeHtml(yi(point.output))}`,
          `${escapeHtml(t("table.cached"))}: ${escapeHtml(yi(point.cached))}`,
          `${escapeHtml(t("chart.estimatedCost"))}: ${escapeHtml(
            point.estimatedCost ? `≈${money(point.estimatedCost)}` : t("cost.missing"),
          )}`,
          `${escapeHtml(t("table.events"))}: ${escapeHtml(integer(point.events))}`,
        ];
      } else {
        const point = currentChartPoints[index];
        if (!point) return;
        lines = [
          `<strong>${escapeHtml(point.name)}</strong>`,
          `${escapeHtml(t("chart.totalValue"))}: ${escapeHtml(yi(point.value))}`,
          `${escapeHtml(t("table.input"))}: ${escapeHtml(yi(point.input))}`,
          `${escapeHtml(t("table.output"))}: ${escapeHtml(yi(point.output))}`,
          `${escapeHtml(t("table.cached"))}: ${escapeHtml(yi(point.cached))}`,
          `${escapeHtml(t("chart.estimatedCost"))}: ${escapeHtml(
            point.estimatedCost ? `≈${money(point.estimatedCost)}` : t("cost.missing"),
          )}`,
          `${escapeHtml(t("table.events"))}: ${escapeHtml(integer(point.events))}`,
        ];
      }
      tooltip.innerHTML = lines.join("<br>");
      tooltip.style.display = "block";
      const tooltipWidth = tooltip.offsetWidth || 220;
      const tooltipHeight = tooltip.offsetHeight || 120;
      const left = Math.min(
        event.clientX + 14,
        window.innerWidth - tooltipWidth - 12,
      );
      const top = Math.min(
        event.clientY + 14,
        window.innerHeight - tooltipHeight - 12,
      );
      tooltip.style.left = `${Math.max(12, left)}px`;
      tooltip.style.top = `${Math.max(12, top)}px`;
    });
    svg.addEventListener("mouseleave", () => {
      byId("chartTooltip").style.display = "none";
    });
  }

  function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.addEventListener("click", () => {
        currentPage = button.dataset.page || "overview";
        render();
      });
    });
    byId("openUsageButton").addEventListener("click", () => {
      currentPage = "usage";
      render();
    });
    byId("refreshButton").addEventListener("click", () => action("/api/refresh"));
    byId("pauseButton").addEventListener("click", togglePaused);
    byId("stopButton").addEventListener("click", stopService);
    byId("sourceRefreshButton").addEventListener("click", () =>
      action("/api/refresh"),
    );
    byId("settingsRefreshButton").addEventListener("click", () =>
      action("/api/refresh"),
    );
    byId("settingsPauseButton").addEventListener("click", togglePaused);
    byId("settingsStopButton").addEventListener("click", stopService);
    byId("searchInput").addEventListener("input", (event) => {
      searchText = event.target.value;
      renderReport();
    });
    byId("settingsForm").addEventListener("submit", (event) => {
      event.preventDefault();
      saveSettings();
    });
    byId("resetSettingsButton").addEventListener("click", resetSettings);
    [
      "languageSelect",
      "themeSelect",
      "currencySelect",
      "exchangeRateInput",
      "refreshSelect",
    ].forEach((id) => {
      byId(id).addEventListener("change", saveSettings);
    });
  }

  function initialize() {
    systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
    systemThemeQuery.addEventListener?.("change", () => {
      if (preferences().theme === "system") render();
    });
    bindEvents();
    bindChartTooltip();
    render();
    loadState(true);
    window.setInterval(loadState, 2000);
  }

  initialize();
})();
