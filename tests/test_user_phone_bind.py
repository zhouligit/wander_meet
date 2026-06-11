"""手机号绑定校验单测。"""

import unittest

from fastapi import HTTPException

from app.models.user import User
from app.services.user_phone_bind import (
    PHONE_BINDING_REQUIRED_DETAIL,
    assert_user_phone_bound,
    user_has_phone,
)


class UserPhoneBindTests(unittest.TestCase):
    def test_user_has_phone(self) -> None:
        self.assertFalse(user_has_phone(User(phone=None)))
        self.assertFalse(user_has_phone(User(phone="138")))
        self.assertTrue(user_has_phone(User(phone="13800138000")))

    def test_assert_user_phone_bound_raises(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            assert_user_phone_bound(User(phone=None))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, PHONE_BINDING_REQUIRED_DETAIL)

    def test_assert_user_phone_bound_passes(self) -> None:
        assert_user_phone_bound(User(phone="13800138000"))


if __name__ == "__main__":
    unittest.main()
