# api-postgres-service# Orders Service (api-postgres-service)

A PostgreSQL-backed orders and transactions API built with FastAPI and SQLAlchemy 2.0.

## Quick Start

1. Clone the repo.
2. Copy `.env.example` to `.env` (adjust if needed).
3. Run `docker-compose up --build`.
4. Visit `http://localhost:8000/health` to verify the service and DB are alive.
5. API docs at `http://localhost:8000/docs`.

## Development

- Migrations: `alembic upgrade head` (inside container or locally with DATABASE_URL set).
- New models: `alembic revision --autogenerate -m "message"`.

## Environment

See `.env.example`. The default values work with Docker Compose.