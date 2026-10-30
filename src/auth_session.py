# SPDX-FileCopyrightText: 2025 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-License-Identifier: Apache-2.0

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone


SESSION_DURATION_SECONDS = 30 * 60
SESSION_COOKIE_NAME = "weedsgalore_session"


def _session_signing_key(signing_secret):
    return hmac.new(
        signing_secret.encode("utf-8"),
        b"weedsgalore-auth-session-v1",
        hashlib.sha256,
    ).digest()


def create_session_token(username, signing_secret, now=None):
    issued_at = int(time.time() if now is None else now)
    payload = json.dumps(
        {
            "username": username,
            "issued_at": issued_at,
            "expires_at": issued_at + SESSION_DURATION_SECONDS,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        _session_signing_key(signing_secret),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return "{}.{}".format(encoded_payload, encoded_signature), issued_at + SESSION_DURATION_SECONDS


def read_session_token(token, signing_secret, now=None):
    if not isinstance(token, str):
        return None
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            _session_signing_key(signing_secret),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None

        payload_bytes = base64.urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )
        payload = json.loads(payload_bytes.decode("utf-8"))
        username = payload["username"]
        issued_at = payload["issued_at"]
        expires_at = payload["expires_at"]
        current_time = int(time.time() if now is None else now)
    except (
        AttributeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):
        return None

    if (
        not isinstance(username, str)
        or not username
        or len(username) > 50
        or not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
        or issued_at > current_time
        or expires_at <= current_time
        or expires_at - issued_at != SESSION_DURATION_SECONDS
    ):
        return None
    return username, expires_at


def create_cookie_manager():
    import extra_streamlit_components as stx

    return stx.CookieManager(key="auth-session-cookies")


def save_session_cookie(cookie_manager, username, signing_secret, secure):
    token, expires_at = create_session_token(username, signing_secret)
    cookie_manager.set(
        SESSION_COOKIE_NAME,
        token,
        key="auth-session-cookie-set",
        path="/",
        expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc),
        secure=secure,
        same_site="lax",
    )
    return expires_at


def load_session_cookie(token, signing_secret, now=None):
    if token is None:
        return None
    return read_session_token(token, signing_secret, now=now)


def clear_session_cookie(cookie_manager):
    if cookie_manager.get(cookie=SESSION_COOKIE_NAME) is not None:
        cookie_manager.delete(SESSION_COOKIE_NAME, key="auth-session-cookie-delete")
