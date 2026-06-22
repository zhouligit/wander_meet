"""活动类目（2026-06 调整）单测。"""

import unittest

from fastapi import HTTPException

from app.services.activity_category import (
    ACTIVITY_CATEGORIES,
    category_display_name,
    normalize_activity_category,
)


class ActivityCategoryTests(unittest.TestCase):
    def test_new_taxonomy_count(self) -> None:
        self.assertEqual(len(ACTIVITY_CATEGORIES), 8)
        self.assertEqual(ACTIVITY_CATEGORIES[0].name, "吃吃喝喝")
        self.assertEqual(ACTIVITY_CATEGORIES[-1].categoryId, "other")

    def test_display_new_pair(self) -> None:
        self.assertEqual(
            category_display_name("outdoor", "picnic"),
            "户外自然 · 野炊",
        )

    def test_display_legacy_retired_l1(self) -> None:
        self.assertEqual(
            category_display_name("games", "boardgame"),
            "游戏娱乐 · 桌游",
        )

    def test_display_legacy_outdoor_camping(self) -> None:
        self.assertEqual(
            category_display_name("outdoor", "camping"),
            "户外自然 · 露营",
        )

    def test_create_rejects_retired_l1(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            normalize_activity_category("games", "boardgame")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_allows_retired_l1(self) -> None:
        cid, sid, label = normalize_activity_category(
            "games", "boardgame", allow_retired=True
        )
        self.assertEqual((cid, sid, label), ("games", "boardgame", None))

    def test_create_new_outdoor_picnic(self) -> None:
        cid, sid, label = normalize_activity_category("outdoor", "picnic")
        self.assertEqual((cid, sid, label), ("outdoor", "picnic", None))

    def test_create_allows_l1_without_sub(self) -> None:
        cid, sid, label = normalize_activity_category("dining", None)
        self.assertEqual((cid, sid, label), ("dining", None, None))


if __name__ == "__main__":
    unittest.main()
