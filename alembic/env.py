"""Alembic environment configuration for async SQLAlchemy + PostgreSQL."""
import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure src/ is on the path so 'from db.base import Base' resolves
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from db.base import Base
from db.models import (
    ActivityModel,
    ApiClientModel,
    CampaignEventModel,
    CampaignModel,
    CustomerModel,
    DashboardModel,
    NotificationModel,
    OpportunityModel,
    PipelineModel,
    PipelineStageModel,
    ReminderModel,
    ReportModel,
    TaskModel,
    TenantModel,
    TicketModel,
    TicketReplyModel,
    UserModel,
    WorkflowExecutionModel,
    WorkflowModel,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_dev",
)
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()