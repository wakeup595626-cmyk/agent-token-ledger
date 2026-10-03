from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_stat, first_int, first_text, issue


class DshAdapter(SourceAdapter):
    name = "dsh"
    agent = "DeepSeek Harness"

    def __init__(self, ledger_path: Path | None = None):
        self.ledger_path = ledger_path

    def scan(self, context: ScanContext) -> ScanResult:
        path = self.ledger_path or (
            context.home / ".dsh" / "token-ledger" / "ledger.json"
        )
        result = ScanResult(source=self.name)
        if not path.exists():
            result.issues.append(
                issue(
                    self.name,
                    "ledger_missing",
                    "Token 账本不存在",
                    raw_ref=str(path),
                )
            )
            return result
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                ledger = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            result.issues.append(
                issue(
                    self.name,
                    "ledger_parse_error",
                    str(exc),
                    raw_ref=str(path),
                    severity="error",
                )
            )
            return result

        by_day_route = ledger.get("byDayRoute") or {}
        if not isinstance(by_day_route, dict):
            result.issues.append(
                issue(
                    self.name,
                    "ledger_shape_error",
                    "账本中的 byDayRoute 字段不是对象",
                    raw_ref=str(path),
                    severity="error",
                )
            )
            return result

        for day, routes in by_day_route.items():
            if not isinstance(routes, dict):
                continue
            timestamp_ms = _day_timestamp_ms(str(day))
            for route, totals in routes.items():
                if not isinstance(totals, dict):
                    continue
                input_tokens = first_int(totals.get("input"))
                output_tokens = first_int(totals.get("output"))
                cache_read = first_int(totals.get("cacheRead"))
                cache_write = first_int(totals.get("cacheWrite"))
                if input_tokens + output_tokens + cache_read + cache_write == 0:
                    continue
                result.events.append(
                    UsageEvent(
                        event_key=f"dsh:{day}:{route}",
                        source=self.name,
                        agent=self.agent,
                        source_kind=SourceKind.AGGREGATE,
                        timestamp_ms=timestamp_ms,
                        input_tokens=input_tokens,
                        cached_input_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        output_tokens=output_tokens,
                        provider_total_tokens=(
                            input_tokens
                            + output_tokens
                            + cache_read
                            + cache_write
                        ),
                        model=first_text(route, default="unknown"),
                        input_includes_cached=False,
                        input_includes_cache_write=False,
                        quality=Quality.AGGREGATE,
                        raw_ref=str(path),
                        metadata={
                            "day": str(day),
                            "route": str(route),
                            "calls": first_int(totals.get("calls")),
                            "ledger_version": ledger.get("version"),
                            "ledger_updated_at_ms": ledger.get("updatedAt"),
                        },
                    )
                )
        result.snapshots.append(
            file_stat(path, source=self.name, event_count=len(result.events), error_count=0)
        )
        return result


def _day_timestamp_ms(day: str) -> int:
    try:
        value = datetime.strptime(day, "%Y-%m-%d").replace(
            hour=12, tzinfo=timezone(timedelta(hours=8))
        )
    except ValueError:
        return 0
    return int(value.timestamp() * 1000)
