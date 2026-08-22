import os
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Set environment variables BEFORE importing the app
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@postgres:5432/orders_test_db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["TESTING"] = "1"


async def _ensure_test_database():
    admin_url = "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'orders_test_db'")
            )
            if not result.scalar():
                await conn.execute(text("CREATE DATABASE orders_test_db"))
    finally:
        await admin_engine.dispose()


# Run database creation before importing app
asyncio.run(_ensure_test_database())

from app.core.config import settings
settings.testing = True
settings.database_url = os.environ["DATABASE_URL"]

from app.main import app
from app.db.session import AsyncSessionLocal


async def _clean_db_async():
    """Delete all rows from all tables."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM order_items"))
        await db.execute(text("DELETE FROM orders"))
        await db.execute(text("DELETE FROM products"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    """Synchronous cleanup – runs async code via asyncio.run."""
    asyncio.run(_clean_db_async())
    yield