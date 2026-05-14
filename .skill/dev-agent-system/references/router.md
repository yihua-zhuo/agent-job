# Router Pattern

Routers handle HTTP, inject dependencies, call services, serialize results.  
No business logic. No try/catch. No `.to_dict()` inside services.

## Template

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.my_service import MyService
from models.my_entity import MyEntityCreate, MyEntityUpdate

router = APIRouter(prefix="/my-entities", tags=["MyEntities"])


@router.get("/")
async def list_entities(
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MyService(session)
    items, total = await svc.list_entities(
        tenant_id=ctx.tenant_id, page=page, page_size=page_size
    )
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{entity_id}")
async def get_entity(
    entity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MyService(session)
    entity = await svc.get_entity(entity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": entity.to_dict()}


@router.post("/", status_code=201)
async def create_entity(
    body: MyEntityCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MyService(session)
    entity = await svc.create_entity(body.model_dump(), tenant_id=ctx.tenant_id)
    return {"success": True, "data": entity.to_dict()}


@router.put("/{entity_id}")
async def update_entity(
    entity_id: int,
    body: MyEntityUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MyService(session)
    entity = await svc.update_entity(
        entity_id, body.model_dump(exclude_unset=True), tenant_id=ctx.tenant_id
    )
    return {"success": True, "data": entity.to_dict()}


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(
    entity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MyService(session)
    await svc.delete_entity(entity_id, tenant_id=ctx.tenant_id)
```

## Register the router in `main.py`

```python
from api.routers.my_entities import router as my_entities_router
app.include_router(my_entities_router)
```

## Rules

- Inject session via `session: AsyncSession = Depends(get_db)` — **never** `async with get_db()`.
- **No try/catch** — `AppException` is caught by the global handler in `main.py`.
- Serialize with `.to_dict()` here, **not** in the service.
- Wrap every response in `{"success": True, "data": ...}`.
- `tenant_id` always comes from `ctx.tenant_id`, never from the request body.
