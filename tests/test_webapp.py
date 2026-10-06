from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from unittest import mock

from agent_token_ledger.model import SourceKind, UsageEvent
from agent_token_ledger.preferences import SUPPORTED_LANGUAGES, PreferenceStore
from agent_token_ledger.webapp import (
    APP_VERSION,
    DASHBOARD_HTML,
    LedgerService,
    PENDING_CLEAR_MARKER,
    ScanPayload,
    WEB_DIR,
    _portable_event_dict,
    clear_pending_cache,
    codex_coverage_gaps,
    codex_session_days,
    create_server,
    load_model_aliases,
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

    def test_clear_app_cache_removes_browser_and_logs_keeps_parse_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "webview").mkdir()
            (base / "edge-app-profile").mkdir()
            (base / "agent-token-ledger.log").write_text("old log", encoding="utf-8")
            (base / "agent-token-ledger.log.1").write_text(
                "old rotated", encoding="utf-8"
            )
            (base / "codex_native_cache_v1.json").write_text("{}", encoding="utf-8")
            (base / "settings.json").write_text("{}", encoding="utf-8")

            service = LedgerService(
                work_dir=base,
                refresh_seconds=30,
                scanner=lambda: _payload(),
            )
            result = service.clear_app_cache()

            self.assertIn("webview", result["removed"])
            self.assertIn("edge-app-profile", result["removed"])
            self.assertIn("agent-token-ledger.log", result["removed"])
            self.assertIn("agent-token-ledger.log.1", result["removed"])
            self.assertTrue(result["kept_parse_cache"])
            self.assertFalse((base / "webview").exists())
            self.assertFalse((base / "edge-app-profile").exists())
            self.assertTrue((base / "agent-token-ledger.log").exists())
            self.assertEqual(
                (base / "agent-token-ledger.log").read_text(encoding="utf-8"),
                "",
            )
            self.assertFalse((base / "agent-token-ledger.log.1").exists())
            self.assertTrue((base / "codex_native_cache_v1.json").exists())
            self.assertTrue((base / "settings.json").exists())

    def test_clear_app_cache_defers_locked_browser_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "webview").mkdir()
            (base / "edge-app-profile").mkdir()
            (base / "agent-token-ledger.log").write_text(
                "old log", encoding="utf-8"
            )

            real_rmtree = shutil.rmtree

            def locked_rmtree(path, *args, **kwargs):
                if Path(path).name == "webview":
                    raise PermissionError(
                        13,
                        "另一个程序正在使用此文件，进程无法访问。",
                        str(path),
                        32,
                    )
                return real_rmtree(path, *args, **kwargs)

            service = LedgerService(
                work_dir=base,
                refresh_seconds=30,
                scanner=lambda: _payload(),
            )
            with mock.patch(
                "agent_token_ledger.webapp.shutil.rmtree",
                side_effect=locked_rmtree,
            ):
                result = service.clear_app_cache()

            self.assertTrue(result["ok"])
            self.assertEqual(result["deferred"], ["webview"])
            self.assertEqual(result["deferred_count"], 1)
            self.assertIn("edge-app-profile", result["removed"])
            self.assertIn("agent-token-ledger.log", result["removed"])
            self.assertTrue((base / "webview").exists())
            self.assertFalse((base / "edge-app-profile").exists())
            self.assertTrue((base / PENDING_CLEAR_MARKER).is_file())

            cleared = clear_pending_cache(base)
            self.assertEqual(cleared, ["webview"])
            self.assertFalse((base / "webview").exists())
            self.assertFalse((base / PENDING_CLEAR_MARKER).exists())

    def test_clear_app_cache_skips_active_window_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "webview").mkdir()
            (base / "webview" / "lock.log").write_text("in use", encoding="utf-8")
            (base / "edge-app-profile").mkdir()
            (base / "agent-token-ledger.log").write_text(
                "old log", encoding="utf-8"
            )

            real_rmtree = shutil.rmtree

            def guarded_rmtree(path, *args, **kwargs):
                if Path(path).name == "webview":
                    raise AssertionError("运行中的窗口 profile 不应被删除")
                return real_rmtree(path, *args, **kwargs)

            service = LedgerService(
                work_dir=base,
                refresh_seconds=30,
                scanner=lambda: _payload(),
            )
            service.set_window_mode("webview")
            with mock.patch(
                "agent_token_ledger.webapp.shutil.rmtree",
                side_effect=guarded_rmtree,
            ):
                result = service.clear_app_cache()

            self.assertTrue(result["ok"])
            self.assertEqual(result["deferred"], ["webview"])
            self.assertEqual(result["deferred_count"], 1)
            self.assertIn("edge-app-profile", result["removed"])
            self.assertIn("agent-token-ledger.log", result["removed"])
            self.assertTrue((base / "webview" / "lock.log").exists())
            self.assertFalse((base / "edge-app-profile").exists())
            self.assertTrue((base / PENDING_CLEAR_MARKER).is_file())

            self.assertEqual(clear_pending_cache(base), ["webview"])
            self.assertFalse((base / "webview").exists())
            self.assertFalse((base / PENDING_CLEAR_MARKER).exists())

    def test_clear_pending_cache_keeps_marker_when_still_locked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "webview").mkdir()
            (base / PENDING_CLEAR_MARKER).write_text(
                json.dumps({"names": ["webview"], "created_at_ms": 0}),
                encoding="utf-8",
            )

            def locked_rmtree(path, *args, **kwargs):
                raise PermissionError(
                    13,
                    "另一个程序正在使用此文件，进程无法访问。",
                    str(path),
                    32,
                )

            with mock.patch(
                "agent_token_ledger.webapp.shutil.rmtree",
                side_effect=locked_rmtree,
            ):
                self.assertEqual(clear_pending_cache(base), [])

            self.assertTrue((base / "webview").exists())
            self.assertTrue((base / PENDING_CLEAR_MARKER).is_file())

            self.assertEqual(clear_pending_cache(base), ["webview"])
            self.assertFalse((base / "webview").exists())
            self.assertFalse((base / PENDING_CLEAR_MARKER).exists())

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

    def test_backup_export_and_import_merge_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                scanner=lambda: _payload(),
            )
            self.assertTrue(service.scan_once())
            backup = json.loads(service.export_backup().decode("utf-8"))

            self.assertEqual(backup["format"], "agent-token-ledger-backup")
            self.assertEqual(backup["schema_version"], 1)
            self.assertEqual(backup["app_version"], APP_VERSION)
            self.assertEqual(len(backup["events"]), 4)
            self.assertEqual(backup["preferences"]["language"], "zh-CN")

            other = LedgerService(
                work_dir=Path(temp) / "other",
                scanner=lambda: _payload(),
            )
            first = other.import_backup(backup)
            self.assertEqual(first["imported_events"], 4)
            self.assertEqual(first["skipped_duplicates"], 0)
            self.assertEqual(
                other.snapshot()["scopes"]["primary"]["processed_tokens"],
                1160,
            )

            second = other.import_backup(backup)
            self.assertEqual(second["imported_events"], 0)
            self.assertEqual(second["skipped_duplicates"], 4)

    def test_backup_redacts_machine_specific_paths(self) -> None:
        event = UsageEvent(
            event_key="path-event",
            source="codex_native",
            agent="Codex",
            source_kind=SourceKind.NATIVE,
            timestamp_ms=1,
            raw_ref="C:\\Users\\alice\\.codex\\sessions\\s.jsonl:12",
            metadata={
                "source_file": "C:\\Users\\alice\\.codex\\sessions\\s.jsonl",
                "source_root": "C:\\Users\\alice\\.codex",
                "format": "new",
                "line_number": 12,
            },
        )
        portable = _portable_event_dict(event)

        self.assertNotIn("Users", portable["raw_ref"])
        self.assertNotIn("processed_tokens", portable)
        self.assertNotIn("input_tokens_total", portable)
        self.assertNotIn("cache_semantics_verified", portable)
        self.assertNotIn("source_file", portable["metadata"])
        self.assertNotIn("source_root", portable["metadata"])
        self.assertEqual(portable["metadata"]["format"], "new")
        self.assertEqual(portable["metadata"]["line_number"], 12)

    def test_backup_http_export_and_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                scanner=lambda: _payload(),
            )
            service.scan_once()
            server = create_server(service, port=0)
            thread = threading.Thread(
                target=server.serve_forever,
                name="webapp-backup-test-server",
                daemon=True,
            )
            thread.start()
            host, port = server.server_address
            base_url = f"http://{host}:{port}"
            try:
                with urllib.request.urlopen(
                    f"{base_url}/api/backup/export", timeout=2
                ) as response:
                    content_type = response.headers["Content-Type"]
                    disposition = response.headers["Content-Disposition"]
                    backup = json.loads(response.read().decode("utf-8"))
                self.assertEqual(content_type, "application/json; charset=utf-8")
                self.assertIn("attachment", disposition)
                self.assertEqual(backup["format"], "agent-token-ledger-backup")
                self.assertEqual(len(backup["events"]), 4)

                import_request = urllib.request.Request(
                    f"{base_url}/api/backup/import",
                    data=json.dumps(backup).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(
                    import_request, timeout=2
                ) as response:
                    imported_state = json.loads(
                        response.read().decode("utf-8")
                    )
                result = imported_state["action_result"]
                self.assertTrue(result["ok"])
                self.assertEqual(result["imported_events"], 0)
                self.assertEqual(result["skipped_duplicates"], 4)

                bad_request = urllib.request.Request(
                    f"{base_url}/api/backup/import",
                    data=json.dumps({"format": "wrong"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(bad_request, timeout=2)
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                service.stop()

    def test_codex_coverage_gaps_marks_dates_without_session_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sessions = home / ".codex" / "sessions"
            archived = home / ".codex" / "archived_sessions"
            sessions.mkdir(parents=True)
            archived.mkdir(parents=True)
            (sessions / "2026-09-30.jsonl").write_text("{}", encoding="utf-8")
            (archived / "2026-10-01-session.jsonl").write_text("{}", encoding="utf-8")

            days = codex_session_days(home)
            self.assertIn("2026-09-30", days)
            self.assertIn("2026-10-01", days)

            gaps = codex_coverage_gaps(home, days=7, today=date(2026, 10, 6))
            gap_dates = {item["date"] for item in gaps}
            self.assertIn("2026-10-02", gap_dates)
            self.assertNotIn("2026-10-06", gap_dates)
            self.assertEqual(
                gaps[0]["reason"],
                "本机未发现该日期的 Codex 原生日志，无法逐请求回算",
            )

    def test_codex_coverage_gaps_uses_mtime_fallback_for_unnamed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sessions = home / ".codex" / "sessions"
            sessions.mkdir(parents=True)
            path = sessions / "session.jsonl"
            path.write_text("{}", encoding="utf-8")
            expected = date.fromtimestamp(path.stat().st_mtime).isoformat()
            self.assertIn(expected, codex_session_days(home))

    def test_load_model_aliases_maps_internal_slugs_to_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".codex").mkdir(parents=True)
            catalog = home / ".codex" / "cockpit-model-catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "models": [
                            {"slug": "gpt-5.6-sol", "display_name": "cn:deepseek-v4-pro"},
                            {"slug": "cn:deepseek-v4-pro", "display_name": "cn:deepseek-v4-pro"},
                            {"slug": "codex-auto-review", "display_name": "Codex Auto Review"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            aliases = load_model_aliases(home)
            self.assertEqual(aliases["gpt-5.6-sol"], "cn:deepseek-v4-pro")
            self.assertNotIn("cn:deepseek-v4-pro", aliases)
            self.assertEqual(aliases["codex-auto-review"], "Codex Auto Review")

    def test_state_exposes_coverage_gaps_and_model_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = LedgerService(
                work_dir=Path(temp),
                refresh_seconds=30,
                scanner=lambda: _payload(),
            )
            self.assertTrue(service.scan_once())
            state = service.snapshot()
            self.assertIn("coverage_gaps", state)
            self.assertIn("model_aliases", state)
            self.assertEqual(state["coverage_gaps"], [])
            self.assertEqual(state["model_aliases"], {})


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
