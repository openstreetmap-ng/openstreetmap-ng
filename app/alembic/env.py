import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import POSTGRES_URL
from app.models.db import *  # noqa: F403
from app.models.db.base import Base

target_metadata = Base.NoID.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_async_engine(POSTGRES_URL)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()
    # maybe not the best idea: await db_update_stats()


def run_migrations_online() -> None:
    """Run migrations in online mode"""
    asyncio.run(run_async_migrations())


run_migrations_online()
