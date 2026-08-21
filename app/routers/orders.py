from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse, OrderStatusUpdate

def _order_to_response(order: Order) -> OrderResponse:
    """Convert an Order object to its response schema."""
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

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(order_data: OrderCreate, db: AsyncSession = Depends(get_db)):
    """
    Create an order and decrement product stock atomically.
    """
    async with db.begin():
        # Validate user exists
        user_result = await db.execute(select(User).where(User.id == order_data.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User {order_data.user_id} not found",
            )

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
            user_id=order_data.user_id,
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

    # After commit, fetch the order with items eagerly loaded
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
    order_with_items = result.scalar_one()

    items_response = [
        OrderItemResponse(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=float(item.unit_price),
            total_price=float(item.total_price),
        )
        for item in order_with_items.items
    ]

    return OrderResponse(
        id=order_with_items.id,
        user_id=order_with_items.user_id,
        status=order_with_items.status,
        total_amount=float(order_with_items.total_amount),
        created_at=order_with_items.created_at,
        items=items_response,
    )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch a single order with its items."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_response(order)


@router.get("/user/{user_id}", response_model=list[OrderResponse])
async def get_user_orders(user_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch all orders for a given user."""
    # Validate user exists
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

# Allowed transitions
STATUS_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: set(),
    OrderStatus.CANCELLED: set(),
}

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(order_id: int, status_update: OrderStatusUpdate, db: AsyncSession = Depends(get_db)):
    """Update the order status with validation against the state machine."""
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
            detail=f"Invalid status transition: {order.status.value} -> {new_status.value}"
        )

    # Update status
    order.status = new_status
    order.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(order)

    return _order_to_response(order)