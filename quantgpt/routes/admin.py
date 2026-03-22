"""Admin panel routes: login, overview, users, tasks, feedbacks."""

import os
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, Task, Feedback, SavedFactor, FeaturedFactor
from ..auth import create_admin_token, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    password: str


@router.post("/login")
async def admin_login(req: AdminLoginRequest):
    """Authenticate admin with password, return JWT."""
    expected = os.environ.get("QUANTGPT_ADMIN_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="管理员密码未配置")
    if req.password != expected:
        raise HTTPException(status_code=401, detail="密码错误")
    token = create_admin_token()
    return {"token": token}


@router.get("/overview", dependencies=[Depends(require_admin)])
async def admin_overview(db: AsyncSession = Depends(get_db)):
    """Aggregated stats: user count, task count, success rate, today active."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    user_count_q = await db.execute(select(func.count(User.id)))
    user_count = user_count_q.scalar() or 0

    task_count_q = await db.execute(select(func.count(Task.id)))
    task_count = task_count_q.scalar() or 0

    success_count_q = await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )
    success_count = success_count_q.scalar() or 0
    success_rate = round(success_count / task_count * 100, 1) if task_count > 0 else 0

    today_active_q = await db.execute(
        select(func.count(func.distinct(Task.user_id))).where(
            Task.created_at >= today_start
        )
    )
    today_active = today_active_q.scalar() or 0

    feedback_count_q = await db.execute(select(func.count(Feedback.id)))
    feedback_count = feedback_count_q.scalar() or 0

    unresolved_q = await db.execute(
        select(func.count(Feedback.id)).where(Feedback.resolved == False)  # noqa: E712
    )
    unresolved_count = unresolved_q.scalar() or 0

    # Task status distribution (for pie chart)
    status_dist_q = await db.execute(
        select(Task.status, func.count(Task.id))
        .group_by(Task.status)
    )
    status_distribution = [
        {"name": row[0], "value": row[1]} for row in status_dist_q.all()
    ]

    # Daily task counts for last 7 days (for trend chart)
    seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_q = await db.execute(
        select(
            func.date_trunc("day", Task.created_at).label("day"),
            func.count(Task.id),
        )
        .where(Task.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    daily_map = {row[0].strftime("%m-%d"): row[1] for row in daily_q.all()}
    daily_tasks = []
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        key = d.strftime("%m-%d")
        daily_tasks.append({"date": key, "count": daily_map.get(key, 0)})

    # Daily new user registrations for last 30 days (for user trend chart)
    thirty_days_ago = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_user_q = await db.execute(
        select(
            func.date_trunc("day", User.created_at).label("day"),
            func.count(User.id),
        )
        .where(User.created_at >= thirty_days_ago)
        .group_by("day")
        .order_by("day")
    )
    daily_user_map = {row[0].strftime("%m-%d"): row[1] for row in daily_user_q.all()}

    # Cumulative user count before the 30-day window
    base_user_q = await db.execute(
        select(func.count(User.id)).where(User.created_at < thirty_days_ago)
    )
    base_user_count = base_user_q.scalar() or 0

    user_trend = []
    cumulative = base_user_count
    for i in range(30):
        d = thirty_days_ago + timedelta(days=i)
        key = d.strftime("%m-%d")
        new_users = daily_user_map.get(key, 0)
        cumulative += new_users
        user_trend.append({"date": key, "new_users": new_users, "total_users": cumulative})

    return {
        "user_count": user_count,
        "task_count": task_count,
        "success_rate": success_rate,
        "today_active": today_active,
        "feedback_count": feedback_count,
        "unresolved_feedback_count": unresolved_count,
        "status_distribution": status_distribution,
        "daily_tasks": daily_tasks,
        "user_trend": user_trend,
    }


@router.get("/users", dependencies=[Depends(require_admin)])
async def admin_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated user list with task counts."""
    offset = (page - 1) * page_size

    # Total count
    total_q = await db.execute(select(func.count(User.id)))
    total = total_q.scalar() or 0

    # Users with task count subquery
    task_count_sub = (
        select(Task.user_id, func.count(Task.id).label("task_count"))
        .group_by(Task.user_id)
        .subquery()
    )

    query = (
        select(User, task_count_sub.c.task_count)
        .outerjoin(task_count_sub, User.id == task_count_sub.c.user_id)
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.all()

    users = []
    for user, task_count in rows:
        users.append({
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "is_active": user.is_active,
            "task_count": task_count or 0,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        })

    return {"users": users, "total": total, "page": page, "page_size": page_size}


@router.get("/tasks", dependencies=[Depends(require_admin)])
async def admin_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="按状态过滤"),
    user_id: str | None = Query(None, description="按用户 ID 过滤"),
    db: AsyncSession = Depends(get_db),
):
    """Paginated task list with filters."""
    offset = (page - 1) * page_size

    # Base count query
    count_query = select(func.count(Task.id))
    if status:
        count_query = count_query.where(Task.status == status)
    if user_id:
        count_query = count_query.where(Task.user_id == user_id)
    total_q = await db.execute(count_query)
    total = total_q.scalar() or 0

    # Main query with user email
    query = (
        select(Task, User.email)
        .outerjoin(User, Task.user_id == User.id)
    )
    if status:
        query = query.where(Task.status == status)
    if user_id:
        query = query.where(Task.user_id == user_id)
    query = query.order_by(desc(Task.created_at)).offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    tasks = []
    for task, email in rows:
        tasks.append({
            "id": task.id,
            "user_email": email,
            "user_id": str(task.user_id),
            "status": task.status,
            "expression": task.expression,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        })

    return {"tasks": tasks, "total": total, "page": page, "page_size": page_size}


@router.get("/feedbacks", dependencies=[Depends(require_admin)])
async def admin_feedbacks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated feedback list."""
    offset = (page - 1) * page_size

    total_q = await db.execute(select(func.count(Feedback.id)))
    total = total_q.scalar() or 0

    query = (
        select(Feedback, User.email)
        .outerjoin(User, Feedback.user_id == User.id)
        .order_by(desc(Feedback.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.all()

    feedbacks = []
    for fb, email in rows:
        feedbacks.append({
            "id": str(fb.id),
            "user_email": email,
            "description": fb.description,
            "screenshot_path": fb.screenshot_path,
            "task_id": fb.task_id,
            "resolved": fb.resolved,
            "resolved_at": fb.resolved_at.isoformat() if fb.resolved_at else None,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        })

    return {"feedbacks": feedbacks, "total": total, "page": page, "page_size": page_size}


@router.patch("/feedbacks/{feedback_id}/resolve", dependencies=[Depends(require_admin)])
async def resolve_feedback(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark feedback as resolved."""
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")

    fb.resolved = True
    fb.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    # Send resolved notification email (fire-and-forget)
    if fb.user_id:
        user = await db.get(User, fb.user_id)
        if user and user.email:
            import asyncio
            from ..email_service import send_feedback_resolved_email

            async def _safe_send():
                try:
                    await send_feedback_resolved_email(user.email, str(fb.id), fb.description)
                except Exception as e:
                    logger.warning(f"Failed to send feedback resolved email to {user.email}: {e}")

            asyncio.create_task(_safe_send())

    return {"id": str(fb.id), "resolved": True, "resolved_at": fb.resolved_at.isoformat()}


# ---- Factor Wall Management ----

@router.get("/factor-wall", dependencies=[Depends(require_admin)])
async def admin_factor_wall(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="pending|approved|rejected"),
    db: AsyncSession = Depends(get_db),
):
    """List all featured factors for admin review."""
    offset = (page - 1) * page_size

    count_q = select(func.count(FeaturedFactor.id))
    if status:
        count_q = count_q.where(FeaturedFactor.status == status)
    total_q = await db.execute(count_q)
    total = total_q.scalar() or 0

    query = (
        select(FeaturedFactor, User.email)
        .outerjoin(User, FeaturedFactor.user_id == User.id)
    )
    if status:
        query = query.where(FeaturedFactor.status == status)
    query = query.order_by(desc(FeaturedFactor.created_at)).offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    factors = []
    for f, email in rows:
        factors.append({
            "id": str(f.id),
            "expression": f.expression,
            "title": f.title,
            "description": f.description,
            "metrics": f.metrics,
            "params": f.params,
            "source": f.source,
            "status": f.status,
            "sort_order": f.sort_order,
            "user_email": email,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
        })

    return {"factors": factors, "total": total, "page": page, "page_size": page_size}


class CreateFeaturedFactorRequest(BaseModel):
    expression: str
    title: str | None = None
    description: str | None = None
    metrics: dict | None = None
    backtest_summary: dict | None = None
    params: dict | None = None
    source: str = "official"
    sort_order: int = 0


@router.post("/factor-wall", dependencies=[Depends(require_admin)], status_code=201)
async def admin_create_featured_factor(
    req: CreateFeaturedFactorRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin: create an official featured factor (auto-approved)."""
    import uuid
    factor = FeaturedFactor(
        id=uuid.uuid4(),
        expression=req.expression,
        title=req.title or req.expression[:60],
        description=req.description,
        metrics=req.metrics,
        backtest_summary=req.backtest_summary,
        params=req.params,
        source=req.source,
        status="approved",
        sort_order=req.sort_order,
        created_at=datetime.now(timezone.utc),
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(factor)
    await db.commit()
    return {"id": str(factor.id), "status": "approved"}


class ReviewFactorRequest(BaseModel):
    status: str  # 'approved' | 'rejected'
    sort_order: int | None = None


@router.patch("/factor-wall/{factor_id}", dependencies=[Depends(require_admin)])
async def admin_review_factor(
    factor_id: str,
    req: ReviewFactorRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin: approve/reject a factor wall submission."""
    import uuid as uuid_mod
    result = await db.execute(
        select(FeaturedFactor).where(FeaturedFactor.id == uuid_mod.UUID(factor_id))
    )
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")

    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态只能是 approved 或 rejected")

    factor.status = req.status
    factor.reviewed_at = datetime.now(timezone.utc)
    if req.sort_order is not None:
        factor.sort_order = req.sort_order

    await db.commit()
    return {"id": str(factor.id), "status": factor.status}


@router.delete("/factor-wall/{factor_id}", dependencies=[Depends(require_admin)], status_code=204)
async def admin_delete_featured_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Admin: delete a featured factor."""
    import uuid as uuid_mod
    result = await db.execute(
        select(FeaturedFactor).where(FeaturedFactor.id == uuid_mod.UUID(factor_id))
    )
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")
    await db.delete(factor)
    await db.commit()
