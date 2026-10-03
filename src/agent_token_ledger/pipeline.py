from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .inventory import inventory_issues
from .model import ScanIssue, SourceKind, UsageEvent
from .sources.antigravity_tools import AntigravityToolsAdapter
from .sources.base import ScanContext, ScanResult, SourceAdapter
from .sources.cockpit_gateway import CockpitGatewayAdapter
from .sources.cockpit_session import CockpitSessionAdapter
from .sources.codex_native import CodexNativeAdapter
from .sources.dsh import DshAdapter
from .sources.traetools import TraeToolsAdapter
from .sources.utils import issue
from .sources.workbuddy import WorkBuddyAdapter, WorkBuddyAiAdapter
from .storage import LedgerDatabase


def default_context(work_dir: Path) -> ScanContext:
    user_home = Path(os.environ.get("USERPROFILE") or Path.home())
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA") or user_home / "AppData" / "Roaming")
        local_appdata = Path(
            os.environ.get("LOCALAPPDATA") or user_home / "AppData" / "Local"
        )
    elif sys.platform == "darwin":
        appdata = Path(os.environ.get("APPDATA") or user_home / "Library" / "Application Support")
        local_appdata = Path(os.environ.get("LOCALAPPDATA") or user_home / "Library" / "Application Support")
    else:
        appdata = Path(os.environ.get("APPDATA") or user_home / ".config")
        local_appdata = Path(os.environ.get("LOCALAPPDATA") or user_home / ".local" / "share")
    return ScanContext(
        home=user_home,
        appdata=appdata,
        local_appdata=local_appdata,
        work_dir=work_dir,
    )


def default_adapters(*, include_gateway: bool = True) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = [
        CodexNativeAdapter(),
        CockpitSessionAdapter(),
        DshAdapter(),
        WorkBuddyAdapter(),
        WorkBuddyAiAdapter(),
        TraeToolsAdapter(),
        AntigravityToolsAdapter(),
    ]
    if include_gateway:
        adapters.insert(1, CockpitGatewayAdapter())
    return adapters


def scan_all(
    context: ScanContext,
    *,
    adapters: list[SourceAdapter] | None = None,
) -> list[ScanResult]:
    return [
        adapter.scan(context)
        for adapter in (adapters if adapters is not None else default_adapters())
    ]


def reconcile(
    events: list[UsageEvent], issues: list[ScanIssue] | None = None
) -> tuple[list[UsageEvent], list[ScanIssue]]:
    issue_list = list(issues or [])
    by_key: dict[tuple[str, str], UsageEvent] = {}
    for event in events:
        key = (event.source, event.event_key)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = event
            continue
        if existing.usage_tuple() != event.usage_tuple():
            issue_list.append(
                issue(
                    "reconcile",
                    "event_key_collision",
                    "同一来源和事件键的记录用量不一致",
                    raw_ref=event.raw_ref,
                    severity="error",
                    metadata={"existing": existing.raw_ref, "key": event.event_key},
                )
            )

    deduped = list(by_key.values())
    coden_native = [
        event for event in deduped if event.source == "codex_native"
    ]
    cockpit = [
        event for event in deduped if event.source == "cockpit_session"
    ]
    others = [
        event
        for event in deduped
        if event.source not in {"codex_native", "cockpit_session"}
    ]

    native_groups: dict[tuple[str, int], list[UsageEvent]] = defaultdict(list)
    without_sequence: list[UsageEvent] = []
    for event in coden_native:
        sequence = _optional_int(event.metadata.get("session_sequence"))
        file_id = str(event.metadata.get("file_id") or event.session_id)
        if file_id and sequence is not None:
            native_groups[(file_id, sequence)].append(event)
        else:
            without_sequence.append(event)

    selected_native: list[UsageEvent] = []
    native_lookup: dict[tuple[str, int], UsageEvent] = {}
    for group_key, group in native_groups.items():
        ordered = sorted(
            group,
            key=lambda item: (
                0
                if item.metadata.get("source_root") == "sessions"
                else 1,
                item.raw_ref,
            ),
        )
        selected = ordered[0]
        selected_native.append(selected)
        native_lookup[group_key] = selected
        for duplicate in ordered[1:]:
            if selected.usage_tuple() != duplicate.usage_tuple():
                issue_list.append(
                    issue(
                        "reconcile",
                        "native_duplicate_mismatch",
                        "重复的 Codex 会话记录用量不一致",
                        raw_ref=duplicate.raw_ref,
                        severity="error",
                        metadata={
                            "selected": selected.raw_ref,
                            "file_id": group_key[0],
                            "session_sequence": group_key[1],
                        },
                    )
                )

    native_usage_counts = Counter(
        (
            str(event.metadata.get("file_id") or event.session_id),
            event.canonical_usage_tuple(),
        )
        for event in selected_native
    )
    selected_cockpit: list[UsageEvent] = []
    overlap_deduped = 0
    for event in cockpit:
        file_id = str(event.metadata.get("file_id") or event.session_id)
        usage_key = (file_id, event.canonical_usage_tuple())
        if native_usage_counts[usage_key] > 0:
            native_usage_counts[usage_key] -= 1
            overlap_deduped += 1
            continue
        selected_cockpit.append(event)
    if overlap_deduped:
        issue_list.append(
            issue(
                "reconcile",
                "cockpit_native_overlap",
                f"已将 {overlap_deduped} 条 Cockpit 镜像记录与 Codex 原始记录去重",
                severity="info",
                metadata={"deduplicated_events": overlap_deduped},
            )
        )

    return (
        others + selected_native + without_sequence + selected_cockpit,
        issue_list,
    )


def persist_scan(
    database: LedgerDatabase,
    results: list[ScanResult],
    *,
    context: ScanContext,
    command: dict,
    include_inventory: bool = True,
) -> int:
    scan_id = database.begin_run(command)
    try:
        all_events: list[UsageEvent] = []
        all_issues: list[ScanIssue] = []
        for result in results:
            all_events.extend(result.events)
            all_issues.extend(result.issues)
            database.add_snapshots(scan_id, result.snapshots)
        if include_inventory:
            all_issues.extend(inventory_issues(context))
        reconciled, reconcile_issues = reconcile(all_events, all_issues)
        inserted, duplicates = database.add_events(scan_id, reconciled)
        database.add_issues(scan_id, reconcile_issues)
        notes = (
            f"raw_events={len(all_events)}; inserted={inserted}; "
            f"deduped={len(all_events) - inserted}; duplicate_key_rows={duplicates}; "
            f"issues={len(reconcile_issues)}"
        )
        database.finish_run(scan_id, "complete", notes)
    except Exception as exc:
        database.connection.rollback()
        database.finish_run(scan_id, "failed", f"{type(exc).__name__}: {exc}")
        raise
    return scan_id


def _optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
