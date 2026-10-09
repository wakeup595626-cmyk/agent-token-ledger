# Agent Token Ledger

[中文](README.md) | **English**

[![CI](https://github.com/wakeup595626-cmyk/agent-token-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/wakeup595626-cmyk/agent-token-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/wakeup595626-cmyk/agent-token-ledger)](https://github.com/wakeup595626-cmyk/agent-token-ledger/releases)

Agent Token Ledger is a Windows desktop application that runs entirely on your own machine. It is not a static web page and never uploads data to a server. Double-click `AgentTokenLedger.exe` and it opens a native application window, automatically detects the agent tools installed on the current computer, and presents token usage in a fully localized interface (Simplified Chinese by default, with seven more languages built in).

## Highlights

- **Local-only and read-only**: no cloud login, no uploads, no remote model calls; listens on `127.0.0.1` only, opens source databases read-only, and never writes, renames, moves or deletes other tools' data.
- **Totals and reference cost**: total tokens (input + output), input, output, cache-hit tokens, and a reference cost in USD and CNY that clearly separates measured amounts from estimates.
- **One chart area, three switchable chart types**: bar chart, line chart and a GitHub-style contribution grid, by agent tool or by model.
- **Per-machine auto-detection**: on every start and refresh it re-reads the current Windows user's `%USERPROFILE%`, `%APPDATA%` and `%LOCALAPPDATA%`, so the same EXE works on any machine without configuration. Missing or unsupported sources are shown as "not found" or "cannot be collected reliably" — never filled with guesses.

Supported sources include Codex, Codex Cockpit mirrors, Cockpit Gateway, DeepSeek Harness, WorkBuddy, WorkBuddy AI, Trae and Antigravity Tools. Antigravity native sessions, TraeWork, Trae SOLO, TeleAgent, CodeBuddy, SheetAgent and GitHub Copilot local sessions have been reviewed and are listed with their status, but are not reliably collectable today.

## Getting started

1. Download `AgentTokenLedger-windows-x64-v1.1.11.zip` from GitHub Releases (the newest version is always listed under [Releases](https://github.com/wakeup595626-cmyk/agent-token-ledger/releases)).
2. Extract it to any writable directory.
3. Double-click `AgentTokenLedger.exe`.

The released EXE bundles its runtime — no separate Python installation is required. Windows 10/11 (64-bit) is the tested platform; the app prefers the Microsoft Edge WebView2 runtime and falls back gracefully.

## Build from source

Requires Python 3.11 or later:

```powershell
python -m pip install -e ".[desktop]"
$env:PYTHONPATH = "src"
python -m agent_token_ledger
```

Run the test suite, a full local scan, validation and report export with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all.ps1
```

Build the single-file Windows executable with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-app.ps1
```

## Project layout

```text
.
├─ src\agent_token_ledger\        Application, scanners, web service and static UI
├─ src\agent_token_ledger\sources Read-only adapters for each agent tool
├─ tests\                         Automated tests
├─ scripts\                       Test, scan, report, build and packaging scripts
├─ docs\                          Architecture, auto-detection, sources, privacy and release docs
├─ assets\                        Application icon
├─ .github\                       CI, release and issue templates
└─ pyproject.toml                 Python package configuration
```

## Privacy boundary

- No cloud account login, no uploads of statistics, sessions or reports.
- No cloud model calls; the app only listens on the loopback address `127.0.0.1`.
- Generated reports contain local source paths and usage evidence. They are meant for local viewing and local delivery — do not upload them to public GitHub repositories.

The full data-authenticity statement lives in `docs/DATA_AUTHENTICITY.md`; detailed usage and build instructions live in the [Chinese README](README.md).

## Current version

Version: `1.1.11` (the newest version is always listed under [Releases](https://github.com/wakeup595626-cmyk/agent-token-ledger/releases)).

See `CHANGELOG.md` for release notes.

## Community and support

- Report bugs through [GitHub Issues](https://github.com/wakeup595626-cmyk/agent-token-ledger/issues).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
