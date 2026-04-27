"""Authentication routes: send-code, verify-code, login, set-password, reset-password, refresh, me."""

import re
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, VerificationCode
from ..email_service import generate_code, send_verification_email
from ..auth import (
    create_access_token,
    create_guest_token,
    create_refresh_token,
    decode_token,
    check_email_rate_limit,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ---- Request/Response models ----

class SendCodeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        if len(v) > 255:
            raise ValueError("邮箱地址过长")
        return v


class VerifyCodeRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("验证码必须是 6 位数字")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()


class SetPasswordRequest(BaseModel):
    password: str
    old_password: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6 or len(v) > 64:
            raise ValueError("密码长度需在 6-64 字符之间")
        return v


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("验证码必须是 6 位数字")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6 or len(v) > 64:
            raise ValueError("密码长度需在 6-64 字符之间")
        return v


# ---- Routes ----

@router.post("/guest-token")
async def guest_token():
    """Issue a signed JWT for anonymous/guest access."""
    return {"access_token": create_guest_token(), "token_type": "bearer"}


@router.post("/send-code")
async def send_code(req: SendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Generate and send verification code to email."""
    check_email_rate_limit(req.email)

    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    vc = VerificationCode(email=req.email, code=code, expires_at=expires_at)
    db.add(vc)
    await db.flush()

    try:
        await send_verification_email(req.email, code)
    except Exception as e:
        logger.error(f"Failed to send email to {req.email}: {e}")
        raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return {"message": "验证码已发送", "expires_in": 300}


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    """Verify code and return JWT tokens. Auto-registers on first login."""
    # Find latest unused, unexpired code for this email
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == req.email,
            VerificationCode.used == False,  # noqa: E712
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    vc = result.scalar_one_or_none()

    if not vc:
        raise HTTPException(status_code=400, detail="验证码已过期或不存在，请重新获取")

    if vc.attempts >= 5:
        vc.used = True
        await db.flush()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新获取")

    vc.attempts += 1

    if vc.code != req.code:
        await db.flush()
        remaining = 5 - vc.attempts
        raise HTTPException(status_code=400, detail=f"验证码错误，还可尝试 {remaining} 次")

    # Code matched
    vc.used = True
    await db.flush()

    # Find or create user
    user_result = await db.execute(select(User).where(User.email == req.email))
    user = user_result.scalar_one_or_none()

    if not user:
        user = User(email=req.email)
        db.add(user)
        await db.flush()
        logger.info(f"New user registered: {req.email}")
    else:
        user.last_login_at = now
        await db.flush()

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "has_password": user.password_hash is not None,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    user_result = await db.execute(select(User).where(User.email == req.email))
    user = user_result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    if not user.password_hash:
        raise HTTPException(status_code=400, detail="该账号尚未设置密码，请使用验证码登录后设置密码")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "has_password": True,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.post("/set-password")
async def set_password(
    req: SetPasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or change password. Requires old_password if already set."""
    if user.password_hash:
        if not req.old_password:
            raise HTTPException(status_code=400, detail="请提供当前密码")
        if not verify_password(req.old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="当前密码错误")

    user.password_hash = hash_password(req.password)
    await db.flush()
    logger.info(f"Password set for user: {user.email}")

    return {"message": "密码设置成功", "has_password": True}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using verification code."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == req.email,
            VerificationCode.used == False,  # noqa: E712
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    vc = result.scalar_one_or_none()

    if not vc:
        raise HTTPException(status_code=400, detail="验证码已过期或不存在，请重新获取")

    if vc.attempts >= 5:
        vc.used = True
        await db.flush()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新获取")

    vc.attempts += 1

    if vc.code != req.code:
        await db.flush()
        remaining = 5 - vc.attempts
        raise HTTPException(status_code=400, detail=f"验证码错误，还可尝试 {remaining} 次")

    vc.used = True
    await db.flush()

    user_result = await db.execute(select(User).where(User.email == req.email))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(req.new_password)
    await db.flush()
    logger.info(f"Password reset for user: {user.email}")

    return {"message": "密码重置成功"}


@router.post("/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using a valid refresh token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的 refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    access_token = create_access_token(user.id, user.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return current user info."""
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "has_password": user.password_hash is not None,
        "subscribe_weekly": user.subscribe_weekly,
        "created_at": user.created_at.isoformat(),
    }


class SubscriptionUpdate(BaseModel):
    subscribe_weekly: bool


@router.patch("/subscription")
async def update_subscription(
    req: SubscriptionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update factor research report subscription preference."""
    user.subscribe_weekly = req.subscribe_weekly
    db.add(user)
    await db.commit()
    return {"subscribe_weekly": user.subscribe_weekly}
