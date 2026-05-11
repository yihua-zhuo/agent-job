"""Async repository base with SQLAlchemy 2.0 async sessions."""

from typing import Any, TypeVar, cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


class BaseRepository:
    """Async repository base providing common CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, query: Select) -> list[Any]:
        """Execute a SELECT query and return all rows."""
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def execute_one(self, query: Select) -> Any | None:
        """Execute a SELECT query and return one row or None."""
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def execute_scalar(self, query: Select) -> Any | None:
        """Execute a SELECT returning a single scalar value."""
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, model: type[T], id_val: int, tenant_id: int) -> T | None:
        """Fetch a row by primary key with tenant isolation."""
        query = select(model).where(
            cast(Any, model).__table__.columns["id"] == id_val,
            cast(Any, model).__table__.columns["tenant_id"] == tenant_id,
        )
        return await self.execute_one(query)

    async def list_by_tenant(self, model: type[T], tenant_id: int, limit: int = 100, offset: int = 0) -> list[T]:
        """List all rows for a tenant with pagination."""
        query = (
            select(model)
            .where(cast(Any, model).__table__.columns["tenant_id"] == tenant_id)
            .limit(limit)
            .offset(offset)
        )
        return await self.execute(query)

    async def count_by_tenant(self, model: type[T], tenant_id: int) -> int:
        """Count rows for a tenant."""
        query = (
            select(func.count()).select_from(model).where(cast(Any, model).__table__.columns["tenant_id"] == tenant_id)
        )
        result = await self.execute_scalar(query)
        return int(result) if result is not None else 0

    async def update_by_id(self, model: type[T], id_val: int, tenant_id: int, **kwargs: Any) -> T | None:
        """Update a row by id + tenant, return the updated row."""
        stmt = (
            update(model)
            .where(
                cast(Any, model).__table__.columns["id"] == id_val,
                cast(Any, model).__table__.columns["tenant_id"] == tenant_id,
            )
            .values(**kwargs)
            .returning(model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def delete_by_id(self, model: type[T], id_val: int, tenant_id: int) -> bool:
        """Delete a row by id + tenant. Returns True if a row was deleted."""
        stmt = delete(model).where(
            cast(Any, model).__table__.columns["id"] == id_val,
            cast(Any, model).__table__.columns["tenant_id"] == tenant_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return cast(Any, result).rowcount > 0
