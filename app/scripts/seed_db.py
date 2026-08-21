import asyncio
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem


async def seed():
    engine = create_async_engine(settings.database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Check if user exists – if not, create it
        result = await session.execute(select(User).where(User.email == "user@example.com"))
        user = result.scalar_one_or_none()
        if not user:
            hashed = hashlib.sha256(b"password123").hexdigest()
            user = User(
                email="user@example.com",
                full_name="Test User",
                hashed_password=hashed,
                is_active=True,
            )
            session.add(user)
            await session.flush()  # get ID without committing
            print(f"Created user: {user.email} with ID {user.id}")
        else:
            print(f"User already exists: {user.email} with ID {user.id}")

        # Define products to seed
        products_data = [
            {"name": "Laptop", "description": "A powerful laptop", "price": 999.99, "stock_quantity": 10},
            {"name": "Mouse", "description": "Wireless mouse", "price": 19.99, "stock_quantity": 50},
            {"name": "Keyboard", "description": "Mechanical keyboard", "price": 79.99, "stock_quantity": 30},
        ]

        # For each product, check if it exists (by name) – if not, add it
        for pdata in products_data:
            result = await session.execute(select(Product).where(Product.name == pdata["name"]))
            product = result.scalar_one_or_none()
            if not product:
                product = Product(**pdata)
                session.add(product)
                print(f"Created product: {pdata['name']}")
            else:
                print(f"Product '{pdata['name']}' already exists, skipping.")

        await session.commit()
        print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())