# CRM · 提取 CustomerRepository 隔离数据访问层

| 元数据 | 值 |
|---|---|
| Issue | #430 |
| 分类 | 10-customers |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：依赖 #430 的下游板块（如有） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`CustomerService` 目前承担了双重职责：编排业务逻辑和构造数据访问查询（create / list / get_by_id / update / delete / count_by_status / search / add_tag / remove_tag / bulk_import）。这种耦合导致同一套查询逻辑无法被其他 service 复用，且单测必须模拟全部 SQL 行为，fixture 极其冗长。提取 `CustomerRepository` 到独立模块是重构路线图（#252 子任务）的第一步，后续各 service 都将遵循同一模式。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层重构。
- **开发者视角**：`CustomerRepository` 提供 10 个数据访问方法，`CustomerService` 通过组合（而非继承）调用它们；单测只需 mock `CustomerRepository`，不再触及 SQL mock handler。

### 1.3 不做什么（剔除）

- [ ] 不在本文件中引入事务边界变更（flush vs commit 由调用方控制）
- [ ] 不改动 `CustomerService` 的业务逻辑（只移动代码，不改变行为）
- [ ] 不创建 Alembic migration（不涉及 schema 变更）

### 1.4 关键 KPI

- [ ] `ruff check src/db/repositories/customer.py src/services/customer_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_repository.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed（原测全部通过，重构不破坏行为）

---

## 2. 当前现状（起点）

### 2.1 现有实现

`CustomerService` 中的数据访问方法（待迁移）：

TBD - 待验证：`src/services/customer_service.py` L? — 需确认 create / list / get_by_id / update / delete / count_by_status / search / add_tag / remove_tag / bulk_import 的具体行号和签名

同类已有 Repository 实现（参考模式）：

TBD - 待验证：`src/db/repositories/` 目录 — 需确认现有 repository 文件名和 `BaseRepository` 的签名

### 2.2 涉及文件清单

- 要改：
  - [`src/services/customer_service.py`](../../src/services/customer_service.py) — 将 10 个数据访问方法移除，改由 `CustomerRepository` 实例承载
  - [`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) — 单测 mock 路径相应更新
- 要建：
  - `src/db/repositories/customer.py` — `CustomerRepository(BaseRepository)` 含 10 个 query 方法
  - `tests/unit/test_customer_repository.py` — `CustomerRepository` 单元测试

### 2.3 缺什么

- [ ] `src/db/repositories/customer.py` 文件不存在，无 `CustomerRepository` 隔离层
- [ ] `CustomerService` 直接持有 `AsyncSession`，无法在 service 间共享同一组查询
- [ ] 无 `CustomerRepository` 的单测，无法独立验证数据访问逻辑

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/repositories/customer.py` | `CustomerRepository(BaseRepository)` 含 create / list / get_by_id / update / delete / count_by_status / search / add_tag / remove_tag / bulk_import |
| `tests/unit/test_customer_repository.py` | `CustomerRepository` 各方法的 mock 单测 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/customer_service.py`](../../src/services/customer_service.py) | 移除 10 个 query 方法；`__init__` 注入 `CustomerRepository` 实例 |
| [`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) | mock `CustomerRepository` 而非内联 SQL handler |

### 3.3 新增能力

- **ORM model**：`CustomerRepository(BaseRepository)` — 10 个 async 方法，全部使用 `session.flush()` 而非 `session.commit()`
- **Service 组合**：`CustomerService` 持有 `CustomerRepository` 实例，业务逻辑不变

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **组合而非继承**：`CustomerRepository(BaseRepository)` 而非直接在 `CustomerService` 上添加方法。理由：service 仍持有 session 并控制事务边界，repository 只负责构造查询并通过 flush 落 DB。
- **flush 而非 commit**：所有写操作调用 `session.flush()` 写入社交缓冲但不提交事务；事务提交由调用方（service → router → 请求结束时由 dependency 提交）负责。理由：与当前 `CustomerService` 行为一致，避免嵌套 commit 引发警告。

### 4.2 版本约束

N/A — 无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Repository 方法**不**调用 `.to_dict()`，返回 ORM 对象；序列化由 service/router 负责
- Repository 写操作使用 `session.flush()`，**不**使用 `session.commit()`
- `CustomerService.__init__` 保持 `session: AsyncSession`（无默认值），新增 `repository: CustomerRepository` 参数

### 4.4 已知坑

1. **SQLAlchemy 列名不可用 `metadata`** → 本文件不涉及新列；若后续扩展，`CustomerModel` 列名用 `event_metadata` / `payload` 等而非 `metadata`
2. **Alembic autogen 误写 JSON 而非 JSONB / TIMESTAMPTZ 而非 DateTime** → 本板块无 migration，无需关注
3. **PYTHONPATH=src** → import 写 `from db.repositories.base import BaseRepository` 而非 `from src.db.repositories...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 BaseRepository 参考，确认签名

[确认 `src/db/repositories/base.py` 中 `BaseRepository` 的 `__init__` 签名和已有通用方法（`get_by_id` 等是否已在上层实现）]

操作：
- a) 读取 `src/db/repositories/base.py` 确认 `BaseRepository.__init__(self, session: AsyncSession)` 签名
- b) 确认 `BaseRepository` 已有通用 CRUD 方法，或需在 `CustomerRepository` 中全部定义

**完成判定**：`ruff check src/db/repositories/base.py` → 0 errors

---

### Step 2: 创建 src/db/repositories/customer.py

[新建 `CustomerRepository(BaseRepository)`，将 `CustomerService` 中 10 个数据访问方法迁移过来，全部使用 `session.flush()` 而非 `session.commit()`]

操作：
- a) 新建 `src/db/repositories/customer.py`
- b) 实现 `CustomerRepository(BaseRepository)` 类，`__init__` 签名与 `BaseRepository` 一致
- c) 迁移方法：create / list / get_by_id / update / delete / count_by_status / search / add_tag / remove_tag / bulk_import
- d) 每个写方法末尾用 `await session.flush()`，不加 `commit()`

示例代码：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from db.repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    async def create(self, tenant_id: int, data: dict) -> CustomerModel:
        # ...

    async def list(self, tenant_id: int, page: int, page_size: int) -> tuple[list[CustomerModel], int]:
        # ...

    async def get_by_id(self, customer_id: int, tenant_id: int) -> CustomerModel | None:
        # ...

    async def update(self, customer_id: int, tenant_id: int, data: dict) -> CustomerModel:
        # ...

    async def delete(self, customer_id: int, tenant_id: int) -> None:
        # ...

    async def count_by_status(self, tenant_id: int) -> dict[str, int]:
        # ...

    async def search(self, tenant_id: int, query: str) -> list[CustomerModel]:
        # ...

    async def add_tag(self, customer_id: int, tenant_id: int, tag: str) -> None:
        # ...

    async def remove_tag(self, customer_id: int, tenant_id: int, tag: str) -> None:
        # ...

    async def bulk_import(self, tenant_id: int, rows: list[dict]) -> int:
        # ...
```

**完成判定**：`ruff check src/db/repositories/customer.py` → 0 errors

---

### Step 3: 重构 CustomerService 引用 CustomerRepository

[将 `CustomerService` 改为持有 `CustomerRepository` 实例，把 10 个 query 方法替换为委托调用，全部原有业务逻辑保持不变]

操作：
- a) 在 `CustomerService.__init__` 中新增 `repository: CustomerRepository` 参数
- b) 将原 10 个 query 方法体替换为 `return await self.repository.xxx(...)`
- c) 保留事务控制（flush 由 repository 负责，commit 由 router/dependency 负责）

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors

---

### Step 4: 创建 CustomerRepository 单元测试

[新建 `tests/unit/test_customer_repository.py`，用 `make_mock_session` + `MockState` 模拟 repository 各方法，验证返回类型和行为]

操作：
- a) 新建 `tests/unit/test_customer_repository.py`
- b) 定义 `mock_db_session` fixture（复用 `tests/unit/conftest.py` 中的 handler 辅助函数）
- c) 为 create / list / get_by_id / update / delete / count_by_status / search / add_tag / remove_tag / bulk_import 各写 1-2 个测试用例

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_repository.py -v` → 全 passed

---

### Step 5: 验证 CustomerService 单元测试仍然通过

[确认 `test_customer_service.py` 在重构后无需改动即可通过；若 mock 路径变化则相应更新]

操作：
- a) 运行 `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v`
- b) 如有失败，检查是否为 `CustomerRepository` mock 路径变更所致，相应更新 fixture

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/db/repositories/customer.py src/services/customer_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_repository.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- [ ] `mypy src/db/repositories/customer.py src/services/customer_service.py` → 0 errors（如 mypy 已配置）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 迁移方法时有遗漏，导致 `CustomerService` 行为改变 | 低 | 高 | revert `customer.py` 并恢复 `customer_service.py` 原状；本板块纯移动代码，不涉及业务逻辑变更，revert 安全 |
| `BaseRepository` 签名与假设不符，导致类型错误 | 中 | 低 | 在 `CustomerRepository` 中显式覆盖 `__init__`，不使用父类签名 |
| 现有测试 fixture 依赖 service 内部 SQL mock，迁移后需重写 | 低 | 中 | 同步更新 `test_customer_service.py` fixture，只需改 mock 对象名称，不改变断言逻辑 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/repositories/customer.py src/services/customer_service.py tests/unit/test_customer_repository.py
git commit -m "refactor(customer): extract CustomerRepository from CustomerService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "refactor: extract CustomerRepository from CustomerService" --body "Closes #430"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/repositories/` 下已有 repository 文件（如有）作为模式参考
- 第三方文档：[SQLAlchemy 2.0 Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- 父 issue / 关联：#252（重构路线图父 issue）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
