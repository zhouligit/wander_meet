import unittest

from fastapi import HTTPException

from app.models.activity_enrollment import ActivityEnrollment
from app.services.enrollment_identity import (
    mask_id_card,
    member_identity_for_organizer,
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

    def test_member_identity_for_organizer_full_fields(self) -> None:
        en = ActivityEnrollment(
            participant_name="周利",
            id_card_number="370402199003073675",
            participant_phone="13012343133",
        )
        row = member_identity_for_organizer(en, show=True)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.idCardNumber, "370402199003073675")
        self.assertEqual(row.phone, "13012343133")
        self.assertIn("****", row.idCardMasked)

    def test_enrollment_roster_item_full_values(self) -> None:
        from app.services.enrollment_identity import enrollment_roster_item

        en = ActivityEnrollment(
            participant_name="周利",
            id_card_number="370402199003073675",
            participant_phone="13012343133",
        )
        item = enrollment_roster_item(en)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.idCardNumber, "370402199003073675")
        self.assertNotIn("*", item.idCardNumber)
        self.assertEqual(item.phone, "13012343133")
        self.assertNotIn("*", item.phone)


if __name__ == "__main__":
    unittest.main()
