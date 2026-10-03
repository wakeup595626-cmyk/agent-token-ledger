from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_token_ledger.cli import main
from agent_token_ledger.inventory import InventoryItem
from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.pipeline import persist_scan
from agent_token_ledger.sources.base import (
    ScanContext,
    ScanResult,
)
from agent_token_ledger.storage import LedgerDatabase


class CliStorageTests(unittest.TestCase):
    def test_persist_report_validate_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database_path = root / "ledger.sqlite"
            context = ScanContext(
                home=root,
                appdata=root / "Roaming",
                local_appdata=root / "Local",
                work_dir=root / "work",
            )
            result = ScanResult(
                source="codex_native",
                events=[
                    UsageEvent(
                        event_key="event-1",
                        source="codex_native",
                        agent="Codex",
                        source_kind=SourceKind.NATIVE,
                        timestamp_ms=1_800_000_000_000,
                        input_tokens=1000,
                        cached_input_tokens=700,
                        output_tokens=50,
                        provider_total_tokens=1050,
                        session_id="session-1",
                        input_includes_cached=True,
                        input_includes_cache_write=True,
                    )
                ],
            )
            with LedgerDatabase(database_path) as database:
                scan_id = persist_scan(
                    database,
                    [result],
                    context=context,
                    command={"test": True},
                    include_inventory=False,
                )
                self.assertEqual(scan_id, 1)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(database_path),
                        "report",
                        "--scope",
                        "primary",
                        "--dimension",
                        "agent",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(exit_code, 0)
            report_data = json.loads(output.getvalue())
            self.assertEqual(
                report_data["overall"]["processed_tokens"], 1050
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    ["--db", str(database_path), "validate", "--json"]
                )
            self.assertEqual(exit_code, 0)
            validation = json.loads(output.getvalue())
            self.assertTrue(validation["passed"])
            self.assertEqual(validation["events"], 1)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(database_path),
                        "report",
                        "--format",
                        "csv",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("processed_tokens", output.getvalue())
            self.assertIn("Codex", output.getvalue())

    def test_scan_json_sources_json_and_text_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database_path = root / "ledger.sqlite"
            context = ScanContext(
                home=root,
                appdata=root / "Roaming",
                local_appdata=root / "Local",
                work_dir=root / "work",
            )
            result = ScanResult(
                source="codex_native",
                events=[
                    UsageEvent(
                        event_key="event-1",
                        source="codex_native",
                        agent="Codex",
                        source_kind=SourceKind.NATIVE,
                        timestamp_ms=1_800_000_000_000,
                        input_tokens=1000,
                        cached_input_tokens=700,
                        output_tokens=50,
                        provider_total_tokens=1050,
                        session_id="session-1",
                        input_includes_cached=True,
                        input_includes_cache_write=True,
                    )
                ],
            )

            output = io.StringIO()
            with (
                patch(
                    "agent_token_ledger.cli.default_context",
                    return_value=context,
                ),
                patch(
                    "agent_token_ledger.cli.default_adapters",
                    return_value=[],
                ),
                patch(
                    "agent_token_ledger.cli.scan_all",
                    return_value=[result],
                ),
                contextlib.redirect_stdout(output),
            ):
                exit_code = main(
                    [
                        "--db",
                        str(database_path),
                        "scan",
                        "--work-dir",
                        str(root / "work"),
                        "--json",
                    ]
                )
            self.assertEqual(exit_code, 0)
            scan_data = json.loads(output.getvalue())
            self.assertEqual(scan_data["raw_events"], 1)
            self.assertEqual(scan_data["deduped_events"], 1)
            self.assertEqual(scan_data["scan_id"], 1)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(database_path),
                        "report",
                        "--format",
                        "text",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("0.0000 亿 (1,050 个 Token)", output.getvalue())
            self.assertIn("Codex", output.getvalue())

            inventory_item = InventoryItem(
                agent="Codex",
                kind="native",
                status="detected",
                paths=["C:/example/.codex/sessions"],
                note="JSONL token events",
            )
            output = io.StringIO()
            with (
                patch(
                    "agent_token_ledger.cli.inventory",
                    return_value=[inventory_item],
                ),
                contextlib.redirect_stdout(output),
            ):
                exit_code = main(["sources", "--json"])
            self.assertEqual(exit_code, 0)
            sources_data = json.loads(output.getvalue())
            self.assertEqual(sources_data[0]["agent"], "Codex")
            self.assertEqual(sources_data[0]["status"], "detected")


if __name__ == "__main__":
    unittest.main()
