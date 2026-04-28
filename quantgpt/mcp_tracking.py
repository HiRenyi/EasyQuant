"""MCP call tracking: fire-and-forget persistence of MCP tool calls to the Task table."""

import asyncio
import json
import logging
import threading
import uuid

logger = logging.getLogger(__name__)

MCP_USER_ID = "00000000-0000-0000-0000-000000000002"


async def _persist_mcp_call(
    task_type: str,
    expression: str | None,
    params: dict,
    result_summary: dict | None,
    error: str | None,
    elapsed: float,
):
    """Write an MCP call record to the Task table (fire-and-forget)."""
    try:
        from .db import _get_session_factory
        factory = _get_session_factory()
    except Exception:
        # DATABASE_URL not set or DB not available — skip silently
        return

    from .models import Task

    task_id = uuid.uuid4().hex[:12]
    status = "failed" if error else "completed"
    params["source"] = "mcp"
    params["elapsed_seconds"] = round(elapsed, 2)

    try:
        async with factory() as session:
            task = Task(
                id=task_id,
                user_id=uuid.UUID(MCP_USER_ID),
                session_id=None,
                status=status,
                task_type=task_type,
                params=params,
                expression=expression,
                result=result_summary,
                error=error,
            )
            session.add(task)
            await session.commit()
            logger.info(f"MCP call tracked: {task_type} task_id={task_id} ({elapsed:.1f}s)")
    except Exception as e:
        logger.warning(f"Failed to persist MCP call: {e}")


def _fire_and_forget(coro):
    """Schedule an async coroutine for fire-and-forget execution.

    In HTTP mode (FastAPI/uvicorn), submits to the running event loop via
    create_task so the DB session stays on the same loop.
    In stdio mode (no running loop), falls back to a background thread.
    """
    try:
        loop = asyncio.get_running_loop()
        # Running inside an async context (HTTP mode) — schedule on same loop
        loop.create_task(coro)
        return
    except RuntimeError:
        pass

    # No running loop (stdio mode) — use a background thread
    def _run():
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.warning(f"MCP tracking error: {e}")
    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=5)


def _extract_summary(result_str: str, task_type: str) -> dict | None:
    """Extract a compact summary from the tool's JSON result."""
    try:
        data = json.loads(result_str)
        if isinstance(data, str):
            data = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None

    if "error" in data:
        return data

    if task_type == "mcp_backtest":
        return {
            "report_path": data.get("report_path"),
            "metrics": data.get("metrics"),
        }
    elif task_type == "mcp_score":
        return {
            "score": data.get("score"),
            "grade": data.get("grade"),
            "key_metrics": data.get("key_metrics"),
        }
    elif task_type in ("mcp_antioverfit", "mcp_rolling"):
        return {
            "score": data.get("score", data.get("composite_score")),
            "recommendation": data.get("recommendation"),
        }
    elif task_type == "mcp_wq_brain":
        return {
            "alpha_id": data.get("alpha_id"),
            "is_metrics": data.get("is_metrics"),
            "submittable": data.get("submittable"),
            "submitted": data.get("submitted"),
        }
    return None


def track_mcp_result(task_type: str, expression: str, params: dict,
                     result_str: str | None, error: str | None, elapsed: float):
    """Inline tracking call — use inside MCP tool function bodies.

    Parses the result JSON for a summary and fires off a background DB write.
    Safe to call from sync context; never raises.
    """
    try:
        summary = None
        if result_str:
            try:
                parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
                inner = parsed.get("result", parsed) if isinstance(parsed, dict) else parsed
                summary = _extract_summary(
                    inner if isinstance(inner, str) else json.dumps(inner),
                    task_type,
                )
            except Exception:
                summary = None

        _fire_and_forget(
            _persist_mcp_call(
                task_type=task_type,
                expression=expression,
                params=params,
                result_summary=summary,
                error=error,
                elapsed=elapsed,
            )
        )
    except Exception as e:
        logger.warning(f"MCP tracking failed: {e}")
