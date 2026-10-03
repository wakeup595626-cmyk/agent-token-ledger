from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .model import Quality, ScanIssue, SourceKind, SourceStat, UsageEvent
from .timeutil import now_ms


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS scan_runs (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_ms INTEGER NOT NULL,
    finished_at_ms INTEGER,
    status TEXT NOT NULL,
    command_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    scan_id INTEGER NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    scanned_at_ms INTEGER NOT NULL,
    event_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    fingerprint TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (scan_id, source, path)
);

CREATE TABLE IF NOT EXISTS events (
    scan_id INTEGER NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    source TEXT NOT NULL,
    agent TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    reasoning_output_tokens INTEGER NOT NULL,
    provider_total_tokens INTEGER,
    account TEXT NOT NULL,
    model TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    cost_usd REAL,
    input_includes_cached INTEGER,
    input_includes_cache_write INTEGER,
    quality TEXT NOT NULL,
    raw_ref TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (scan_id, source, event_key)
);

CREATE INDEX IF NOT EXISTS events_scan_agent
ON events(scan_id, agent, timestamp_ms);

CREATE INDEX IF NOT EXISTS events_scan_session
ON events(scan_id, source, session_id);

CREATE TABLE IF NOT EXISTS issues (
    scan_id INTEGER NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_ref TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);
"""


class LedgerDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> LedgerDatabase:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def begin_run(self, command: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO scan_runs(started_at_ms, status, command_json)
            VALUES (?, 'running', ?)
            """,
            (now_ms(), json.dumps(command, ensure_ascii=False, sort_keys=True)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(self, scan_id: int, status: str, notes: str = "") -> None:
        self.connection.execute(
            """
            UPDATE scan_runs
            SET finished_at_ms=?, status=?, notes=?
            WHERE scan_id=?
            """,
            (now_ms(), status, notes, scan_id),
        )
        self.connection.commit()

    def add_events(
        self, scan_id: int, events: Iterable[UsageEvent]
    ) -> tuple[int, int]:
        inserted = 0
        duplicates = 0
        for event in events:
            try:
                self.connection.execute(
                    """
                    INSERT INTO events(
                        scan_id, event_key, source, agent, source_kind, timestamp_ms,
                        input_tokens, cached_input_tokens, cache_write_tokens,
                        output_tokens, reasoning_output_tokens, provider_total_tokens,
                        account, model, session_id, turn_id, request_id, response_id,
                        cost_usd, input_includes_cached, input_includes_cache_write,
                        quality, raw_ref, metadata_json
                    ) VALUES (
                        :scan_id, :event_key, :source, :agent, :source_kind,
                        :timestamp_ms, :input_tokens, :cached_input_tokens,
                        :cache_write_tokens, :output_tokens,
                        :reasoning_output_tokens, :provider_total_tokens,
                        :account, :model, :session_id, :turn_id, :request_id,
                        :response_id, :cost_usd, :input_includes_cached,
                        :input_includes_cache_write, :quality, :raw_ref,
                        :metadata_json
                    )
                    """,
                    {
                        "scan_id": scan_id,
                        "event_key": event.event_key,
                        "source": event.source,
                        "agent": event.agent,
                        "source_kind": str(event.source_kind),
                        "timestamp_ms": event.timestamp_ms,
                        "input_tokens": event.input_tokens,
                        "cached_input_tokens": event.cached_input_tokens,
                        "cache_write_tokens": event.cache_write_tokens,
                        "output_tokens": event.output_tokens,
                        "reasoning_output_tokens": event.reasoning_output_tokens,
                        "provider_total_tokens": event.provider_total_tokens,
                        "account": event.account,
                        "model": event.model,
                        "session_id": event.session_id,
                        "turn_id": event.turn_id,
                        "request_id": event.request_id,
                        "response_id": event.response_id,
                        "cost_usd": event.cost_usd,
                        "input_includes_cached": _bool_to_db(
                            event.input_includes_cached
                        ),
                        "input_includes_cache_write": _bool_to_db(
                            event.input_includes_cache_write
                        ),
                        "quality": str(event.quality),
                        "raw_ref": event.raw_ref,
                        "metadata_json": json.dumps(
                            event.metadata, ensure_ascii=False, sort_keys=True
                        ),
                    },
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        self.connection.commit()
        return inserted, duplicates

    def add_snapshots(
        self, scan_id: int, snapshots: Iterable[SourceStat]
    ) -> None:
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO source_snapshots(
                scan_id, source, path, size_bytes, mtime_ns, scanned_at_ms,
                event_count, error_count, fingerprint, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    item.source,
                    item.path,
                    item.size_bytes,
                    item.mtime_ns,
                    item.scanned_at_ms,
                    item.event_count,
                    item.error_count,
                    item.fingerprint,
                    json.dumps(item.metadata, ensure_ascii=False, sort_keys=True),
                )
                for item in snapshots
            ],
        )
        self.connection.commit()

    def add_issues(self, scan_id: int, issues: Iterable[ScanIssue]) -> None:
        self.connection.executemany(
            """
            INSERT INTO issues(
                scan_id, source, severity, code, message, raw_ref, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    issue.source,
                    issue.severity,
                    issue.code,
                    issue.message,
                    issue.raw_ref,
                    json.dumps(issue.metadata, ensure_ascii=False, sort_keys=True),
                )
                for issue in issues
            ],
        )
        self.connection.commit()

    def latest_scan_id(self) -> int:
        row = self.connection.execute(
            """
            SELECT scan_id
            FROM scan_runs
            WHERE status='complete'
            ORDER BY scan_id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise RuntimeError("No completed scan exists in the ledger")
        return int(row["scan_id"])

    def scan_run(self, scan_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM scan_runs WHERE scan_id=?",
            (scan_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Scan {scan_id} does not exist")
        return dict(row)

    def events(self, scan_id: int) -> list[UsageEvent]:
        rows = self.connection.execute(
            "SELECT * FROM events WHERE scan_id=? ORDER BY timestamp_ms, source, event_key",
            (scan_id,),
        ).fetchall()
        return [event_from_row(row, scan_id) for row in rows]

    def snapshots(self, scan_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM source_snapshots WHERE scan_id=? ORDER BY source, path",
            (scan_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def issues(self, scan_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM issues WHERE scan_id=? ORDER BY source, code, rowid",
            (scan_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def _bool_to_db(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _db_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def event_from_row(row: sqlite3.Row, scan_id: int | None = None) -> UsageEvent:
    return UsageEvent(
        event_key=str(row["event_key"]),
        source=str(row["source"]),
        agent=str(row["agent"]),
        source_kind=SourceKind(row["source_kind"]),
        timestamp_ms=int(row["timestamp_ms"]),
        input_tokens=int(row["input_tokens"]),
        cached_input_tokens=int(row["cached_input_tokens"]),
        cache_write_tokens=int(row["cache_write_tokens"]),
        output_tokens=int(row["output_tokens"]),
        reasoning_output_tokens=int(row["reasoning_output_tokens"]),
        provider_total_tokens=(
            None
            if row["provider_total_tokens"] is None
            else int(row["provider_total_tokens"])
        ),
        account=str(row["account"]),
        model=str(row["model"]),
        session_id=str(row["session_id"]),
        turn_id=str(row["turn_id"]),
        request_id=str(row["request_id"]),
        response_id=str(row["response_id"]),
        cost_usd=None if row["cost_usd"] is None else float(row["cost_usd"]),
        input_includes_cached=_db_to_bool(row["input_includes_cached"]),
        input_includes_cache_write=_db_to_bool(
            row["input_includes_cache_write"]
        ),
        quality=Quality(row["quality"]),
        raw_ref=str(row["raw_ref"]),
        metadata=json.loads(row["metadata_json"] or "{}"),
    )
