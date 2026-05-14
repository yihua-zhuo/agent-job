# Service Pattern

One service class per domain. Constructor requires `AsyncSession` — no default, no `None`.

## Template

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from db.models.my_entity import MyEntity
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class MyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Single fetch ──────────────────────────────────────────────────────────
    async def get_entity(self, entity_id: int, tenant_id: int) -> MyEntity:
        result = await self.session.execute(
            select(MyEntity)
            .where(MyEntity.id == entity_id, MyEntity.tenant_id == tenant_id)
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundException("MyEntity")
        return entity  # ← ORM object, never .to_dict()

    # ── Paginated list ────────────────────────────────────────────────────────
    async def list_entities(
        self, tenant_id: int, page: int, page_size: int
    ) -> tuple[list[MyEntity], int]:
        base_q = select(MyEntity).where(MyEntity.tenant_id == tenant_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_q.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_q.offset((page - 1) * page_size).limit(page_size)
        )
        items = result.scalars().all()
        return list(items), total

    # ── Create ────────────────────────────────────────────────────────────────
    async def create_entity(self, data: dict, tenant_id: int) -> MyEntity:
        entity = MyEntity(**data, tenant_id=tenant_id)
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    # ── Update ────────────────────────────────────────────────────────────────
    async def update_entity(
        self, entity_id: int, data: dict, tenant_id: int
    ) -> MyEntity:
        entity = await self.get_entity(entity_id, tenant_id)
        for key, value in data.items():
            setattr(entity, key, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    # ── Delete ────────────────────────────────────────────────────────────────
    async def delete_entity(self, entity_id: int, tenant_id: int) -> None:
        entity = await self.get_entity(entity_id, tenant_id)
        await self.session.delete(entity)
        await self.session.commit()
```

## Rules

- **`__init__`** always takes `session: AsyncSession` — no default value, never `None`.
- **Return** ORM objects or `(list, total)` tuples for paginated results.
- **Raise** `AppException` subclasses (`NotFoundException`, `ValidationException`, etc.) — never return error responses.
- **Never** call `.to_dict()` — that is the router's responsibility.
- **Every** query must filter by `tenant_id`.
- Use `scalar_one_or_none()` for single-row fetches; raise `NotFoundException` if `None`.
