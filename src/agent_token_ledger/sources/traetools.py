from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from ..timeutil import to_epoch_ms
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_stat, first_int, first_text, issue, iter_jsonl


class TraeToolsAdapter(SourceAdapter):
    name = "traetools"
    agent = "Trae"

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir

    def scan(self, context: ScanContext) -> ScanResult:
        data_dir = self.data_dir or (
            context.appdata / "TraeTools" / "data"
        )
        result = ScanResult(source=self.name)
        if not data_dir.exists():
            result.issues.append(
                issue(
                    self.name,
                    "data_missing",
                    "TraeTools 数据目录不存在",
                    raw_ref=str(data_dir),
                )
            )
            return result

        seen: dict[str, UsageEvent] = {}
        for path in sorted(data_dir.glob("usage_*.jsonl")):
            file_events = 0
            errors = 0
            account_ref = _account_ref(path)
            for line_number, record, error in iter_jsonl(path):
                if error:
                    errors += 1
                    result.issues.append(
                        issue(
                            self.name,
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
                    account_ref=account_ref,
                    path=path,
                    line_number=line_number,
                )
                if event is None:
                    continue
                existing = seen.get(event.event_key)
                if existing is not None:
                    if existing.canonical_usage_tuple() != event.canonical_usage_tuple():
                        result.issues.append(
                            issue(
                                self.name,
                                "duplicate_event_mismatch",
                                "重复的 Trae 用量记录数值不一致",
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
                    source=self.name,
                    event_count=file_events,
                    error_count=errors,
                )
            )
        result.events = list(seen.values())
        return result


def _event_from_record(
    *,
    record: dict,
    account_ref: str,
    path: Path,
    line_number: int,
) -> UsageEvent | None:
    input_tokens = first_int(record.get("InputToken"))
    output_tokens = first_int(record.get("OutputToken"))
    cache_read = first_int(record.get("CacheReadToken"))
    cache_write = first_int(record.get("CacheWriteToken"))
    if input_tokens + output_tokens + cache_read + cache_write == 0:
        return None
    timestamp_ms = to_epoch_ms(record.get("UsageTime"), unit="s")
    if timestamp_ms is None:
        timestamp_ms = to_epoch_ms(record.get("UsageDateTime"))
    if timestamp_ms is None:
        timestamp_ms = int(path.stat().st_mtime * 1000)
    session_id = first_text(record.get("SessionId"))
    model = first_text(record.get("ModelName"), record.get("Mode"), default="unknown")
    fingerprint_data = {
        "session": session_id,
        "time": record.get("UsageTime"),
        "mode": record.get("Mode"),
        "model": model,
        "input": input_tokens,
        "output": output_tokens,
        "cache_read": cache_read,
        "cache_write": cache_write,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_data,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    return UsageEvent(
        event_key=f"traetools:{fingerprint}",
        source="traetools",
        agent="Trae",
        source_kind=SourceKind.NATIVE,
        timestamp_ms=timestamp_ms,
        input_tokens=input_tokens,
        cached_input_tokens=cache_read,
        cache_write_tokens=cache_write,
        output_tokens=output_tokens,
        provider_total_tokens=first_int(
            record.get("TotalToken"),
            default=input_tokens + output_tokens,
        ),
        account=account_ref,
        model=model,
        session_id=session_id,
        input_includes_cached=True,
        input_includes_cache_write=True,
        quality=Quality.EXACT,
        cost_usd=_number_or_none(record.get("CostMoneyFloat")),
        raw_ref=f"{path}:{line_number}",
        metadata={
            "mode": first_text(record.get("Mode")),
            "credits": _number_or_none(record.get("CreditsFloat")),
            "usage_datetime": first_text(record.get("UsageDateTime")),
            "source_file": str(path),
        },
    )


def _account_ref(path: Path) -> str:
    stem = path.stem.removeprefix("usage_")
    return "trae-account-" + stem[:8]


def _number_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
