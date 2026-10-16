import unittest

from src.gestion_authorisation import (
    ANALYSIS_PAGE,
    USER_MANAGEMENT_PAGE,
    can_access_page,
    get_accessible_pages,
)


class AuthorizationTests(unittest.TestCase):
    def test_user_can_only_access_parcel_analysis(self):
        self.assertEqual(get_accessible_pages("user"), (ANALYSIS_PAGE,))
        self.assertTrue(can_access_page("user", ANALYSIS_PAGE))
        self.assertFalse(can_access_page("user", USER_MANAGEMENT_PAGE))

    def test_admin_can_access_both_pages(self):
        self.assertEqual(
            get_accessible_pages("admin"),
            (ANALYSIS_PAGE, USER_MANAGEMENT_PAGE),
        )
        self.assertTrue(can_access_page("admin", ANALYSIS_PAGE))
        self.assertTrue(can_access_page("admin", USER_MANAGEMENT_PAGE))

    def test_unknown_role_defaults_to_non_admin_access(self):
        self.assertEqual(get_accessible_pages("unknown"), (ANALYSIS_PAGE,))
        self.assertFalse(can_access_page("unknown", USER_MANAGEMENT_PAGE))


if __name__ == "__main__":
    unittest.main()
