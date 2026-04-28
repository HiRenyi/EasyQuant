"""Shared fixtures for QuantGPT tests."""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["AUTH_DISABLED"] = "false"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("QUANTGPT_ADMIN_PASSWORD", "test-admin-pw")

from quantgpt.models import Base, User
from quantgpt.auth import hash_password, create_access_token
from quantgpt.backtest import api_context
from quantgpt import db as db_module


@pytest.fixture(autouse=True)
def _enable_api_context():
    with api_context():
        yield


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine):
    """AsyncClient wired to the FastAPI app with an in-memory SQLite DB."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from quantgpt.api_server import app
    from quantgpt.db import get_db

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the DB and return it."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("test123456"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization headers with a valid access token for test_user."""
    token = create_access_token(test_user.id, test_user.email)
    return {"Authorization": f"Bearer {token}"}
