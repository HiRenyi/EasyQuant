"""Tests for quantgpt/auth.py — JWT, password hashing, rate limiting."""

import os
import time
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only-do-not-use-in-production")

from quantgpt.auth import (
    _email_rate,
    _extract_token,
    check_email_rate_limit,
    create_access_token,
    create_admin_token,
    create_guest_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_auth_disabled,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "my_secure_password_123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_for_same_password(self):
        pw = "same_password"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2
        assert verify_password(pw, h1)
        assert verify_password(pw, h2)


class TestAccessToken:
    def test_create_and_decode(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["email"] == "user@example.com"
        assert payload["type"] == "access"

    def test_expired_token_raises(self):
        uid = uuid.uuid4()
        with patch.dict(os.environ, {"JWT_ACCESS_TOKEN_EXPIRE_HOURS": "0"}):
            token = create_access_token(uid, "user@example.com")
        with pytest.raises(HTTPException, match="过期"):
            decode_token(token)


class TestRefreshToken:
    def test_create_and_decode(self):
        uid = uuid.uuid4()
        token = create_refresh_token(uid)
        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "refresh"


class TestGuestToken:
    def test_create_and_decode(self):
        token = create_guest_token()
        payload = decode_token(token)
        assert payload["type"] == "guest"
        assert payload["sub"] == "00000000-0000-0000-0000-000000000001"


class TestAdminToken:
    def test_create_and_decode(self):
        token = create_admin_token()
        payload = decode_token(token)
        assert payload["type"] == "admin"
        assert payload["sub"] == "admin"


class TestDecodeToken:
    def test_invalid_token_raises(self):
        with pytest.raises(HTTPException, match="无效"):
            decode_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        token = create_access_token(uuid.uuid4(), "a@b.com")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException):
            decode_token(tampered)


class TestEmailRateLimit:
    def setup_method(self):
        _email_rate.clear()

    def test_first_send_allowed(self):
        check_email_rate_limit("new@example.com")

    def test_second_send_within_limit_blocked(self):
        check_email_rate_limit("rate@example.com")
        with pytest.raises(HTTPException) as exc_info:
            check_email_rate_limit("rate@example.com")
        assert exc_info.value.status_code == 429

    def test_different_emails_independent(self):
        check_email_rate_limit("a@example.com")
        check_email_rate_limit("b@example.com")

    def test_expired_entries_cleaned(self):
        _email_rate["old@example.com"] = time.monotonic() - 400
        check_email_rate_limit("new2@example.com")
        assert "old@example.com" not in _email_rate


class TestExtractToken:
    def test_bearer_header(self):
        class FakeRequest:
            headers = {"Authorization": "Bearer abc123"}
            query_params = {}
        assert _extract_token(FakeRequest()) == "abc123"

    def test_query_param_fallback(self):
        class FakeRequest:
            headers = {}
            query_params = {"token": "qp_token"}
        assert _extract_token(FakeRequest()) == "qp_token"

    def test_no_token_raises(self):
        class FakeRequest:
            headers = {}
            query_params = {}
        with pytest.raises(HTTPException, match="未提供"):
            _extract_token(FakeRequest())


class TestIsAuthDisabled:
    def test_default_is_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUTH_DISABLED", None)
            assert is_auth_disabled()

    def test_enabled_when_false(self):
        with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
            assert not is_auth_disabled()

    def test_disabled_when_true(self):
        with patch.dict(os.environ, {"AUTH_DISABLED": "true"}):
            assert is_auth_disabled()

    def test_disabled_when_1(self):
        with patch.dict(os.environ, {"AUTH_DISABLED": "1"}):
            assert is_auth_disabled()
