import unittest

from app.models.user import User
from app.services.user_profile import (
    assert_user_profile_complete,
    profile_is_complete,
)


class UserProfileGateTests(unittest.TestCase):
    def test_profile_is_complete_always_true(self) -> None:
        self.assertTrue(profile_is_complete(User(nickname="旅人1234")))
        self.assertTrue(profile_is_complete(User(nickname="小明")))

    def test_assert_user_profile_complete_noop(self) -> None:
        assert_user_profile_complete(User(nickname="旅人1234"))


if __name__ == "__main__":
    unittest.main()
