from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db

router = APIRouter(tags=["health"])

@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """
    Health check that also tests the database connection.
    """
    try:
        # Execute a simple query to ensure DB is reachable
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "api-postgres-service", "db": "connected"}
    except Exception as e:
        return {"status": "error", "service": "api-postgres-service", "db": str(e)}