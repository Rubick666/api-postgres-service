from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.routers import health

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager – runs on startup and shutdown.
    """
    # Startup: Create database tables (if they don't exist)
    # In production, you'd use Alembic migrations instead.
    # We'll use Alembic later, but for development we auto-create.
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created (if not already).")
    yield
    # Shutdown: nothing special here

app = FastAPI(
    title="Orders Service API",
    version="0.1.0",
    description="PostgreSQL-backed orders and transactions service",
    lifespan=lifespan,
)

# Include routers
app.include_router(health.router)

@app.get("/")
async def root():
    return {"message": "Orders Service is running"}