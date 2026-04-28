"""Tests for backtest task routes — health, stats, task CRUD."""

import time

import pytest

from quantgpt.task_store import tasks, tasks_lock

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_tasks():
    tasks.clear()
    yield
    tasks.clear()


class TestHealthEndpoint:
    async def test_returns_ok(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_tasks" in data
        assert "auth_disabled" in data


class TestTaskStats:
    async def test_returns_stats(self, client, test_user, auth_headers):
        resp = await client.get("/api/v1/tasks/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "completed" in data
        assert "running" in data

    async def test_with_tasks_present(self, client, test_user, auth_headers):
        uid = str(test_user.id)
        with tasks_lock:
            tasks["t1"] = {"task_id": "t1", "user_id": uid, "status": "running", "created_at": time.time()}
            tasks["t2"] = {"task_id": "t2", "user_id": uid, "status": "completed", "created_at": time.time()}
        resp = await client.get("/api/v1/tasks/stats", headers=auth_headers)
        data = resp.json()
        assert data["total"] >= 1
        assert data["running"] >= 1


class TestListTasks:
    async def test_empty_list(self, client, test_user, auth_headers):
        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []

    async def test_lists_user_tasks(self, client, test_user, auth_headers, db_session):
        from quantgpt.models import Task as TaskModel
        t = TaskModel(
            id="test-task-1",
            user_id=test_user.id,
            status="completed",
            task_type="backtest",
            expression="rank(close)",
        )
        db_session.add(t)
        await db_session.commit()

        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "test-task-1"


class TestGetTask:
    async def test_get_existing_task(self, client, test_user, auth_headers, db_session):
        from quantgpt.models import Task as TaskModel
        t = TaskModel(
            id="detail-task-1",
            user_id=test_user.id,
            status="completed",
            task_type="backtest",
            expression="rank(volume)",
            result={"score": 50},
        )
        db_session.add(t)
        await db_session.commit()

        resp = await client.get("/api/v1/tasks/detail-task-1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "detail-task-1"
        assert data["expression"] == "rank(volume)"

    async def test_get_nonexistent_task(self, client, test_user, auth_headers):
        resp = await client.get("/api/v1/tasks/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestCancelTask:
    async def test_cancel_running_task(self, client, test_user, auth_headers):
        uid = str(test_user.id)
        with tasks_lock:
            tasks["cancel-me"] = {
                "task_id": "cancel-me",
                "user_id": uid,
                "status": "running",
                "cancelled": False,
                "created_at": time.time(),
            }
        resp = await client.post("/api/v1/tasks/cancel-me/cancel", headers=auth_headers)
        assert resp.status_code == 200
        assert tasks["cancel-me"]["status"] == "cancelled"

    async def test_cancel_nonexistent_task(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/tasks/nonexistent/cancel", headers=auth_headers)
        assert resp.status_code == 404

    async def test_cancel_completed_task_fails(self, client, test_user, auth_headers):
        uid = str(test_user.id)
        with tasks_lock:
            tasks["done-task"] = {
                "task_id": "done-task",
                "user_id": uid,
                "status": "completed",
                "cancelled": False,
                "created_at": time.time(),
            }
        resp = await client.post("/api/v1/tasks/done-task/cancel", headers=auth_headers)
        assert resp.status_code == 400


class TestAutoBacktestValidation:
    async def test_empty_prompt_rejected(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auto_backtest", json={
            "prompt": "",
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_invalid_universe_rejected(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auto_backtest", json={
            "prompt": "test factor",
            "universe": "invalid_universe",
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_invalid_date_format_rejected(self, client, test_user, auth_headers):
        resp = await client.post("/api/v1/auto_backtest", json={
            "prompt": "test factor",
            "start_date": "01-01-2023",
        }, headers=auth_headers)
        assert resp.status_code == 422
