"""群聊角标统计单测。"""

import unittest

from app.services.chat_unread import parse_activity_pk


class ChatBadgeStatsTests(unittest.TestCase):
    def test_parse_activity_pk(self) -> None:
        self.assertEqual(parse_activity_pk("act_42"), 42)
        self.assertEqual(parse_activity_pk("42"), 42)
        self.assertEqual(parse_activity_pk(""), 0)
        self.assertEqual(parse_activity_pk("act_x"), 0)


if __name__ == "__main__":
    unittest.main()
