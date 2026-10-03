from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.pipeline import persist_scan
from agent_token_ledger.sources.base import ScanContext, ScanResult
from agent_token_ledger.storage import LedgerDatabase


def _context(root: Path) -> ScanContext:
    return ScanContext(
        home=root,
        appdata=root / "Roaming",
        local_appdata=root / "Local",
        work_dir=root / "work",
    )


def _result(key: str) -> ScanResult:
    return ScanResult(
        source="codex_native",
        events=[
            UsageEvent(
                event_key=key,
                source="codex_native",
                agent="Codex",
                source_kind=SourceKind.NATIVE,
                timestamp_ms=1_800_000_000_000,
                input_tokens=100,
                cached_input_tokens=40,
                output_tokens=10,
                provider_total_tokens=110,
                session_id="session-1",
                input_includes_cached=True,
            )
        ],
    )


class StoragePruneTests(unittest.TestCase):
    def _run_scans(
        self,
        database: LedgerDatabase,
        context: ScanContext,
        count: int,
        **kwargs,
    ) -> int:
        last_id = 0
        for index in range(count):
            last_id = persist_scan(
                database,
                [_result(f"event-{index}")],
                context=context,
                command={"test": True},
                include_inventory=False,
                **kwargs,
            )
        return last_id

    def test_prune_keeps_only_recent_scans(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = _context(root)
            with LedgerDatabase(root / "ledger.sqlite") as database:
                last_id = self._run_scans(database, context, 15)
                self.assertEqual(database.scan_count(), 10)
                self.assertEqual(database.latest_scan_id(), last_id)

    def test_prune_respects_custom_keep(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = _context(root)
            with LedgerDatabase(root / "ledger.sqlite") as database:
                last_id = self._run_scans(database, context, 6, keep_scans=3)
                self.assertEqual(database.scan_count(), 3)
                self.assertEqual(database.latest_scan_id(), last_id)

    def test_prune_disabled_with_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = _context(root)
            with LedgerDatabase(root / "ledger.sqlite") as database:
                self._run_scans(database, context, 12, keep_scans=0)
                self.assertEqual(database.scan_count(), 12)

    def test_prune_never_drops_latest_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = _context(root)
            with LedgerDatabase(root / "ledger.sqlite") as database:
                last_id = self._run_scans(database, context, 4, keep_scans=1)
                self.assertEqual(database.scan_count(), 1)
                self.assertEqual(database.latest_scan_id(), last_id)


if __name__ == "__main__":
    unittest.main()