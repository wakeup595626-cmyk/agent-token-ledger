from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_token_ledger import app as app_module


class DataDirTests(unittest.TestCase):
    def test_env_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            override = Path(temp) / "custom"
            with patch.dict(
                "os.environ", {"AGENT_TOKEN_LEDGER_DATA_DIR": str(override)}
            ):
                chosen = app_module._default_data_dir()
            self.assertEqual(chosen, override)

    def test_prefers_non_system_fixed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict("os.environ", {"AGENT_TOKEN_LEDGER_DATA_DIR": ""}):
                with patch.object(
                    app_module,
                    "_non_system_fixed_roots",
                    return_value=[root],
                ):
                    chosen = app_module._default_data_dir()
            self.assertEqual(chosen, root / "AgentTokenLedger")
            self.assertTrue(chosen.is_dir())

    def test_falls_back_to_local_appdata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp) / "Local"
            with patch.dict(
                "os.environ",
                {
                    "AGENT_TOKEN_LEDGER_DATA_DIR": "",
                    "LOCALAPPDATA": str(local),
                },
            ):
                with patch.object(
                    app_module,
                    "_non_system_fixed_roots",
                    return_value=[],
                ):
                    chosen = app_module._default_data_dir()
            self.assertEqual(chosen, local / "AgentTokenLedger")

    def test_migrate_copies_settings_and_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            legacy = base / "AgentTokenLedger"
            legacy.mkdir()
            (legacy / "settings.json").write_text(
                '{"language":"zh-CN"}', encoding="utf-8"
            )
            (legacy / "codex_native_cache_v1.json").write_text(
                '{"version":1,"files":{}}', encoding="utf-8"
            )
            (legacy / "dsh_native_cache_v1.json").write_text(
                '{"version":1,"files":{}}', encoding="utf-8"
            )
            target = base / "target"
            target.mkdir()
            with patch.dict("os.environ", {"LOCALAPPDATA": str(base)}):
                app_module._migrate_legacy_data(target)
            self.assertTrue((target / "settings.json").is_file())
            self.assertTrue((target / "codex_native_cache_v1.json").is_file())
            self.assertTrue((target / "dsh_native_cache_v1.json").is_file())
            self.assertTrue((legacy / "settings.json").is_file())

    def test_migrate_skips_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            legacy = base / "AgentTokenLedger"
            legacy.mkdir()
            (legacy / "settings.json").write_text(
                '{"currency":"USD"}', encoding="utf-8"
            )
            target = base / "target"
            target.mkdir()
            (target / "settings.json").write_text(
                '{"currency":"CNY"}', encoding="utf-8"
            )
            with patch.dict("os.environ", {"LOCALAPPDATA": str(base)}):
                app_module._migrate_legacy_data(target)
            self.assertEqual(
                (target / "settings.json").read_text(encoding="utf-8"),
                '{"currency":"CNY"}',
            )


if __name__ == "__main__":
    unittest.main()