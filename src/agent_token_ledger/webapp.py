from __future__ import annotations

import copy
import errno
import http.server
import json
import logging
import os
import re
import shutil
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .inventory import inventory_issues, inventory_summary, inventory_with_errors
from .model import ScanIssue, UsageEvent
from .pipeline import default_adapters, default_context, reconcile
from .preferences import (
    DEFAULT_PREFERENCES,
    PreferenceStore,
    merge_preferences,
)
from .pricing import (
    COST_ANCHOR_FILE_NAME,
    CostAnchor,
    derive_cost_anchor,
    load_cost_anchor,
    merge_cost_anchors,
    save_cost_anchor,
)
from .reporting import (
    Report,
    build_scope_summaries,
    render_csv,
    report,
    report_dimensions,
)
from .sources.base import ScanContext, ScanResult
from .startup import StartupManager
from .timeutil import LOCAL_TIMEZONE, iso_from_ms, now_ms
from .validation import validate_snapshot


APP_NAME = "agent-token-ledger"
APP_TITLE = "本机智能体用量账本"
APP_VERSION = __version__
LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_REFRESH_SECONDS = 30
SCOPES = ("primary", "native", "visible")
DIMENSIONS = ("agent", "source", "model", "account", "date", "kind")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
BACKUP_FORMAT = "agent-token-ledger-backup"
BACKUP_SCHEMA_VERSION = 1
BACKUP_MAX_BYTES = 256 * 1024 * 1024
PENDING_CLEAR_MARKER = "pending-cache-clear.json"


@dataclass(slots=True)
class ScanPayload:
    """A complete, in-memory snapshot produced by one scan."""

    events: list[UsageEvent]
    issues: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    snapshots: list[dict[str, Any]]
    work_dir: str = ""
    source_summary: dict[str, int] = field(default_factory=dict)
    coverage_gaps: list[dict[str, Any]] = field(default_factory=list)
    model_aliases: dict[str, str] = field(default_factory=dict)


_SESSION_DATE_RE = re.compile(r"(20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?([0-2]\d|3[01])")
_MODEL_ALIASES_CACHE: dict[Path, tuple[int, float, dict[str, str]]] = {}


def _codex_session_day(path: Path) -> str:
    """Return the best-effort date for a Codex session JSONL file."""
    match = _SESSION_DATE_RE.search(path.name)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return ""


def codex_session_days(home: Path) -> set[str]:
    """Collect dates that have at least one Codex session JSONL file."""
    days: set[str] = set()
    for directory in (
        home / ".codex" / "sessions",
        home / ".codex" / "archived_sessions",
    ):
        if not directory.is_dir():
            continue
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for path in entries:
            if not path.is_file() or path.suffix.lower() != ".jsonl":
                continue
            day = _codex_session_day(path)
            if day:
                days.add(day)
    return days


def codex_coverage_gaps(
    home: Path,
    *,
    days: int = 7,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Return dates in the last N days without a Codex session file.

    The current day is excluded because a day that has just started rarely has
    a complete log yet and would otherwise add noise.
    """
    today = today or date.today()
    present = codex_session_days(home)
    gaps: list[dict[str, Any]] = []
    for offset in range(1, days + 1):
        day = today - timedelta(days=offset)
        day_text = day.isoformat()
        if day_text not in present:
            gaps.append(
                {
                    "date": day_text,
                    "reason": "本机未发现该日期的 Codex 原生日志，无法逐请求回算",
                }
            )
    return gaps


def load_model_aliases(home: Path) -> dict[str, str]:
    """Map internal Codex model slugs to upstream model names.

    The local catalog can be large, so a small cache keyed by size and mtime
    avoids re-reading it on every scan. Missing or malformed catalogs return
    an empty mapping rather than failing the scan.
    """
    catalog = home / ".codex" / "cockpit-model-catalog.json"
    try:
        stat = catalog.stat()
    except OSError:
        return {}
    if not catalog.is_file() or stat.st_size > 64 * 1024 * 1024:
        return {}
    cached = _MODEL_ALIASES_CACHE.get(catalog)
    if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime:
        return cached[2]
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return {}
    aliases: dict[str, str] = {}
    for item in models:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        upstream = str(
            item.get("display_name") or item.get("description") or ""
        ).strip()
        if slug and upstream and upstream != slug:
            aliases[slug] = upstream
    _MODEL_ALIASES_CACHE[catalog] = (stat.st_size, stat.st_mtime, aliases)
    return aliases


class LedgerService:
    """Owns the background scan loop and the dashboard state."""

    def __init__(
        self,
        *,
        work_dir: Path,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
        skip_gateway: bool = False,
        scanner: Callable[[], ScanPayload] | None = None,
        startup_manager: StartupManager | None = None,
    ):
        self.work_dir = Path(work_dir)
        self._preference_store = PreferenceStore(self.work_dir / "settings.json")
        self.preferences = self._preference_store.load()
        self._cost_anchor_path = self.work_dir / COST_ANCHOR_FILE_NAME
        self._cost_anchor = load_cost_anchor(self._cost_anchor_path)
        preferred_refresh = (
            int(self.preferences["refresh_seconds"])
            if self._preference_store.exists
            else int(refresh_seconds)
        )
        self.refresh_seconds = max(5, preferred_refresh)
        self.skip_gateway = bool(skip_gateway)
        self._scanner = scanner or self._default_scanner
        self._startup_manager = startup_manager or StartupManager()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._idle_event = threading.Event()
        self._idle_event.set()
        self._thread: threading.Thread | None = None
        self._shutdown_callback: Callable[[], None] | None = None
        self._window_mode = "service"
        self._scanning = False
        self._paused = False
        self._force_refresh = False
        self._scan_number = 0
        self._events: list[UsageEvent] = []
        self._last_payload: ScanPayload | None = None
        self._started_at_ms = now_ms()
        startup = self._startup_manager.status().to_dict()
        self._state: dict[str, Any] = {
            "app": APP_NAME,
            "title": APP_TITLE,
            "version": APP_VERSION,
            "status": "starting",
            "scanning": False,
            "paused": False,
            "scan_id": 0,
            "refresh_seconds": self.refresh_seconds,
            "preferences": dict(self.preferences),
            "cost_anchor": self._anchor_state(),
            "started_at_ms": self._started_at_ms,
            "started_at": iso_from_ms(self._started_at_ms),
            "last_scan_started_at_ms": None,
            "last_scan_started_at": "",
            "last_scan_finished_at_ms": None,
            "last_scan_finished_at": "",
            "last_scan_duration_ms": None,
            "next_scan_ms": None,
            "next_scan_at": "",
            "scopes": {},
            "validation": {},
            "sources": [],
            "source_summary": {},
            "snapshots": [],
            "source_runtime": [],
            "issues": [],
            "notes": [],
            "coverage_gaps": [],
            "model_aliases": {},
            "last_error": "",
            "work_dir": str(self.work_dir),
            "window_mode": self._window_mode,
            "startup_supported": bool(startup["supported"]),
            "startup_enabled": bool(startup["enabled"]),
            "startup_error": str(startup.get("error") or ""),
            "startup_command": str(startup.get("command") or ""),
        }

    def set_shutdown_callback(self, callback: Callable[[], None] | None) -> None:
        with self._lock:
            self._shutdown_callback = callback

    def set_window_mode(self, mode: str) -> None:
        with self._lock:
            self._window_mode = str(mode or "service")
            self._state["window_mode"] = self._window_mode

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="agent-token-ledger-scan",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3)

    def request_shutdown(self) -> None:
        self.stop()
        callback = self._shutdown_callback
        if callback is not None:
            callback()

    def is_running(self) -> bool:
        thread = self._thread
        return (
            thread is not None
            and thread.is_alive()
            and not self._stop_event.is_set()
        )

    def is_scanning(self) -> bool:
        with self._lock:
            return self._scanning

    def set_paused(self, paused: bool) -> bool:
        with self._lock:
            self._paused = bool(paused)
            self._state["paused"] = self._paused
            self._state["next_scan_ms"] = None
            self._state["next_scan_at"] = ""
            if self._paused:
                self._state["status"] = "paused"
            elif self._scanning:
                self._state["status"] = "scanning"
            elif self._state.get("status") not in {"error", "starting", "stopping"}:
                self._state["status"] = "ready"
        self._wake_event.set()
        return self._paused

    def toggle_paused(self) -> bool:
        with self._lock:
            next_paused = not self._paused
        return self.set_paused(next_paused)

    def request_refresh(self) -> bool:
        with self._lock:
            self._force_refresh = True
            if self._scanning:
                started = False
            else:
                started = True
        self._wake_event.set()
        return started

    def update_preferences(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            normalized = merge_preferences(self.preferences, updates)
            self.preferences = self._preference_store.save(normalized)
            self.refresh_seconds = int(self.preferences["refresh_seconds"])
            self._state["preferences"] = dict(self.preferences)
            self._state["refresh_seconds"] = self.refresh_seconds
            # /api/report rebuilds the visible report after a preference change.
            # Rebuilding all report sections here made each price edit wait on
            # the full event set before the save could be acknowledged.
        self._wake_event.set()
        return dict(self.preferences)

    def reset_preferences(self) -> dict[str, Any]:
        return self.update_preferences(copy.deepcopy(DEFAULT_PREFERENCES))

    def reset_model_prices(self) -> dict[str, Any]:
        return self.update_preferences(
            {
                "model_prices": copy.deepcopy(
                    DEFAULT_PREFERENCES["model_prices"]
                )
            }
        )

    def startup_status(self) -> dict[str, Any]:
        status = self._startup_manager.status().to_dict()
        with self._lock:
            self._state.update(
                {
                    "startup_supported": bool(status["supported"]),
                    "startup_enabled": bool(status["enabled"]),
                    "startup_error": str(status.get("error") or ""),
                    "startup_command": str(status.get("command") or ""),
                }
            )
        return status

    def set_startup_enabled(self, enabled: bool) -> dict[str, Any]:
        status = self._startup_manager.set_enabled(bool(enabled)).to_dict()
        with self._lock:
            self._state.update(
                {
                    "startup_supported": bool(status["supported"]),
                    "startup_enabled": bool(status["enabled"]),
                    "startup_error": str(status.get("error") or ""),
                    "startup_command": str(status.get("command") or ""),
                }
            )
        return status

    def filtered_report(self, query: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
            prices = copy.deepcopy(
                self.preferences.get("model_prices") or {}
            )
            anchor = self._cost_anchor
            scope = str(query.get("scope") or "primary").strip().lower()
            if scope not in SCOPES:
                scope = "primary"
            period = _resolve_period(events, query, now_ms=now_ms())

        current_reports = report_dimensions(
            events,
            scope=scope,
            dimensions=DIMENSIONS,
            agent=str(query.get("agent") or ""),
            model=str(query.get("model") or ""),
            account=str(query.get("account") or ""),
            start_ms=period["start_ms"],
            end_ms=period["end_ms"],
            generated_at_ms=period["generated_at_ms"],
            prices=prices,
            anchor=anchor,
        )
        reports = {
            dimension: value.to_dict()
            for dimension, value in current_reports.items()
        }

        previous_overall: dict[str, Any] | None = None
        comparison: dict[str, Any] | None = None
        if period["previous_start_ms"] is not None:
            previous_report = report(
                events,
                scope=scope,
                dimension="agent",
                agent=str(query.get("agent") or ""),
                model=str(query.get("model") or ""),
                account=str(query.get("account") or ""),
                start_ms=period["previous_start_ms"],
                end_ms=period["previous_end_ms"],
                generated_at_ms=period["generated_at_ms"],
                prices=prices,
                anchor=anchor,
            )
            previous_overall = previous_report.overall.to_dict()
            comparison = _comparison_dict(
                current_reports["agent"].overall.to_dict(),
                previous_overall,
            )

        notes = list(reports["agent"].get("notes", []))
        anchor_note = self._anchor_note_for(events)
        if anchor_note:
            notes.append(anchor_note)
        return {
            "scope": scope,
            "range": period["range"],
            "range_label": period["range_label"],
            "start_ms": period["start_ms"],
            "end_ms": period["end_ms"],
            "start_time": (
                iso_from_ms(period["start_ms"])
                if period["start_ms"] is not None
                else ""
            ),
            "end_time": (
                iso_from_ms(period["end_ms"])
                if period["end_ms"] is not None
                else ""
            ),
            "previous_start_ms": period["previous_start_ms"],
            "previous_end_ms": period["previous_end_ms"],
            "overall": reports["agent"]["overall"],
            "groups": reports["agent"]["groups"],
            "reports": reports,
            "previous_overall": previous_overall,
            "comparison": comparison,
            "notes": notes,
        }

    def export_report(
        self,
        query: dict[str, Any],
        *,
        format_name: str,
        dimension: str,
    ) -> tuple[bytes, str, str]:
        scope = str(query.get("scope") or "primary").strip().lower()
        if scope not in SCOPES:
            scope = "primary"
        if dimension not in DIMENSIONS:
            dimension = "agent"
        with self._lock:
            events = list(self._events)
            prices = copy.deepcopy(
                self.preferences.get("model_prices") or {}
            )
            anchor = self._cost_anchor
        period = _resolve_period(events, query, now_ms=now_ms())
        value = report(
            events,
            scope=scope,
            dimension=dimension,
            agent=str(query.get("agent") or ""),
            model=str(query.get("model") or ""),
            account=str(query.get("account") or ""),
            start_ms=period["start_ms"],
            end_ms=period["end_ms"],
            generated_at_ms=period["generated_at_ms"],
            prices=prices,
            anchor=anchor,
        )
        if format_name == "json":
            body = json.dumps(
                value.to_dict(),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            return body, "application/json; charset=utf-8", "json"
        return (
            ("\ufeff" + render_csv(value)).encode("utf-8"),
            "text/csv; charset=utf-8",
            "csv",
        )

    def export_backup(self) -> bytes:
        """把当前设置与统计事件打包成可移植的 JSON 备份，不写入任何文件。"""

        with self._lock:
            exported_at_ms = now_ms()
            payload = {
                "format": BACKUP_FORMAT,
                "schema_version": BACKUP_SCHEMA_VERSION,
                "app_version": APP_VERSION,
                "exported_at_ms": exported_at_ms,
                "exported_at": iso_from_ms(exported_at_ms),
                "preferences": copy.deepcopy(self.preferences),
                "events": [
                    _portable_event_dict(event)
                    for event in self._events
                ],
            }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def import_backup(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把备份 JSON 合并进当前内存统计，返回导入与去重结果。"""

        if not isinstance(payload, dict):
            raise ValueError("备份内容无效：不是有效的 JSON 对象")
        if payload.get("format") != BACKUP_FORMAT:
            raise ValueError("备份内容无效：不是本软件的备份文件")
        try:
            schema_version = int(payload.get("schema_version") or 0)
        except (TypeError, ValueError):
            schema_version = 0
        if schema_version != BACKUP_SCHEMA_VERSION:
            raise ValueError(f"备份版本不受支持：{schema_version}")

        raw_events = payload.get("events")
        if raw_events is None:
            raw_events = []
        if not isinstance(raw_events, list):
            raise ValueError("备份内容无效：统计记录缺失或格式不正确")

        preferences = payload.get("preferences")
        imported_events = 0
        skipped_duplicates = 0
        skipped_invalid = 0
        with self._lock:
            seen = {
                (event.source, event.event_key)
                for event in self._events
                if event.source and event.event_key
            }
            for item in raw_events:
                if not isinstance(item, dict):
                    skipped_invalid += 1
                    continue
                try:
                    event = UsageEvent.from_dict(item)
                except (TypeError, ValueError):
                    skipped_invalid += 1
                    continue
                if not event.source or not event.event_key:
                    skipped_invalid += 1
                    continue
                key = (event.source, event.event_key)
                if key in seen:
                    skipped_duplicates += 1
                    continue
                seen.add(key)
                self._events.append(event)
                imported_events += 1
            self._rebuild_state_from_events()
            if isinstance(preferences, dict):
                try:
                    self.update_preferences(preferences)
                except OSError as exc:
                    raise ValueError(
                        f"导入设置保存失败：{type(exc).__name__}: {exc}"
                    ) from exc
        return {
            "imported_events": imported_events,
            "skipped_duplicates": skipped_duplicates,
            "skipped_invalid": skipped_invalid,
        }

    def _rebuild_state_from_events(self) -> None:
        """根据当前内存事件重算报告与校验结果，供导入后刷新界面使用。"""

        generated_at_ms = now_ms()
        self._learn_cost_anchor(self._events)
        report_sections = self._build_report_sections(
            self._events,
            generated_at_ms=generated_at_ms,
        )
        validation = validate_snapshot(
            self._events,
            list(self._state.get("issues") or []),
        )
        self._state.update(
            {
                **report_sections,
                "cost_anchor": self._anchor_state(),
                "validation": validation,
                "source_runtime": _source_runtime(self._events),
            }
        )

    def diagnostics(self) -> dict[str, Any]:
        startup = self.startup_status()
        with self._lock:
            preferences = copy.deepcopy(self.preferences)
            preferences.pop("model_prices", None)
            return {
                "app": APP_NAME,
                "title": APP_TITLE,
                "version": APP_VERSION,
                "status": self._state.get("status"),
                "scan_id": self._state.get("scan_id"),
                "scanning": self._scanning,
                "paused": self._paused,
                "window_mode": self._window_mode,
                "work_dir": str(self.work_dir),
                "refresh_seconds": self.refresh_seconds,
                "last_scan_started_at": self._state.get(
                    "last_scan_started_at", ""
                ),
                "last_scan_finished_at": self._state.get(
                    "last_scan_finished_at", ""
                ),
                "events": len(self._events),
                "cost_anchor": self._anchor_state(),
                "source_summary": copy.deepcopy(
                    self._state.get("source_summary", {})
                ),
                "validation": copy.deepcopy(
                    self._state.get("validation", {})
                ),
                "last_error": self._state.get("last_error", ""),
                "preferences": preferences,
                "startup": startup,
            }

    def open_data_directory(self) -> dict[str, Any]:
        target = self.work_dir.resolve()
        if not target.is_dir():
            raise FileNotFoundError(f"数据目录不存在：{target}")
        if hasattr(os, "startfile"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            webbrowser.open(target.as_uri(), new=1, autoraise=True)
        return {"opened": True, "path": str(target)}

    def clear_app_cache(self) -> dict[str, Any]:
        base = self.work_dir.resolve()
        removed: list[str] = []
        deferred: list[str] = []
        failures: list[str] = []

        # 浏览器缓存目录：当前窗口正在使用的 profile 一定处于被占用状态，
        # 不做半途删除，直接登记为“下次启动再清理”；未被使用的另一个
        # profile 可以安全删除。若它仍被外部进程占用，同样转入待清理。
        active_profile = {
            "webview": "webview",
            "edge": "edge-app-profile",
        }.get(self._window_mode, "")
        for name in ("webview", "edge-app-profile"):
            target = (base / name).resolve()
            if target.parent != base or not target.exists():
                continue
            if name == active_profile:
                deferred.append(name)
                continue
            try:
                _remove_tree_or_file(target)
                removed.append(name)
            except OSError as exc:
                if _is_file_in_use(exc):
                    deferred.append(name)
                else:
                    failures.append(f"{name}：{type(exc).__name__}: {exc}")

        # 运行日志：截断当前日志并删除轮转备份，避免日志只增不减。
        log_names = ["agent-token-ledger.log"]
        log_names.extend(
            sorted(
                path.name
                for path in base.glob("agent-token-ledger.log.*")
                if path.is_file()
            )
        )
        for name in log_names:
            target = (base / name).resolve()
            if target.parent != base or not target.exists():
                continue
            try:
                if name == "agent-token-ledger.log":
                    # 日志句柄以追加模式打开，截断后下次写入从文件头开始，不会残留空字节。
                    target.open("w", encoding="utf-8").close()
                else:
                    target.unlink()
                removed.append(name)
            except OSError as exc:
                failures.append(f"{name}：{type(exc).__name__}: {exc}")

        self._persist_pending_clear(deferred)

        if failures:
            return {
                "ok": False,
                "removed": removed,
                "deferred": deferred,
                "failures": failures,
                "removed_count": len(removed),
                "deferred_count": len(deferred),
                "failure_count": len(failures),
                "message": "部分缓存无法清除：" + "；".join(failures),
                "work_dir": str(base),
                "kept_parse_cache": True,
            }
        if deferred:
            return {
                "ok": True,
                "removed": removed,
                "deferred": deferred,
                "failures": [],
                "removed_count": len(removed),
                "deferred_count": len(deferred),
                "failure_count": 0,
                "message": "浏览器缓存正在使用，将在下次启动时自动清理",
                "work_dir": str(base),
                "kept_parse_cache": True,
            }
        return {
            "ok": True,
            "removed": removed,
            "deferred": [],
            "failures": [],
            "removed_count": len(removed),
            "deferred_count": 0,
            "failure_count": 0,
            "message": "",
            "work_dir": str(base),
            "kept_parse_cache": True,
        }

    def _persist_pending_clear(self, deferred: list[str]) -> None:
        _write_pending_clear_marker(self.work_dir, deferred)

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        return self._idle_event.wait(timeout)

    def scan_once(self) -> bool:
        """Run one scan synchronously unless a scan is already in progress."""

        with self._lock:
            if self._stop_event.is_set() or self._scanning:
                return False
            self._scanning = True
            self._idle_event.clear()
            started_at_ms = now_ms()
            self._state["status"] = "scanning"
            self._state["scanning"] = True
            self._state["last_scan_started_at_ms"] = started_at_ms
            self._state["last_scan_started_at"] = iso_from_ms(started_at_ms)
            self._state["last_error"] = ""

        try:
            payload = self._scanner()
            finished_at_ms = now_ms()
            new_state = self._build_payload_state(
                payload,
                started_at_ms=started_at_ms,
                finished_at_ms=finished_at_ms,
            )
            with self._lock:
                self._scan_number += 1
                new_state["scan_id"] = self._scan_number
                new_state["status"] = "ready"
                self._state.update(new_state)
            return True
        except Exception as exc:  # The service must remain usable after one bad scan.
            logging.exception("agent token ledger scan failed")
            with self._lock:
                self._state["status"] = "error"
                self._state["last_error"] = f"{type(exc).__name__}: {exc}"
                self._state["last_scan_finished_at_ms"] = now_ms()
                self._state["last_scan_finished_at"] = iso_from_ms(
                    self._state["last_scan_finished_at_ms"]
                )
            return False
        finally:
            with self._lock:
                self._scanning = False
                self._state["scanning"] = False
                self._idle_event.set()

    def snapshot(self) -> dict[str, Any]:
        self.startup_status()
        with self._lock:
            data = copy.deepcopy(self._state)
            data["scanning"] = self._scanning
            data["paused"] = self._paused
            if self._paused:
                data["status"] = "paused"
            elif self._scanning:
                data["status"] = "scanning"
            return data

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                should_scan = self._force_refresh or not self._paused
                self._force_refresh = False
            if should_scan:
                self.scan_once()

            if self._stop_event.is_set():
                break

            with self._lock:
                if self._paused:
                    self._state["next_scan_ms"] = None
                    self._state["next_scan_at"] = ""
                    timeout = 1.0
                else:
                    next_scan_ms = now_ms() + self.refresh_seconds * 1000
                    self._state["next_scan_ms"] = next_scan_ms
                    self._state["next_scan_at"] = iso_from_ms(next_scan_ms)
                    timeout = float(self.refresh_seconds)
            self._wake_event.wait(timeout)
            self._wake_event.clear()

    def _default_scanner(self) -> ScanPayload:
        context = default_context(self.work_dir)
        adapters = default_adapters(include_gateway=not self.skip_gateway)
        events: list[UsageEvent] = []
        issues: list[ScanIssue] = []
        snapshots: list[dict[str, Any]] = []
        source_errors: dict[str, str] = {}

        for adapter in adapters:
            try:
                result = adapter.scan(context)
            except Exception as exc:
                source_errors[adapter.name] = f"{type(exc).__name__}: {exc}"
                issues.append(
                    ScanIssue(
                        source=adapter.name,
                        severity="error",
                        code="scan_failed",
                        message=f"{type(exc).__name__}: {exc}",
                        raw_ref="",
                        metadata={"adapter": adapter.__class__.__name__},
                    )
                )
                continue
            events.extend(result.events)
            issues.extend(result.issues)
            snapshots.extend(asdict(item) for item in result.snapshots)

        source_items = inventory_with_errors(context, source_errors)
        issues.extend(inventory_issues(context, source_errors))
        coverage_gaps = codex_coverage_gaps(context.home)
        model_aliases = load_model_aliases(context.home)
        reconciled, reconciled_issues = reconcile(events, issues)
        issue_dicts = [_issue_to_dict(item) for item in reconciled_issues]
        return ScanPayload(
            events=reconciled,
            issues=issue_dicts,
            sources=[item.to_dict() for item in source_items],
            snapshots=snapshots,
            work_dir=str(context.work_dir),
            source_summary=inventory_summary(source_items),
            coverage_gaps=coverage_gaps,
            model_aliases=model_aliases,
        )

    def _build_payload_state(
        self,
        payload: ScanPayload,
        *,
        started_at_ms: int,
        finished_at_ms: int,
    ) -> dict[str, Any]:
        issue_dicts = [_issue_to_dict(item) for item in payload.issues]
        validation = validate_snapshot(payload.events, issue_dicts)
        self._events = list(payload.events)
        self._last_payload = payload
        self._learn_cost_anchor(payload.events)
        report_sections = self._build_report_sections(
            payload.events,
            generated_at_ms=finished_at_ms,
        )
        notes = list(report_sections.get("notes") or [])
        anchor_note = self._anchor_note_for(payload.events)
        if anchor_note:
            notes.append(anchor_note)
        notes.append(
            "「最近 7 天」按自然日统计（今天起往前共 7 个日历日，不是滚动"
            " 168 小时）；要与上游或反代面板对比时，请先确认双方时间范围一致，"
            "累计总量请切换到「全部时间」。"
        )
        coverage_gaps = payload.coverage_gaps
        if coverage_gaps:
            gap_dates = "、".join(item["date"] for item in coverage_gaps)
            notes.append(
                f"近 7 天本机 Codex 原生日志有 {len(coverage_gaps)} 个日期缺失"
                f"（{gap_dates}），这些日期的用量无法逐请求回算。"
            )
        else:
            notes.append("近 7 天本机 Codex 原生日志覆盖完整。")
        if payload.model_aliases:
            notes.append(
                "模型对照来自本机 Codex 模型目录，未识别为上游模型的内部名称会保留原名显示。"
            )
        else:
            notes.append("本机未发现 Codex 模型目录，内部模型名将保留原名显示。")
        report_sections["notes"] = notes
        source_runtime = _source_runtime(payload.events)
        sorted_issues = sorted(
            issue_dicts,
            key=lambda item: (
                SEVERITY_ORDER.get(str(item.get("severity")), 9),
                str(item.get("source") or ""),
                str(item.get("code") or ""),
            ),
        )
        return {
            "status": "ready",
            "scan_id": self._scan_number + 1,
            "refresh_seconds": self.refresh_seconds,
            "preferences": dict(self.preferences),
            "last_scan_started_at_ms": started_at_ms,
            "last_scan_started_at": iso_from_ms(started_at_ms),
            "last_scan_finished_at_ms": finished_at_ms,
            "last_scan_finished_at": iso_from_ms(finished_at_ms),
            "last_scan_duration_ms": max(0, finished_at_ms - started_at_ms),
            **report_sections,
            "validation": validation,
            "sources": payload.sources,
            "source_summary": payload.source_summary,
            "snapshots": payload.snapshots,
            "source_runtime": source_runtime,
            "cost_anchor": self._anchor_state(),
            "coverage_gaps": payload.coverage_gaps,
            "model_aliases": payload.model_aliases,
            "issues": sorted_issues[:100],
            "last_error": "",
            "work_dir": payload.work_dir or str(self.work_dir),
            "window_mode": self._window_mode,
        }

    def _build_report_sections(
        self,
        events: list[UsageEvent],
        *,
        generated_at_ms: int,
    ) -> dict[str, Any]:
        prices = self.preferences.get("model_prices") or {}
        summaries = build_scope_summaries(
            events,
            scopes=SCOPES,
            prices=prices,
            anchor=self._cost_anchor,
        )
        return {
            "scopes": {
                scope: summaries[scope]["overall"].to_dict()
                for scope in SCOPES
            },
            "notes": summaries["primary"]["notes"],
        }

    def _anchor_state(self) -> dict[str, Any]:
        """Expose the learned cost anchor so the dashboard can explain it."""

        anchor = self._cost_anchor
        if anchor is None or not anchor.usable:
            return {"active": False}
        return {
            "active": True,
            "updated_at_ms": anchor.updated_at_ms,
            "updated_at": (
                iso_from_ms(anchor.updated_at_ms)
                if anchor.updated_at_ms
                else ""
            ),
            "global_rate_usd_per_million": round(
                anchor.global_rate_usd_per_million, 6
            ),
            "model_count": len(anchor.model_rates_usd_per_million),
            "costed_events": anchor.costed_events,
            "costed_tokens": anchor.costed_tokens,
            "known_usd": round(anchor.known_usd, 6),
        }

    def _anchor_note_for(self, events: list[UsageEvent]) -> str:
        """Explain the anchor only when the snapshot lost every real cost."""

        anchor = self._cost_anchor
        if anchor is None or not anchor.usable:
            return ""
        if any(event.cost_usd is not None for event in events):
            return ""
        when = (
            iso_from_ms(anchor.updated_at_ms)
            if anchor.updated_at_ms
            else "此前"
        )
        return (
            f"本次扫描没有发现带实收费用的记录，参考费用沿用 {when} 学习的"
            f"单价锚点（来自 {anchor.costed_events:,} 条实采记录、约 "
            f"${anchor.global_rate_usd_per_million:,.3f}/百万 Token），"
            "避免退回占位价格；锚点保存在数据目录的 cost_anchor_v1.json。"
        )

    def _learn_cost_anchor(self, events: list[UsageEvent]) -> None:
        """Merge learnable rates into the anchor and persist them."""

        derived = derive_cost_anchor(events, updated_at_ms=now_ms())
        if derived is None:
            return
        with self._lock:
            merged = merge_cost_anchors(self._cost_anchor, derived)
            if merged is None:
                return
            save_cost_anchor(self._cost_anchor_path, merged)
            self._cost_anchor = merged


class LedgerRequestHandler(http.server.BaseHTTPRequestHandler):
    """Small local-only JSON/HTML handler for the dashboard."""

    service: LedgerService
    server_version = f"AgentTokenLedger/{APP_VERSION}"

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._handle_get()
        except Exception as exc:
            self._handle_request_error("读取接口失败", exc)

    def _handle_get(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self._send_html(DASHBOARD_HTML)
            return
        if path.startswith("/assets/"):
            name = path.removeprefix("/assets/")
            if name in STATIC_FILES:
                content_type, filename = STATIC_FILES[name]
                self._send_static(filename, content_type)
                return
        if path == "/api/state":
            self._send_json(self.service.snapshot())
            return
        if path == "/api/health":
            state = self.service.snapshot()
            self._send_json(
                {
                    "app": APP_NAME,
                    "version": APP_VERSION,
                    "status": state.get("status"),
                    "scan_id": state.get("scan_id", 0),
                }
            )
            return
        if path == "/api/preferences":
            self._send_json(self.service.snapshot().get("preferences", {}))
            return
        if path == "/api/report":
            self._send_json(
                self.service.filtered_report(_query_dict(parsed.query))
            )
            return
        if path == "/api/diagnostics":
            self._send_json(self.service.diagnostics())
            return
        if path == "/api/export":
            query = _query_dict(parsed.query)
            format_name = str(query.get("format") or "csv").lower()
            if format_name not in {"csv", "json"}:
                format_name = "csv"
            dimension = str(query.get("dimension") or "agent").lower()
            body, content_type, extension = self.service.export_report(
                query,
                format_name=format_name,
                dimension=dimension,
            )
            filename = _export_filename(
                dimension=dimension,
                range_name=str(query.get("range") or "all"),
                extension=extension,
            )
            self._send_download(
                body,
                content_type=content_type,
                filename=filename,
            )
            return
        if path == "/api/backup/export":
            body = self.service.export_backup()
            self._send_download(
                body,
                content_type="application/json; charset=utf-8",
                filename=(
                    "agent-token-ledger-backup-"
                    f"{date.today().isoformat()}.json"
                ),
            )
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self._send_json({"error": "未找到请求的地址", "path": path}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._handle_post()
        except Exception as exc:
            self._handle_request_error("操作接口失败", exc)

    def _handle_post(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/refresh":
            self.service.request_refresh()
            self._send_json(self.service.snapshot())
            return
        if path == "/api/pause":
            paused = self._read_json_body().get("paused")
            if paused is None:
                self.service.toggle_paused()
            else:
                self.service.set_paused(bool(paused))
            self._send_json(self.service.snapshot())
            return
        if path == "/api/startup":
            body = self._read_json_body()
            enabled = body.get("enabled")
            if not isinstance(enabled, bool):
                self._send_json(
                    {"error": "enabled 必须是布尔值", "path": path},
                    status=400,
                )
                return
            status = self.service.set_startup_enabled(enabled)
            payload = self.service.snapshot()
            ok = bool(status.get("supported")) and not bool(
                status.get("error")
            )
            payload["action_result"] = {
                "ok": ok,
                "message": (
                    "已开启开机自动启动"
                    if ok and enabled
                    else "已关闭开机自动启动"
                    if ok
                    else str(status.get("error") or "开机自动启动设置失败")
                ),
            }
            self._send_json(payload)
            return
        if path == "/api/preferences":
            self.service.update_preferences(self._read_json_body())
            self._send_json(self.service.snapshot())
            return
        if path == "/api/preferences/reset":
            self.service.reset_preferences()
            payload = self.service.snapshot()
            payload["action_result"] = {
                "ok": True,
                "message": "已恢复默认设置",
            }
            self._send_json(payload)
            return
        if path == "/api/preferences/prices/reset":
            self.service.reset_model_prices()
            payload = self.service.snapshot()
            payload["action_result"] = {
                "ok": True,
                "message": "已恢复默认模型价格",
            }
            self._send_json(payload)
            return
        if path == "/api/data/open":
            result = self.service.open_data_directory()
            payload = self.service.snapshot()
            payload["action_result"] = {"ok": True, **result}
            self._send_json(payload)
            return
        if path == "/api/cache/clear":
            result = self.service.clear_app_cache()
            payload = self.service.snapshot()
            payload["action_result"] = {"ok": True, **result}
            self._send_json(payload)
            return
        if path == "/api/backup/import":
            try:
                body = self._read_json_body(max_bytes=BACKUP_MAX_BYTES)
            except ValueError as exc:
                self._send_json(
                    {"error": str(exc), "path": path},
                    status=400,
                )
                return
            if not body:
                self._send_json(
                    {"error": "未收到备份内容", "path": path},
                    status=400,
                )
                return
            try:
                result = self.service.import_backup(body)
            except ValueError as exc:
                self._send_json(
                    {"error": str(exc), "path": path},
                    status=400,
                )
                return
            payload = self.service.snapshot()
            payload["action_result"] = {"ok": True, **result}
            self._send_json(payload)
            return
        if path == "/api/stop":
            self._send_json(
                {
                    "app": APP_NAME,
                    "status": "stopping",
                    "message": "服务正在停止",
                }
            )
            threading.Thread(
                target=self.service.request_shutdown,
                name="agent-token-ledger-stop",
                daemon=True,
            ).start()
            return
        self._send_json({"error": "未找到请求的地址", "path": path}, status=404)

    def _handle_request_error(self, label: str, exc: Exception) -> None:
        logging.exception("%s", label)
        message = f"{label}：{type(exc).__name__}: {exc}"
        try:
            self._send_json(
                {
                    "error": message,
                    "message": message,
                },
                status=500,
            )
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _read_json_body(
        self,
        *,
        max_bytes: int = 1024 * 1024,
    ) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        if length > max_bytes:
            raise ValueError(f"请求内容过大，超过 {max_bytes} 字节限制")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _send_json(self, value: Any, *, status: int = 200) -> None:
        body = json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _send_download(
        self,
        body: bytes,
        *,
        content_type: str,
        filename: str,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, value: str) -> None:
        self._send_bytes(
            value.encode("utf-8"),
            content_type="text/html; charset=utf-8",
            csp=True,
        )

    def _send_static(self, filename: str, content_type: str) -> None:
        self._send_bytes(
            (WEB_DIR / filename).read_bytes(),
            content_type=content_type,
            csp=False,
        )

    def _send_bytes(
        self,
        body: bytes,
        *,
        content_type: str,
        csp: bool,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if csp:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; "
                "font-src 'self'",
            )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        logging.debug("http %s - %s", self.address_string(), format % args)


def create_server(
    service: LedgerService,
    *,
    host: str = LOCAL_HOST,
    port: int = DEFAULT_PORT,
) -> http.server.ThreadingHTTPServer:
    handler = type(
        "BoundLedgerRequestHandler",
        (LedgerRequestHandler,),
        {"service": service},
    )
    server = _LedgerHttpServer((host, int(port)), handler)
    server.daemon_threads = True
    return server


class _LedgerHttpServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


def run_webapp(
    *,
    work_dir: Path,
    host: str = LOCAL_HOST,
    port: int = DEFAULT_PORT,
    refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
    skip_gateway: bool = False,
    open_browser: bool = True,
    open_window: bool = False,
) -> int:
    service = LedgerService(
        work_dir=work_dir,
        refresh_seconds=refresh_seconds,
        skip_gateway=skip_gateway,
    )
    server, actual_port, existing = _bind_server(service, host=host, port=port)
    if server is None:
        if existing and existing.get("app") == APP_NAME:
            url = f"http://{host}:{actual_port}/"
            if open_window:
                _run_existing_window(url, Path(work_dir))
            elif open_browser:
                _open_browser(url)
            return 0
        raise RuntimeError(f"无法在 {host}:{port} 启动本地服务")

    actual_host = host
    url = f"http://{actual_host}:{actual_port}/"
    logging.info("Agent Token Ledger listening on %s", url)

    if open_window:
        return _run_window_application(
            service=service,
            server=server,
            url=url,
            work_dir=Path(work_dir),
        )

    service.set_shutdown_callback(
        lambda: threading.Thread(
            target=server.shutdown,
            name="agent-token-ledger-http-stop",
            daemon=True,
        ).start()
    )
    service.start()
    if open_browser:
        _open_browser(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        server.server_close()
    return 0


def _bind_server(
    service: LedgerService,
    *,
    host: str,
    port: int,
) -> tuple[
    http.server.ThreadingHTTPServer | None,
    int,
    dict[str, Any],
]:
    candidates = [int(port)] + [
        int(port) + offset
        for offset in range(1, 11)
        if int(port) + offset <= 65535
    ]
    for candidate in candidates:
        existing = _probe_service(host, candidate)
        if (
            existing
            and existing.get("app") == APP_NAME
            and existing.get("version") == APP_VERSION
        ):
            return None, candidate, existing
        try:
            server = create_server(service, host=host, port=candidate)
        except OSError:
            continue
        return server, int(server.server_address[1]), {}
    return None, int(port), _probe_service(host, port)


def _probe_existing(host: str, port: int) -> bool:
    info = _probe_service(host, port)
    return bool(info and info.get("app") == APP_NAME)


def _probe_service(host: str, port: int) -> dict[str, Any]:
    url = f"http://{host}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=0.6) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return {}
    return value if isinstance(value, dict) else {}


def _is_file_in_use(exc: OSError) -> bool:
    if getattr(exc, "winerror", None) in (32, 33):
        return True
    return getattr(exc, "errno", None) == getattr(errno, "EBUSY", None)


def _remove_tree_or_file(target: Path) -> None:
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def _write_pending_clear_marker(work_dir: Path, names: list[str]) -> None:
    """写入“下次启动时清理”标记；传入空列表表示清除标记。"""

    marker = Path(work_dir) / PENDING_CLEAR_MARKER
    if not names:
        marker.unlink(missing_ok=True)
        return
    payload = {
        "names": sorted(set(names)),
        "created_at_ms": now_ms(),
    }
    tmp = marker.with_name(marker.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, marker)


def clear_pending_cache(work_dir: Path) -> list[str]:
    """启动时消费“下次启动清理”标记，删除上次被运行中窗口占用的缓存目录。"""

    base = Path(work_dir).resolve()
    marker = base / PENDING_CLEAR_MARKER
    if not marker.is_file():
        return []
    names: list[str] = []
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            names = [str(name) for name in (payload.get("names") or [])]
    except (OSError, ValueError):
        logging.warning("读取待清理缓存标记失败，忽略本次清理", exc_info=True)
        marker.unlink(missing_ok=True)
        return []
    cleared: list[str] = []
    still_pending: list[str] = []
    for name in ("webview", "edge-app-profile"):
        if name not in names:
            continue
        target = (base / name).resolve()
        if target.parent != base or not target.exists():
            continue
        try:
            _remove_tree_or_file(target)
            cleared.append(name)
        except OSError:
            still_pending.append(name)
            logging.warning("启动清理缓存时仍有项目被占用：%s", name, exc_info=True)
    if still_pending:
        # 旧实例可能尚未完全退出：保留标记，下次启动继续清理。
        _write_pending_clear_marker(base, still_pending)
    else:
        marker.unlink(missing_ok=True)
    return cleared


def _run_existing_window(url: str, work_dir: Path) -> None:
    from .desktop import open_window

    session = open_window(url, work_dir)
    try:
        session.run()
    finally:
        session.close()


def _run_window_application(
    *,
    service: LedgerService,
    server: http.server.ThreadingHTTPServer,
    url: str,
    work_dir: Path,
) -> int:
    from .desktop import open_window

    clear_pending_cache(work_dir)

    server_thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.5},
        name="agent-token-ledger-http",
        daemon=True,
    )
    server_thread.start()
    service.start()
    session = open_window(url, work_dir)
    service.set_window_mode(session.mode)

    def shutdown() -> None:
        service.stop()
        session.close()
        server.shutdown()

    service.set_shutdown_callback(
        lambda: threading.Thread(
            target=shutdown,
            name="agent-token-ledger-desktop-stop",
            daemon=True,
        ).start()
    )
    try:
        session.run()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        session.close()
        server.shutdown()
        server.server_close()
    return 0


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        logging.exception("could not open browser")


def _issue_to_dict(value: ScanIssue | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return asdict(value)


def _source_runtime(events: list[UsageEvent]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        key = (event.source, event.agent)
        item = grouped.setdefault(
            key,
            {
                "source": event.source,
                "agent": event.agent,
                "events": 0,
                "processed_tokens": 0,
                "costed_events": 0,
                "cost_usd": 0.0,
                "sessions": set(),
            },
        )
        item["events"] += 1
        item["processed_tokens"] += event.processed_tokens
        if event.cost_usd is not None:
            item["costed_events"] += 1
            item["cost_usd"] += event.cost_usd
        if event.session_id:
            item["sessions"].add(event.session_id)
    result = []
    for item in grouped.values():
        item["sessions"] = len(item["sessions"])
        item["processed_yi"] = item["processed_tokens"] / 100_000_000
        item["cost_usd"] = round(item["cost_usd"], 8)
        result.append(item)
    result.sort(
        key=lambda item: (
            -item["processed_tokens"],
            str(item["agent"]).casefold(),
            str(item["source"]).casefold(),
        )
    )
    return result


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return _jsonable(value.value)
    return str(value)


def _query_dict(query: str) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(query, keep_blank_values=False)
    return {
        str(key): str(values[0])
        for key, values in parsed.items()
        if values
    }


def _export_filename(
    *,
    dimension: str,
    range_name: str,
    extension: str,
) -> str:
    safe_dimension = "".join(
        character
        for character in dimension
        if character.isalnum() or character in {"-", "_"}
    )
    safe_range = "".join(
        character
        for character in range_name
        if character.isalnum() or character in {"-", "_"}
    )
    return (
        f"agent-token-ledger-{safe_dimension or 'agent'}-"
        f"{safe_range or 'all'}.{extension}"
    )


def _portable_event_dict(event: UsageEvent) -> dict[str, Any]:
    """生成可移植的事件字典，移除本机专属的绝对路径。"""

    data = event.to_dict()
    for key in (
        "non_cached_input_tokens",
        "input_tokens_total",
        "processed_tokens",
        "non_cached_input_and_output_tokens",
        "cache_semantics_verified",
    ):
        data.pop(key, None)
    data["raw_ref"] = _redact_absolute_path(str(data.get("raw_ref") or ""))
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        data["metadata"] = {
            str(key): _redact_absolute_path(value)
            for key, value in metadata.items()
            if str(key) not in {"source_file", "source_root", "file_path", "path"}
        }
    return data


def _redact_absolute_path(value: Any) -> Any:
    if not isinstance(value, str) or not _is_absolute_path(value):
        return value
    text = value.strip()
    return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _is_absolute_path(value: str) -> bool:
    text = value.strip()
    if len(text) < 3:
        return False
    if text.startswith(("\\", "//")):
        return True
    if len(text) >= 2 and text[1] == ":":
        return True
    return text.startswith(("/", "\\"))


def _resolve_period(
    events: list[UsageEvent],
    query: dict[str, Any],
    *,
    now_ms: int,
) -> dict[str, Any]:
    range_name = str(query.get("range") or "all").strip().lower()
    if range_name not in {"7d", "30d", "90d", "month", "all", "custom"}:
        range_name = "all"
    generated_at_ms = int(now_ms)
    now_local = datetime.fromtimestamp(
        generated_at_ms / 1000,
        tz=LOCAL_TIMEZONE,
    )
    event_times = [
        int(event.timestamp_ms)
        for event in events
        if int(event.timestamp_ms or 0) > 0
    ]
    earliest = min(event_times) if event_times else None
    latest = max(event_times) if event_times else None

    start_ms: int | None
    end_ms: int | None
    previous_start_ms: int | None = None
    previous_end_ms: int | None = None

    if range_name == "all":
        start_ms = earliest
        end_ms = latest
    elif range_name == "custom":
        start_ms = _parse_date_bound(
            query.get("start"),
            end_of_day=False,
        ) or earliest
        end_ms = _parse_date_bound(
            query.get("end"),
            end_of_day=True,
        ) or _end_of_local_day(now_local)
    elif range_name == "month":
        start_ms = _start_of_local_day(now_local.replace(day=1))
        end_ms = generated_at_ms
        previous_month_end = datetime(
            now_local.year,
            now_local.month,
            1,
            tzinfo=LOCAL_TIMEZONE,
        ) - timedelta(milliseconds=1)
        previous_start = previous_month_end.replace(day=1)
        previous_start_ms = _start_of_local_day(previous_start)
        previous_end_ms = int(previous_month_end.timestamp() * 1000)
    else:
        days = int(range_name.removesuffix("d"))
        current_start = now_local - timedelta(days=days - 1)
        start_ms = _start_of_local_day(current_start)
        end_ms = generated_at_ms
        previous_end = datetime.fromtimestamp(
            (start_ms - 1) / 1000,
            tz=LOCAL_TIMEZONE,
        )
        previous_start = previous_end - timedelta(days=days - 1)
        previous_start_ms = _start_of_local_day(previous_start)
        previous_end_ms = int(previous_end.timestamp() * 1000)

    if range_name == "custom" and start_ms is not None and end_ms is not None:
        duration = max(0, end_ms - start_ms)
        previous_end_ms = start_ms - 1 if start_ms > 0 else None
        previous_start_ms = (
            max(0, start_ms - duration - 1)
            if previous_end_ms is not None
            else None
        )

    return {
        "range": range_name,
        "range_label": range_name,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "previous_start_ms": previous_start_ms,
        "previous_end_ms": previous_end_ms,
        "generated_at_ms": generated_at_ms,
    }


def _comparison_dict(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {"has_previous": True}
    for key in (
        "processed_tokens",
        "input_tokens_total",
        "cached_input_tokens",
        "output_tokens",
        "cost_total_usd",
        "events",
    ):
        current_value = float(current.get(key) or 0)
        previous_value = float(previous.get(key) or 0)
        delta = current_value - previous_value
        percent = (
            (delta / previous_value) * 100
            if previous_value
            else None
        )
        result[key] = {
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "percent": percent,
            "direction": (
                "up"
                if delta > 0
                else "down"
                if delta < 0
                else "flat"
            ),
        }
    return result


def _start_of_local_day(value: datetime) -> int:
    return int(
        datetime.combine(
            value.date(),
            datetime_time.min,
            tzinfo=LOCAL_TIMEZONE,
        ).timestamp()
        * 1000
    )


def _end_of_local_day(value: datetime) -> int:
    return int(
        datetime.combine(
            value.date(),
            datetime_time(23, 59, 59, 999000),
            tzinfo=LOCAL_TIMEZONE,
        ).timestamp()
        * 1000
    )


def _parse_date_bound(value: Any, *, end_of_day: bool) -> int | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, pattern).date()
        except ValueError:
            continue
        return (
            _end_of_local_day(
                datetime.combine(parsed, datetime_time.min)
            )
            if end_of_day
            else _start_of_local_day(
                datetime.combine(parsed, datetime_time.min)
            )
        )
    return None

WEB_DIR = Path(__file__).with_name("web")
STATIC_FILES = {
    "index.html": ("text/html; charset=utf-8", "index.html"),
    "styles.css": ("text/css; charset=utf-8", "styles.css"),
    "app.js": ("text/javascript; charset=utf-8", "app.js"),
    "runtime.js": ("text/javascript; charset=utf-8", "runtime.js"),
    "favicon.svg": ("image/svg+xml", "favicon.svg"),
}


def read_static(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


DASHBOARD_HTML = read_static("index.html")
