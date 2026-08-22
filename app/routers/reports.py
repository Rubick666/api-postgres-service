from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.core.dependencies import require_admin
from app.db.session import get_db
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.order import RevenueByDay

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/revenue", response_model=list[RevenueByDay])
async def revenue_by_day(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),  # admin required
):
    statuses = [OrderStatus.PAID, OrderStatus.SHIPPED]

    stmt = (
        select(
            func.date(Order.created_at).label("date"),
            func.sum(Order.total_amount).label("total_revenue"),
            func.count(Order.id).label("order_count"),
        )
        .where(
            Order.status.in_(statuses),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        RevenueByDay(
            date=row.date,
            total_revenue=float(row.total_revenue),
            order_count=row.order_count,
        )
        for row in rows
    ]