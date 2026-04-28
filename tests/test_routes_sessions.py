"""Integration tests for session and factor-library routes."""

import uuid

import pytest

from quantgpt.auth import create_access_token
from quantgpt.models import User

pytestmark = pytest.mark.asyncio


class TestSessionCRUD:
    async def test_create_session(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/sessions", json={"name": "My Session"}, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Session"
        assert "id" in data

    async def test_list_sessions(self, client, test_user, auth_headers):
        await client.post("/api/v1/sessions", json={"name": "S1"}, headers=auth_headers)
        await client.post("/api/v1/sessions", json={"name": "S2"}, headers=auth_headers)
        resp = await client.get("/api/v1/sessions", headers=auth_headers)
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) >= 2

    async def test_rename_session(self, client, test_user, auth_headers):
        create_resp = await client.post("/api/v1/sessions", json={"name": "Old"}, headers=auth_headers)
        sid = create_resp.json()["id"]
        resp = await client.patch(f"/api/v1/sessions/{sid}", json={"name": "New"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    async def test_delete_session(self, client, test_user, auth_headers):
        create_resp = await client.post("/api/v1/sessions", json={"name": "ToDelete"}, headers=auth_headers)
        sid = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/sessions/{sid}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_delete_nonexistent_session_404(self, client, test_user, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/api/v1/sessions/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_user_isolation(self, client, db_session, test_user, auth_headers):
        create_resp = await client.post("/api/v1/sessions", json={"name": "UserA"}, headers=auth_headers)
        sid = create_resp.json()["id"]

        other_user = User(id=uuid.uuid4(), email="other@test.com", is_active=True)
        db_session.add(other_user)
        await db_session.commit()
        other_token = create_access_token(other_user.id, other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        resp = await client.delete(f"/api/v1/sessions/{sid}", headers=other_headers)
        assert resp.status_code == 404

    async def test_no_auth_rejected(self, client):
        resp = await client.get("/api/v1/sessions")
        assert resp.status_code == 401


class TestFactorLibrary:
    async def test_save_factor(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/factor-library", json={
            "expression": "rank(close)",
            "name": "Test Factor",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["expression"] == "rank(close)"
        assert data["name"] == "Test Factor"

    async def test_duplicate_factor_rejected(self, client, test_user, auth_headers):
        await client.post("/api/v1/factor-library", json={
            "expression": "rank(volume)",
        }, headers=auth_headers)
        resp = await client.post("/api/v1/factor-library", json={
            "expression": "rank(volume)",
        }, headers=auth_headers)
        assert resp.status_code == 409

    async def test_list_factors(self, client, test_user, auth_headers):
        await client.post("/api/v1/factor-library", json={
            "expression": "ts_mean(close, 5)",
        }, headers=auth_headers)
        resp = await client.get("/api/v1/factor-library", headers=auth_headers)
        assert resp.status_code == 200
        factors = resp.json()["factors"]
        assert len(factors) >= 1

    async def test_update_factor(self, client, test_user, auth_headers):
        create_resp = await client.post("/api/v1/factor-library", json={
            "expression": "zscore(close)",
        }, headers=auth_headers)
        fid = create_resp.json()["id"]
        resp = await client.patch(f"/api/v1/factor-library/{fid}", json={
            "name": "Updated Name",
            "note": "Added a note",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["note"] == "Added a note"

    async def test_delete_factor(self, client, test_user, auth_headers):
        create_resp = await client.post("/api/v1/factor-library", json={
            "expression": "rank(amount)",
        }, headers=auth_headers)
        fid = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/factor-library/{fid}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_factor_user_isolation(self, client, db_session, test_user, auth_headers):
        create_resp = await client.post("/api/v1/factor-library", json={
            "expression": "rank(open)",
        }, headers=auth_headers)
        fid = create_resp.json()["id"]

        other_user = User(id=uuid.uuid4(), email="other2@test.com", is_active=True)
        db_session.add(other_user)
        await db_session.commit()
        other_token = create_access_token(other_user.id, other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        resp = await client.delete(f"/api/v1/factor-library/{fid}", headers=other_headers)
        assert resp.status_code == 404
