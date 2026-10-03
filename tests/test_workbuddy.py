from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_token_ledger.sources.base import ScanContext
from agent_token_ledger.sources.workbuddy import WorkBuddyAiAdapter


class WorkBuddyTests(unittest.TestCase):
    def test_ai_cache_write_is_split_without_changing_processed_total(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "projects"
            root.mkdir()
            records = [
                {
                    "type": "assistant",
                    "id": "event-1",
                    "sessionId": "session-1",
                    "timestamp": "2026-10-02T00:00:00Z",
                    "message": {
                        "model": "deepseek-chat",
                        "usage": {
                            "input_tokens": 29951,
                            "output_tokens": 87,
                            "total_tokens": 30038,
                        },
                    },
                    "providerData": {
                        "usage": {"totalTokens": 30038},
                        "rawUsage": {
                            "prompt_cache_write_tokens": 29949,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                            "cache_write_input_tokens": 0,
                        },
                    },
                },
                {
                    "type": "assistant",
                    "id": "event-2",
                    "sessionId": "session-1",
                    "timestamp": "2026-10-02T00:00:01Z",
                    "message": {
                        "model": "deepseek-chat",
                        "usage": {
                            "input_tokens": 30566,
                            "cache_read_input_tokens": 29949,
                            "output_tokens": 37,
                            "total_tokens": 30603,
                        },
                    },
                    "providerData": {
                        "usage": {"totalTokens": 30603},
                        "rawUsage": {"prompt_cache_write_tokens": 615},
                    },
                },
            ]
            path = root / "session.jsonl"
            path.write_text(
                "\n".join(json.dumps(row) for row in records) + "\n",
                encoding="utf-8",
            )
            context = ScanContext(
                home=Path(temp),
                appdata=Path(temp) / "Roaming",
                local_appdata=Path(temp) / "Local",
                work_dir=Path(temp) / "work",
            )

            result = WorkBuddyAiAdapter(root=root).scan(context)

            self.assertEqual(len(result.events), 2)
            first, second = result.events
            self.assertEqual(first.cache_write_tokens, 29949)
            self.assertEqual(first.non_cached_input_tokens, 2)
            self.assertEqual(first.processed_tokens, 30038)
            self.assertEqual(second.cached_input_tokens, 29949)
            self.assertEqual(second.cache_write_tokens, 615)
            self.assertEqual(second.non_cached_input_tokens, 2)
            self.assertEqual(second.processed_tokens, 30603)
            self.assertEqual(first.metadata["cache_write_source"], "providerData.rawUsage")


if __name__ == "__main__":
    unittest.main()
