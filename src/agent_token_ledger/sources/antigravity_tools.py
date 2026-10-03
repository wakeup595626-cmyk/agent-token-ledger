from __future__ import annotations

import sqlite3
from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from ..timeutil import to_epoch_ms
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_stat, first_int, first_text, issue, masked_account


class AntigravityToolsAdapter(SourceAdapter):
    name = "antigravity_tools"
    agent = "Antigravity"

    def __init__(self, database: Path | None = None):
        self.database = database

    def scan(self, context: ScanContext) -> ScanResult:
        path = self.database or context.home / ".antigravity_tools" / "token_stats.db"
        result = ScanResult(source=self.name)
        if not path.exists():
            result.issues.append(
                issue(
                    self.name,
                    "database_missing",
                    "Token 统计数据库不存在",
                    raw_ref=str(path),
                )
            )
            return result
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        try:
            rows = connection.execute(
                """
                SELECT id, timestamp, account_email, model, input_tokens,
                       output_tokens, total_tokens, cached_tokens
                FROM token_usage
                ORDER BY timestamp, id
                """
            ).fetchall()
        except sqlite3.Error as exc:
            result.issues.append(
                issue(
                    self.name,
                    "database_read_error",
                    str(exc),
                    raw_ref=str(path),
                )
            )
            connection.close()
            return result
        connection.close()

        for row in rows:
            input_tokens = first_int(row["input_tokens"])
            output_tokens = first_int(row["output_tokens"])
            result.events.append(
                UsageEvent(
                    event_key=f"antigravity-tools:{first_int(row['id'])}",
                    source=self.name,
                    agent=self.agent,
                    source_kind=SourceKind.PROXY,
                    timestamp_ms=to_epoch_ms(row["timestamp"], unit="s") or 0,
                    input_tokens=input_tokens,
                    cached_input_tokens=first_int(row["cached_tokens"]),
                    output_tokens=output_tokens,
                    provider_total_tokens=first_int(
                        row["total_tokens"], default=input_tokens + output_tokens
                    ),
                    account=masked_account(first_text(row["account_email"])),
                    model=first_text(row["model"], default="unknown"),
                    input_includes_cached=True,
                    input_includes_cache_write=True,
                    quality=Quality.EXACT,
                    raw_ref=f"{path}#token_usage",
                    metadata={"proxy_tool": "Antigravity Tools"},
                )
            )
        result.snapshots.append(
            file_stat(
                path,
                source=self.name,
                event_count=len(rows),
                error_count=0,
                hash_limit_bytes=0,
                metadata={"live_sqlite": True},
            )
        )
        return result
