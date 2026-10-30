import unittest

from src.auth_session import (
    SESSION_DURATION_SECONDS,
    create_session_token,
    read_session_token,
    load_session_cookie,
)


class AuthSessionTests(unittest.TestCase):
    def test_session_token_restores_username_until_thirty_minute_expiry(self):
        token, expires_at = create_session_token("admin.user", "test-secret", now=1000)

        self.assertEqual(expires_at, 1000 + SESSION_DURATION_SECONDS)
        self.assertEqual(
            read_session_token(token, "test-secret", now=1001),
            ("admin.user", expires_at),
        )
        self.assertEqual(
            load_session_cookie(token, "test-secret", now=1001),
            ("admin.user", expires_at),
        )
        self.assertIsNone(
            load_session_cookie(token, "test-secret", now=expires_at)
        )

    def test_session_token_rejects_tampering_and_wrong_secret(self):
        token, _ = create_session_token("admin.user", "test-secret", now=1000)
        encoded_payload, encoded_signature = token.split(".", 1)
        tampered_token = "{}.{}".format(encoded_payload[:-1] + "A", encoded_signature)

        self.assertIsNone(read_session_token(tampered_token, "test-secret", now=1001))
        self.assertIsNone(read_session_token(token, "different-secret", now=1001))

    def test_session_token_rejects_malformed_values(self):
        for token in ("", "not-a-token", "%%%.%%%", None):
            with self.subTest(token=token):
                self.assertIsNone(read_session_token(token, "test-secret", now=1001))


if __name__ == "__main__":
    unittest.main()
