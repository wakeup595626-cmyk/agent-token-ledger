from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_token_ledger.cli import main
from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.pipeline import persist_scan
from agent_token_ledger.sources.base import ScanContext, ScanResult
from agent_token_ledger.storage import LedgerDatabase


class DeliveryTests(unittest.TestCase):
    def test_cli_export_writes_reports_validation_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database_path = root / "var" / "ledger.sqlite"
            reports = root / "reports"
            context = ScanContext(
                home=root,
                appdata=root / "Roaming",
                local_appdata=root / "Local",
                work_dir=root / "var",
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
                persist_scan(
                    database,
                    [result],
                    context=context,
                    command={"test": True},
                    include_inventory=False,
                )

            output = io.StringIO()
            with (
                patch("agent_token_ledger.delivery.inventory", return_value=[]),
                contextlib.redirect_stdout(output),
            ):
                exit_code = main(
                    [
                        "--db",
                        str(database_path),
                        "export",
                        "--output-dir",
                        str(reports),
                        "--work-dir",
                        str(root / "var"),
                        "--json",
                    ]
                )

            self.assertEqual(exit_code, 0)
            result_data = json.loads(output.getvalue())
            self.assertEqual(result_data["reports"], 18)
            self.assertTrue(result_data["validation"]["passed"])
            self.assertTrue((reports / "summary.json").is_file())
            self.assertTrue((reports / "sources.json").is_file())
            self.assertTrue((reports / "validation.json").is_file())
            self.assertTrue((reports / "primary" / "agent.csv").is_file())
            self.assertTrue((reports / "manifest.sha256").is_file())

            manifest_lines = (
                reports / "manifest.sha256"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(manifest_lines), 65)


if __name__ == "__main__":
    unittest.main()
