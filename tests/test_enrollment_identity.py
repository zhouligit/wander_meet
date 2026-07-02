import unittest

from fastapi import HTTPException

from app.services.enrollment_identity import (
    mask_id_card,
    validate_cn_id_card,
    validate_participant_name,
)


class EnrollmentIdentityTests(unittest.TestCase):
    def test_validate_participant_name_ok(self) -> None:
        self.assertEqual(validate_participant_name("张三"), "张三")
        self.assertEqual(validate_participant_name("  Li Ming "), "Li Ming")

    def test_validate_participant_name_rejects_short(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            validate_participant_name("张")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validate_cn_id_card_ok(self) -> None:
        self.assertEqual(
            validate_cn_id_card("110101199003074477"), "110101199003074477"
        )

    def test_validate_cn_id_card_rejects_bad_checksum(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            validate_cn_id_card("110101199003074478")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_mask_id_card(self) -> None:
        self.assertEqual(mask_id_card("110101199003074477"), "110101********4477")


if __name__ == "__main__":
    unittest.main()
