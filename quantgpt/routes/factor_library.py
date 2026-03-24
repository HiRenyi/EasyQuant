"""Factor Library routes — save/list/update/delete user's saved factors."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func, cast, Float, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..auth import get_current_user, get_optional_user
from ..models import User, SavedFactor, FeaturedFactor

router = APIRouter(prefix="/api/v1/factor-library", tags=["factor-library"])


class SaveFactorRequest(BaseModel):
    task_id: str | None = None
    expression: str
    name: str | None = None
    note: str | None = None
    tags: list[str] = Field(default_factory=list)
    metrics: dict | None = None
    backtest_summary: dict | None = None
    params: dict | None = None
    report_url: str | None = None


class UpdateFactorRequest(BaseModel):
    name: str | None = None
    note: str | None = None
    tags: list[str] | None = None


def _factor_to_dict(f: SavedFactor) -> dict:
    return {
        "id": str(f.id),
        "task_id": f.task_id,
        "expression": f.expression,
        "name": f.name,
        "note": f.note,
        "tags": f.tags or [],
        "metrics": f.metrics,
        "backtest_summary": f.backtest_summary,
        "params": f.params,
        "report_url": f.report_url,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.post("", status_code=201)
async def save_factor(
    req: SaveFactorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 防重复：同一用户同一表达式不允许重复收藏
    existing = await db.execute(
        select(SavedFactor).where(
            SavedFactor.user_id == user.id,
            SavedFactor.expression == req.expression,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该因子已收藏")

    factor = SavedFactor(
        id=uuid.uuid4(),
        user_id=user.id,
        task_id=req.task_id,
        expression=req.expression,
        name=req.name or req.expression[:60],
        note=req.note,
        tags=req.tags,
        metrics=req.metrics,
        backtest_summary=req.backtest_summary,
        params=req.params,
        report_url=req.report_url,
        market="a_share",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(factor)
    await db.commit()
    await db.refresh(factor)
    return _factor_to_dict(factor)


@router.get("")
async def list_factors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedFactor)
        .where(SavedFactor.user_id == user.id)
        .order_by(desc(SavedFactor.created_at))
    )
    factors = result.scalars().all()
    return {"factors": [_factor_to_dict(f) for f in factors]}


@router.patch("/{factor_id}")
async def update_factor(
    factor_id: str,
    req: UpdateFactorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedFactor).where(
            SavedFactor.id == uuid.UUID(factor_id),
            SavedFactor.user_id == user.id,
        )
    )
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    if req.name is not None:
        factor.name = req.name
    if req.note is not None:
        factor.note = req.note
    if req.tags is not None:
        factor.tags = req.tags
    factor.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(factor)
    return _factor_to_dict(factor)


@router.delete("/{factor_id}", status_code=204)
async def delete_factor(
    factor_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedFactor).where(
            SavedFactor.id == uuid.UUID(factor_id),
            SavedFactor.user_id == user.id,
        )
    )
    factor = result.scalar_one_or_none()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    await db.delete(factor)
    await db.commit()


# ---- Factor Wall (public) ----

@router.get("/wall")
async def factor_wall(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: approved featured factors for the factor wall."""
    result = await db.execute(
        select(FeaturedFactor)
        .where(FeaturedFactor.status == "approved")
        .order_by(desc(FeaturedFactor.sort_order), desc(FeaturedFactor.created_at))
        .limit(limit)
    )
    factors = result.scalars().all()

    return {
        "factors": [
            {
                "id": str(f.id),
                "expression": f.expression,
                "title": f.title,
                "description": f.description,
                "metrics": {
                    "sharpe": (f.metrics or {}).get("sharpe"),
                    "cagr": (f.metrics or {}).get("cagr"),
                    "max_drawdown": (f.metrics or {}).get("max_drawdown"),
                    "ic_mean": (f.metrics or {}).get("ic_mean"),
                    "score": (f.metrics or {}).get("score"),
                    "grade": (f.metrics or {}).get("grade"),
                },
                "params": {
                    "universe": (f.params or {}).get("universe"),
                    "holding_period": (f.params or {}).get("holding_period"),
                },
                "source": f.source,
            }
            for f in factors
        ],
        "total": len(factors),
    }


class SubmitFactorRequest(BaseModel):
    expression: str
    title: str | None = None
    description: str | None = None
    metrics: dict | None = None
    backtest_summary: dict | None = None
    params: dict | None = None
    report_url: str | None = None


@router.post("/wall/submit", status_code=201)
async def submit_to_wall(
    req: SubmitFactorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a factor to the factor wall (pending approval)."""
    # Check for duplicate submission by same user
    existing = await db.execute(
        select(FeaturedFactor).where(
            FeaturedFactor.user_id == user.id,
            FeaturedFactor.expression == req.expression,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该因子已投稿")

    factor = FeaturedFactor(
        id=uuid.uuid4(),
        user_id=user.id,
        expression=req.expression,
        title=req.title or req.expression[:60],
        description=req.description,
        metrics=req.metrics,
        backtest_summary=req.backtest_summary,
        params=req.params,
        report_url=req.report_url,
        source="submission",
        status="pending",
        market="a_share",
        created_at=datetime.now(timezone.utc),
    )
    db.add(factor)
    await db.commit()
    return {"id": str(factor.id), "status": "pending"}
