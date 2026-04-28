"""Factor Library routes — save/list/update/delete user's saved factors."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_db
from ..models import SavedFactor, User

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
