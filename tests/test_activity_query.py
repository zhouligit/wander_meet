"""活动列表时间窗 filter 单测。"""

import unittest
from datetime import UTC, datetime, timedelta

from app.services.activity_query import (
    HOME_ACTIVITY_WINDOW_DAYS,
    date_range_start_filters,
)


class ActivityQueryDateRangeTests(unittest.TestCase):
    def test_next7d_includes_upcoming_within_window(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        filters = date_range_start_filters("next7d", now_utc=now)
        self.assertEqual(len(filters), 2)

    def test_next7d_window_days_constant(self) -> None:
        self.assertEqual(HOME_ACTIVITY_WINDOW_DAYS, 7)


if __name__ == "__main__":
    unittest.main()
