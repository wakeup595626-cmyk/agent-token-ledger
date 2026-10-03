from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_token_ledger.inventory import (
    inventory,
    inventory_summary,
    inventory_with_errors,
)
from agent_token_ledger.pipeline import default_context
from agent_token_ledger.sources.base import ScanContext


class InventoryTests(unittest.TestCase):
    def test_empty_computer_reports_supported_sources_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = _context(root)
            items = inventory(context)
            summary = inventory_summary(items)

            supported = [item for item in items if item.status != "unsupported"]
            self.assertTrue(supported)
            self.assertTrue(all(item.status == "missing" for item in supported))
            self.assertEqual(summary["detected"], 0)
            self.assertEqual(summary["missing"], len(supported))
            self.assertGreater(summary["unsupported"], 0)

    def test_creating_one_source_path_only_detects_that_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex" / "sessions").mkdir(parents=True)
            items = inventory(_context(root))

            codex_native = _find(items, "Codex", "native")
            codex_derived = _find(items, "Codex", "derived")
            self.assertEqual(codex_native.status, "detected")
            self.assertEqual(codex_derived.status, "missing")

    def test_multi_path_source_is_detected_when_any_path_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex" / "archived_sessions").mkdir(parents=True)
            items = inventory(_context(root))
            codex_native = _find(items, "Codex", "native")

            self.assertEqual(codex_native.status, "detected")
            self.assertEqual(len(codex_native.to_dict()["existing_paths"]), 1)

    def test_unsupported_sources_keep_their_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".trae").mkdir(parents=True)
            items = inventory(_context(root))
            traework = _find(items, "TraeWork", "native")
            traework_cn = _find(items, "TraeWork CN", "native")

            self.assertEqual(traework.status, "unsupported")
            self.assertEqual(traework_cn.status, "unsupported")

    def test_adapter_error_is_only_applied_to_existing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".workbuddy" / "projects").mkdir(parents=True)
            items = inventory_with_errors(
                _context(root),
                {"workbuddy": "读取权限不足"},
            )

            workbuddy = _find(items, "WorkBuddy", "native")
            workbuddy_ai = _find(items, "WorkBuddy AI", "native")
            self.assertEqual(workbuddy.status, "error")
            self.assertEqual(workbuddy.metadata["error"], "读取权限不足")
            self.assertEqual(workbuddy_ai.status, "missing")

    def test_default_context_follows_current_windows_user_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "Users" / "AnotherUser"
            appdata = home / "AppData" / "Roaming"
            local_appdata = home / "AppData" / "Local"
            with patch.dict(
                os.environ,
                {
                    "USERPROFILE": str(home),
                    "APPDATA": str(appdata),
                    "LOCALAPPDATA": str(local_appdata),
                },
            ):
                context = default_context(root / "work")

            self.assertEqual(context.home, home)
            self.assertEqual(context.appdata, appdata)
            self.assertEqual(context.local_appdata, local_appdata)

    def test_default_context_uses_xdg_paths_on_linux(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home" / "someone"
            with patch.object(sys, "platform", "linux"), patch.dict(
                os.environ,
                {},
            ):
                os.environ.pop("USERPROFILE", None)
                os.environ.pop("APPDATA", None)
                os.environ.pop("LOCALAPPDATA", None)
                with patch("pathlib.Path.home", return_value=home):
                    context = default_context(root / "work")

            self.assertEqual(context.home, home)
            self.assertEqual(context.appdata, home / ".config")
            self.assertEqual(context.local_appdata, home / ".local" / "share")

    def test_default_context_uses_library_paths_on_macos(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "Users" / "someone"
            with patch.object(sys, "platform", "darwin"), patch.dict(
                os.environ,
                {},
            ):
                os.environ.pop("USERPROFILE", None)
                os.environ.pop("APPDATA", None)
                os.environ.pop("LOCALAPPDATA", None)
                with patch("pathlib.Path.home", return_value=home):
                    context = default_context(root / "work")

            self.assertEqual(context.home, home)
            self.assertEqual(
                context.appdata, home / "Library" / "Application Support"
            )
            self.assertEqual(
                context.local_appdata, home / "Library" / "Application Support"
            )


def _context(root: Path) -> ScanContext:
    return ScanContext(
        home=root,
        appdata=root / "AppData" / "Roaming",
        local_appdata=root / "AppData" / "Local",
        work_dir=root / "var",
    )


def _find(items, agent: str, kind: str):
    return next(
        item
        for item in items
        if item.agent == agent and item.kind == kind
    )


if __name__ == "__main__":
    unittest.main()
