from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Create the async engine
engine = create_async_engine(
    settings.database_url,
    echo=True,  # log SQL queries – helpful for learning
    future=True,
)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """FastAPI dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        yield session