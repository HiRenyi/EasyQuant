"""Tests for wq_brain_batch route and MCP tracking."""

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio


class TestBatchSubmitValidation:
    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/wq-brain/batch-submit", json={
            "expression": "rank(close)",
        })
        assert resp.status_code in (401, 403)

    async def test_returns_503_when_not_configured(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "", "WQ_BRAIN_PASSWORD": ""}, clear=False):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
            }, headers=auth_headers)
            assert resp.status_code == 503

    async def test_rejects_invalid_region(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
                "regions": ["INVALID"],
            }, headers=auth_headers)
            assert resp.status_code == 400
            assert "region" in resp.json()["detail"].lower()

    async def test_rejects_invalid_universe(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
                "universes": ["INVALID"],
            }, headers=auth_headers)
            assert resp.status_code == 400
            assert "universe" in resp.json()["detail"].lower()

    async def test_rejects_invalid_neutralization(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
                "neutralizations": ["BOGUS"],
            }, headers=auth_headers)
            assert resp.status_code == 400
            assert "neutralization" in resp.json()["detail"].lower()

    async def test_rejects_invalid_delay(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
                "delays": [5],
            }, headers=auth_headers)
            assert resp.status_code == 400
            assert "delay" in resp.json()["detail"].lower()

    async def test_rejects_too_many_combinations(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                "expression": "rank(close)",
                "regions": ["USA", "CHN"],
                "delays": [0, 1],
                "universes": ["TOP3000", "TOP1000", "TOP500", "TOP200"],
                "neutralizations": ["MARKET", "SUBINDUSTRY", "INDUSTRY", "SECTOR", "NONE"],
            }, headers=auth_headers)
            assert resp.status_code == 400
            assert "组合数" in resp.json()["detail"]


class TestBatchSubmitCreatesTask:
    async def test_creates_task_with_defaults(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            with patch("quantgpt.routes.wq_brain_batch._run_batch_task"):
                resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                    "expression": "rank(close)",
                }, headers=auth_headers)
                assert resp.status_code == 202
                data = resp.json()
                assert "task_id" in data
                assert data["status"] == "pending"
                assert data["total_combinations"] == 1

    async def test_creates_task_with_sweep(self, client, test_user, auth_headers):
        with patch.dict(os.environ, {"WQ_BRAIN_EMAIL": "a@b.com", "WQ_BRAIN_PASSWORD": "pw"}):
            with patch("quantgpt.routes.wq_brain_batch._run_batch_task"):
                resp = await client.post("/api/v1/wq-brain/batch-submit", json={
                    "expression": "rank(close/open)",
                    "regions": ["USA", "CHN"],
                    "delays": [0, 1],
                    "universes": ["TOP3000"],
                    "neutralizations": ["SUBINDUSTRY", "MARKET"],
                }, headers=auth_headers)
                assert resp.status_code == 202
                data = resp.json()
                assert data["total_combinations"] == 2 * 2 * 1 * 2


class TestBatchRequestModel:
    def test_defaults(self):
        from quantgpt.routes.wq_brain_batch import WQBrainBatchRequest
        req = WQBrainBatchRequest(expression="rank(close)")
        assert req.regions == ["USA"]
        assert req.delays == [1]
        assert req.universes == ["TOP3000"]
        assert req.neutralizations == ["SUBINDUSTRY"]
        assert req.decay == 0
        assert req.truncation == 0.08
        assert req.auto_submit is False

    def test_custom_values(self):
        from quantgpt.routes.wq_brain_batch import WQBrainBatchRequest
        req = WQBrainBatchRequest(
            expression="ts_mean(close, 5)",
            regions=["USA", "CHN"],
            delays=[0, 1],
            decay=5,
            truncation=0.1,
            auto_submit=True,
        )
        assert req.regions == ["USA", "CHN"]
        assert req.delays == [0, 1]
        assert req.decay == 5
        assert req.auto_submit is True


class TestMCPTrackingBatch:
    def test_extract_summary_batch(self):
        import json
        from quantgpt.mcp_tracking import _extract_summary

        data = json.dumps({
            "total_combinations": 8,
            "best_fitness": 1.23,
            "best_key": "USA_D1_TOP3000_SUBINDUSTRY",
            "submittable_count": 2,
        })
        summary = _extract_summary(data, "mcp_wq_brain_batch")
        assert summary["total_combinations"] == 8
        assert summary["best_fitness"] == 1.23
        assert summary["best_key"] == "USA_D1_TOP3000_SUBINDUSTRY"
        assert summary["submittable_count"] == 2

    def test_extract_summary_batch_error(self):
        import json
        from quantgpt.mcp_tracking import _extract_summary

        data = json.dumps({"error": "WQ BRAIN 未配置"})
        summary = _extract_summary(data, "mcp_wq_brain_batch")
        assert "error" in summary
