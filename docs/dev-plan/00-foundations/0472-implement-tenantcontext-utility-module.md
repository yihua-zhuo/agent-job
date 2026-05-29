# TenantContext · 线程安全租户上下文工具模块

| 元数据 | 值 |
|---|---|
| Issue | #472 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [TenantMiddleware 实现](../00-foundations/0473-implement-tenantmiddleware-and-require-tenant-dependency.md) |
| 启用后赋能 | [ActivityService CRUD + 列表](../20-sales/0485-add-missing-activityservice-methods.md), [TenantService CRUD](../99-misc/0474-implement-tenantservice-with-crud-and-list-tenants.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前代码中跨协程传递 `tenant_id` 依赖手写参数层层透传，缺乏统一上下文存储机制，导致异步调用路径上容易遗漏 `tenant_id` 参数。FastAPI 路由层每次都从 `AuthContext` 取值后再手动传入 service — 这是一种可消除的重复样板。TenantMiddleware（#473）的底层需要一个线程/协程安全的存储载体，供其在请求入口处写入 `tenant_id`，供下游任何 service 在无需显式传入的情况下读取。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层工具模块。
- **开发者视角**：`from internal.middleware.tenant_context import set_tenant_id, get_tenant_id, clear` 即可在任意 async 上下文读写当前租户 ID，无需额外科林传递。后续 #473 TenantMiddleware 写入，后续 service 直接调用 `get_tenant_id()` 获取。

### 1.3 不做什么（剔除）

- [ ] 不实现 TenantMiddleware — 那是 #473 的工作
- [ ] 不实现 TenantService — 那是 #474 的工作
- [ ] 不引入 FastAPI / Starlette 依赖
- [ ] 不作为 `get_db` 替代品或 session provider

### 1.4 关键 KPI

- [`PYTHONPATH=src pytest tests/unit/test_tenant_context.py -v` → `2 passed`]
- [`ruff check src/internal/middleware/tenant_context.py` → 0 errors]
- [`ruff check src/internal/middleware/tenant_context.py && ruff format --check src/internal/middleware/tenant_context.py` → 全部 exit 0]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

`src/internal/middleware/` 目录尚未存在，`tenant_context.py` 为全新创建。相关已有代码参考：

- `src/dependencies/` 下有 `require_auth` 和 `AuthContext` 定义（从属 #473），其中 `AuthContext` 包含 `tenant_id: int` 字段
- 现有 service 构造签名均为 `__init__(self, session: AsyncSession)`，尚无从 context 读取 tenant 的先例

**待验证**：`src/internal/middleware/` 目录是否已存在；若已存在 `__init__.py`，其导出内容。

### 2.2 涉及文件清单

- 要改：
  - `src/internal/middleware/__init__.py` — 新增 `tenant_context` 三函数导出（如文件存在）
- 要建：
  - `src/internal/middleware/tenant_context.py` — 核心模块
  - `tests/unit/test_tenant_context.py` — 单元测试

### 2.3 缺什么

- [ ] 无线程/协程安全的 `tenant_id` 上下文存储，service 无法从 context 读取当前租户
- [ ] 无 `set_tenant_id` / `get_tenant_id` / `clear` 三合一工具 API
- [ ] 无针对 tenant context 的单元测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/internal/middleware/tenant_context.py` | 线程安全 tenant_id 上下文存储，基于 `contextvars` |
| `tests/unit/test_tenant_context.py` | 覆盖 `test_set_and_get_tenant_id` 和 `test_clear_tenant_id` 两个用例 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/internal/middleware/__init__.py` | 新增 `set_tenant_id, get_tenant_id, clear` 导出（若文件存在） |

### 3.3 新增能力

- **Python module**：`src/internal/middleware/tenant_context.py`，无外部依赖
- **Public API**：
  - `set_tenant_id(tenant_id: int) -> None`
  - `get_tenant_id() -> int | None`
  - `clear() -> None`
- **Unit tests**：`tests/unit/test_tenant_context.py`，2 个测试用例

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `contextvars.ContextVar` 不选 `threading.local`**：`contextvars` 是 Python 3.7+ 为异步场景设计的上下文本地存储，自动在 `asyncio` 协程间正确传播；`threading.local` 在 async/await 场景下同一线程内跨协程会意外共享状态。本 CRM 为全异步架构，选 `contextvars` 是唯一正确选项。
- **选独立 utility module 不放进 TenantMiddleware**：单一职责，TenantMiddleware 写入 context，utility 负责存储，职责清晰且可独立测试。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| Python | ≥ 3.11（项目已有） | `contextvars` 在 3.7+ 可用，本项目使用 3.11+ |

### 4.3 兼容性约束

- 不得引入 `fastapi`、`starlette`、`sqlalchemy` 依赖 — 这是纯 stdlib 工具
- `clear()` 必须在请求结束时（如 TenantMiddleware 依赖块中）被调用，防止 tenant_id 泄漏到下一个请求
- `get_tenant_id()` 返回 `int | None`，调用方需自行处理 `None` 场景（不应静默默认为 0）

### 4.4 已知坑

1. **contextvars 在 fork 后丢失（如 uvicorn 重载）** → 规避：每次请求由 TenantMiddleware 重新 `set_tenant_id`，不在进程启动时预先写入
2. **误用 `contextvars` 导致跨协程串台（理论上不会，但容易和 `threading.local` 混淆）** → 规避：模块级写明文档字符串，且单元测试覆盖跨协程传播场景

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/internal/middleware/tenant_context.py`

创建目录结构（若不存在）并写入核心模块。使用 `contextvars.ContextVar` 实现线程/协程安全存储。

操作：
- a) 确认目录 `src/internal/middleware/` 存在，不存在则创建
- b) 创建 `tenant_context.py`，内容如下：

```python
"""Thread-safe tenant ID storage using contextvars.

Unlike threading.local, ContextVar correctly propagates across
asyncio tasks within the same request context.
"""
from contextvars import ContextVar
from typing import Optional

_tenant_id_var: ContextVar[Optional[int]] = ContextVar("tenant_id", default=None)


def set_tenant_id(tenant_id: int) -> None:
    """Store the current tenant_id in the request context."""
    _tenant_id_var.set(tenant_id)


def get_tenant_id() -> Optional[int]:
    """Retrieve the current tenant_id from the request context.

    Returns None if no tenant context has been set.
    """
    return _tenant_id_var.get()


def clear() -> None:
    """Clear the tenant context.

    Call this at the end of a request to prevent tenant_id leaking
    into subsequent requests processed by the same worker.
    """
    _tenant_id_var.set(None)
```

**完成判定**：`ruff check src/internal/middleware/tenant_context.py` → 0 errors

### Step 2: 更新 `src/internal/middleware/__init__.py` 导出

若 `__init__.py` 存在，追加三函数导出；若不存在则创建空文件（仅含 `__init__.py` 标记）并添加导出。

操作：
- a) 检查 `src/internal/middleware/__init__.py` 是否存在
- b) 写入或追加以下内容：

```python
from .tenant_context import clear, get_tenant_id, set_tenant_id

__all__ = ["clear", "get_tenant_id", "set_tenant_id"]
```

**完成判定**：`ruff check src/internal/middleware/__init__.py` → 0 errors

### Step 3: 编写单元测试 `tests/unit/test_tenant_context.py`

创建测试文件，覆盖两个指定用例，另补充一个协程传播测试。

```python
"""Unit tests for tenant_context module."""
import pytest
from tests.unit.conftest import *  # noqa: F403

from internal.middleware.tenant_context import clear, get_tenant_id, set_tenant_id


class TestTenantContext:
    def test_set_and_get_tenant_id(self):
        clear()
        set_tenant_id(42)
        assert get_tenant_id() == 42
        clear()

    def test_clear_tenant_id(self):
        set_tenant_id(99)
        clear()
        assert get_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_id_propagates_across_await(self):
        clear()
        set_tenant_id(7)

        async def helper():
            return get_tenant_id()

        result = await helper()
        assert result == 7
        clear()
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tenant_context.py -v` → `3 passed`

### Step 4: Ruff 检查与格式化验证

操作：
- 运行 `ruff check src/internal/middleware/tenant_context.py tests/unit/test_tenant_context.py`
- 运行 `ruff format --check src/internal/middleware/tenant_context.py tests/unit/test_tenant_context.py`
- 修正所有报告的问题

**完成判定**：两条命令均 exit 0

---

## 6. 验收

- [ ] `ruff check src/internal/middleware/tenant_context.py tests/unit/test_tenant_context.py` → 0 errors
- [ ] `ruff format --check src/internal/middleware/tenant_context.py tests/unit/test_tenant_context.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_tenant_context.py -v` → `3 passed`
- [ ] `PYTHONPATH=src python -c "from internal.middleware.tenant_context import set_tenant_id, get_tenant_id, clear; clear(); set_tenant_id(1); assert get_tenant_id() == 1; clear(); assert get_tenant_id() is None; print('OK')"` → `OK`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#473 TenantMiddleware` 未正确调用 `clear()` 导致 tenant_id 跨请求泄漏 | 低 | 高 | 在 TenantMiddleware `finally` 块强制调用 `tenant_context.clear()`；本板块交付的 `clear()` API 已就绪，泄漏问题属于 #473 的接入缺陷，不阻塞合入 |
| 未来某 service 错误依赖 `get_tenant_id()` 而忘记传入 `tenant_id` 导致查询缺少租户过滤 | 中 | 高 | 后续 #488 ActivityService 等所有 service 审查中明确"context 只用于日志/tracing，查询仍需显式 tenant_id 参数"；CodeReview 阶段拦截 |
| `contextvars` 在极端嵌套协程场景下行为不符合预期 | 低 | 低 | 已有 `test_tenant_id_propagates_across_await` 覆盖基本路径；后续发现边界场景追加测试即可 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/internal/middleware/tenant_context.py src/internal/middleware/__init__.py tests/unit/test_tenant_context.py
git commit -m "feat(foundations): add TenantContext utility module (closes #472)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(foundations): add TenantContext utility module" --body "Closes #472"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/dependencies/` 下 `AuthContext` 定义（#473 引入）
- 第三方文档：[contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html)
- 父 issue：#447
- 依赖板块：#471（TenantMiddleware 框架），#473（TenantMiddleware 完整实现）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
