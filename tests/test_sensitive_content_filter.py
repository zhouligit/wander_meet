"""敏感词过滤单测（unittest，无需 pytest）。"""

import unittest

from app.services.local_text_content_filter import local_text_blocked_reason
from app.services.sensitive_content_filter import sensitive_text_blocked_reason


class SensitiveContentFilterTests(unittest.TestCase):
    def test_blocks_leader_name(self) -> None:
        self.assertIsNotNone(sensitive_text_blocked_reason("今天提到习近平"))

    def test_blocks_spaced_variant(self) -> None:
        self.assertIsNotNone(sensitive_text_blocked_reason("习 近 平"))

    def test_allows_normal_travel_text(self) -> None:
        self.assertIsNone(sensitive_text_blocked_reason("周末想去故宫和颐和园"))

    def test_strict_blocks_meme_alias(self) -> None:
        self.assertIsNone(sensitive_text_blocked_reason("维尼熊", strict=False))
        self.assertIsNotNone(sensitive_text_blocked_reason("维尼熊", strict=True))

    def test_contact_still_blocked(self) -> None:
        self.assertIsNotNone(local_text_blocked_reason("加我微信 abc1234567"))

    def test_tiananmen_place_ok_event_not(self) -> None:
        self.assertIsNone(sensitive_text_blocked_reason("明天去天安门广场"))
        self.assertIsNotNone(sensitive_text_blocked_reason("天安门事件"))


if __name__ == "__main__":
    unittest.main()
