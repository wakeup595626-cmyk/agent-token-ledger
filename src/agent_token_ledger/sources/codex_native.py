from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil

from ..model import Quality, ScanIssue, SourceKind, UsageEvent
from ..timeutil import now_ms, to_epoch_ms
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_fingerprint, file_stat, first_int, first_text, issue, iter_jsonl


#: 按文件解析缓存的版本号。解析逻辑变化导致缓存字段不兼容时递增。
_CACHE_VERSION = 1
_CACHE_FILENAME = "codex_native_cache_v1.json"


@dataclass(slots=True)
class _ParsedCodex:
    events: list[UsageEvent]
    issues: list
    errors: int
    had_usage_records: bool


class CodexNativeAdapter(SourceAdapter):
    name = "codex_native"
    agent = "Codex"

    def __init__(self, roots: list[Path] | None = None):
        self.roots = roots

    def scan(self, context: ScanContext) -> ScanResult:
        roots = self.roots or [
            context.home / ".codex" / "sessions",
            context.home / ".codex" / "archived_sessions",
        ]
        cache = _load_cache(context)
        cached_files = cache.get("files", {})
        changed = False
        seen_paths: set[str] = set()
        result = ScanResult(source=self.name)
        for root in roots:
            if not root.exists():
                result.issues.append(
                    issue(self.name, "root_missing", "来源目录不存在", raw_ref=str(root))
                )
                continue
            source_root = (
                "sessions"
                if root.name == "sessions"
                else "archived_sessions"
            )
            for path in sorted(root.rglob("*.jsonl")):
                cache_key = str(path)
                seen_paths.add(cache_key)
                fingerprint = file_fingerprint(path)
                cached = cached_files.get(cache_key)
                parsed = None
                if isinstance(cached, dict) and cached.get("fingerprint") == fingerprint:
                    parsed = _parsed_from_cache(cached)
                if parsed is None:
                    parsed = _parse_file(
                        path,
                        self.name,
                        self.agent,
                        source_root=source_root,
                    )
                    cached_files[cache_key] = {
                        "fingerprint": fingerprint,
                        "events": [event.to_dict() for event in parsed.events],
                        "issues": [asdict(item) for item in parsed.issues],
                        "errors": parsed.errors,
                        "had_usage_records": parsed.had_usage_records,
                    }
                    changed = True
                result.events.extend(parsed.events)
                result.issues.extend(parsed.issues)
                result.snapshots.append(
                    file_stat(
                        path,
                        source=self.name,
                        event_count=len(parsed.events),
                        error_count=parsed.errors,
                        metadata={
                            "format": "new" if parsed.had_usage_records else "legacy",
                            "input_includes_cached": True,
                            "input_includes_cache_write": True,
                        },
                    )
                )
        stale_keys = [key for key in cached_files if key not in seen_paths]
        for key in stale_keys:
            cached_files.pop(key, None)
        if stale_keys or changed:
            _save_cache(context, cache)
        return result


def _parse_file(
    path: Path,
    source: str,
    agent: str,
    *,
    source_root: str,
) -> _ParsedCodex:
    lines: list[tuple[int, dict]] = []
    issues = []
    errors = 0
    for line_number, record, error in iter_jsonl(path):
        if error:
            errors += 1
            issues.append(
                issue(
                    source,
                    "jsonl_parse_error",
                    error,
                    raw_ref=f"{path}:{line_number}",
                )
            )
            continue
        if record is not None:
            lines.append((line_number, record))

    had_usage_records = any(
        record.get("type") == "token_usage_record"
        for _, record in lines
    )
    file_id = _file_id(path)
    session_id = file_id
    payload_session_id = ""
    turn_models: dict[str, str] = {}
    current_model = ""
    sequence = 0
    last_legacy_usage: tuple[int, int, int, int] | None = None
    events: list[UsageEvent] = []

    for line_number, record in lines:
        record_type = str(record.get("type") or "")
        payload = record.get("payload") or {}
        if record_type == "session_meta":
            payload_session_id = first_text(
                payload.get("id"),
                payload.get("session_id"),
                default=payload_session_id,
            )
            continue
        if record_type == "turn_context":
            turn_id = first_text(payload.get("turn_id"))
            model = first_text(payload.get("model"))
            if model:
                current_model = model
            if turn_id and model:
                turn_models[turn_id] = model
            continue

        if had_usage_records and record_type != "token_usage_record":
            continue
        if not had_usage_records and not (
            record_type == "event_msg"
            and str(payload.get("type") or "") == "token_count"
        ):
            continue

        if record_type == "token_usage_record":
            usage = payload.get("usage") or {}
            event_session = first_text(
                payload.get("session_id"),
                payload.get("thread_id"),
                default=session_id,
            )
            if file_id:
                event_session = file_id
            turn_id = first_text(payload.get("turn_id"), payload.get("root_turn_id"))
            response_id = first_text(payload.get("response_id"))
            identity = response_id or f"line-{line_number}"
            event_key = f"codex-new:{file_id or 'unknown'}:{identity}"
            raw_ref = f"{path}:{line_number}"
        else:
            info = payload.get("info") or {}
            usage = info.get("last_token_usage") or {}
            event_session = session_id
            turn_id = ""
            response_id = ""
            sequence += 1
            event_key = f"codex-legacy:{file_id or 'unknown'}:{sequence:08d}"
            raw_ref = f"{path}:{line_number}"

        input_tokens = first_int(
            usage.get("input_tokens"),
            usage.get("inputTokens"),
        )
        cached_tokens = first_int(
            usage.get("cached_input_tokens"),
            usage.get("cachedTokens"),
        )
        cache_write_tokens = first_int(
            usage.get("cache_write_input_tokens"),
            usage.get("cache_write_tokens"),
        )
        output_tokens = first_int(
            usage.get("output_tokens"),
            usage.get("outputTokens"),
        )
        reasoning_tokens = first_int(
            usage.get("reasoning_output_tokens"),
            usage.get("reasoning_tokens"),
        )
        provider_total = first_int(
            usage.get("total_tokens"),
            usage.get("totalTokens"),
            default=input_tokens + output_tokens,
        )
        processed_input_and_output = input_tokens + output_tokens
        provider_total_with_reasoning = (
            processed_input_and_output + reasoning_tokens
        )
        if (
            input_tokens == 0
            and cached_tokens == 0
            and cache_write_tokens == 0
            and output_tokens == 0
        ):
            continue
        usage_tuple = (
            input_tokens,
            cached_tokens,
            cache_write_tokens,
            output_tokens,
        )
        if not had_usage_records:
            if last_legacy_usage == usage_tuple:
                continue
            last_legacy_usage = usage_tuple

        timestamp_ms = to_epoch_ms(
            record.get("timestamp"),
            default=to_epoch_ms(path.stat().st_mtime, unit="s"),
        )
        if timestamp_ms is None:
            timestamp_ms = int(path.stat().st_mtime * 1000)
        model = turn_models.get(turn_id, current_model)
        events.append(
            UsageEvent(
                event_key=event_key,
                source=source,
                agent=agent,
                source_kind=SourceKind.NATIVE,
                timestamp_ms=timestamp_ms,
                input_tokens=input_tokens,
                cached_input_tokens=cached_tokens,
                cache_write_tokens=cache_write_tokens,
                output_tokens=output_tokens,
                reasoning_output_tokens=reasoning_tokens,
                provider_total_tokens=provider_total,
                model=model,
                session_id=event_session,
                turn_id=turn_id,
                response_id=response_id,
                input_includes_cached=True,
                input_includes_cache_write=True,
                quality=Quality.EXACT,
                raw_ref=raw_ref,
                metadata={
                    "format": "new" if had_usage_records else "legacy",
                    "line_number": line_number,
                    "session_sequence": _sequence_for_event(
                        events, event_session
                    ),
                    "file_id": file_id,
                    "source_file": str(path),
                    "payload_session_id": payload_session_id,
                    "source_root": source_root,
                    "provider_total_equals_input_plus_output": (
                        provider_total == processed_input_and_output
                    ),
                    "provider_total_equals_input_output_reasoning": (
                        provider_total == provider_total_with_reasoning
                    ),
                    "provider_total_delta": (
                        provider_total - processed_input_and_output
                    ),
                },
            )
        )
    return _ParsedCodex(events, issues, errors, had_usage_records)


def _sequence_for_event(events: list[UsageEvent], session_id: str) -> int:
    return 1 + sum(1 for event in events if event.session_id == session_id)


def _file_id(path: Path) -> str:
    match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$",
        path.stem,
    )
    return match.group(1) if match else path.stem


def _load_cache(context: ScanContext) -> dict:
    empty = {"version": _CACHE_VERSION, "files": {}}
    path = context.work_dir / _CACHE_FILENAME
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
        return empty
    files = data.get("files")
    if not isinstance(files, dict):
        return empty
    return {"version": _CACHE_VERSION, "files": files}


def _save_cache(context: ScanContext, cache: dict) -> None:
    """Best-effort 写入解析缓存，失败静默忽略，不影响扫描结果。"""
    path = context.work_dir / _CACHE_FILENAME
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, separators=(",", ":"))
        try:
            tmp_path.replace(path)
        except OSError as exc:
            # EFS 加密目录即使临时文件与目标同目录，os.replace 也可能报 WinError 17，
            # 回退为复制覆盖，保证缓存仍能落盘。
            if getattr(exc, "winerror", None) != 17:
                raise
            shutil.copyfile(tmp_path, path)
            tmp_path.unlink(missing_ok=True)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _parsed_from_cache(cached: dict) -> _ParsedCodex | None:
    """把缓存字典还原成解析结果；任何字段不合法都返回 None 触发重解析。"""
    events: list[UsageEvent] = []
    for item in cached.get("events") or []:
        if not isinstance(item, dict):
            return None
        try:
            events.append(UsageEvent.from_dict(item))
        except (TypeError, ValueError, KeyError):
            return None
    issues: list[ScanIssue] = []
    for item in cached.get("issues") or []:
        if not isinstance(item, dict):
            return None
        try:
            issues.append(ScanIssue(**item))
        except TypeError:
            return None
    return _ParsedCodex(
        events=events,
        issues=issues,
        errors=int(cached.get("errors") or 0),
        had_usage_records=bool(cached.get("had_usage_records")),
    )
