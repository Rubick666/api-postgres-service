from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.models.user import User  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.routers import health, orders, reports, auth
from app.tasks.expire_orders import expire_stale_orders  # import background task

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if not settings.testing:
        task = asyncio.create_task(expire_stale_orders())
        print("Background task started.")
    yield
    if not settings.testing:
        task.cancel()
        print("Background task stopped.")

app = FastAPI(
    title="Orders Service API",
    version="0.1.0",
    description="PostgreSQL-backed orders and transactions service",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(orders.router)
app.include_router(reports.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"message": "Orders Service is running"}