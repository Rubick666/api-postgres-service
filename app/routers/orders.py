from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, AdminUser
from app.db.session import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
    OrderStatusUpdate,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_amount=float(order.total_amount),
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=float(item.unit_price),
                total_price=float(item.total_price),
            )
            for item in order.items
        ],
    )


# ------------------------------------------------------------
# Create order (any authenticated user)
# ------------------------------------------------------------
@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(
    order_data: OrderCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        order_items = []
        total_amount = Decimal("0.00")

        for item in order_data.items:
            result = await db.execute(
                select(Product).where(Product.id == item.product_id)
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {item.product_id} not found",
                )
            if product.stock_quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for product {product.name} "
                        f"(requested {item.quantity}, available {product.stock_quantity})"
                    ),
                )

            line_total = Decimal(product.price) * item.quantity
            total_amount += line_total

            order_items.append(
                {
                    "product_id": product.id,
                    "quantity": item.quantity,
                    "unit_price": Decimal(product.price),
                    "total_price": line_total,
                }
            )
            product.stock_quantity -= item.quantity

        order = Order(
            user_id=current_user.id,  # <-- use authenticated user ID
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(order)
        await db.flush()

        for item_data in order_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            )
            db.add(order_item)

    # After commit, fetch order with items (eagerly loaded)
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
    order_with_items = result.scalar_one()
    return _order_to_response(order_with_items)


# ------------------------------------------------------------
# Get single order (owner or admin)
# ------------------------------------------------------------
@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Allow access if owner or admin
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return _order_to_response(order)


# ------------------------------------------------------------
# Get all orders for a user (admin or self)
# ------------------------------------------------------------
@router.get("/user/{user_id}", response_model=list[OrderResponse])
async def get_user_orders(
    user_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    # Only admin or the user themselves can see their orders
    if user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view orders of this user")

    # Check user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return [_order_to_response(order) for order in orders]


# ------------------------------------------------------------
# Update order status (admin only)
# ------------------------------------------------------------
@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    admin_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    # Allowed transitions
    STATUS_TRANSITIONS = {
        OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
        OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED: set(),
        OrderStatus.CANCELLED: set(),
    }

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = status_update.status
    allowed = STATUS_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {order.status.value} -> {new_status.value}",
        )

    order.status = new_status
    order.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(order)
    # Reload items
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
    order_with_items = result.scalar_one()
    return _order_to_response(order_with_items)