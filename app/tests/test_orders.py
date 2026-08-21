import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem
import hashlib

# Setup database for tests (use a separate test database? For simplicity, we'll reuse development DB but clean it)
# We'll use a fixture to create fresh tables and seed minimal data.

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.mark.asyncio
async def test_create_order_success(client):
    # Insert a user and a product directly via the session
    async with AsyncSessionLocal() as db:
        user = User(email="test@test.com", full_name="Test", hashed_password="hash", is_active=True)
        product = Product(name="Test Product", price=10.00, stock_quantity=5)
        db.add(user)
        db.add(product)
        await db.commit()
        await db.refresh(user)
        await db.refresh(product)

    response = client.post("/orders/", json={
        "user_id": user.id,
        "items": [{"product_id": product.id, "quantity": 2}]
    })
    assert response.status_code == 201
    data = response.json()
    assert data["total_amount"] == 20.00
    assert data["status"] == "pending"
    assert data["items"][0]["quantity"] == 2

    # Check stock decremented
    async with AsyncSessionLocal() as db:
        updated = await db.get(Product, product.id)
        assert updated.stock_quantity == 3

@pytest.mark.asyncio
async def test_create_order_insufficient_stock_rollback(client):
    # Create a product with low stock
    async with AsyncSessionLocal() as db:
        product = Product(name="Limited", price=5.00, stock_quantity=1)
        db.add(product)
        await db.commit()
        await db.refresh(product)

    response = client.post("/orders/", json={
        "user_id": 1,  # user from previous test maybe, but ensure exists (use create user again if needed)
        "items": [{"product_id": product.id, "quantity": 5}]
    })
    assert response.status_code == 400
    # Ensure product stock remains 1 (rollback)
    async with AsyncSessionLocal() as db:
        updated = await db.get(Product, product.id)
        assert updated.stock_quantity == 1