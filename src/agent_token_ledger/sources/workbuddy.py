from __future__ import annotations

from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from ..timeutil import to_epoch_ms
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import (
    file_stat,
    first_int,
    first_nonzero_int,
    first_text,
    issue,
    iter_jsonl,
)


class WorkBuddyAdapter(SourceAdapter):
    name = "workbuddy"
    agent = "WorkBuddy"

    def __init__(self, root: Path | None = None):
        self.root = root

    def scan(self, context: ScanContext) -> ScanResult:
        root = self.root or context.home / ".workbuddy" / "projects"
        return _scan_variant(
            root=root,
            source=self.name,
            agent=self.agent,
        )


class WorkBuddyAiAdapter(SourceAdapter):
    name = "workbuddy_ai"
    agent = "WorkBuddy AI"

    def __init__(self, root: Path | None = None):
        self.root = root

    def scan(self, context: ScanContext) -> ScanResult:
        root = self.root or context.home / ".workbuddy-ai" / "projects"
        return _scan_variant(
            root=root,
            source=self.name,
            agent=self.agent,
        )


def _scan_variant(*, root: Path, source: str, agent: str) -> ScanResult:
    result = ScanResult(source=source)
    if not root.exists():
        result.issues.append(
            issue(
                source,
                "root_missing",
                "项目目录不存在",
                raw_ref=str(root),
            )
        )
        return result

    seen: dict[str, UsageEvent] = {}
    for path in sorted(root.rglob("*.jsonl")):
        file_events = 0
        errors = 0
        for line_number, record, error in iter_jsonl(path):
            if error:
                errors += 1
                result.issues.append(
                    issue(
                        source,
                        "jsonl_parse_error",
                        error,
                        raw_ref=f"{path}:{line_number}",
                    )
                )
                continue
            if record is None:
                continue
            event = _event_from_record(
                record=record,
                source=source,
                agent=agent,
                path=path,
                line_number=line_number,
            )
            if event is None:
                continue
            existing = seen.get(event.event_key)
            if existing is not None:
                if existing.usage_tuple() != event.usage_tuple():
                    result.issues.append(
                        issue(
                            source,
                            "duplicate_event_mismatch",
                            "同一 WorkBuddy 事件编号的用量不一致",
                            raw_ref=event.raw_ref,
                            severity="error",
                            metadata={"existing": existing.raw_ref},
                        )
                    )
                continue
            seen[event.event_key] = event
            file_events += 1
        result.snapshots.append(
            file_stat(
                path,
                source=source,
                event_count=file_events,
                error_count=errors,
            )
        )
    result.events = list(seen.values())
    return result


def _event_from_record(
    *,
    record: dict,
    source: str,
    agent: str,
    path: Path,
    line_number: int,
) -> UsageEvent | None:
    message = record.get("message") or {}
    usage = message.get("usage") or {}
    if not isinstance(usage, dict) or not usage:
        return None
    session_id = first_text(record.get("sessionId"))
    record_id = first_text(
        record.get("id"),
        message.get("id"),
        default=f"line-{line_number}",
    )
    input_tokens = first_int(
        usage.get("input_tokens"),
        usage.get("inputTokens"),
    )
    provider_data = record.get("providerData") or {}
    provider_usage = provider_data.get("usage") or {}
    raw_usage = provider_data.get("rawUsage") or {}
    cached_tokens = first_int(
        usage.get("cache_read_input_tokens"),
        usage.get("cached_input_tokens"),
        usage.get("cachedTokens"),
    )
    cache_write_tokens = first_nonzero_int(
        usage.get("cache_creation_input_tokens"),
        usage.get("cache_write_input_tokens"),
        usage.get("prompt_cache_write_tokens"),
        raw_usage.get("cache_creation_input_tokens"),
        raw_usage.get("cache_write_input_tokens"),
        raw_usage.get("prompt_cache_write_tokens"),
    )
    output_tokens = first_int(
        usage.get("output_tokens"),
        usage.get("outputTokens"),
    )
    if input_tokens + cached_tokens + cache_write_tokens + output_tokens == 0:
        return None
    reasoning_tokens = first_int(
        usage.get("reasoning_output_tokens"),
        usage.get("reasoning_tokens"),
        raw_usage.get("completion_thinking_tokens"),
    )
    provider_total = first_int(
        usage.get("total_tokens"),
        provider_usage.get("totalTokens"),
        raw_usage.get("total_tokens"),
        default=input_tokens + output_tokens,
    )
    model = first_text(
        message.get("model"),
        provider_data.get("model"),
        record.get("model"),
        default="unknown",
    )
    timestamp_ms = to_epoch_ms(record.get("timestamp"))
    if timestamp_ms is None:
        timestamp_ms = int(path.stat().st_mtime * 1000)
    return UsageEvent(
        event_key=f"{source}:{session_id or 'unknown'}:{record_id}",
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
        session_id=session_id,
        response_id=record_id,
        input_includes_cached=True,
        input_includes_cache_write=True,
        quality=Quality.EXACT,
        raw_ref=f"{path}:{line_number}",
        metadata={
            "record_type": first_text(record.get("type")),
            "source_file": str(path),
            "cache_write_source": (
                "usage"
                if any(
                    usage.get(key) is not None
                    for key in (
                        "cache_creation_input_tokens",
                        "cache_write_input_tokens",
                        "prompt_cache_write_tokens",
                    )
                )
                else "providerData.rawUsage"
            ),
        },
    )
