from __future__ import annotations

import json
import re
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.preferences import SUPPORTED_LANGUAGES, PreferenceStore
from agent_token_ledger.webapp import (
    APP_VERSION,
    DASHBOARD_HTML,
    LedgerService,
    ScanPayload,
    WEB_DIR,
    create_server,
)


class WebappTests(unittest.TestCase):
    def test_dashboard_language_select_lists_every_supported_language(self) -> None:
        match = re.search(
            r'<select[^>]*id="languageSelect"[^>]*>(.*?)</select>',
            DASHBOARD_HTML,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "界面语言下拉框必须出现在仪表盘中")
        values = set(re.findall(r'value="([^"]+)"', match.group(1)))
        self.assertEqual(values, SUPPORTED_LANGUAGES)

    def test_translation_catalog_covers_every_supported_language(self) -> None:
        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        for code in sorted(SUPPORTED_LANGUAGES):
            self.assertIn(
                f'"{code}": {{',
                app_js,
                f"翻译目录缺少 {code} 语言块",
            )

    def test_service_builds_three_scopes_and_runtime_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                refresh_seconds=30,
                scanner=lambda: _payload(),
            )
            self.assertTrue(service.scan_once())
            state = service.snapshot()

            self.assertEqual(state["status"], "ready")
            self.assertEqual(state["scan_id"], 1)
            self.assertTrue(state["validation"]["passed"])
            self.assertEqual(
                state["scopes"]["primary"]["processed_tokens"],
                1160,
            )
            self.assertEqual(
                state["scopes"]["native"]["processed_tokens"],
                1050,
            )
            self.assertEqual(
                state["scopes"]["visible"]["processed_tokens"],
                2000,
            )
            self.assertAlmostEqual(
                state["scopes"]["primary"]["cost_usd"],
                0.2,
            )
            self.assertEqual(state["scopes"]["primary"]["costed_events"], 2)
            self.assertAlmostEqual(
                state["scopes"]["visible"]["cost_usd"],
                0.45,
            )
            self.assertEqual(state["scopes"]["primary"]["events"], 2)
            self.assertEqual(len(state["source_runtime"]), 4)
            self.assertEqual(state["scopes"]["visible"]["events"], 4)
            self.assertIsInstance(state["notes"], list)
            self.assertTrue(any("日常总用量" in note for note in state["notes"]))
            self.assertEqual(state["source_summary"]["total"], 1)
            self.assertEqual(state["source_summary"]["detected"], 1)
            self.assertEqual(state["version"], APP_VERSION)

    def test_preferences_are_validated_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                scanner=lambda: _payload(),
            )

            fallback = service.update_preferences(
                {
                    "language": "xx-XX",
                    "currency": "EUR",
                    "exchange_rate": 500,
                    "refresh_seconds": 5,
                    "theme": "paper",
                }
            )
            self.assertEqual(fallback["language"], "zh-CN")
            self.assertEqual(fallback["currency"], "CNY")
            self.assertEqual(fallback["exchange_rate"], 100.0)
            self.assertEqual(fallback["refresh_seconds"], 10)
            self.assertEqual(fallback["theme"], "light")

            saved = service.update_preferences(
                {
                    "language": "en-US",
                    "currency": "USD",
                    "exchange_rate": 7.35,
                    "refresh_seconds": 60,
                    "theme": "dark",
                }
            )
            self.assertEqual(saved["language"], "en-US")
            self.assertEqual(saved["currency"], "USD")
            self.assertEqual(saved["exchange_rate"], 7.35)
            self.assertEqual(saved["refresh_seconds"], 60)
            self.assertEqual(saved["theme"], "dark")
            self.assertEqual(service.refresh_seconds, 60)
            self.assertEqual(service.snapshot()["preferences"], saved)
            self.assertTrue((Path(temp) / "settings.json").is_file())

            for code in ("zh-TW", "ja-JP", "ko-KR", "de-DE", "fr-FR", "es-ES"):
                updated = service.update_preferences({"language": code})
                self.assertEqual(updated["language"], code)
            self.assertEqual(service.snapshot()["preferences"]["language"], "es-ES")

    def test_preferences_fall_back_when_windows_replace_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = PreferenceStore(Path(temp) / "settings.json")
            replace_error = OSError("cannot move across encrypted volumes")
            replace_error.winerror = 17
            with mock.patch.object(
                Path,
                "replace",
                side_effect=replace_error,
            ):
                saved = store.save(
                    {
                        "language": "zh-CN",
                        "currency": "CNY",
                        "exchange_rate": 7.21,
                        "refresh_seconds": 30,
                        "theme": "light",
                    }
                )

            self.assertEqual(saved["exchange_rate"], 7.21)
            self.assertTrue(store.path.is_file())
            self.assertEqual(store.load()["exchange_rate"], 7.21)
            self.assertFalse(store.path.with_suffix(".json.tmp").exists())

    def test_pause_and_refresh_state_are_exposed_by_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            calls = {"count": 0}

            def scanner() -> ScanPayload:
                calls["count"] += 1
                return _payload()

            service = LedgerService(
                work_dir=Path(temp),
                scanner=scanner,
            )
            self.assertTrue(service.set_paused(True))
            self.assertTrue(service.snapshot()["paused"])
            self.assertTrue(service.request_refresh())
            self.assertTrue(service.scan_once())
            self.assertEqual(calls["count"], 1)
            self.assertFalse(service.set_paused(False))
            self.assertFalse(service.snapshot()["paused"])

    def test_pause_overrides_scanning_status_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            started = threading.Event()
            release = threading.Event()

            def scanner() -> ScanPayload:
                started.set()
                release.wait(2)
                return _payload()

            service = LedgerService(
                work_dir=Path(temp),
                scanner=scanner,
            )
            worker = threading.Thread(
                target=service.scan_once,
                name="webapp-pause-test",
                daemon=True,
            )
            worker.start()
            self.assertTrue(started.wait(1))

            self.assertTrue(service.set_paused(True))
            paused_state = service.snapshot()
            self.assertTrue(paused_state["paused"])
            self.assertEqual(paused_state["status"], "paused")

            release.set()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(service.snapshot()["status"], "paused")

            service.set_paused(False)
            self.assertEqual(service.snapshot()["status"], "ready")

    def test_http_api_assets_and_dashboard_have_no_external_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                scanner=lambda: _payload(),
            )
            service.scan_once()
            server = create_server(service, port=0)
            thread = threading.Thread(
                target=server.serve_forever,
                name="webapp-test-server",
                daemon=True,
            )
            thread.start()
            host, port = server.server_address
            base_url = f"http://{host}:{port}"
            try:
                with urllib.request.urlopen(
                    f"{base_url}/api/state", timeout=2
                ) as response:
                    state = json.loads(response.read().decode("utf-8"))
                self.assertEqual(state["app"], "agent-token-ledger")
                self.assertEqual(state["scopes"]["primary"]["processed_tokens"], 1160)

                with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
                    html = response.read().decode("utf-8")
                self.assertIn("智能体用量账本", html)
                self.assertIn('id="chartTypeTabs"', html)
                self.assertIn('id="chartMetricTabs"', html)
                self.assertNotIn('id="heatmapRangeTabs"', html)
                self.assertIn('id="settingsStopButton"', html)
                self.assertIn('id="startupToggle"', html)
                self.assertIn('data-page="overview"', html)
                self.assertIn('data-page="usage"', html)
                self.assertIn('data-page="sources"', html)
                self.assertIn('data-page="quality"', html)
                self.assertIn('data-page="settings"', html)
                self.assertIn("/assets/app.js", html)
                self.assertIn("/assets/styles.css", html)
                self.assertNotIn("https://", html)
                self.assertNotIn('src="http://', html)
                self.assertNotIn("src='http://", html)
                self.assertNotIn('href="http://', html)
                self.assertNotIn("href='http://", html)

                with urllib.request.urlopen(
                    f"{base_url}/assets/app.js", timeout=2
                ) as response:
                    app_js = response.read().decode("utf-8")
                self.assertIn("window.AgentTokenLedgerTranslations", app_js)
                self.assertIn('"range.30"', app_js)
                self.assertIn('"settings.startupTitle"', app_js)
                self.assertNotIn("https://", app_js)

                with urllib.request.urlopen(
                    f"{base_url}/assets/runtime.js", timeout=2
                ) as response:
                    runtime_js = response.read().decode("utf-8")
                self.assertIn("renderChartPanel", runtime_js)
                self.assertIn("chartTypeOptions", runtime_js)
                self.assertIn(
                    'on("settingsStopButton", "click", stopService)',
                    runtime_js,
                )
                self.assertIn(
                    'on("startupToggle", "change", toggleStartup)',
                    runtime_js,
                )
                self.assertIn('post("/api/stop")', runtime_js)
                self.assertNotIn("其他模型", runtime_js)
                self.assertNotIn("https://", runtime_js)

                with urllib.request.urlopen(
                    f"{base_url}/assets/styles.css", timeout=2
                ) as response:
                    styles = response.read().decode("utf-8")
                self.assertIn(".app-shell", styles)
                self.assertIn(".heatmap-cell.level-4", styles)
                self.assertNotIn("https://", styles)

                with urllib.request.urlopen(
                    f"{base_url}/api/state", timeout=2
                ) as response:
                    live_state = json.loads(response.read().decode("utf-8"))
                self.assertEqual(live_state["version"], APP_VERSION)
                self.assertEqual(live_state["source_summary"]["detected"], 1)

                with urllib.request.urlopen(
                    f"{base_url}/api/preferences", timeout=2
                ) as response:
                    preferences = json.loads(response.read().decode("utf-8"))
                self.assertEqual(preferences["language"], "zh-CN")
                self.assertEqual(preferences["currency"], "CNY")

                with urllib.request.urlopen(
                    f"{base_url}/api/report?range=7d", timeout=2
                ) as response:
                    seven_day_report = json.loads(
                        response.read().decode("utf-8")
                    )
                self.assertEqual(seven_day_report["range"], "7d")
                self.assertEqual(seven_day_report["overall"]["events"], 2)
                self.assertEqual(
                    seven_day_report["overall"]["processed_tokens"],
                    1160,
                )
                self.assertIn("cost_total_usd", seven_day_report["overall"])
                self.assertIn("agent", seven_day_report["reports"])
                self.assertIn("model", seven_day_report["reports"])

                with urllib.request.urlopen(
                    f"{base_url}/api/report?range=30d", timeout=2
                ) as response:
                    thirty_day_report = json.loads(
                        response.read().decode("utf-8")
                    )
                self.assertEqual(thirty_day_report["range"], "30d")
                self.assertEqual(thirty_day_report["overall"]["events"], 2)

                today = time.strftime("%Y-%m-%d", time.localtime())
                with urllib.request.urlopen(
                    (
                        f"{base_url}/api/report?range=custom"
                        f"&start={today}&end={today}"
                    ),
                    timeout=2,
                ) as response:
                    custom_report = json.loads(
                        response.read().decode("utf-8")
                    )
                self.assertEqual(custom_report["range"], "custom")
                self.assertEqual(custom_report["overall"]["events"], 2)

                preference_request = urllib.request.Request(
                    f"{base_url}/api/preferences",
                    data=json.dumps(
                        {
                            "language": "en-US",
                            "currency": "USD",
                            "exchange_rate": 7.31,
                            "refresh_seconds": 60,
                            "theme": "dark",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    preference_request, timeout=2
                ) as response:
                    saved_state = json.loads(response.read().decode("utf-8"))
                self.assertEqual(saved_state["preferences"]["language"], "en-US")
                self.assertEqual(saved_state["preferences"]["currency"], "USD")
                self.assertEqual(saved_state["preferences"]["exchange_rate"], 7.31)
                self.assertEqual(saved_state["preferences"]["refresh_seconds"], 60)
                self.assertEqual(saved_state["preferences"]["theme"], "dark")

                price_request = urllib.request.Request(
                    f"{base_url}/api/preferences",
                    data=json.dumps(
                        {
                            "model_prices": {
                                "gpt-5": {
                                    "input": 9.99,
                                    "cached_input": 0.99,
                                    "output": 19.99,
                                }
                            }
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    price_request, timeout=2
                ) as response:
                    priced_state = json.loads(
                        response.read().decode("utf-8")
                    )
                self.assertEqual(
                    priced_state["preferences"]["model_prices"]["gpt-5"][
                        "input"
                    ],
                    9.99,
                )

                reset_prices_request = urllib.request.Request(
                    f"{base_url}/api/preferences/prices/reset",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    reset_prices_request, timeout=2
                ) as response:
                    reset_state = json.loads(
                        response.read().decode("utf-8")
                    )
                self.assertEqual(
                    reset_state["preferences"]["model_prices"]["gpt-5"][
                        "input"
                    ],
                    1.25,
                )
                self.assertTrue(reset_state["action_result"]["ok"])

                request = urllib.request.Request(
                    f"{base_url}/api/pause",
                    data=b'{"paused":true}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    paused_state = json.loads(response.read().decode("utf-8"))
                self.assertTrue(paused_state["paused"])
            finally:
                server.shutdown()
                server.server_close()
                service.stop()

        self.assertIn("<!doctype html>", DASHBOARD_HTML.lower())


def _payload() -> ScanPayload:
    base_ms = int(time.time() * 1000)
    events = [
        UsageEvent(
            event_key="native-1",
            source="codex_native",
            agent="Codex",
            source_kind=SourceKind.NATIVE,
            timestamp_ms=base_ms - 4_000,
            input_tokens=1000,
            cached_input_tokens=600,
            output_tokens=50,
            provider_total_tokens=1050,
            session_id="native-session",
            input_includes_cached=True,
            input_includes_cache_write=True,
            cost_usd=0.12,
        ),
        UsageEvent(
            event_key="derived-1",
            source="cockpit_session",
            agent="Codex",
            source_kind=SourceKind.DERIVED,
            timestamp_ms=base_ms - 3_000,
            input_tokens=800,
            cached_input_tokens=200,
            output_tokens=10,
            provider_total_tokens=810,
            session_id="derived-session",
            input_includes_cached=True,
            input_includes_cache_write=True,
            cost_usd=0.20,
        ),
        UsageEvent(
            event_key="aggregate-1",
            source="dsh",
            agent="DeepSeek Harness",
            source_kind=SourceKind.AGGREGATE,
            timestamp_ms=base_ms - 2_000,
            input_tokens=100,
            output_tokens=10,
            provider_total_tokens=110,
            session_id="dsh-session",
            input_includes_cached=True,
            input_includes_cache_write=True,
            cost_usd=0.08,
        ),
        UsageEvent(
            event_key="gateway-1",
            source="cockpit_gateway",
            agent="Cockpit Gateway",
            source_kind=SourceKind.GATEWAY,
            timestamp_ms=base_ms - 1_000,
            input_tokens=25,
            output_tokens=5,
            provider_total_tokens=30,
            session_id="gateway-session",
            input_includes_cached=True,
            input_includes_cache_write=True,
            cost_usd=0.05,
        ),
    ]
    return ScanPayload(
        events=events,
        issues=[
            {
                "source": "inventory",
                "severity": "info",
                "code": "source_unavailable",
                "message": "测试来源不可用说明",
                "raw_ref": "",
                "metadata": {},
            }
        ],
        sources=[
            {
                "agent": "Codex",
                "kind": "native",
                "status": "detected",
                "paths": ["C:/example/.codex/sessions"],
                "existing_paths": ["C:/example/.codex/sessions"],
                "exists": True,
                "note": "测试 JSONL 来源",
                "metadata": {},
            }
        ],
        snapshots=[],
        work_dir="test",
        source_summary={
            "total": 1,
            "supported": 1,
            "detected": 1,
            "missing": 0,
            "unsupported": 0,
            "error": 0,
        },
    )


if __name__ == "__main__":
    unittest.main()
