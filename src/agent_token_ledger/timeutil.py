from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


LOCAL_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def to_epoch_ms(
    value: Any, *, unit: str | None = None, default: int | None = None
) -> int | None:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        number = int(value)
        if unit == "s":
            return number * 1000
        if unit == "ms":
            return number
        # Current Agent ledgers are either seconds around 1.7e9 or ms around 1.7e12.
        return number * 1000 if abs(number) < 10_000_000_000 else number
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return to_epoch_ms(int(text), unit=unit)
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return default
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    return default


def day_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=LOCAL_TIMEZONE).strftime(
        "%Y-%m-%d"
    )


def iso_from_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=LOCAL_TIMEZONE).isoformat()
