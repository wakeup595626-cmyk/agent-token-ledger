from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..model import ScanIssue, SourceStat
from ..timeutil import now_ms


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                text = line.strip()
                if not text:
                    continue
                try:
                    value = json.loads(text)
                except json.JSONDecodeError as exc:
                    yield line_number, None, f"{exc.msg} at column {exc.colno}"
                    continue
                if isinstance(value, dict):
                    yield line_number, value, None
    except OSError as exc:
        yield 0, None, str(exc)


def file_stat(
    path: Path,
    *,
    source: str,
    event_count: int,
    error_count: int,
    metadata: dict[str, Any] | None = None,
    hash_limit_bytes: int = 64 * 1024 * 1024,
) -> SourceStat:
    stat = path.stat()
    fingerprint = f"stat:{stat.st_size}:{stat.st_mtime_ns}"
    if stat.st_size <= hash_limit_bytes:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        fingerprint = "sha256:" + digest.hexdigest()
    return SourceStat(
        source=source,
        path=str(path),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        scanned_at_ms=now_ms(),
        event_count=event_count,
        error_count=error_count,
        fingerprint=fingerprint,
        metadata=metadata or {},
    )


def issue(
    source: str,
    code: str,
    message: str,
    *,
    raw_ref: str = "",
    severity: str = "warning",
    metadata: dict[str, Any] | None = None,
) -> ScanIssue:
    return ScanIssue(
        source=source,
        severity=severity,
        code=code,
        message=message,
        raw_ref=raw_ref,
        metadata=metadata or {},
    )


def first_int(*values: Any, default: int = 0) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return default


def first_nonzero_int(*values: Any, default: int = 0) -> int:
    saw_zero = False
    for value in values:
        if value is None or value == "":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number != 0:
            return number
        saw_zero = True
    return 0 if saw_zero else default


def first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def masked_account(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if "@" in text:
        local, domain = text.split("@", 1)
        visible = local[:1] if local else "*"
        return f"{visible}***@{domain}"
    if len(text) <= 8:
        return text[:2] + "***"
    return text[:4] + "***" + text[-3:]
