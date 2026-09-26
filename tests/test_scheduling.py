from __future__ import annotations

from datetime import datetime, timezone
import unittest

from queuer.repositories._shared import isoformat_utc
from queuer.scheduling import is_daily_schedule_due, parse_schedule_override, parse_utc_timestamp


class SchedulingTests(unittest.TestCase):
    def test_parse_schedule_override_returns_utc_datetime(self) -> None:
        scheduled_for = parse_schedule_override(
            "2030-05-01",
            "09:30",
            "America/New_York",
            now=datetime(2030, 4, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertIsNotNone(scheduled_for)
        self.assertEqual(datetime(2030, 5, 1, 13, 30, tzinfo=timezone.utc), scheduled_for)

    def test_daily_schedule_only_fires_once_per_day(self) -> None:
        now = datetime(2030, 5, 1, 14, 0, tzinfo=timezone.utc)
        self.assertTrue(is_daily_schedule_due(now, "09:00", "America/New_York", last_sent_at=None))

        sent_after_window = datetime(2030, 5, 1, 13, 5, tzinfo=timezone.utc)
        self.assertFalse(
            is_daily_schedule_due(now, "09:00", "America/New_York", last_sent_at=sent_after_window)
        )

    def test_isoformat_utc_does_not_duplicate_utc_offset_for_aware_datetimes(self) -> None:
        aware = datetime(2026, 9, 26, 18, 32, tzinfo=timezone.utc)

        serialized = isoformat_utc(aware)

        self.assertEqual("2026-09-26T18:32:00Z", serialized)

    def test_parse_utc_timestamp_accepts_legacy_aware_utc_suffix(self) -> None:
        parsed = parse_utc_timestamp("2026-09-26T18:32:00+00:00Z")

        self.assertEqual(datetime(2026, 9, 26, 18, 32, tzinfo=timezone.utc), parsed)

    def test_parse_utc_timestamp_accepts_duplicate_utc_offset(self) -> None:
        parsed = parse_utc_timestamp("2026-09-26T18:32:00+00:00+00:00")

        self.assertEqual(datetime(2026, 9, 26, 18, 32, tzinfo=timezone.utc), parsed)


if __name__ == "__main__":
    unittest.main()