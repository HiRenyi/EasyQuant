"""Paper trading (模拟盘) routes."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import PaperStrategy, PaperSnapshot, PaperOrder, User
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/paper", tags=["paper"])

MAX_STRATEGIES_PER_USER = 5


class CreateStrategyRequest(BaseModel):
    expression: str
    name: str | None = None
    universe: str = "hs300"
    holding_period: int = Field(default=5, ge=1, le=60)
    n_groups: int = Field(default=5, ge=2, le=20)
    initial_capital: float = Field(default=1_000_000.0, ge=10_000, le=100_000_000)
    source_task_id: str | None = None


class UpdateStrategyRequest(BaseModel):
    status: str  # active | paused | stopped


# ---- Routes ----


@router.post("/strategies", status_code=201)
async def create_strategy(
    req: CreateStrategyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建模拟盘策略。"""
    # Check limit
    count_q = await db.execute(
        select(func.count(PaperStrategy.id)).where(
            PaperStrategy.user_id == user.id,
            PaperStrategy.status != "stopped",
        )
    )
    count = count_q.scalar() or 0
    if count >= MAX_STRATEGIES_PER_USER:
        raise HTTPException(status_code=400, detail=f"最多创建 {MAX_STRATEGIES_PER_USER} 个活跃策略")

    strategy = PaperStrategy(
        id=uuid.uuid4(),
        user_id=user.id,
        name=req.name or req.expression[:40],
        expression=req.expression,
        universe=req.universe,
        holding_period=req.holding_period,
        n_groups=req.n_groups,
        initial_capital=req.initial_capital,
        current_value=req.initial_capital,
        status="active",
        source_task_id=req.source_task_id,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)

    return _strategy_to_dict(strategy)


@router.get("/strategies")
async def list_strategies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的模拟盘策略列表。"""
    result = await db.execute(
        select(PaperStrategy)
        .where(PaperStrategy.user_id == user.id)
        .order_by(desc(PaperStrategy.created_at))
    )
    strategies = result.scalars().all()
    return {"strategies": [_strategy_to_dict(s) for s in strategies]}


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取策略详情 + 净值曲线。"""
    strategy = await _get_user_strategy(db, strategy_id, user.id)

    # Fetch snapshots
    snap_q = await db.execute(
        select(PaperSnapshot)
        .where(PaperSnapshot.strategy_id == strategy.id)
        .order_by(PaperSnapshot.date)
    )
    snapshots = snap_q.scalars().all()

    data = _strategy_to_dict(strategy)
    data["nav_curve"] = [
        {"date": s.date, "value": s.portfolio_value, "daily_return": s.daily_return}
        for s in snapshots
    ]
    return data


@router.get("/strategies/{strategy_id}/positions")
async def get_positions(
    strategy_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前持仓。"""
    strategy = await _get_user_strategy(db, strategy_id, user.id)

    # Latest snapshot with positions
    snap_q = await db.execute(
        select(PaperSnapshot)
        .where(PaperSnapshot.strategy_id == strategy.id, PaperSnapshot.positions.isnot(None))
        .order_by(desc(PaperSnapshot.date))
        .limit(1)
    )
    snap = snap_q.scalar_one_or_none()
    positions = snap.positions if snap else {}
    return {"date": snap.date if snap else None, "positions": positions}


@router.get("/strategies/{strategy_id}/orders")
async def get_orders(
    strategy_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取交易记录。"""
    strategy = await _get_user_strategy(db, strategy_id, user.id)
    offset = (page - 1) * page_size

    total_q = await db.execute(
        select(func.count(PaperOrder.id)).where(PaperOrder.strategy_id == strategy.id)
    )
    total = total_q.scalar() or 0

    orders_q = await db.execute(
        select(PaperOrder)
        .where(PaperOrder.strategy_id == strategy.id)
        .order_by(desc(PaperOrder.date))
        .offset(offset)
        .limit(page_size)
    )
    orders = orders_q.scalars().all()

    return {
        "orders": [
            {
                "id": str(o.id),
                "date": o.date,
                "stock_code": o.stock_code,
                "direction": o.direction,
                "shares": o.shares,
                "price": o.price,
                "amount": o.amount,
                "commission": o.commission,
            }
            for o in orders
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    req: UpdateStrategyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """暂停/恢复/停止策略。"""
    if req.status not in ("active", "paused", "stopped"):
        raise HTTPException(status_code=400, detail="状态只能是 active / paused / stopped")

    strategy = await _get_user_strategy(db, strategy_id, user.id)

    if strategy.status == "stopped":
        raise HTTPException(status_code=400, detail="已停止的策略无法修改")

    strategy.status = req.status
    strategy.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _strategy_to_dict(strategy)


# ---- Helpers ----

async def _get_user_strategy(db: AsyncSession, strategy_id: str, user_id) -> PaperStrategy:
    import uuid as uuid_mod
    result = await db.execute(
        select(PaperStrategy).where(
            PaperStrategy.id == uuid_mod.UUID(strategy_id),
            PaperStrategy.user_id == user_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return strategy


def _strategy_to_dict(s: PaperStrategy) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "expression": s.expression,
        "universe": s.universe,
        "holding_period": s.holding_period,
        "n_groups": s.n_groups,
        "initial_capital": s.initial_capital,
        "current_value": s.current_value,
        "total_return": (s.current_value / s.initial_capital - 1) if s.initial_capital else 0,
        "status": s.status,
        "last_rebalance_date": s.last_rebalance_date,
        "next_rebalance_date": s.next_rebalance_date,
        "source_task_id": s.source_task_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
