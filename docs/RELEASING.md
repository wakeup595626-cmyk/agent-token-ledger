# 构建与发布

## 开发环境

- Windows 10/11
- Python 3.11 或更高版本
- PowerShell 5.1 或 PowerShell 7

安装桌面构建依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

## 本地验收

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m agent_token_ledger --db var/ledger.sqlite scan --work-dir var --json
python -m agent_token_ledger --db var/ledger.sqlite validate --json
python -m agent_token_ledger --db var/ledger.sqlite export --output-dir reports --work-dir var --json
```

## 一键生成报告

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all.ps1
```

## 构建桌面程序

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-app.ps1
```

默认把 `AgentTokenLedger.exe` 放到当前用户桌面。可用 `-DesktopDir` 指定其他目录，或用 `-NoDesktop` 只构建不复制。

构建脚本会：

- 运行自动测试。
- 检查并安装固定版本的 PyInstaller 和 pywebview。
- 打包 Web 资源、WebView2 运行库和动态导入。
- 生成带版本号的 Windows ZIP 和 SHA-256。

## 生成发布包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package.ps1
```

会在 `outputs` 生成：

| 包 | 用途 | 是否适合 GitHub |
| --- | --- | --- |
| `agent-token-ledger-v<version>-source.zip` | 公共源码、文档、测试、脚本 | 是 |
| `agent-token-ledger-v<version>-reports.zip` | 本机扫描报告 | 否 |
| `agent-token-ledger-v<version>-delivery.zip` | 源码加本机报告 | 否 |

## GitHub 发布流程

1. 确认 `CHANGELOG.md`、`pyproject.toml`、`src/agent_token_ledger/__init__.py` 与 `README.md` / `README.en.md` 中的版本号和产物文件名一致。
2. 运行测试、报告生成、桌面构建和发布包生成。
3. 只把源码目录和公共源码包提交或发布，不上传 `var`、`reports` 和本机交付包。
4. 打标签：`v` + `pyproject.toml` 中的版本号（例如 `v1.1.3`）。
5. 在 GitHub Release 中附加 `AgentTokenLedger-windows-x64-v<version>.zip`、`agent-token-ledger-v<version>-source.zip` 和对应 SHA-256。
6. 同步 `README.md` / `README.en.md` 的下载文件名与「当前版本」号后再发布，避免文档版本停留在旧版本。

仓库不包含自动推送脚本，也不会代替维护者登录 GitHub。
