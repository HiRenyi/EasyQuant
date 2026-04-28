"""Daily market summary routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import DailySummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/daily-summaries", tags=["daily-summary"])


@router.get("")
async def list_summaries(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """列出最近的盘后总结。"""
    result = await db.execute(
        select(DailySummary)
        .where(DailySummary.market == "a_share")
        .order_by(desc(DailySummary.date))
        .limit(limit)
    )
    summaries = result.scalars().all()
    return {
        "summaries": [
            {
                "id": str(s.id),
                "date": s.date,
                "title": s.title,
                "metrics": s.metrics,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in summaries
        ]
    }


@router.get("/{date}")
async def get_summary(
    date: str,
    db: AsyncSession = Depends(get_db),
):
    """获取指定日期的盘后总结。"""
    result = await db.execute(
        select(DailySummary).where(
            DailySummary.date == date,
            DailySummary.market == "a_share",
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="该日期暂无盘后总结")

    return {
        "id": str(summary.id),
        "date": summary.date,
        "market": summary.market,
        "title": summary.title,
        "content": summary.content,
        "metrics": summary.metrics,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
    }


@router.post("/generate", status_code=201)
async def trigger_generate(
    date: str = Query(None, description="Target date YYYY-MM-DD, defaults to today"),
    db: AsyncSession = Depends(get_db),
):
    """手动触发生成盘后总结（可指定日期）。"""
    from ..daily_summary import generate_daily_summary

    result = await generate_daily_summary(db, market="a_share", date=date)
    if result is None:
        return {"message": "该日期总结已存在，无需重复生成"}
    return result
