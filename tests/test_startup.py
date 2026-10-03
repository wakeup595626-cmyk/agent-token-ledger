from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from agent_token_ledger.startup import (
    RUN_VALUE_NAME,
    StartupManager,
)
from agent_token_ledger.webapp import LedgerService, create_server


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.read_count = 0
        self.write_count = 0
        self.delete_count = 0
        self.read_error: Exception | None = None
        self.write_error: Exception | None = None
        self.delete_error: Exception | None = None

    def read_value(self, name: str) -> str | None:
        self.read_count += 1
        if self.read_error is not None:
            raise self.read_error
        return self.values.get(name)

    def write_value(self, name: str, value: str) -> None:
        self.write_count += 1
        if self.write_error is not None:
            raise self.write_error
        self.values[name] = value

    def delete_value(self, name: str) -> None:
        self.delete_count += 1
        if self.delete_error is not None:
            raise self.delete_error
        self.values.pop(name, None)


class StartupManagerTests(unittest.TestCase):
    def test_source_run_is_unsupported_without_touching_registry(self) -> None:
        registry = FakeRegistry()
        manager = StartupManager(
            executable=Path(r"C:\Apps\AgentTokenLedger.exe"),
            platform="win32",
            frozen=False,
            registry=registry,
        )

        status = manager.status()

        self.assertFalse(status.supported)
        self.assertFalse(status.enabled)
        self.assertIn("发布版", status.error)
        self.assertEqual(registry.read_count, 0)
        self.assertEqual(registry.write_count, 0)

    def test_enable_writes_current_exe_startup_command(self) -> None:
        registry = FakeRegistry()
        executable = Path(r"C:\Program Files\Agent Token Ledger\AgentTokenLedger.exe")
        manager = StartupManager(
            executable=executable,
            platform="win32",
            frozen=True,
            registry=registry,
        )

        status = manager.set_enabled(True)

        expected = subprocess.list2cmdline([str(executable), "--startup"])
        self.assertTrue(status.supported)
        self.assertTrue(status.enabled)
        self.assertEqual(status.command, expected)
        self.assertEqual(registry.values[RUN_VALUE_NAME], expected)
        self.assertEqual(registry.write_count, 1)

    def test_disable_removes_only_the_named_startup_value(self) -> None:
        registry = FakeRegistry()
        registry.values[RUN_VALUE_NAME] = '"old.exe" --startup'
        registry.values["SomeoneElse"] = "keep-me"
        manager = StartupManager(
            executable=Path(r"C:\Apps\AgentTokenLedger.exe"),
            platform="win32",
            frozen=True,
            registry=registry,
        )

        status = manager.set_enabled(False)

        self.assertTrue(status.supported)
        self.assertFalse(status.enabled)
        self.assertNotIn(RUN_VALUE_NAME, registry.values)
        self.assertEqual(registry.values["SomeoneElse"], "keep-me")
        self.assertEqual(registry.delete_count, 1)

    def test_registry_error_is_reported_in_chinese(self) -> None:
        registry = FakeRegistry()
        registry.read_error = PermissionError("access denied")
        manager = StartupManager(
            executable=Path(r"C:\Apps\AgentTokenLedger.exe"),
            platform="win32",
            frozen=True,
            registry=registry,
        )

        with self.assertLogs(level="ERROR"):
            status = manager.status()

        self.assertTrue(status.supported)
        self.assertFalse(status.enabled)
        self.assertIn("读取开机启动设置失败", status.error)
        self.assertIn("PermissionError", status.error)

    def test_web_api_updates_startup_state(self) -> None:
        registry = FakeRegistry()
        manager = StartupManager(
            executable=Path(r"C:\Apps\AgentTokenLedger.exe"),
            platform="win32",
            frozen=True,
            registry=registry,
        )
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                startup_manager=manager,
            )
            server = create_server(service, port=0)
            thread = threading.Thread(
                target=server.serve_forever,
                name="startup-api-test-server",
                daemon=True,
            )
            thread.start()
            host, port = server.server_address
            base_url = f"http://{host}:{port}"
            try:
                with urllib.request.urlopen(
                    f"{base_url}/api/state",
                    timeout=2,
                ) as response:
                    initial = json.loads(response.read().decode("utf-8"))
                self.assertTrue(initial["startup_supported"])
                self.assertFalse(initial["startup_enabled"])

                request = urllib.request.Request(
                    f"{base_url}/api/startup",
                    data=b'{"enabled":true}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    updated = json.loads(response.read().decode("utf-8"))

                self.assertTrue(updated["startup_enabled"])
                self.assertTrue(updated["action_result"]["ok"])
                self.assertIn(RUN_VALUE_NAME, registry.values)
            finally:
                server.shutdown()
                server.server_close()
                service.stop()


if __name__ == "__main__":
    unittest.main()
