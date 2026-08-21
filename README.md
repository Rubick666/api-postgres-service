# Orders Service (`api-postgres-service`)

A PostgreSQL-backed orders and transactions API built with FastAPI, SQLAlchemy 2.0 (async), and Alembic.

## Features

* ✅ **Health check** endpoint with database connectivity testing
* ✅ **Product model** with inventory tracking
* ✅ **Order management**, including:

  * **Transactional order creation** — creates an order and decrements product stock atomically
  * **Order status enum** — `PENDING`, `PAID`, `SHIPPED`, and `CANCELLED`
  * **Order items with price snapshots** — stores the unit price at the time of purchase
* ✅ **Seed script** for demo data, including users and products
* ✅ **Alembic migrations** for schema evolution

## Tech Stack

* **FastAPI** — Async web framework
* **SQLAlchemy 2.0** — Async ORM
* **asyncpg** — Async PostgreSQL driver
* **PostgreSQL 16** — Relational database
* **Alembic** — Database migrations
* **Docker Compose** — Local development environment
* **Pydantic v2** — Data validation and settings management

## Quick Start

1. **Clone** the repository.
2. **Copy** `.env.example` to `.env` and adjust the values if needed.
3. **Run** the service with Docker Compose:

```bash
docker-compose up --build
```

4. **Seed** the database *(optional, but recommended for demo data)*:

```bash
docker-compose exec api python -m app.scripts.seed_db
```

5. **Verify** that the service is running:

* Health check: `http://localhost:8000/health`
* API documentation: `http://localhost:8000/docs`

## Environment Variables

See `.env.example` for the full configuration.

```env
APP_ENV=development
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=orders_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

The default values are configured to work with Docker Compose.

## API Endpoints

### `GET /health`

Returns service and database status.

### `POST /orders/`

Creates a new order and decrements product stock **atomically**.

**Request body:**

```json
{
  "user_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    },
    {
      "product_id": 2,
      "quantity": 1
    }
  ]
}
```

**Response:** `201 Created`

```json
{
  "id": 1,
  "user_id": 1,
  "status": "pending",
  "total_amount": 2019.97,
  "created_at": "2026-08-21T08:32:22.075209+00:00",
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "unit_price": 999.99,
      "total_price": 1999.98
    },
    {
      "product_id": 2,
      "quantity": 1,
      "unit_price": 19.99,
      "total_price": 19.99
    }
  ]
}
```

**Error handling:**

* `404` — User or product not found
* `400` — Insufficient stock

### `GET /orders/{order_id}`

Fetches a single order with all its items.

### `GET /orders/user/{user_id}`

Fetches all orders for a given user, sorted by `created_at` descending.

### `PATCH /orders/{order_id}/status`

Updates the order status with validation against a state machine.

**Request body:**

```json
{
  "status": "paid"
}
```

**Allowed transitions:**

* `PENDING` → `PAID` or `CANCELLED`
* `PAID` → `SHIPPED` or `CANCELLED`
* `SHIPPED` → No further transitions
* `CANCELLED` → No further transitions

An **invalid transition** returns `400 Bad Request`.

### `GET /reports/revenue`

Returns daily revenue aggregation for completed orders (`PAID` or `SHIPPED`) within a specified date range.

**Query parameters:**

* `start_date` — Date in `YYYY-MM-DD` format
* `end_date` — Date in `YYYY-MM-DD` format

**Response:**

```json
[
  {
    "date": "2026-08-21",
    "total_revenue": 1999.98,
    "order_count": 1
  }
]
```

## Database Schema

| Table         | Columns                                                                 | Notes                                   |
| ------------- | ----------------------------------------------------------------------- | --------------------------------------- |
| `users`       | `id`, `email`, `full_name`, `is_active`, `hashed_password`              | Unique email                            |
| `products`    | `id`, `name`, `description`, `price`, `stock_quantity`                  | Price stored as `NUMERIC(10,2)`         |
| `orders`      | `id`, `user_id`, `status`, `total_amount`, `created_at`, `updated_at`   | Status enum and foreign key to `users`  |
| `order_items` | `id`, `order_id`, `product_id`, `quantity`, `unit_price`, `total_price` | Foreign keys to `orders` and `products` |

## Key Design Decisions

### Transactional Integrity

The `POST /orders/` endpoint wraps all database operations in a single transaction.

If any validation or database operation fails—for example, when a product has insufficient stock—the entire transaction is **rolled back**. This ensures that:

* No partial order is created.
* Product stock remains unchanged if the order fails.
* The order and inventory data remain consistent.

### Price Snapshot

The `order_items.unit_price` field stores the product's price at the time of purchase.

This preserves historical order accuracy even if the product's current price changes later.

## Development

### Seed Demo Data

If you need to populate the database with fresh demo data:

```bash
docker-compose exec api python -m app.scripts.seed_db
```

### Inspect the Database

To inspect the products table directly:

```bash
docker-compose exec postgres psql -U postgres -d orders_db -c "SELECT * FROM products;"
```

## Migrations

Alembic is configured for database schema management.

After making changes to your SQLAlchemy models, generate a new migration:

```bash
docker-compose exec api alembic revision --autogenerate -m "description"
```

Then apply the migration:

```bash
docker-compose exec api alembic upgrade head
```

Alternatively, if running the project locally with `DATABASE_URL` configured, you can run:

```bash
alembic upgrade head
```
