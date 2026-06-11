"""活动列表时间窗 filter 单测。"""

import unittest
from datetime import UTC, datetime, timedelta

from app.services.activity_query import (
    HOME_ACTIVITY_WINDOW_DAYS,
    date_range_start_filters,
    next7d_window_bounds,
)


class ActivityQueryDateRangeTests(unittest.TestCase):
    def test_next7d_includes_upcoming_within_window(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        filters = date_range_start_filters("next7d", now_utc=now)
        self.assertEqual(len(filters), 2)

    def test_next7d_includes_started_today_beijing(self) -> None:
        """今天已开始的活动仍应出现在近 7 天列表（未结束）。"""
        now = datetime(2026, 6, 11, 6, 30, tzinfo=UTC)
        earliest, latest = next7d_window_bounds(now)
        started_this_morning = datetime(2026, 6, 11, 4, 0, tzinfo=UTC)
        self.assertGreaterEqual(started_this_morning, earliest)
        self.assertLessEqual(started_this_morning, latest)

    def test_next7d_excludes_started_before_today_beijing(self) -> None:
        now = datetime(2026, 6, 11, 6, 30, tzinfo=UTC)
        earliest, _ = next7d_window_bounds(now)
        old = datetime(2026, 5, 19, 15, 52, tzinfo=UTC)
        self.assertLess(old, earliest)

    def test_next7d_window_days_constant(self) -> None:
        self.assertEqual(HOME_ACTIVITY_WINDOW_DAYS, 7)


if __name__ == "__main__":
    unittest.main()
