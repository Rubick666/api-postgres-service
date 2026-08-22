import asyncio
import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.product import Product


@pytest.fixture
def admin_token(client):
    resp = client.post(
        "/auth/register",
        json={"email": "admin@test.com", "password": "adminpass", "full_name": "Admin"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def user_token(client):
    resp = client.post(
        "/auth/register",
        json={"email": "user@test.com", "password": "userpass", "full_name": "User"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def test_create_order_success(client, admin_token):
    async def add_product():
        async with AsyncSessionLocal() as db:
            prod = Product(name="Test Product", price=10.00, stock_quantity=5)
            db.add(prod)
            await db.commit()
            await db.refresh(prod)
            return prod.id

    product_id = asyncio.run(add_product())

    resp = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 2}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["total_amount"] == 20.00
    assert data["status"] == "pending"


def test_create_order_insufficient_stock(client, admin_token):
    async def add_product():
        async with AsyncSessionLocal() as db:
            prod = Product(name="Limited", price=5.00, stock_quantity=1)
            db.add(prod)
            await db.commit()
            await db.refresh(prod)
            return prod.id

    product_id = asyncio.run(add_product())

    resp = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 5}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400, resp.text

    async def get_stock():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Product).where(Product.id == product_id))
            prod = result.scalar_one()
            return prod.stock_quantity

    stock = asyncio.run(get_stock())
    assert stock == 1