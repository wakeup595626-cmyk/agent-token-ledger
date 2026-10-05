from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_token_ledger.sources import codex_native
from agent_token_ledger.sources.base import ScanContext
from agent_token_ledger.sources.codex_native import CodexNativeAdapter


class CodexNativeTests(unittest.TestCase):
    def _context(self, root: Path) -> ScanContext:
        return ScanContext(
            home=root,
            appdata=root / "Roaming",
            local_appdata=root / "Local",
            work_dir=root / "work",
        )

    def _write(self, root: Path, name: str, rows: list[dict]) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_new_format_counts_once_and_ignores_legacy_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write(
                root,
                "sessions/2026/10/02/rollout-test-11111111-1111-1111-1111-111111111111.jsonl",
                [
                    {
                        "timestamp": "2026-10-02T00:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "session-new"},
                    },
                    {
                        "timestamp": "2026-10-02T00:00:01Z",
                        "type": "turn_context",
                        "payload": {"turn_id": "turn-1", "model": "gpt-5"},
                    },
                    {
                        "timestamp": "2026-10-02T00:00:02Z",
                        "type": "token_usage_record",
                        "payload": {
                            "session_id": "session-new",
                            "turn_id": "turn-1",
                            "response_id": "response-1",
                            "usage": {
                                "input_tokens": 1000,
                                "cached_input_tokens": 700,
                                "cache_write_input_tokens": 100,
                                "output_tokens": 50,
                                "reasoning_output_tokens": 30,
                                "total_tokens": 1050,
                            },
                        },
                    },
                    {
                        "timestamp": "2026-10-02T00:00:03Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 700,
                                    "output_tokens": 50,
                                    "total_tokens": 1050,
                                }
                            },
                        },
                    },
                ],
            )

            result = CodexNativeAdapter(roots=[root / "sessions"]).scan(
                self._context(root)
            )

            self.assertEqual(len(result.events), 1)
            event = result.events[0]
            self.assertEqual(event.input_tokens, 1000)
            self.assertEqual(event.cached_input_tokens, 700)
            self.assertEqual(event.cache_write_tokens, 100)
            self.assertEqual(event.non_cached_input_tokens, 200)
            self.assertEqual(event.processed_tokens, 1050)
            self.assertEqual(event.model, "gpt-5")
            self.assertTrue(
                event.metadata["provider_total_equals_input_plus_output"]
            )

    def test_legacy_format_uses_last_usage_and_deduplicates_repeats(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write(
                root,
                "sessions/2026/10/02/test-22222222-2222-2222-2222-222222222222.jsonl",
                [
                    {
                        "timestamp": "2026-10-02T00:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 80,
                                    "output_tokens": 20,
                                    "total_tokens": 120,
                                },
                                "total_token_usage": {
                                    "input_tokens": 999999,
                                    "output_tokens": 999999,
                                    "total_tokens": 1999998,
                                },
                            },
                        },
                    },
                    {
                        "timestamp": "2026-10-02T00:00:01Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 100,
                                    "cached_input_tokens": 80,
                                    "output_tokens": 20,
                                    "total_tokens": 120,
                                }
                            },
                        },
                    },
                    {
                        "timestamp": "2026-10-02T00:00:02Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 200,
                                    "cached_input_tokens": 100,
                                    "output_tokens": 50,
                                    "reasoning_output_tokens": 30,
                                    "total_tokens": 280,
                                }
                            },
                        },
                    },
                ],
            )

            result = CodexNativeAdapter(roots=[root / "sessions"]).scan(
                self._context(root)
            )

            self.assertEqual(len(result.events), 2)
            self.assertEqual(
                sum(event.processed_tokens for event in result.events), 370
            )
            second = result.events[1]
            self.assertEqual(second.provider_total_tokens, 280)
            self.assertEqual(second.processed_tokens, 250)
            self.assertTrue(
                second.metadata[
                    "provider_total_equals_input_output_reasoning"
                ]
            )
            self.assertEqual(second.metadata["provider_total_delta"], 30)

    def test_scan_reuses_cache_for_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write(
                root,
                "sessions/2026/10/02/rollout-33333333-3333-3333-3333-333333333333.jsonl",
                [
                    {
                        "timestamp": "2026-10-02T00:00:00Z",
                        "type": "token_usage_record",
                        "payload": {
                            "session_id": "session-cache",
                            "turn_id": "turn-1",
                            "response_id": "response-1",
                            "usage": {
                                "input_tokens": 500,
                                "cached_input_tokens": 200,
                                "output_tokens": 80,
                                "total_tokens": 580,
                            },
                        },
                    },
                ],
            )
            adapter = CodexNativeAdapter(roots=[root / "sessions"])
            context = self._context(root)

            first = adapter.scan(context)
            self.assertEqual(len(first.events), 1)
            self.assertTrue(
                (context.work_dir / "codex_native_cache_v1.json").is_file()
            )

            parse_calls: list[Path] = []
            real_parse = codex_native._parse_file

            def counting_parse(*args, **kwargs):
                parse_calls.append(args[0])
                return real_parse(*args, **kwargs)

            with mock.patch.object(
                codex_native, "_parse_file", side_effect=counting_parse
            ):
                second = adapter.scan(context)

            self.assertEqual(len(second.events), 1)
            self.assertEqual(parse_calls, [])
            self.assertEqual(
                second.events[0].to_dict()["input_tokens"],
                first.events[0].to_dict()["input_tokens"],
            )

    def test_save_cache_falls_back_when_replace_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write(
                root,
                "sessions/2026/10/02/rollout-44444444-4444-4444-4444-444444444444.jsonl",
                [
                    {
                        "timestamp": "2026-10-02T00:00:00Z",
                        "type": "token_usage_record",
                        "payload": {
                            "session_id": "session-efs",
                            "turn_id": "turn-1",
                            "response_id": "response-1",
                            "usage": {
                                "input_tokens": 10,
                                "cached_input_tokens": 0,
                                "output_tokens": 5,
                                "total_tokens": 15,
                            },
                        },
                    },
                ],
            )
            adapter = CodexNativeAdapter(roots=[root / "sessions"])
            context = self._context(root)

            replace_error = OSError("cannot move across encrypted volumes")
            replace_error.winerror = 17
            with mock.patch.object(
                Path, "replace", side_effect=replace_error
            ):
                result = adapter.scan(context)

            self.assertEqual(len(result.events), 1)
            cache_path = context.work_dir / "codex_native_cache_v1.json"
            self.assertTrue(cache_path.is_file())
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(len(cached["files"]), 1)



if __name__ == "__main__":
    unittest.main()
