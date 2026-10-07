from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL, make_url

# Alembic is executed from backend/. Load backend/.env explicitly so migrations
# use the same DATABASE_URL as the FastAPI application.
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)

config = context.config

target_metadata = None


def database_url() -> URL:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is required to run Alembic migrations.")

    url = make_url(raw)

    # SQLAlchemy maps plain postgresql:// to psycopg2 by default. AniVideos v16
    # uses psycopg 3, so force the corresponding SQLAlchemy dialect explicitly.
    if url.drivername in {"postgresql", "postgres", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")

    if url.drivername != "postgresql+psycopg":
        raise RuntimeError(
            "DATABASE_URL must point to PostgreSQL. "
            f"Received driver: {url.drivername!r}."
        )

    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Do not use engine_from_config here. Passing postgresql:// through the
    # generic config path makes SQLAlchemy select psycopg2. Creating the engine
    # from the normalized URL guarantees psycopg 3 is used.
    connectable = create_engine(database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
