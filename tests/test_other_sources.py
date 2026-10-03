from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_token_ledger.sources.base import ScanContext
from agent_token_ledger.sources.antigravity_tools import AntigravityToolsAdapter
from agent_token_ledger.sources.cockpit_gateway import CockpitGatewayAdapter
from agent_token_ledger.sources.cockpit_session import CockpitSessionAdapter
from agent_token_ledger.sources.dsh import DshAdapter
from agent_token_ledger.sources.traetools import TraeToolsAdapter


class OtherSourceTests(unittest.TestCase):
    def _context(self, root: Path) -> ScanContext:
        return ScanContext(
            home=root,
            appdata=root / "Roaming",
            local_appdata=root / "Local",
            work_dir=root / "work",
        )

    def test_dsh_sums_four_independent_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = root / "ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "byDayRoute": {
                            "2026-10-02": {
                                "deepseek-chat": {
                                    "input": 100,
                                    "output": 20,
                                    "cacheRead": 300,
                                    "cacheWrite": 40,
                                    "calls": 2,
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = DshAdapter(ledger_path=ledger).scan(self._context(root))

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.non_cached_input_tokens, 100)
            self.assertEqual(event.cached_input_tokens, 300)
            self.assertEqual(event.cache_write_tokens, 40)
            self.assertEqual(event.processed_tokens, 460)
            self.assertEqual(event.model, "deepseek-chat")

    def test_trae_duplicate_export_rows_are_counted_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            data.mkdir()
            row = {
                "SessionId": "session-1",
                "UsageTime": 1780000000,
                "UsageDateTime": "2026-10-02 00:00:00",
                "Mode": "solo",
                "ModelName": "model-1",
                "InputToken": 100,
                "OutputToken": 20,
                "CacheReadToken": 60,
                "CacheWriteToken": 5,
                "TotalToken": 120,
            }
            for name in ("usage_account-one.jsonl", "usage_account-two.jsonl"):
                (data / name).write_text(
                    json.dumps(row) + "\n", encoding="utf-8"
                )

            result = TraeToolsAdapter(data_dir=data).scan(self._context(root))

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.cached_input_tokens, 60)
            self.assertEqual(event.cache_write_tokens, 5)
            self.assertEqual(event.non_cached_input_tokens, 35)
            self.assertEqual(event.processed_tokens, 120)

    def test_cockpit_session_reads_read_only_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "cockpit.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE session_usage_events (
                    request_id TEXT PRIMARY KEY,
                    instance_id TEXT,
                    instance_name TEXT,
                    session_id TEXT,
                    model TEXT,
                    timestamp INTEGER,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    output_tokens INTEGER,
                    file_path TEXT
                );
                """
            )
            connection.execute(
                "INSERT INTO session_usage_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "request-1",
                    "instance-1",
                    "user@example.com",
                    "session-1",
                    "gpt-5",
                    1780000000,
                    1000,
                    700,
                    50,
                    "C:/sessions/rollout-11111111-1111-1111-1111-111111111111.jsonl",
                ),
            )
            connection.commit()
            connection.close()

            result = CockpitSessionAdapter(database=database).scan(
                self._context(root)
            )

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.non_cached_input_tokens, 300)
            self.assertEqual(event.processed_tokens, 1050)
            self.assertEqual(event.account, "u***@example.com")

    def test_cockpit_gateway_is_audited_separately_with_exact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "gateway.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_key TEXT,
                    timestamp INTEGER,
                    request_id TEXT,
                    account_id TEXT,
                    email TEXT,
                    api_key_label TEXT,
                    model_id TEXT,
                    requested_model TEXT,
                    upstream_model TEXT,
                    gateway_mode TEXT,
                    request_kind TEXT,
                    success INTEGER,
                    http_status INTEGER,
                    error_category TEXT,
                    latency_ms INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    cached_tokens INTEGER,
                    reasoning_tokens INTEGER,
                    estimated_cost_usd REAL,
                    client_instance_id TEXT
                );
                """
            )
            connection.execute(
                """
                INSERT INTO request_logs(
                    event_key, timestamp, request_id, account_id, email,
                    api_key_label, model_id, requested_model, upstream_model,
                    gateway_mode, request_kind, success, http_status,
                    error_category, latency_ms, input_tokens, output_tokens,
                    total_tokens, cached_tokens, reasoning_tokens,
                    estimated_cost_usd, client_instance_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "gateway-event-1",
                    1_800_000_000_000,
                    "request-1",
                    "account-1",
                    "user@example.com",
                    "key-label",
                    "gpt-5",
                    "gpt-5-requested",
                    "gpt-5-upstream",
                    "responses",
                    "chat",
                    1,
                    200,
                    "",
                    120,
                    1000,
                    50,
                    1050,
                    700,
                    25,
                    0.01,
                    "client-1",
                ),
            )
            connection.commit()
            connection.close()

            result = CockpitGatewayAdapter(database=database).scan(
                self._context(root)
            )

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.source_kind, "gateway")
            self.assertEqual(event.timestamp_ms, 1_800_000_000_000)
            self.assertEqual(event.non_cached_input_tokens, 300)
            self.assertEqual(event.processed_tokens, 1050)
            self.assertEqual(event.account, "u***@example.com")
            self.assertEqual(event.model, "gpt-5-requested")
            self.assertTrue(result.snapshots[0].metadata["live_sqlite"])

    def test_antigravity_tools_converts_seconds_and_marks_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "antigravity.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE token_usage (
                    id INTEGER PRIMARY KEY,
                    timestamp INTEGER,
                    account_email TEXT,
                    model TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    cached_tokens INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO token_usage VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    1,
                    1_800_000_000,
                    "proxy-user@example.com",
                    "claude-sonnet",
                    1000,
                    50,
                    1050,
                    700,
                ),
            )
            connection.commit()
            connection.close()

            result = AntigravityToolsAdapter(database=database).scan(
                self._context(root)
            )

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.source_kind, "proxy")
            self.assertEqual(event.timestamp_ms, 1_800_000_000_000)
            self.assertEqual(event.non_cached_input_tokens, 300)
            self.assertEqual(event.processed_tokens, 1050)
            self.assertEqual(event.account, "p***@example.com")
            self.assertTrue(result.snapshots[0].metadata["live_sqlite"])


if __name__ == "__main__":
    unittest.main()
