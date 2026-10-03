from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from ..timeutil import now_ms, to_epoch_ms
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_stat, first_int, first_text, issue, masked_account


class CockpitSessionAdapter(SourceAdapter):
    name = "cockpit_session"
    agent = "Codex"

    def __init__(self, database: Path | None = None):
        self.database = database

    def scan(self, context: ScanContext) -> ScanResult:
        path = self.database or (
            context.home / ".antigravity_cockpit" / "codex_session_usage.sqlite"
        )
        result = ScanResult(source=self.name)
        if not path.exists():
            result.issues.append(
                issue(self.name, "database_missing", "数据库不存在", raw_ref=str(path))
            )
            return result
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        try:
            rows = connection.execute(
                """
                SELECT request_id, instance_id, instance_name, session_id, model,
                       timestamp, input_tokens, cached_input_tokens, output_tokens,
                       file_path
                FROM session_usage_events
                ORDER BY timestamp, request_id
                """
            ).fetchall()
        except sqlite3.Error as exc:
            result.issues.append(
                issue(self.name, "database_read_error", str(exc), raw_ref=str(path))
            )
            connection.close()
            return result
        connection.close()

        for row in rows:
            request_id = first_text(row["request_id"])
            session_id = first_text(row["session_id"])
            request_sequence = _request_sequence(request_id)
            result.events.append(
                UsageEvent(
                    event_key=f"cockpit-session:{request_id}",
                    source=self.name,
                    agent=self.agent,
                    source_kind=SourceKind.DERIVED,
                    timestamp_ms=to_epoch_ms(row["timestamp"], unit="s") or 0,
                    input_tokens=first_int(row["input_tokens"]),
                    cached_input_tokens=first_int(row["cached_input_tokens"]),
                    output_tokens=first_int(row["output_tokens"]),
                    provider_total_tokens=(
                        first_int(row["input_tokens"])
                        + first_int(row["output_tokens"])
                    ),
                    account=masked_account(
                        first_text(row["instance_name"], row["instance_id"])
                    ),
                    model=first_text(row["model"]),
                    session_id=session_id,
                    request_id=request_id,
                    input_includes_cached=True,
                    input_includes_cache_write=True,
                    quality=Quality.EXACT,
                    raw_ref=f"{path}#session_usage_events",
                    metadata={
                        "instance_id": first_text(row["instance_id"]),
                        "instance_name": first_text(row["instance_name"]),
                        "source_file": first_text(row["file_path"]),
                        "file_id": _file_id(first_text(row["file_path"])),
                        "request_sequence": request_sequence,
                    },
                )
            )
        result.snapshots.append(
            file_stat(path, source=self.name, event_count=len(rows), error_count=0)
        )
        return result


def _request_sequence(request_id: str) -> int | None:
    match = re.search(r":(\d+)$", request_id)
    return int(match.group(1)) if match else None


def _file_id(path_text: str) -> str:
    if not path_text:
        return ""
    name = Path(path_text).stem
    match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$",
        name,
    )
    return match.group(1) if match else name
