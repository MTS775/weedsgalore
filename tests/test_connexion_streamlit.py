import unittest

from src.connexion_streamlit import (
    hash_password,
    validate_user_fields,
    validate_password,
    validate_username,
    verify_password,
)


class AuthenticationHelpersTests(unittest.TestCase):
    def test_password_hash_verifies_only_matching_password(self):
        password_hash = hash_password("a-strong-password")

        self.assertTrue(verify_password("a-strong-password", password_hash))
        self.assertFalse(verify_password("a-different-password", password_hash))

    def test_password_hash_uses_a_new_salt_each_time(self):
        first_hash = hash_password("a-strong-password")
        second_hash = hash_password("a-strong-password")

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(first_hash.startswith("$pbkdf2_sha256$"))

    def test_username_is_trimmed_and_validated(self):
        self.assertEqual(validate_username("  admin.user  "), "admin.user")

    def test_username_rejects_unsupported_characters(self):
        with self.assertRaises(ValueError):
            validate_username("admin user")

    def test_username_rejects_short_names(self):
        with self.assertRaises(ValueError):
            validate_username("ab")

    def test_password_requires_at_least_twelve_characters(self):
        with self.assertRaises(ValueError):
            validate_password("too-short")

    def test_password_rejects_extreme_length(self):
        with self.assertRaises(ValueError):
            validate_password("x" * 257)

    def test_user_fields_trim_values_and_allow_optional_email(self):
        self.assertEqual(
            validate_user_fields(" admin ", " Admin User ", " "),
            ("admin", "Admin User", None, None),
        )

    def test_user_fields_require_name(self):
        with self.assertRaises(ValueError):
            validate_user_fields("admin", " ", "")

    def test_user_fields_trim_optional_first_name(self):
        self.assertEqual(
            validate_user_fields("admin", "Martin", "", prenom="  Alice  "),
            ("admin", "Martin", None, "Alice"),
        )

    def test_user_fields_allow_empty_first_name(self):
        self.assertEqual(
            validate_user_fields("admin", "Martin", "", prenom=" "),
            ("admin", "Martin", None, None),
        )

    def test_user_fields_reject_first_name_over_limit(self):
        with self.assertRaises(ValueError):
            validate_user_fields("admin", "Martin", "", prenom="A" * 101)


if __name__ == "__main__":
    unittest.main()
