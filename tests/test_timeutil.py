from __future__ import annotations

import unittest
from datetime import datetime, timezone

from agent_token_ledger.timeutil import day_from_ms, iso_from_ms


class TimeUtilTests(unittest.TestCase):
    def test_day_boundary_uses_shanghai_time(self) -> None:
        timestamp_ms = int(
            datetime(2026, 10, 2, 16, 30, tzinfo=timezone.utc).timestamp()
            * 1000
        )

        self.assertEqual(day_from_ms(timestamp_ms), "2026-10-03")
        self.assertEqual(iso_from_ms(timestamp_ms), "2026-10-03T00:30:00+08:00")


if __name__ == "__main__":
    unittest.main()
