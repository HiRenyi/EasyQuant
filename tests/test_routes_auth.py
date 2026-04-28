"""Integration tests for auth routes — API-level tests with in-memory SQLite."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quantgpt.auth import create_access_token, create_refresh_token
from quantgpt.models import User, VerificationCode

pytestmark = pytest.mark.asyncio


class TestGuestToken:
    async def test_returns_token(self, client):
        resp = await client.post("/api/v1/auth/guest-token")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestSendCode:
    async def test_invalid_email_rejected(self, client):
        resp = await client.post("/api/v1/auth/send-code", json={"email": "not-an-email"})
        assert resp.status_code == 422

    @patch("quantgpt.routes.auth.send_verification_email", new_callable=AsyncMock)
    async def test_valid_email_sends_code(self, mock_send, client, db_session):
        resp = await client.post("/api/v1/auth/send-code", json={"email": "user@test.com"})
        assert resp.status_code == 200
        assert resp.json()["expires_in"] == 300
        mock_send.assert_awaited_once()

    @patch("quantgpt.routes.auth.send_verification_email", new_callable=AsyncMock)
    async def test_rate_limit_blocks_rapid_resend(self, mock_send, client):
        from quantgpt.auth import _email_rate
        _email_rate.clear()
        resp1 = await client.post("/api/v1/auth/send-code", json={"email": "ratelimit@test.com"})
        assert resp1.status_code == 200
        resp2 = await client.post("/api/v1/auth/send-code", json={"email": "ratelimit@test.com"})
        assert resp2.status_code == 429


class TestVerifyCode:
    async def _insert_code(self, db_session: AsyncSession, email: str, code: str):
        vc = VerificationCode(
            email=email,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(vc)
        await db_session.commit()

    async def test_valid_code_returns_tokens(self, client, db_session):
        await self._insert_code(db_session, "newuser@test.com", "123456")
        resp = await client.post("/api/v1/auth/verify-code", json={
            "email": "newuser@test.com",
            "code": "123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "newuser@test.com"

    async def test_wrong_code_rejected(self, client, db_session):
        await self._insert_code(db_session, "wrong@test.com", "111111")
        resp = await client.post("/api/v1/auth/verify-code", json={
            "email": "wrong@test.com",
            "code": "999999",
        })
        assert resp.status_code == 400
        assert "错误" in resp.json()["detail"]

    async def test_expired_code_rejected(self, client, db_session):
        vc = VerificationCode(
            email="expired@test.com",
            code="654321",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(vc)
        await db_session.commit()
        resp = await client.post("/api/v1/auth/verify-code", json={
            "email": "expired@test.com",
            "code": "654321",
        })
        assert resp.status_code == 400

    async def test_code_validation_format(self, client):
        resp = await client.post("/api/v1/auth/verify-code", json={
            "email": "a@b.com",
            "code": "abc",
        })
        assert resp.status_code == 422

    async def test_max_attempts_locks_code(self, client, db_session):
        vc = VerificationCode(
            email="locked@test.com",
            code="111111",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            attempts=5,
        )
        db_session.add(vc)
        await db_session.commit()
        resp = await client.post("/api/v1/auth/verify-code", json={
            "email": "locked@test.com",
            "code": "111111",
        })
        assert resp.status_code == 400
        assert "次数" in resp.json()["detail"]


class TestLogin:
    async def test_login_with_password(self, client, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "test123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"

    async def test_wrong_password_rejected(self, client, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrong_password",
        })
        assert resp.status_code == 401

    async def test_nonexistent_user_rejected(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com",
            "password": "any_password",
        })
        assert resp.status_code == 401

    async def test_no_password_set_gets_hint(self, client, db_session):
        user = User(id=uuid.uuid4(), email="nopw@test.com", is_active=True)
        db_session.add(user)
        await db_session.commit()
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nopw@test.com",
            "password": "any",
        })
        assert resp.status_code == 400
        assert "验证码" in resp.json()["detail"]


class TestRefresh:
    async def test_refresh_returns_new_access_token(self, client, test_user):
        refresh = create_refresh_token(test_user.id)
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_access_token_not_accepted_as_refresh(self, client, test_user):
        access = create_access_token(test_user.id, test_user.email)
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access,
        })
        assert resp.status_code == 401


class TestMe:
    async def test_returns_user_info(self, client, test_user, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["has_password"] is True

    async def test_no_token_unauthorized(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestSetPassword:
    async def test_set_first_password(self, client, db_session, auth_headers):
        user = User(id=uuid.uuid4(), email="nopw2@test.com", is_active=True)
        db_session.add(user)
        await db_session.commit()
        token = create_access_token(user.id, user.email)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/auth/set-password", json={
            "password": "newpassword123",
        }, headers=headers)
        assert resp.status_code == 200

    async def test_change_password_requires_old(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auth/set-password", json={
            "password": "newpassword123",
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "当前密码" in resp.json()["detail"]

    async def test_change_password_with_correct_old(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auth/set-password", json={
            "password": "newpassword123",
            "old_password": "test123456",
        }, headers=auth_headers)
        assert resp.status_code == 200

    async def test_short_password_rejected(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auth/set-password", json={
            "password": "ab",
            "old_password": "test123456",
        }, headers=auth_headers)
        assert resp.status_code == 422
