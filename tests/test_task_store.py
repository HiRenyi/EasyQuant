"""Tests for task_store.py — rate limiter, task management, SSE tickets."""

import time

import pytest

from quantgpt.task_store import (
    CancelledException,
    _rate_buckets,
    active_task_count,
    check_cancelled,
    check_rate_limit,
    cleanup_tasks,
    create_sse_ticket,
    sanitize_task_response,
    tasks,
    validate_sse_ticket,
)


class TestRateLimiter:
    def setup_method(self):
        _rate_buckets.clear()

    def test_allows_first_request(self):
        assert check_rate_limit("1.2.3.4") is True

    def test_allows_multiple_within_limit(self):
        for _ in range(10):
            assert check_rate_limit("1.2.3.4") is True

    def test_blocks_after_limit(self):
        for _ in range(50):
            check_rate_limit("1.2.3.4")
        assert check_rate_limit("1.2.3.4") is False

    def test_different_ips_independent(self):
        for _ in range(50):
            check_rate_limit("1.1.1.1")
        assert check_rate_limit("1.1.1.1") is False
        assert check_rate_limit("2.2.2.2") is True


class TestTaskStore:
    def setup_method(self):
        tasks.clear()

    def test_active_task_count_empty(self):
        assert active_task_count() == 0

    def test_active_task_count_running(self):
        tasks["t1"] = {"status": "running"}
        tasks["t2"] = {"status": "completed"}
        tasks["t3"] = {"status": "pending"}
        assert active_task_count() == 2

    def test_check_cancelled_raises(self):
        tasks["t1"] = {"cancelled": True}
        with pytest.raises(CancelledException):
            check_cancelled("t1")

    def test_check_cancelled_no_raise_when_not_cancelled(self):
        tasks["t1"] = {"cancelled": False}
        check_cancelled("t1")

    def test_check_cancelled_no_raise_when_missing(self):
        check_cancelled("nonexistent")

    def test_cleanup_tasks_removes_expired(self):
        tasks["old"] = {
            "status": "completed",
            "created_at": time.time() - 99999,
        }
        tasks["fresh"] = {
            "status": "completed",
            "created_at": time.time(),
        }
        tasks["running"] = {
            "status": "running",
            "created_at": time.time() - 99999,
        }
        cleanup_tasks()
        assert "old" not in tasks
        assert "fresh" in tasks
        assert "running" in tasks


class TestSanitizeTaskResponse:
    def test_converts_timestamp(self):
        result = sanitize_task_response({"created_at": 1700000000})
        assert isinstance(result["created_at"], str)
        assert "2023" in result["created_at"]

    def test_non_dict_passthrough(self):
        assert sanitize_task_response("not a dict") == "not a dict"

    def test_no_created_at(self):
        result = sanitize_task_response({"status": "ok"})
        assert result == {"status": "ok"}


class TestSSETickets:
    def test_create_and_validate(self):
        ticket = create_sse_ticket("task-1", "user-1")
        assert isinstance(ticket, str)
        assert len(ticket) > 10

        user_id = validate_sse_ticket(ticket, "task-1")
        assert user_id == "user-1"

    def test_ticket_consumed_on_validation(self):
        ticket = create_sse_ticket("task-1", "user-1")
        validate_sse_ticket(ticket, "task-1")
        assert validate_sse_ticket(ticket, "task-1") is None

    def test_wrong_task_id_rejected(self):
        ticket = create_sse_ticket("task-1", "user-1")
        assert validate_sse_ticket(ticket, "task-2") is None

    def test_invalid_ticket_returns_none(self):
        assert validate_sse_ticket("bogus-ticket", "task-1") is None

    def test_expired_ticket_rejected(self):
        from quantgpt.task_store import _sse_tickets, _sse_tickets_lock

        ticket = create_sse_ticket("task-1", "user-1")
        with _sse_tickets_lock:
            _sse_tickets[ticket]["expires"] = time.monotonic() - 1
        assert validate_sse_ticket(ticket, "task-1") is None
