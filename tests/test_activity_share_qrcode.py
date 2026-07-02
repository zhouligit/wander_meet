import unittest

from app.services.activity_share_qrcode import (
    build_activity_share_scene,
    parse_activity_share_scene,
)


class ActivityShareQrcodeTests(unittest.TestCase):
    def test_build_scene(self) -> None:
        self.assertEqual(build_activity_share_scene(42), "42")

    def test_parse_scene(self) -> None:
        self.assertEqual(parse_activity_share_scene("42"), 42)
        self.assertEqual(parse_activity_share_scene("id=42"), 42)
        self.assertEqual(parse_activity_share_scene("sa=42"), 42)
        self.assertEqual(parse_activity_share_scene("id%3D42"), 42)
        self.assertIsNone(parse_activity_share_scene("1011"))
        self.assertIsNone(parse_activity_share_scene(""))
        self.assertIsNone(parse_activity_share_scene("inv=ABC"))


if __name__ == "__main__":
    unittest.main()
