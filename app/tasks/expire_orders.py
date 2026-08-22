import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.order import Order, OrderStatus

async def expire_stale_orders():
    """Cancel orders older than 2 days that are still PENDING."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(days=2)
                # Update orders
                await db.execute(
                    update(Order)
                    .where(Order.status == OrderStatus.PENDING,
                           Order.created_at < cutoff)
                    .values(status=OrderStatus.CANCELLED,
                            updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
        except Exception as e:
            print(f"Error in expire_stale_orders: {e}")
        await asyncio.sleep(3600)  # run every hour