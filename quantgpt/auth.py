"""JWT creation/verification and FastAPI authentication dependency."""

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import User

logger = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"

# Email send rate limit (in-memory): email -> timestamp
_email_rate: dict[str, float] = {}
EMAIL_RATE_LIMIT_SECONDS = 60


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    return secret


def create_access_token(user_id: UUID, email: str) -> str:
    expire_hours = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "24"))
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm=_JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    expire_days = int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, _get_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")


def check_email_rate_limit(email: str) -> None:
    """Raise HTTPException if email was sent too recently."""
    now = time.monotonic()
    last_sent = _email_rate.get(email)
    if last_sent and now - last_sent < EMAIL_RATE_LIMIT_SECONDS:
        remaining = int(EMAIL_RATE_LIMIT_SECONDS - (now - last_sent))
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {remaining} 秒后重试")
    _email_rate[email] = now


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header or query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Fallback for SSE (EventSource can't set headers)
    token = request.query_params.get("token")
    if token:
        return token
    raise HTTPException(status_code=401, detail="未提供认证信息")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract JWT → load user from DB."""
    token = _extract_token(request)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="无效的 Token 类型")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的 Token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


GUEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def create_guest_token() -> str:
    """Create a signed JWT for anonymous/guest access (7-day expiry)."""
    payload = {
        "sub": GUEST_USER_ID,
        "type": "guest",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm=_JWT_ALGORITHM)


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None for guest/anonymous requests."""
    try:
        token = _extract_token(request)
    except HTTPException:
        return None  # No token = guest
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    if payload.get("type") == "guest":
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user


def create_admin_token() -> str:
    """Create JWT for admin with type='admin', 24h expiry."""
    payload = {
        "type": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret(), algorithm=_JWT_ALGORITHM)


async def require_admin(request: Request) -> bool:
    """FastAPI dependency: verify admin JWT token."""
    token = _extract_token(request)
    payload = decode_token(token)
    if payload.get("type") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return True


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
