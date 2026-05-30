# Optimistic Lock · Add updated_at + ResourceLockService + Redis SET NX EX

| 元数据 | 值 |
|---|---|
| Issue | #492 |
| 分类 | 70-platform |
| 优先级 | 推荐 |
| 工作量 | 2 工作日 |
| 依赖 | #491 (板块491) |
| 启用后赋能 | TBD - 待确认：依赖本板块的下游模块（如事件溯源或冲突检测消费方） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Multi-tenant CRM workloads involve concurrent edits to the same customer, opportunity, or ticket by different workers (API scripts, background jobs, duplicate form submissions). Without a lock mechanism the last-write-wins silently overwrites previous changes. Without an `updated_at` guard the service cannot detect whether the entity was modified between read and write — the classic lost-update problem. Issue #492 delivers the primitive layer on which all conflict-safe edit flows are built.

### 1.2 做完后

- **用户视角**：无用户可见 changes — this is a pure infrastructure addition.
- **开发者视角**：`ResourceLockService` provides atomic `acquire` / `release` / `extend` on any `(resource_type, resource_id, tenant_id)` key backed by Redis `SET NX EX`. Services can call `check_updated_at(svc, entity_id, tenant_id, expected_at)` before persisting; a mismatch raises `ConflictException`. Test fixtures cover the happy path, lock timeout, and double-acquire rejection.

### 1.3 不做什么（剔除）

- [ ] No frontend changes; not adding lock UI elements here.
- [ ] No new API endpoints beyond internal `ResourceLockService` (the service is called by existing service methods, not exposed directly as a REST route).
- [ ] No distributed transaction or saga coordinator — just the lock primitive and the `updated_at` guard.
- [ ] No migration of existing rows' `updated_at` values; existing `NULL` is treated as epoch (lock is always acquirable on pre-existing rows).

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_resource_lock.py tests/unit/test_lock_integration.py -v` → all passed
- `ruff check src/services/resource_lock.py src/services/lock_mixin.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- `ruff check src/db/models/ --select=E501` → 0 errors on all touched model files

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 下存在 `customer.py`, `opportunity.py`, `ticket.py` 等 ORM 模型文件 — 具体行号需确认 `Base` 定义及 `__tablename__` 行所在位置。建议执行 `grep -n "class Customer\|__tablename__" src/db/models/customer.py` 后补充。

以下为根据 issue #492推断的已有 schema 结构（待验证）：

```
#推断：src/db/models/customer.py (TBD 确认路径)
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # 缺少 updated_at 字段
```

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/db/models/customer.py` — 添加 `updated_at: Mapped[datetime]` 列（ nullable=False, server_default=func.now())
  - TBD - 待验证：`src/db/models/opportunity.py` — 同上
  - TBD - 待验证：`src/db/models/ticket.py` — 同上
  - TBD - 待验证：`src/schemas/` 下的相应 Pydantic schema — 添加 `lock_holder: Optional[str]`, `lock_expires_at: Optional[datetime]`
- 要建：
  - `src/services/resource_lock.py` — `ResourceLockService` 使用 Redis `SET NX EX` 实现
  - `src/services/lock_mixin.py` — `LockMixin` 提供 `check_updated_at`辅助方法，供其他 service 复用
  - `alembic/versions/<id>_add_updated_at_and_lock_fields.sql` —迁移脚本  - `tests/unit/test_resource_lock.py` — unit test for lock service  - `tests/unit/test_lock_integration.py` — unit test for conflict detection via `check_updated_at`

### 2.3 缺什么

- [ ] `Customer` / `Opportunity` / `Ticket` ORM models lack `updated_at` column → cannot detect stale writes
- [ ] No lock service exists → concurrent edits race without arbitration
- [ ] No `lock_holder` / `lock_expires_at` fields on schemas → no visibility into who holds a lock
- [ ] No Alembic migration for the new columns → schema drift unprotected
- [ ] Existing service methods cannot check for conflict before `UPDATE` → last-write-wins silently

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/resource_lock.py` | `ResourceLockService` — Redis-backed atomic lock acquire/release/extend with5-min TTL |
| `src/services/lock_mixin.py` | `LockMixin` — mixin providing `check_updated_at()` conflict guard for use by domain services |
| `alembic/versions/<id>_add_updated_at_and_lock_fields.py` | 对 `customers` / `opportunities` / `tickets` 表添加 `updated_at` 及其他必要字段 |
| `tests/unit/test_resource_lock.py` | 覆盖 acquire / release / timeout / double-acquire-reject 的 mock Redis 测试 |
| `tests/unit/test_lock_integration.py` | 覆盖 `check_updated_at` 检测到 mismatch 时 raise `ConflictException` 的测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/db/models/customer.py` | 添加 `updated_at: Mapped[datetime]` 列，`server_default=func.now()`, `onupdate=func.now()` |
| TBD - 待验证：`src/db/models/opportunity.py` | 同上 |
| TBD - 待验证：`src/db/models/ticket.py` | 同上 |
| TBD - 待验证：`src/schemas/customer.py` | 添加 `lock_holder: Optional[str]`, `lock_expires_at: Optional[datetime]` 到 `CustomerResponse` |
| TBD - 待验证：`src/schemas/opportunity.py` | 同上 |
| TBD - 待验证：`src/schemas/ticket.py` | 同上 |

### 3.3 新增能力

- **Service method**：`ResourceLockService(Context).acquire(resource_type, resource_id, tenant_id) -> LockInfo`; `.release(...) -> bool`; `.extend(...) -> bool`
- **Service method**：`LockMixin.check_updated_at(entity, expected_at, tenant_id)` — raises `ConflictException` on mismatch (called by CustomerService / TicketService before update)
- **ORM model**：N/A —扩展现有 ORM 模型，不新建表
- **Migration**：`alembic upgrade head` 添加 `updated_at`, `lock_holder`, `lock_expires_at` 列到 `customers`, `opportunities`, `tickets` 表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Redis `SET key value NX EX300` 不选数据库行锁（SERIALIZABLE）**：MySQL/Postgres row-level locks hold a connection open, starving the pool under moderate contention. Redis lock is connectionless and survives app-process restarts.
- **5-minute TTL 不选更长**：Long locks create dead-lock windows for abandoned browser tabs. 5 min is the standard tradeoff in CRM workflows; callers are expected to extend the lock before expiry if the operation is still running.
- **`LockMixin` 而非继承 `ResourceLockService`**：Mixin avoids Liskov violating "is-a" relationship — a service like `TicketService` is not a lock service, it merely *uses* one. Composition via a `self.locks = ResourceLockService(ctx)` field is preferred over inheritance.
- **`updated_at` 作为乐观锁版本号而非独立的 `version`整数列**：兼容现有 timestamp audit columns; no extra index needed; already present for audit.

### 4.2 版本约束

|依赖 | 版本 | 理由 |
|------|------|------|
| `redis[hiredis]` | `≥5.0` | `SET NX EX` with `KEEPTTL` option added in redis-py 4.2; `hiredis` parser needed for async performance |
| `alembic` | `≥ 1.11` | Required for `op.execute(sql)` async compat in migration env |

### 4.3 兼容性约束

- Multi-tenant：every Redis key includes `tenant_id` as prefix: `lock:{tenant_id}:{resource_type}:{resource_id}` — no cross-tenant lock bleed.
- Service returns ORM/dataclass objects, **not** calling `.to_dict()`; serialization by router.
- Service errors raise `AppException` subclasses, **not** returning `ApiResponse.error()`.
- Redis client is async (`redis.asyncio`); `ResourceLockService` methods are `async def`.

### 4.4 已知坑

1. **Alembic autogen emits `sa.JSON()` instead of `sa.JSONB()`** → after autogenerate, manually edit: `import sqlalchemy as sa; col.type = sa.JSONB()` for any JSONB columns.
2. **Alembic autogen omits `timezone=True` on DateTime columns** → after autogenerate, add `timezone=True` to `DateTime(timezone=True)` for all timestamp columns (avoids naive/aware mismatch in Python `datetime` comparisons).
3. **Redis `SET NX` is atomic but `EXPIRE` is not — a crash between `SET` and `EXPIRE` leaves a key with no TTL** → use `SET key value NX EX 300` (set + expiry in one atomic redis command) to avoid this.
4. **Pre-existing rows have `NULL` `updated_at`** → treat `NULL` as "always acquirable": `check_updated_at` treats `None expected_at` as always valid (no conflict). Migration seeds `updated_at = NOW()` for all existing rows to avoid NULL on new rows going forward.

---

## 5. 实现步骤（按顺序）

### Step 1: Write Unit Test Fixtures for Redis MockAdd minimal Redis mock fixtures in `tests/unit/conftest.py` so all lock-service tests run without a real Redis instance.

操作：
- a) In `tests/unit/conftest.py`, add a `make_redis_mock()` factory returning an object with `acquire_key`, `released_keys`, and `lock_ttl` state. The mock records calls for assertions in test files.
- b) Patch `src.services.resource_lock.RedisClient` to return the mock via a fixture scope `"function"` — each test gets a fresh mock.

```python
# tests/unit/conftest.py — snippet to add
class MockRedisLock:
    def __init__(self):
        self.store: dict[str, tuple[str, int]] = {}  # key -> (value, expire_unix)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = (value, int(time.time()) + ex if ex else 0)
        return True

    async def get(self, key):
        if key not in self.store:
            return None
        value, expire = self.store[key]
        if expire and expire < int(time.time()):
            del self.store[key]
            return None
        return value

    async def delete(self, key):
        self.store.pop(key, None)
        return True
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_resource_lock.py::test_fixtures -v` exists and passes (no-op smoke test file exists)

---

### Step 2: Implement ResourceLockService

创建 `src/services/resource_lock.py` with three async methods.

操作：
- a) Write `src/services/resource_lock.py`:

```python
# src/services/resource_lock.py
from dataclasses import dataclass
from datetime import datetime, timezonefrom typing import Optional
import redis.asyncio as redis

LOCK_TTL_SECONDS = 300 # 5 minutes

@dataclass(slots=True)
class LockInfo:
    resource_type: str
    resource_id: int
    tenant_id: int
    holder: str
    acquired_at: datetime
    expires_at: datetime

class ResourceLockService:
    def __init__(self, redis_client: redis.Redis):
        self._r = redis_client

    def _key(self, tenant_id: int, resource_type: str, resource_id: int) -> str:
        return f"lock:{tenant_id}:{resource_type}:{resource_id}"

    async def acquire(
        self,
        tenant_id: int,
        resource_type: str,
        resource_id: int,
        holder: str,
        ttl_seconds: int = LOCK_TTL_SECONDS,
    ) -> Optional[LockInfo]:
        key = self._key(tenant_id, resource_type, resource_id)
        now = datetime.now(timezone.utc)
        ok = await self._r.set(key, holder, nx=True, ex=ttl_seconds)
        if not ok:
            return None
        expires_at = datetime.fromtimestamp(
            (await self._r.ttl(key)) + int(time.time()), tz=timezone.utc
        )
        return LockInfo(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            holder=holder,
            acquired_at=now,
            expires_at=expires_at,
        )

    async def release(
        self,
        tenant_id: int,
        resource_type: str,
        resource_id: int,
        holder: str,
    ) -> bool:
        key = self._key(tenant_id, resource_type, resource_id)
        current = await self._r.get(key)
        if current != holder:
            return False
        await self._r.delete(key)
        return True

    async def extend(
        self,
        tenant_id: int,
        resource_type: str,
        resource_id: int,
        holder: str,
        additional_seconds: int = LOCK_TTL_SECONDS,
    ) -> bool:
        key = self._key(tenant_id, resource_type, resource_id)
        current = await self._r.get(key)
        if current != holder:
            return False
        await self._r.expire(key, additional_seconds)
        return True
```

- b) Add `"redis[hiredis]"` to `pyproject.toml` dependencies section (check existing entries first before appending).

**完成判定**：`ruff check src/services/resource_lock.py` → 0 errors---

### Step 3: Write and Pass ResourceLockService Unit Tests

操作：
- a) Write `tests/unit/test_resource_lock.py` covering:
  - `test_acquire_success` — `acquire` returns `LockInfo` on free key
  - `test_acquire_already_held` — `acquire` returns `None` when another holder holds the key
  - `test_release_success` — `release` returns `True` when holder matches
  - `test_release_wrong_holder` — `release` returns `False` when holder mismatches
  - `test_extend_success` — `extend` returns `True` when holder matches
  - `test_extend_wrong_holder` — `extend` returns `False` when holder mismatches
- b) Write `tests/unit/test_lock_integration.py` covering:
  - `test_check_updated_at_match` — no exception raised when `entity.updated_at == expected_at`
  - `test_check_updated_at_mismatch` — raises `ConflictException` when timestamps differ
 - `test_check_updated_at_none_expected` — `None` expected is always valid (pre-existing rows)

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_resource_lock.py tests/unit/test_lock_integration.py -v` → all passed

---

### Step 4: Implement Alembic Migration for updated_at + lock fields

操作：
- a) Spin up clean `alembic_dev` DB per CLAUDE.md instructions:

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
```

- b) Run `alembic revision --autogenerate -m "add_updated_at_and_lock_fields"`
- c) Edit the generated file in `alembic/versions/<id>_add_updated_at_and_lock_fields.py` — add `timezone=True` to all `DateTime` columns and replace any `sa.JSON()` with `sa.JSONB()` if present.
- d) Backfill existing rows so new `NOT NULL` columns have values:

```python
# In the migration up() after add_column statements:
op.execute("UPDATE customers SET updated_at = NOW() WHERE updated_at IS NULL")
op.execute("UPDATE opportunities SET updated_at = NOW() WHERE updated_at IS NULL")
op.execute("UPDATE tickets SET updated_at = NOW() WHERE updated_at IS NULL")
```

- e) Verify upgrade/downgrade cycle: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all exit 0

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0

---

### Step 5: Add updated_at to ORM Models and lock fields to Schemas

操作：
- a) In `src/db/models/customer.py` (TBD 确认路径), add after existing column declarations:

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default=func.now(),
    onupdate=func.now(),
)
lock_holder: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
lock_expires_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

- b) Repeat for `opportunity.py` and `ticket.py`.
- c) In the respective Pydantic schema files (TBD 确认 `src/schemas/` 路径) add `lock_holder: Optional[str] = None`, `lock_expires_at: Optional[datetime] = None` to response schemas.
- d) Import each model in `alembic/env.py` (per CLAUDE.md requirement, every model registered with `Base.metadata` must be imported there so `--autogenerate` picks it up).

**完成判定**：`ruff check src/db/models/customer.py src/db/models/opportunity.py src/db/models/ticket.py` → 0 errors

---

### Step 6: Implement LockMixin and wire check_updated_at into existing Services

操作：
- a) Write `src/services/lock_mixin.py`:

```python
# src/services/lock_mixin.py
from datetime import datetime
from pkg.errors.app_exceptions import ConflictException

class LockMixin:
    def check_updated_at(
        self,
        entity_updated_at: Optional[datetime],
        expected_at: Optional[datetime],
        tenant_id: int,
        resource_type: str,
        resource_id: int,
    ) -> None:
        """Raise ConflictException if entity has been updated since read."""
        if expected_at is None:
            return  # None expected means pre-existing row, always valid
        if entity_updated_at is None:
            return
        if entity_updated_at != expected_at:
            raise ConflictException(
                f"{resource_type}/{resource_id} was modified by another process "
                f"at {entity_updated_at}; expected {expected_at}"
            )
```

- b) In `src/services/customer_service.py` (TBD 确认路径), before the `session.commit()` in `update_customer`, add call to `self.check_updated_at(...)`. The pattern:

```python
async def update_customer(self, customer_id: int, tenant_id: int, data: CustomerUpdate, expected_updated_at: Optional[datetime]) -> CustomerModel:
    result = await self.session.execute(
        select(CustomerModel).where(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise NotFoundException("Customer")
    self.check_updated_at(entity.updated_at, expected_updated_at, tenant_id, "customer", customer_id)
    # ... apply updates ...
    await self.session.commit()
    await self.session.refresh(entity)
    return entity
```

- c) Repeat wiring in `opportunity_service.py` (TBD 确认路径) and `ticket_service.py` (TBD 确认路径).

**完成判定**：`ruff check src/services/lock_mixin.py src/services/customer_service.py src/services/opportunity_service.py src/services/ticket_service.py` →0 errors

---

## 6. 验收

- [ ] `ruff check src/services/resource_lock.py src/services/lock_mixin.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_resource_lock.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_lock_integration.py -v` → all passed
- [ ] `ruff check src/db/models/customer.py src/db/models/opportunity.py src/db/models/ticket.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- [ ] `ruff check src/services/customer_service.py src/services/opportunity_service.py src/services/ticket_service.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Redis unavailable — `ResourceLockService.acquire` throws `redis.exceptions.ConnectionError`, blocking all lock operations | 中 | 高 | Feature flag `ENFORCE_LOCKS=false` bypasses lock checks; services proceed in best-effort mode (last-write-wins) until Redis recovers. Lock guard is advisory not mandatory for initial rollout. |
| Migration adds `NOT NULL updated_at` but existing rows have `NULL` and backfill SQL is too slow on a large table | 中 | 中 | Change migration to `nullable=True` initially; run backfill as a separate background job after merge; add `NOT NULL + DEFAULT` in a follow-up non-blocking migration. |
| `check_updated_at` wired into all three services but one service was missed in the refactor branch, producing `AttributeError` at runtime | 低 | 高 | Revert only the wiring commit (`git revert <commit>`) — migration and service files are independent. Pre-merge CI runs `pytest tests/integration/` which exercises real service paths. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/resource_lock.py src/services/lock_mixin.py \
 tests/unit/test_resource_lock.py tests/unit/test_lock_integration.py \
  alembic/versions/<id>_add_updated_at_and_lock_fields.py \
  src/db/models/customer.py src/db/models/opportunity.py src/db/models/ticket.py \
  src/schemas/customer.py src/schemas/opportunity.py src/schemas/ticket.py \
  pyproject.toml
git commit -m "feat(platform): add optimistic-lock fields and ResourceLockService

Closes #492"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(platform): #492 add updated_at + ResourceLockService" --body "Closes #492"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Resource lock pattern: [Redis SETNX pattern — Redis official docs](https://redis.io/commands/set/)
- SQLAlchemy `onupdate`: [SQLAlchemyMappedColumn docs — relationship attribute events](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html#simple-attribute-reflection)
- ConflictException: [`pkg/errors/app_exceptions.py`](../../../src/pkg/errors/app_exceptions.py) — existing in this repo
- Subtask parent: #80
- Dependency: #491 (板块491)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
