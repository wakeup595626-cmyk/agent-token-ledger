from __future__ import annotations

import sqlite3
from pathlib import Path

from ..model import Quality, SourceKind, UsageEvent
from .base import ScanContext, ScanResult, SourceAdapter
from .utils import file_stat, first_int, first_text, issue, masked_account


class CockpitGatewayAdapter(SourceAdapter):
    name = "cockpit_gateway"
    agent = "Cockpit Gateway"

    def __init__(self, database: Path | None = None):
        self.database = database

    def scan(self, context: ScanContext) -> ScanResult:
        path = self.database or (
            context.home / ".antigravity_cockpit" / "codex_local_access_logs.sqlite"
        )
        result = ScanResult(source=self.name)
        if not path.exists():
            result.issues.append(
                issue(
                    self.name,
                    "database_missing",
                    "数据库不存在",
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
                SELECT event_key, timestamp, request_id, account_id, email,
                       api_key_label, model_id, requested_model, upstream_model,
                       gateway_mode, request_kind, success, http_status,
                       error_category, latency_ms, input_tokens, output_tokens,
                       total_tokens, cached_tokens, reasoning_tokens,
                       estimated_cost_usd, client_instance_id
                FROM request_logs
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
            account = masked_account(
                first_text(row["email"], row["api_key_label"], row["account_id"])
            )
            result.events.append(
                UsageEvent(
                    event_key=f"cockpit-gateway:{first_text(row['event_key'])}",
                    source=self.name,
                    agent=self.agent,
                    source_kind=SourceKind.GATEWAY,
                    timestamp_ms=first_int(row["timestamp"]),
                    input_tokens=first_int(row["input_tokens"]),
                    cached_input_tokens=first_int(row["cached_tokens"]),
                    output_tokens=first_int(row["output_tokens"]),
                    reasoning_output_tokens=first_int(row["reasoning_tokens"]),
                    provider_total_tokens=first_int(row["total_tokens"]),
                    account=account,
                    model=first_text(
                        row["requested_model"], row["model_id"], row["upstream_model"]
                    ),
                    request_id=first_text(row["request_id"]),
                    cost_usd=float(row["estimated_cost_usd"] or 0),
                    input_includes_cached=True,
                    input_includes_cache_write=True,
                    quality=Quality.EXACT,
                    raw_ref=f"{path}#request_logs",
                    metadata={
                        "gateway_mode": first_text(row["gateway_mode"]),
                        "request_kind": first_text(row["request_kind"]),
                        "success": bool(row["success"]),
                        "http_status": row["http_status"],
                        "error_category": first_text(row["error_category"]),
                        "latency_ms": first_int(row["latency_ms"]),
                        "client_instance_id": first_text(row["client_instance_id"]),
                    },
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
