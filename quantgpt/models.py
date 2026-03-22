"""SQLAlchemy ORM models for QuantGPT."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index, Float,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # bcrypt, NULL=未设置密码
    nickname = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user", lazy="selectin")
    tasks = relationship("Task", back_populates="user", lazy="selectin")
    reports = relationship("Report", back_populates="user", lazy="selectin")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_verification_codes_email_used", "email", "used"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")
    tasks = relationship("Task", back_populates="session", lazy="selectin")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(12), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="pending")
    task_type = Column(String(20), nullable=True, default="backtest")
    parent_task_id = Column(String(12), ForeignKey("tasks.id"), nullable=True)
    params = Column(JSON, nullable=True)
    expression = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("User", back_populates="tasks")
    session = relationship("Session", back_populates="tasks")
    reports = relationship("Report", back_populates="task", lazy="selectin")


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(String(12), ForeignKey("tasks.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="reports")
    task = relationship("Task", back_populates="reports")


class SavedFactor(Base):
    __tablename__ = "saved_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(String(12), ForeignKey("tasks.id"), nullable=True)
    expression = Column(Text, nullable=False)
    name = Column(String(200), nullable=True)       # 用户自定义名称
    note = Column(Text, nullable=True)              # 备注
    tags = Column(JSON, nullable=True)              # 标签列表
    metrics = Column(JSON, nullable=True)           # 快照：report_metrics
    backtest_summary = Column(JSON, nullable=True)  # 快照：backtest_summary
    params = Column(JSON, nullable=True)            # 回测参数
    report_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("User")


class FeaturedFactor(Base):
    __tablename__ = "featured_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expression = Column(Text, nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)
    backtest_summary = Column(JSON, nullable=True)
    params = Column(JSON, nullable=True)
    report_url = Column(String(500), nullable=True)
    source = Column(String(20), nullable=False, default="submission")  # 'official' | 'submission'
    status = Column(String(20), nullable=False, default="pending")     # 'pending' | 'approved' | 'rejected'
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    screenshot_path = Column(String(500), nullable=True)
    task_id = Column(String(12), nullable=True)
    user_agent = Column(String(500), nullable=True)
    page_url = Column(String(500), nullable=True)
    webhook_sent = Column(Boolean, default=False, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User")


class PaperStrategy(Base):
    __tablename__ = "paper_strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    expression = Column(Text, nullable=False)
    universe = Column(String(20), nullable=False, default="hs300")
    holding_period = Column(Integer, nullable=False, default=5)
    n_groups = Column(Integer, nullable=False, default=5)
    initial_capital = Column(Float, nullable=False, default=1_000_000.0)
    current_value = Column(Float, nullable=False, default=1_000_000.0)
    status = Column(String(20), nullable=False, default="active")  # active | paused | stopped
    last_rebalance_date = Column(String(10), nullable=True)
    next_rebalance_date = Column(String(10), nullable=True)
    source_task_id = Column(String(12), ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("User")
    snapshots = relationship("PaperSnapshot", back_populates="strategy", lazy="selectin",
                             order_by="PaperSnapshot.date")
    orders = relationship("PaperOrder", back_populates="strategy", lazy="selectin")


class PaperSnapshot(Base):
    __tablename__ = "paper_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("paper_strategies.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    portfolio_value = Column(Float, nullable=False)
    daily_return = Column(Float, nullable=True)
    positions = Column(JSON, nullable=True)  # {stock_code: shares}

    strategy = relationship("PaperStrategy", back_populates="snapshots")

    __table_args__ = (
        Index("ix_paper_snapshots_strategy_date", "strategy_id", "date", unique=True),
    )


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("paper_strategies.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    stock_code = Column(String(20), nullable=False)
    direction = Column(String(4), nullable=False)  # buy | sell
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    commission = Column(Float, nullable=False, default=0.0)

    strategy = relationship("PaperStrategy", back_populates="orders")
