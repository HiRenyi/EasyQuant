"""Tests for wq_brain_client.py and routes/wq_brain.py."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from quantgpt.wq_brain_client import SUBMIT_THRESHOLDS, WQBrainClient, is_configured

pytestmark = pytest.mark.asyncio


class TestIsConfigured:
    def test_not_configured_when_empty(self):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "", "WQ_BRAIN_PASSWORD": ""}, clear=False):
            assert is_configured() is False

    def test_not_configured_when_missing(self):
        env = os.environ.copy()
        env.pop("WQ_BRAIN_EMAIL", None)
        env.pop("WQ_BRAIN_PASSWORD", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_configured() is False

    def test_configured_when_both_set(self):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}, clear=False):
            assert is_configured() is True


class TestWQBrainClient:
    def test_init_from_params(self):
        c = WQBrainClient(email="test@test.com", password="pass")
        assert c.email == "test@test.com"
        assert c.password == "pass"

    def test_init_from_env(self):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "env@test.com", "WQ_BRAIN_PASSWORD": "envpw"}):
            c = WQBrainClient()
            assert c.email == "env@test.com"
            assert c.password == "envpw"

    def test_close_without_session(self):
        c = WQBrainClient(email="a", password="b")
        c.close()

    def test_is_submittable_all_pass(self):
        c = WQBrainClient(email="a", password="b")
        checks = {"is": {"checks": [
            {"name": "test1", "result": "PASS"},
            {"name": "test2", "result": "PASS"},
        ]}}
        assert c.is_submittable(checks) is True

    def test_is_submittable_with_fail(self):
        c = WQBrainClient(email="a", password="b")
        checks = {"is": {"checks": [
            {"name": "test1", "result": "PASS"},
            {"name": "test2", "result": "FAIL"},
        ]}}
        assert c.is_submittable(checks) is False

    def test_is_submittable_with_pending(self):
        c = WQBrainClient(email="a", password="b")
        checks = {"is": {"checks": [
            {"name": "test1", "result": "PASS"},
            {"name": "test2", "result": "PENDING"},
        ]}}
        assert c.is_submittable(checks) is False

    def test_is_submittable_empty(self):
        c = WQBrainClient(email="a", password="b")
        assert c.is_submittable({}) is True

    @patch("quantgpt.wq_brain_client.httpx.Client")
    def test_authenticate_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"permissions": ["SUBMIT"]}
        mock_client.post.return_value = mock_resp

        c = WQBrainClient(email="a@b.com", password="pw")
        assert c.authenticate() is True

    @patch("quantgpt.wq_brain_client.httpx.Client")
    def test_authenticate_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client.post.return_value = mock_resp

        c = WQBrainClient(email="a@b.com", password="wrong")
        assert c.authenticate() is False

    @patch("quantgpt.wq_brain_client.httpx.Client")
    def test_authenticate_biometric(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"inquiry": "biometric_required"}
        mock_client.post.return_value = mock_resp

        c = WQBrainClient(email="a@b.com", password="pw")
        assert c.authenticate() is False


class TestWQBrainStatusEndpoint:
    async def test_status_returns_config(self, client):
        resp = await client.get("/api/v1/wq-brain/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "thresholds" in data
        assert data["thresholds"]["sharpe"] == 1.25


class TestWQBrainSubmitEndpoint:
    async def test_submit_requires_auth(self, client):
        resp = await client.post("/api/v1/wq-brain/submit", json={
            "expression": "rank(close)",
        })
        assert resp.status_code in (401, 403)

    async def test_submit_returns_503_when_not_configured(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "", "WQ_BRAIN_PASSWORD": ""}, clear=False):
            resp = await client.post("/api/v1/wq-brain/submit", json={
                "expression": "rank(close)",
            }, headers=auth_headers)
            assert resp.status_code == 503

    async def test_submit_creates_task(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}, clear=False):
            with patch("quantgpt.routes.wq_brain._run_wq_brain_task"):
                resp = await client.post("/api/v1/wq-brain/submit", json={
                    "expression": "rank(close)",
                }, headers=auth_headers)
                assert resp.status_code == 202
                data = resp.json()
                assert "task_id" in data
                assert data["status"] == "pending"


class TestSubmitAlphaEndpoint:
    async def test_submit_alpha_requires_auth(self, client):
        resp = await client.post("/api/v1/wq-brain/fake-task/submit-alpha")
        assert resp.status_code in (401, 403)

    async def test_submit_alpha_task_not_found(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}, clear=False):
            resp = await client.post("/api/v1/wq-brain/nonexistent/submit-alpha", headers=auth_headers)
            assert resp.status_code == 404
