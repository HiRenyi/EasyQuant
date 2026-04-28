"""Integration tests for admin routes."""

import os
from unittest.mock import patch

import pytest

from quantgpt.auth import create_admin_token

pytestmark = pytest.mark.asyncio


class TestAdminLogin:
    async def test_correct_password(self, client):
        resp = await client.post("/api/v1/admin/login", json={
            "password": "test-admin-pw",
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    async def test_wrong_password(self, client):
        resp = await client.post("/api/v1/admin/login", json={
            "password": "wrong-password",
        })
        assert resp.status_code == 401

    async def test_empty_admin_password_returns_503(self, client):
        with patch.dict(os.environ, {"QUANTGPT_ADMIN_PASSWORD": ""}):
            resp = await client.post("/api/v1/admin/login", json={
                "password": "anything",
            })
            assert resp.status_code == 503


class TestAdminOverview:
    async def test_requires_admin_token(self, client, test_user, auth_headers):
        resp = await client.get("/api/v1/admin/overview", headers=auth_headers)
        assert resp.status_code == 403

    async def test_no_token_unauthorized(self, client):
        resp = await client.get("/api/v1/admin/overview")
        assert resp.status_code == 401

    @pytest.mark.skip(reason="admin_overview uses date_trunc which is PostgreSQL-only")
    async def test_admin_can_access(self, client, test_user):
        token = create_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/admin/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "user_count" in data
        assert "task_count" in data
        assert "success_rate" in data


class TestAdminUsers:
    async def test_list_users(self, client, test_user):
        token = create_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert data["total"] >= 1

    async def test_pagination(self, client, test_user):
        token = create_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/admin/users?page=1&page_size=1", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["users"]) <= 1
