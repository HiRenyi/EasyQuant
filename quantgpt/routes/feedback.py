"""Feedback submission routes."""

import base64
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_db
from ..models import Feedback as FeedbackModel
from ..models import User
from ..task_store import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

_FEEDBACK_DIR = Path(__file__).resolve().parent.parent.parent / "feedback"
_FEEDBACK_WEBHOOK_URL = os.environ.get("QUANTGPT_FEEDBACK_WEBHOOK", "")
_FEEDBACK_WEBHOOK_SECRET = os.environ.get("QUANTGPT_FEEDBACK_WEBHOOK_SECRET", "")
MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024
_MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024


class FeedbackRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000, description="问题描述")
    screenshot: str | None = Field(None, description="截图 base64 (data:image/png;base64,...)")
    task_id: str | None = Field(None, description="关联的任务 ID")
    page_url: str | None = Field(None, max_length=500, description="当前页面 URL")
    user_agent: str | None = Field(None, max_length=500, description="浏览器 UA")


def _feishu_sign(secret: str, timestamp: int) -> str:
    import hashlib
    import hmac
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _send_webhook(webhook_url: str, feedback_data: dict) -> bool:
    import httpx

    user_email = feedback_data.get("user_email", "unknown")
    description = feedback_data.get("description", "")
    task_id = feedback_data.get("task_id", "")
    page_url = feedback_data.get("page_url", "")
    created_at = feedback_data.get("created_at", "")
    screenshot_url = feedback_data.get("screenshot_url", "")

    elements: list[dict] = [
        {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**用户**\n{user_email}"}}],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**时间**\n{created_at}"}}],
                },
            ],
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**问题描述**\n{description}"},
        },
    ]

    extra_parts = []
    if task_id:
        extra_parts.append(f"**任务 ID:** `{task_id}`")
    if page_url:
        extra_parts.append(f"**页面:** {page_url}")
    if screenshot_url:
        extra_parts.append(f"**截图:** [查看截图]({screenshot_url})")
    if extra_parts:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(extra_parts)},
        })

    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "QuantGPT Feedback Bot"}],
    })

    payload: dict = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "新用户反馈"},
                "template": "orange",
            },
            "elements": elements,
        },
    }

    if _FEEDBACK_WEBHOOK_SECRET:
        timestamp = int(time.time())
        sign = _feishu_sign(_FEEDBACK_WEBHOOK_SECRET, timestamp)
        payload["timestamp"] = str(timestamp)
        payload["sign"] = sign

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook_url, json=payload)
            if resp.status_code < 300:
                body = resp.json() if resp.text else {}
                if body.get("code", 0) != 0:
                    logger.warning(f"Webhook API error: {body}")
                    return False
                return True
            logger.warning(f"Webhook returned {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Webhook send failed: {e}")
        return False


def _save_screenshot_to_disk(feedback_id: str, screenshot_b64: str) -> str | None:
    try:
        if "," in screenshot_b64:
            screenshot_b64 = screenshot_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(screenshot_b64)

        if len(img_bytes) > _MAX_SCREENSHOT_BYTES:
            logger.warning(f"Screenshot too large: {len(img_bytes)} bytes")
            return None

        if img_bytes[:4] == b'\x89PNG':
            ext = ".png"
        elif img_bytes[:3] == b'\xff\xd8\xff':
            ext = ".jpg"
        else:
            logger.warning("Screenshot is not a valid PNG or JPEG")
            return None

        _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{feedback_id}{ext}"
        filepath = _FEEDBACK_DIR / filename
        filepath.write_bytes(img_bytes)
        return str(filepath.relative_to(Path(__file__).resolve().parent.parent.parent))
    except Exception as e:
        logger.error(f"Screenshot save failed: {e}")
        return None


@router.post("/api/v1/feedback", status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    if req.screenshot and len(req.screenshot) > MAX_SCREENSHOT_SIZE:
        raise HTTPException(status_code=400, detail="截图文件过大（最大5MB）")

    feedback_id = uuid.uuid4().hex[:16]
    now = datetime.now()

    screenshot_path = None
    if req.screenshot:
        screenshot_path = _save_screenshot_to_disk(feedback_id, req.screenshot)

    feedback_record = FeedbackModel(
        user_id=user.id,
        description=req.description,
        screenshot_path=screenshot_path,
        task_id=req.task_id,
        user_agent=req.user_agent,
        page_url=req.page_url,
        webhook_sent=False,
    )
    db.add(feedback_record)

    webhook_sent = False
    if _FEEDBACK_WEBHOOK_URL:
        screenshot_url = ""
        if screenshot_path:
            host = request.headers.get("host", "localhost:8003")
            scheme = request.headers.get("x-forwarded-proto", "http")
            screenshot_url = f"{scheme}://{host}/api/v1/feedback-screenshots/{feedback_id}"

        feedback_data = {
            "user_email": user.email,
            "description": req.description,
            "task_id": req.task_id,
            "page_url": req.page_url,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "screenshot_url": screenshot_url,
        }
        webhook_sent = _send_webhook(_FEEDBACK_WEBHOOK_URL, feedback_data)
        feedback_record.webhook_sent = webhook_sent

    _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    local_record = {
        "id": feedback_id,
        "user_email": user.email,
        "description": req.description,
        "task_id": req.task_id,
        "page_url": req.page_url,
        "user_agent": req.user_agent,
        "screenshot_path": screenshot_path,
        "webhook_sent": webhook_sent,
        "created_at": now.isoformat(),
    }
    json_path = _FEEDBACK_DIR / f"{feedback_id}.json"
    json_path.write_text(json.dumps(local_record, ensure_ascii=False, indent=2))

    await db.commit()

    import asyncio

    from ..email_service import send_feedback_received_email

    async def _safe_send():
        try:
            await send_feedback_received_email(user.email, feedback_id, req.description)
        except Exception as e:
            logger.warning(f"Failed to send feedback confirmation email to {user.email}: {e}")

    asyncio.create_task(_safe_send())

    logger.info(f"Feedback {feedback_id} from {user.email} (webhook={'OK' if webhook_sent else 'skip/fail'})")

    return {
        "id": feedback_id,
        "status": "received",
        "webhook_sent": webhook_sent,
    }


_SAFE_FEEDBACK_ID_RE = re.compile(r"^[a-f0-9]{16}$")


@router.get("/api/v1/feedback-screenshots/{feedback_id}")
async def get_feedback_screenshot(feedback_id: str):
    feedback_id = feedback_id.removesuffix(".png")
    if not _SAFE_FEEDBACK_ID_RE.match(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    filepath = (_FEEDBACK_DIR / f"{feedback_id}.png").resolve()
    if not filepath.is_relative_to(_FEEDBACK_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(filepath), media_type="image/png")
