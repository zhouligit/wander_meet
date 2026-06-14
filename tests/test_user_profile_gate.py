import unittest

from fastapi import HTTPException

from app.models.user import User
from app.services.user_profile import (
    PROFILE_INCOMPLETE_DETAIL,
    assert_user_profile_complete,
    profile_is_complete,
)


class UserProfileGateTests(unittest.TestCase):
    def test_assert_user_profile_complete_raises(self) -> None:
        user = User(nickname="旅人1234", gender=None, birth_date=None)
        with self.assertRaises(HTTPException) as ctx:
            assert_user_profile_complete(user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, PROFILE_INCOMPLETE_DETAIL)

    def test_assert_user_profile_complete_passes(self) -> None:
        user = User(nickname="小明", gender=None, birth_date=None)
        assert_user_profile_complete(user)
        self.assertTrue(profile_is_complete(user))


if __name__ == "__main__":
    unittest.main()
