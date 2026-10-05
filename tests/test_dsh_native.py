from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_token_ledger.sources.base import ScanContext
from agent_token_ledger.sources.dsh import (
    DshAdapter,
    _parse_session_file,
    _pick_session_file,
)


def _line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False) + "\n"


def _header(provider: str = "deepseek-official", model: str = "deepseek-chat") -> dict:
    return {
        "seq": 0,
        "type": "request/header",
        "data": {"header": {"config": {"provider": provider, "model": model}}},
    }


def _message(
    turn: int,
    step: int,
    seq: int,
    input_tokens: int,
    output_tokens: int = 20,
    cache_read: int = 0,
    cache_write: int = 0,
    total_tokens: int | None = None,
) -> dict:
    total = (
        input_tokens + output_tokens + cache_read + cache_write
        if total_tokens is None
        else total_tokens
    )
    return {
        "seq": seq,
        "type": "assistant/message",
        "data": {
            "turn": turn,
            "step": step,
            "usage": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "cacheReadTokens": cache_read,
                "cacheWriteTokens": cache_write,
                "totalTokens": total,
            },
        },
    }


def _chunk(
    turn: int,
    step: int,
    seq: int,
    input_tokens: int,
    output_tokens: int = 1,
    total_tokens: int | None = None,
) -> dict:
    total = input_tokens + output_tokens if total_tokens is None else total_tokens
    return {
        "seq": seq,
        "type": "assistant/chunk",
        "data": {
            "turn": turn,
            "step": step,
            "chunk": {
                "type": "usage",
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "cacheReadTokens": 0,
                    "cacheWriteTokens": 0,
                    "totalTokens": total,
                },
            },
        },
    }


def _parse(path: Path):
    return _parse_session_file(path, "session-1", None, "dsh", "DeepSeek Harness")


class DshNativeTests(unittest.TestCase):
    def test_chunk_then_message_same_turn_step_replaces_not_sums(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "session.jsonl"
            path.write_text(
                "".join(
                    [
                        _line(_header()),
                        _line(_chunk(0, 0, 1, 10, 1)),
                        _line(_message(0, 0, 2, 100, 20, cache_read=300)),
                    ]
                ),
                encoding="utf-8",
            )
            parsed = _parse(path)
            self.assertEqual(parsed.errors, 0)
            self.assertEqual(len(parsed.events), 1)
            event = parsed.events[0]
            self.assertEqual(event.input_tokens, 100)
            self.assertEqual(event.output_tokens, 20)
            self.assertEqual(event.cached_input_tokens, 300)
            self.assertEqual(event.model, "deepseek-official/deepseek-chat")
            self.assertIn(":0:0:1", event.event_key)

    def test_retry_starts_new_call_index_for_same_turn_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "session.jsonl"
            path.write_text(
                "".join(
                    [
                        _line(_header()),
                        _line(_message(1, 2, 1, 100)),
                        _line({"seq": 2, "type": "llm/retry-started", "data": {"turn": 1, "step": 2}}),
                        _line(_message(1, 2, 3, 200)),
                    ]
                ),
                encoding="utf-8",
            )
            parsed = _parse(path)
            self.assertEqual(len(parsed.events), 2)
            first, second = parsed.events
            self.assertEqual(first.input_tokens, 100)
            self.assertEqual(second.input_tokens, 200)
            self.assertIn(":1:2:1", first.event_key)
            self.assertIn(":1:2:2", second.event_key)
            self.assertEqual(parsed.calls, 2)

    def test_duplicate_seq_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "session.jsonl"
            path.write_text(
                "".join(
                    [
                        _line(_header()),
                        _line(_message(0, 0, 1, 100)),
                        _line(_message(0, 0, 1, 999)),
                    ]
                ),
                encoding="utf-8",
            )
            parsed = _parse(path)
            self.assertEqual(len(parsed.events), 1)
            self.assertEqual(parsed.events[0].input_tokens, 100)

    def test_pick_session_file_prefers_v3_then_v2_then_plain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            v3 = root / "session.v3.jsonl.zstd"
            v2 = root / "session.jsonl.zstd"
            plain = root / "session.jsonl"
            plain.touch()
            v2.touch()
            v3.touch()
            self.assertEqual(_pick_session_file(root), v3)
            v3.unlink()
            self.assertEqual(_pick_session_file(root), v2)
            v2.unlink()
            self.assertEqual(_pick_session_file(root), plain)

    def test_friend_scenario_sessions_dir_is_scanned_without_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sessions = root / "sessions" / "session-a"
            sessions.mkdir(parents=True)
            (sessions / "session.jsonl").write_text(
                "".join(
                    [
                        _line(_header(provider="aliyun", model="deepseek-v4-pro")),
                        _line(_message(0, 0, 1, 100, 20, cache_read=300)),
                    ]
                ),
                encoding="utf-8",
            )
            context = ScanContext(
                home=root,
                appdata=root / "Roaming",
                local_appdata=root / "Local",
                work_dir=root / "work",
                dsh_home=root,
            )
            result = DshAdapter().scan(context)
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].source_kind, "native")
            self.assertEqual(result.events[0].model, "aliyun/deepseek-v4-pro")

    def test_empty_dsh_home_falls_back_to_missing_ledger_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = ScanContext(
                home=root,
                appdata=root / "Roaming",
                local_appdata=root / "Local",
                work_dir=root / "work",
                dsh_home=root,
            )
            result = DshAdapter().scan(context)
            self.assertEqual(len(result.events), 0)
            self.assertTrue(
                any(issue.code == "ledger_missing" for issue in result.issues)
            )


class DshLocationTests(unittest.TestCase):
    def test_dsh_home_env_overrides_user_home(self) -> None:
        from agent_token_ledger.pipeline import _resolve_dsh_locations

        with tempfile.TemporaryDirectory() as temp:
            dsh_home = Path(temp) / "custom-dsh"
            with mock.patch.dict(os.environ, {"DSH_HOME": str(dsh_home)}):
                primary, _ = _resolve_dsh_locations(Path(temp))
            self.assertEqual(primary, dsh_home)


if __name__ == "__main__":
    unittest.main()