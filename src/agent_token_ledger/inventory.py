from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .model import ScanIssue
from .sources.utils import issue


@dataclass(slots=True)
class InventoryItem:
    agent: str
    kind: str
    status: str
    paths: list[str] = field(default_factory=list)
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["existing_paths"] = [
            path for path in self.paths if Path(path).exists()
        ]
        data["exists"] = bool(data["existing_paths"])
        return data


def inventory(context) -> list[InventoryItem]:
    return inventory_with_errors(context)


def inventory_with_errors(
    context,
    errors: dict[str, str] | None = None,
) -> list[InventoryItem]:
    """Return source candidates with a machine-readable local status.

    ``detected`` means that at least one known path exists on this computer.
    ``missing`` means the source is supported, but none of its paths exist.
    ``unsupported`` is used only after a documented review found no reliable
    token ledger.  ``error`` means a path exists, but its adapter failed.
    """

    source_errors = errors or {}
    home = context.home
    appdata = context.appdata
    local_appdata = context.local_appdata
    items = [
        InventoryItem(
            "Codex",
            "native",
            "supported",
            [str(home / ".codex" / "sessions"), str(home / ".codex" / "archived_sessions")],
            "本机原始日志中的令牌记录",
            {
                "source": "codex_native",
                "precision": "request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "Codex",
            "derived",
            "supported",
            [str(home / ".antigravity_cockpit" / "codex_session_usage.sqlite")],
            "Cockpit 会话用量镜像",
            {
                "source": "cockpit_session",
                "precision": "request",
                "read_only": True,
                "overlap": "Codex native",
            },
        ),
        InventoryItem(
            "Cockpit Gateway",
            "gateway",
            "supported",
            [str(home / ".antigravity_cockpit" / "codex_local_access_logs.sqlite")],
            "代理请求日志，与原始记录分开统计",
            {
                "source": "cockpit_gateway",
                "precision": "request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "DeepSeek Harness",
            "native",
            "supported",
            [
                str((context.dsh_home or (home / ".dsh")) / "sessions"),
                str((context.dsh_home or (home / ".dsh")) / "token-ledger" / "ledger.json"),
            ],
            "本机原生日志为主，插件汇总账本兜底",
            {
                "source": "dsh",
                "precision": "request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "WorkBuddy",
            "native",
            "supported",
            [str(home / ".workbuddy" / "projects")],
            "本机原始日志中的消息用量",
            {
                "source": "workbuddy",
                "precision": "request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "WorkBuddy AI",
            "native",
            "supported",
            [str(home / ".workbuddy-ai" / "projects")],
            "本机原始日志中的消息用量",
            {
                "source": "workbuddy_ai",
                "precision": "request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "Trae",
            "native",
            "supported",
            [str(appdata / "TraeTools" / "data")],
            "TraeTools 导出的用量记录",
            {
                "source": "traetools",
                "precision": "exported request rows",
                "read_only": True,
            },
        ),
        InventoryItem(
            "Antigravity",
            "proxy",
            "supported",
            [str(home / ".antigravity_tools" / "token_stats.db")],
            "Antigravity Tools 的统计记录，不是本机历史",
            {
                "source": "antigravity_tools",
                "precision": "proxy request",
                "read_only": True,
            },
        ),
        InventoryItem(
            "Antigravity",
            "native",
            "unsupported",
            [str(home / ".gemini" / "antigravity" / "conversations")],
            "已只读检查 10 个会话数据库，结构和元数据中都没有令牌或用量字段",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "sqlite_schema_and_json_blob_key_scan",
            },
        ),
        InventoryItem(
            "TraeWork",
            "native",
            "unsupported",
            [
                str(home / ".trae"),
                str(appdata / "TraeWorkAssistant"),
            ],
            "本机助手数据只有额度、签到状态和工具配置，没有模型令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "targeted_json_log_key_scan",
            },
        ),
        InventoryItem(
            "TraeWork CN",
            "native",
            "unsupported",
            [
                str(home / ".trae-cn"),
                str(home / ".trae-local"),
                str(local_appdata / "com.traework.assistant"),
            ],
            "只发现配置、记忆、扩展和浏览器状态，没有模型令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "targeted_json_log_key_scan",
            },
        ),
        InventoryItem(
            "Trae SOLO",
            "native",
            "unsupported",
            [str(appdata / "TRAE SOLO")],
            "本机智能体数据库已加密，无法读取令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "non_sqlite_header_and_targeted_log_scan",
            },
        ),
        InventoryItem(
            "Trae SOLO CN",
            "native",
            "unsupported",
            [str(appdata / "TRAE SOLO CN")],
            "本机智能体数据库已加密，无法读取令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "non_sqlite_header_and_targeted_log_scan",
            },
        ),
        InventoryItem(
            "TeleAgent",
            "native",
            "unsupported",
            [
                str(home / ".config" / "TeleAgent"),
                str(appdata / "TeleAgent"),
                str(local_appdata / "teleagent-updater"),
            ],
            "只发现技能计数和更新程序，没有模型令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "targeted_json_log_key_scan",
            },
        ),
        InventoryItem(
            "CodeBuddy",
            "native",
            "unsupported",
            [
                str(appdata / "CodeBuddy"),
                str(appdata / "CodeBuddy CN"),
                str(home / ".codebuddy"),
            ],
            "状态和记忆监听日志中没有模型令牌用量账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "targeted_json_log_key_scan",
            },
        ),
        InventoryItem(
            "SheetAgent",
            "plugin",
            "unsupported",
            [str(home / ".sheetagent")],
            "只发现 MCP 日志，没有独立的令牌账本",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "targeted_log_key_scan",
            },
        ),
        InventoryItem(
            "GitHub Copilot",
            "native",
            "unsupported",
            [
                str(home / ".copilot"),
                str(
                    appdata
                    / "Code"
                    / "User"
                    / "globalStorage"
                    / "github.copilot-chat"
                ),
                str(appdata / "Code" / "User" / "globalStorage" / "emptyWindowChatSessions"),
            ],
            "Copilot 会话记录为空，聊天记录中只有模型配置，没有令牌用量",
            {
                "reviewed_on": "2026-10-02",
                "evidence": "sqlite_schema_and_targeted_jsonl_key_scan",
            },
        ),
    ]
    return [_resolve_status(item, source_errors) for item in items]


def inventory_summary(items: list[InventoryItem]) -> dict[str, int]:
    counts = {
        "total": len(items),
        "supported": 0,
        "detected": 0,
        "missing": 0,
        "unsupported": 0,
        "error": 0,
    }
    for item in items:
        if item.status == "unsupported":
            counts["unsupported"] += 1
            continue
        counts["supported"] += 1
        if item.status in {"detected", "missing", "error"}:
            counts[item.status] += 1
    return counts


def _resolve_status(
    item: InventoryItem,
    errors: dict[str, str],
) -> InventoryItem:
    if item.status == "unsupported":
        return item
    existing_paths = [path for path in item.paths if Path(path).exists()]
    if not existing_paths:
        item.status = "missing"
        return item
    source_name = str(item.metadata.get("source") or "")
    if source_name and source_name in errors:
        item.status = "error"
        item.metadata["error"] = errors[source_name]
        return item
    item.status = "detected"
    return item


def inventory_issues(
    context,
    errors: dict[str, str] | None = None,
) -> list[ScanIssue]:
    issues: list[ScanIssue] = []
    for item in inventory_with_errors(context, errors):
        if item.status == "unsupported":
            paths = ", ".join(item.paths) if item.paths else "没有已知的本机路径"
            issues.append(
                issue(
                    "inventory",
                    "source_unsupported",
                    f"{item.agent}: {item.note}",
                    raw_ref=paths,
                    severity="info",
                    metadata={
                        "agent": item.agent,
                        "kind": item.kind,
                        "status": item.status,
                    },
                )
            )
        elif item.status == "error":
            paths = ", ".join(item.paths) if item.paths else "没有已知的本机路径"
            issues.append(
                issue(
                    "inventory",
                    "source_read_error",
                    f"{item.agent}: {item.metadata.get('error', '读取失败')}",
                    raw_ref=paths,
                    severity="error",
                    metadata={
                        "agent": item.agent,
                        "kind": item.kind,
                        "status": item.status,
                    },
                )
            )
    return issues
