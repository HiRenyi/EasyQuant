"""Session CRUD routes."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, Session, Task as TaskModel, Report as ReportModel, SavedFactor
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    name: str | None = Field(None, max_length=200, description="会话名称")


class RenameSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="新名称")


@router.post("", status_code=201)
async def create_session(
    req: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新会话。"""
    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        name=req.name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "id": str(session.id),
        "name": session.name,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.get("")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户所有会话，按 updated_at 降序。"""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(desc(Session.updated_at))
    )
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "id": str(s.id),
                "name": s.name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }


@router.patch("/{session_id}")
async def rename_session(
    session_id: str,
    req: RenameSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重命名会话。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.name = req.name
    await db.commit()
    return {
        "id": str(session.id),
        "name": session.name,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话（级联删除关联任务）。"""
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete in FK order: reports → saved_factors → tasks → session
    task_ids_result = await db.execute(
        select(TaskModel.id).where(TaskModel.session_id == session.id)
    )
    task_ids = [row[0] for row in task_ids_result.fetchall()]

    if task_ids:
        await db.execute(
            ReportModel.__table__.delete().where(ReportModel.task_id.in_(task_ids))
        )
        await db.execute(
            SavedFactor.__table__.delete().where(SavedFactor.task_id.in_(task_ids))
        )
        await db.execute(
            TaskModel.__table__.delete().where(TaskModel.session_id == session.id)
        )
    await db.delete(session)
    await db.commit()
