# Sales · Quote-to-Contract Workflow Automation

| 元数据 | 值 |
|---|---|
| Issue | #72 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 3-5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 90-frontend, 40-campaigns |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前销售管线（pipeline）仅支持商机阶段管理，缺乏报价 → 合同的标准流程。销售团队无法在系统内完成 quote-to-cash 全链路，PDF 报价单依赖人工生成，合同签署状态无法跟踪。竞品 HubSpot / Salesforce 均具备完整的 quote-to-contract 能力，此功能为 CRM 核心差异点。

### 1.2 做完后

- **用户视角**：销售可在商机详情页直接生成报价单，预填客户与产品信息；报价单支持 PDF 预览并邮件发送给客户；合同创建后可跟踪签署状态（sent / viewed / signed），过期前自动提醒。
- **开发者视角**：新增 `QuoteService`、`ContractService` 两个 service 类；新增 `POST/GET/PUT /quotes`、`POST/GET /contracts` 等 REST API；新增 `quotes`、`quote_items`、`contracts` 三张 ORM 模型及对应 Alembic migration。

### 1.3 不做什么（剔除）

- [ ] Frontend 实现（专属 `90-frontend` 板块负责）
- [ ] DocuSign / HelloSign API 实际对接（integration scaffolding 预埋，真实密钥注入由 infra 板块处理）
- [ ] 多语言 i18n / 邮件模板定制化
- [ ] 报价单历史版本（audit trail）
- [ ] 合同自动续约逻辑

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_quote_service.py tests/unit/test_contract_service.py -v` → ≥ 12 passed
- `PYTHONPATH=src pytest tests/integration/test_quote_contract_integration.py -v` → 全 passed
- `ruff check src/services/quote_service.py src/services/contract_service.py src/api/routers/quotes.py src/api/routers/contracts.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `mypy src/services/quote_service.py src/services/contract_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/opportunity.py` L? — 现有 `opportunities` 表 schema，确认 `tenant_id`、`customer_id`、`stage` 字段存在

TBD - 待验证：`src/services/opportunity_service.py` L? — 现有商机 service，确认已有 list/get 方法可扩展

TBD - 待验证：`src/api/routers/opportunities.py` L? — 现有商机 router，确认可追加 "Create Quote" action endpoint

### 2.2 涉及文件清单

- 要改：
  - `src/services/opportunity_service.py` — 新增 `create_quote_from_opportunity` 方法
  - `src/api/routers/opportunities.py` — 新增 `POST /opportunities/{id}/quote` endpoint
  - `src/db/models/opportunity.py` — 如需扩展关联字段
- 要建：
  - `src/db/models/quote.py` — `Quote`、`QuoteItem` ORM 模型
  - `src/db/models/contract.py` — `Contract` ORM 模型
  - `src/services/quote_service.py` — 报价单业务逻辑
  - `src/services/contract_service.py` — 合同业务逻辑
  - `src/api/routers/quotes.py` — 报价单 REST API
  - `src/api/routers/contracts.py` — 合同 REST API
  - `alembic/versions/<id>_create_quotes_contracts_tables.py` — schema migration
  - `tests/unit/test_quote_service.py` — unit test
  - `tests/unit/test_contract_service.py` — unit test
  - `tests/integration/test_quote_contract_integration.py` — integration test

### 2.3 缺什么

- [ ] `quotes` / `quote_items` / `contracts` 三张表及 ORM 模型
- [ ] `QuoteService` / `ContractService` 业务逻辑层
- [ ] `/quotes` / `/contracts` REST API 路由
- [ ] Alembic migration（含 `tenant_id` 索引）
- [ ] 商机 → 报价单快捷创建路径（`POST /opportunities/{id}/quote`）
- [ ] PDF 生成工具函数（weasyprint / reportlab）
- [ ] e-signature status tracking 字段与更新逻辑
- [ ] 完整的 unit + integration 测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/quote.py` | `Quote` 与 `QuoteItem` ORM 模型，含 `tenant_id` 索引 |
| `src/db/models/contract.py` | `Contract` ORM 模型，含 `tenant_id` 索引 |
| `src/services/quote_service.py` | 报价单创建 / 更新 / 状态变更 / PDF 生成业务逻辑 |
| `src/services/contract_service.py` | 合同创建 / 签署状态跟踪 / 过期提醒业务逻辑 |
| `src/api/routers/quotes.py` | 报价单 CRUD REST API（`/quotes` 路由） |
| `src/api/routers/contracts.py` | 合同 CRUD REST API（`/contracts` 路由） |
| `alembic/versions/<id>_create_quotes_contracts_tables.py` | `quotes`、`quote_items`、`contracts` 三表 migration |
| `tests/unit/test_quote_service.py` | `QuoteService` unit 测试（mock DB） |
| `tests/unit/test_contract_service.py` | `ContractService` unit 测试（mock DB） |
| `tests/integration/test_quote_contract_integration.py` | quote + contract integration 测试（real DB） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/opportunity_service.py`](../../src/services/opportunity_service.py) | 新增 `create_quote_from_opportunity(self, opportunity_id, tenant_id)` 方法 |
| [`src/api/routers/opportunities.py`](../../src/api/routers/opportunities.py) | 新增 `POST /opportunities/{opportunity_id}/quote` endpoint |
| `alembic/env.py` | import 新模型 `Quote`、`QuoteItem`、`Contract` 以便 autogenerate |

### 3.3 新增能力

- **ORM model**：`Quote` (`src/db/models/quote.py`)，字段：`id, tenant_id, opportunity_id, customer_id, amount, status, valid_until, created_at`
- **ORM model**：`QuoteItem` (`src/db/models/quote.py`)，字段：`id, quote_id, product_id, quantity, unit_price, discount`
- **ORM model**：`Contract` (`src/db/models/contract.py`)，字段：`id, tenant_id, quote_id, customer_id, amount, status, signed_at, expires_at`
- **Service method**：`QuoteService.create_quote(self, opportunity_id, tenant_id, items, discount) -> Quote`
- **Service method**：`QuoteService.send_quote(self, quote_id, tenant_id) -> Quote`（更新 status → sent，触发邮件）
- **Service method**：`ContractService.create_contract(self, quote_id, tenant_id) -> Contract`
- **Service method**：`ContractService.update_signature_status(self, contract_id, tenant_id, status) -> Contract`
- **API endpoint**：`POST /quotes` — 创建报价单
- **API endpoint**：`GET /quotes` — 列表（支持 status filter）
- **API endpoint**：`GET /quotes/{quote_id}` — 详情
- **API endpoint**：`PUT /quotes/{quote_id}` — 更新报价单（含 line items）
- **API endpoint**：`POST /quotes/{quote_id}/send` — 发送报价单
- **API endpoint**：`GET /quotes/{quote_id}/pdf` — 下载 PDF
- **API endpoint**：`POST /contracts` — 从报价单创建合同
- **API endpoint**：`GET /contracts` — 合同列表
- **API endpoint**：`GET /contracts/{contract_id}` — 合同详情
- **API endpoint**：`PUT /contracts/{contract_id}/signature-status` — 更新签署状态
- **Migration**：`alembic upgrade head` 创建 `quotes`、`quote_items`、`contracts` 三表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **PDF 生成选 WeasyPrint 不选 reportlab**：WeasyPrint 接收 HTML 模板，样式更好维护；reportlab 需要 imperative API，不利于模板化。后续 frontend 板块可复用同一 HTML 模板。
- **e-signature 状态走轮询而非 webhook**：初期接入 HelloSign/DocuSign mock，状态字段 `signature_status` (enum: pending / sent / viewed / signed / declined)，后续 infra 板块接入真实 webhook。
- **优惠（discount）存 `quote_items` 层级而非 `quote` 层级**：支持逐行折扣，更灵活；`Quote.total_amount` 在 service 层实时计算。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `weasyprint` | `>=60.0` | PDF 生成，HTML → PDF 转换，支持 CSS 分页 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`，每个 service 方法签名必须含 `tenant_id: int` 参数
- `Quote.__init__` / `Contract.__init__` 接收 `session: AsyncSession`，**禁止** `session=None` 默认值
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`）
- router inject session via `session: AsyncSession = Depends(get_db)`，**禁止** `async with get_db() as session:`
- 列名**禁止**使用 `metadata`（与 `Base.metadata` 冲突）→ 使用 `event_metadata` / `signature_metadata` 替代
- 所有 enum 字段使用 `ENUM` 类型（PostgreSQL），不在 Python 侧用 string free-text

### 4.4 已知坑

1. **Alembic autogenerate 把 `JSONB` 写成 `JSON`** → 规避：migration 手动改回 `sa.JSONB()`，并在 `alembic/env.py` 确认不覆盖
2. **Alembic autogenerate 遗漏 `timezone=True` on `DateTime`** → 规避：migration 手动改为 `DateTime(timezone=True)`，防止时区歧义
3. **列名 `metadata` 与 `Base.metadata` 冲突** → 规避：合同表用 `signature_metadata JSONB` 替代，报价单表用 `event_metadata JSONB`
4. **PYTHONPATH=src 导致 import 写成 `from src.db.models...`** → 规避：所有 import 必须 `from db.models...`，**禁止** `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ORM 模型（Quote / QuoteItem / Contract）

在 `src/db/models/` 下新增两个文件：

`src/db/models/quote.py`：

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class QuoteStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    EXPIRED = "expired"
    REJECTED = "rejected"


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        Index("ix_quotes_tenant_id", "tenant_id"),
        Index("ix_quotes_opportunity_id", "opportunity_id"),
        Index("ix_quotes_customer_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunities.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus), default=QuoteStatus.DRAFT)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    items: Mapped[list["QuoteItem"]] = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (Index("ix_quote_items_quote_id", "quote_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))

    quote: Mapped["Quote"] = relationship("Quote", back_populates="items")
```

`src/db/models/contract.py`：

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ContractStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    EXPIRED = "expired"
    DECLINED = "declined"


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("ix_contracts_tenant_id", "tenant_id"),
        Index("ix_contracts_quote_id", "quote_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotes.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus), default=ContractStatus.DRAFT)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.quote import Quote, QuoteItem, QuoteStatus; from db.models.contract import Contract, ContractStatus; print('models OK')"` → 退出码 0

---

### Step 2: 生成 Alembic Migration

参考 `alembic/env.py` 的 import 格式，在 `alembic/env.py` 新增：

```python
from db.models.quote import Quote, QuoteItem  # 新增
from db.models.contract import Contract        # 新增
```

然后执行 autogenerate（参考 CLAUDE.md §Alembic Migrations）：

```bash
# 1. 启动干净 DB
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. 对准 head
alembic upgrade head

# 3. 生成 diff
alembic revision --autogenerate -m "create_quotes_contracts_tables"

# 4. 手动修正 alembic/versions/<id>_create_quotes_contracts_tables.py：
#    - JSON → JSONB（如果有）
#    - DateTime → DateTime(timezone=True)（如果有）
#    - 确认 downgrade() 有 drop_table

# 5. 验证可双向迁移
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# 6. 二次 autogen 应产生空迁移（若有残留 drift 则补完）
alembic revision --autogenerate -m "drift_check"
# 若新文件 up/down 均 pass，删除该文件
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0；`alembic history --verbose | head -20` 显示新 revision

---

### Step 3: 实现 QuoteService

新建 `src/services/quote_service.py`：

```python
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.quote import Quote, QuoteItem, QuoteStatus
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class QuoteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_quote(
        self,
        opportunity_id: int,
        customer_id: int,
        tenant_id: int,
        items: list[dict],
        valid_until_days: int = 30,
    ) -> Quote:
        quote = Quote(
            tenant_id=tenant_id,
            opportunity_id=opportunity_id,
            customer_id=customer_id,
            status=QuoteStatus.DRAFT,
            valid_until=datetime.utcnow() + timedelta(days=valid_until_days),
        )
        self.session.add(quote)
        await self.session.flush()

        total = Decimal("0.00")
        for item in items:
            qi = QuoteItem(
                quote_id=quote.id,
                product_id=item["product_id"],
                quantity=item.get("quantity", 1),
                unit_price=Decimal(str(item["unit_price"])),
                discount=Decimal(str(item.get("discount", "0.00"))),
            )
            self.session.add(qi)
            line_total = qi.unit_price * qi.quantity * (1 - qi.discount / 100)
            total += line_total

        quote.amount = total
        await self.session.commit()
        await self.session.refresh(quote)
        return quote

    async def get_quote(self, quote_id: int, tenant_id: int) -> Quote:
        result = await self.session.execute(
            select(Quote)
            .options(selectinload(Quote.items))
            .where(Quote.id == quote_id, Quote.tenant_id == tenant_id)
        )
        quote = result.scalar_one_or_none()
        if quote is None:
            raise NotFoundException("Quote")
        return quote

    async def list_quotes(self, tenant_id: int, status: QuoteStatus | None = None, page: int = 1, page_size: int = 20) -> tuple[list[Quote], int]:
        query = select(Quote).where(Quote.tenant_id == tenant_id)
        if status:
            query = query.where(Quote.status == status)
        count_result = await self.session.execute(
            select(Quote.id).where(Quote.tenant_id == tenant_id)
        )
        total = len(count_result.scalars().all())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update_quote_items(self, quote_id: int, tenant_id: int, items: list[dict]) -> Quote:
        quote = await self.get_quote(quote_id, tenant_id)
        if quote.status not in (QuoteStatus.DRAFT,):
            raise ValidationException("Cannot update items on a non-draft quote")
        await self.session.execute(
            update(QuoteItem).where(QuoteItem.quote_id == quote_id)
        )
        for item in items:
            qi = QuoteItem(
                quote_id=quote_id,
                product_id=item["product_id"],
                quantity=item.get("quantity", 1),
                unit_price=Decimal(str(item["unit_price"])),
                discount=Decimal(str(item.get("discount", "0.00"))),
            )
            self.session.add(qi)
        await self.session.commit()
        return await self.get_quote(quote_id, tenant_id)

    async def send_quote(self, quote_id: int, tenant_id: int) -> Quote:
        quote = await self.get_quote(quote_id, tenant_id)
        if quote.status == QuoteStatus.SIGNED:
            raise ValidationException("Quote already signed")
        quote.status = QuoteStatus.SENT
        await self.session.commit()
        await self.session.refresh(quote)
        return quote

    async def update_status(self, quote_id: int, tenant_id: int, status: QuoteStatus) -> Quote:
        quote = await self.get_quote(quote_id, tenant_id)
        quote.status = status
        await self.session.commit()
        await self.session.refresh(quote)
        return quote
```

**完成判定**：`ruff check src/services/quote_service.py` → 0 errors；`mypy src/services/quote_service.py` → 0 errors

---

### Step 4: 实现 ContractService

新建 `src/services/contract_service.py`：

```python
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.contract import Contract, ContractStatus
from db.models.quote import Quote, QuoteStatus
from pkg.errors.app_exceptions import ConflictException, NotFoundException, ValidationException


class ContractService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_contract(self, quote_id: int, tenant_id: int) -> Contract:
        result = await self.session.execute(
            select(Quote).where(Quote.id == quote_id, Quote.tenant_id == tenant_id)
        )
        quote = result.scalar_one_or_none()
        if quote is None:
            raise NotFoundException("Quote")
        if quote.status != QuoteStatus.SIGNED:
            raise ValidationException("Contract can only be created from a signed quote")
        existing = await self.session.execute(
            select(Contract).where(Contract.quote_id == quote_id, Contract.tenant_id == tenant_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictException("Contract already exists for this quote")

        contract = Contract(
            tenant_id=tenant_id,
            quote_id=quote_id,
            customer_id=quote.customer_id,
            amount=quote.amount,
            status=ContractStatus.DRAFT,
        )
        self.session.add(contract)
        await self.session.commit()
        await self.session.refresh(contract)
        return contract

    async def get_contract(self, contract_id: int, tenant_id: int) -> Contract:
        result = await self.session.execute(
            select(Contract).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
        )
        contract = result.scalar_one_or_none()
        if contract is None:
            raise NotFoundException("Contract")
        return contract

    async def list_contracts(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Contract], int]:
        query = select(Contract).where(Contract.tenant_id == tenant_id).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        count_result = await self.session.execute(
            select(Contract.id).where(Contract.tenant_id == tenant_id)
        )
        total = len(count_result.scalars().all())
        return list(result.scalars().all()), total

    async def update_signature_status(
        self, contract_id: int, tenant_id: int, status: ContractStatus, signed_at: datetime | None = None
    ) -> Contract:
        contract = await self.get_contract(contract_id, tenant_id)
        contract.status = status
        if signed_at is not None:
            contract.signed_at = signed_at
        await self.session.commit()
        await self.session.refresh(contract)
        return contract
```

**完成判定**：`ruff check src/services/contract_service.py` → 0 errors；`mypy src/services/contract_service.py` → 0 errors

---

### Step 5: 实现 REST API 路由

新建 `src/api/routers/quotes.py`：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.opportunities import get_db
from db.models.quote import QuoteStatus
from services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["Quotes"])


@router.post("/")
async def create_quote(
    payload: dict,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quote = await svc.create_quote(
        opportunity_id=payload["opportunity_id"],
        customer_id=payload["customer_id"],
        tenant_id=ctx.tenant_id,
        items=payload["items"],
        valid_until_days=payload.get("valid_until_days", 30),
    )
    return {"success": True, "data": quote.to_dict()}


@router.get("/")
async def list_quotes(
    status: QuoteStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quotes, total = await svc.list_quotes(ctx.tenant_id, status=status, page=page, page_size=page_size)
    return {
        "success": True,
        "data": {
            "items": [q.to_dict() for q in quotes],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{quote_id}")
async def get_quote(
    quote_id: int,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quote = await svc.get_quote(quote_id, ctx.tenant_id)
    return {"success": True, "data": quote.to_dict()}


@router.put("/{quote_id}")
async def update_quote(
    quote_id: int,
    payload: dict,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quote = await svc.update_quote_items(quote_id, ctx.tenant_id, payload["items"])
    return {"success": True, "data": quote.to_dict()}


@router.post("/{quote_id}/send")
async def send_quote(
    quote_id: int,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quote = await svc.send_quote(quote_id, ctx.tenant_id)
    return {"success": True, "data": quote.to_dict()}
```

新建 `src/api/routers/contracts.py`：

```python
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.opportunities import get_db
from services.contract_service import ContractService

router = APIRouter(prefix="/contracts", tags=["Contracts"])


class SignatureStatusPayload(BaseModel):
    status: str
    signed_at: datetime | None = None


@router.post("/")
async def create_contract(
    payload: dict,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ContractService(session)
    contract = await svc.create_contract(payload["quote_id"], ctx.tenant_id)
    return {"success": True, "data": contract.to_dict()}


@router.get("/")
async def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ContractService(session)
    contracts, total = await svc.list_contracts(ctx.tenant_id, page=page, page_size=page_size)
    return {
        "success": True,
        "data": {
            "items": [c.to_dict() for c in contracts],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{contract_id}")
async def get_contract(
    contract_id: int,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ContractService(session)
    contract = await svc.get_contract(contract_id, ctx.tenant_id)
    return {"success": True, "data": contract.to_dict()}


@router.put("/{contract_id}/signature-status")
async def update_signature_status(
    contract_id: int,
    payload: SignatureStatusPayload,
    ctx=Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ContractService(session)
    from db.models.contract import ContractStatus
    status_enum = ContractStatus(payload.status)
    contract = await svc.update_signature_status(contract_id, ctx.tenant_id, status_enum, payload.signed_at)
    return {"success": True, "data": contract.to_dict()}
```

**完成判定**：`ruff check src/api/routers/quotes.py src/api/routers/contracts.py` → 0 errors

---

### Step 6: 扩展 OpportunityService 与路由（Create Quote 快捷入口）

在 `src/services/opportunity_service.py` 新增方法：

```python
async def create_quote_from_opportunity(self, opportunity_id: int, tenant_id: int, items: list[dict], valid_until_days: int = 30) -> Quote:
    """Create a Quote pre-filled from an Opportunity's customer and products."""
    opp = await self.get_opportunity(opportunity_id, tenant_id)
    from services.quote_service import QuoteService
    quote_svc = QuoteService(self.session)
    return await quote_svc.create_quote(
        opportunity_id=opportunity_id,
        customer_id=opp.customer_id,
        tenant_id=tenant_id,
        items=items,
        valid_until_days=valid_until_days,
    )
```

在 `src/api/routers/opportunities.py` 新增 endpoint：

```python
@router.post("/{opportunity_id}/quote")
async def create_quote_from_opportunity(
    opportunity_id: int,
    payload: dict,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    quote = await svc.create_quote_from_opportunity(
        opportunity_id=opportunity_id,
        tenant_id=ctx.tenant_id,
        items=payload["items"],
        valid_until_days=payload.get("valid_until_days", 30),
    )
    return {"success": True, "data": quote.to_dict()}
```

**完成判定**：`ruff check src/services/opportunity_service.py src/api/routers/opportunities.py` → 0 errors

---

### Step 7: 编写单元测试

`tests/unit/test_quote_service.py`（使用 `MockState` + `make_mock_session`，参考 CLAUDE.md §Unit Test SQL Mocks）：

```python
import pytest
from decimal import Decimal

from services.quote_service import QuoteService
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])

@pytest.fixture
def quote_service(mock_db_session):
    return QuoteService(mock_db_session)

class TestQuoteService:
    async def test_create_quote_draft(self, quote_service, mock_db_session):
        # mock opportunity/customer exist in state
        quote = await quote_service.create_quote(
            opportunity_id=1, customer_id=1, tenant_id=1,
            items=[{"product_id": 1, "unit_price": "100.00", "quantity": 2, "discount": "0.00"}],
        )
        assert quote.status.value == "draft"
        assert quote.amount == Decimal("200.00")

    async def test_get_quote_not_found(self, quote_service):
        from pkg.errors.app_exceptions import NotFoundException
        with pytest.raises(NotFoundException):
            await quote_service.get_quote(9999, tenant_id=1)

    async def test_send_quote_updates_status(self, quote_service):
        quote = await quote_service.create_quote(
            opportunity_id=1, customer_id=1, tenant_id=1,
            items=[{"product_id": 1, "unit_price": "50.00", "quantity": 1}],
        )
        sent = await quote_service.send_quote(quote.id, tenant_id=1)
        assert sent.status.value == "sent"

    async def test_list_quotes_with_filter(self, quote_service):
        await quote_service.create_quote(1, 1, 1, [{"product_id": 1, "unit_price": "10.00"}])
        quotes, total = await quote_service.list_quotes(tenant_id=1, page=1, page_size=20)
        assert total >= 1
```

`tests/unit/test_contract_service.py`（结构同上，覆盖 create_contract、update_signature_status、ConflictException/ValidationException 路径）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_quote_service.py tests/unit/test_contract_service.py -v` → ≥ 12 passed

---

### Step 8: 编写集成测试

`tests/integration/test_quote_contract_integration.py`（使用 `db_schema`、`tenant_id`、`async_session` fixtures；参考 CLAUDE.md §Integration Test Fixtures）：

```python
import pytest
from datetime import datetime, timedelta

from db.models.opportunity import Opportunity
from db.models.customer import Customer
from services.quote_service import QuoteService
from services.contract_service import ContractService
from db.models.quote import QuoteStatus
from db.models.contract import ContractStatus
from pkg.errors.app_exceptions import ValidationException, ConflictException, NotFoundException

@pytest.mark.integration
class TestQuoteContractIntegration:
    async def test_full_quote_to_contract_flow(self, db_schema, tenant_id, async_session):
        # Seed customer + opportunity
        customer = Customer(name="Test Customer", tenant_id=tenant_id)
        async_session.add(customer)
        await async_session.flush()
        opp = Opportunity(customer_id=customer.id, tenant_id=tenant_id, name="Test Opp", stage="proposal")
        async_session.add(opp)
        await async_session.flush()

        # Create quote
        quote_svc = QuoteService(async_session)
        quote = await quote_svc.create_quote(
            opportunity_id=opp.id, customer_id=customer.id, tenant_id=tenant_id,
            items=[{"product_id": 1, "unit_price": "500.00", "quantity": 2}],
        )
        assert quote.status == QuoteStatus.DRAFT

        # Send quote
        quote = await quote_svc.send_quote(quote.id, tenant_id=tenant_id)
        assert quote.status == QuoteStatus.SENT

        # Mark as signed
        quote = await quote_svc.update_status(quote.id, tenant_id=tenant_id, status=QuoteStatus.SIGNED)

        # Create contract
        contract_svc = ContractService(async_session)
        contract = await contract_svc.create_contract(quote.id, tenant_id=tenant_id)
        assert contract.amount == quote.amount

        # Update signature status
        contract = await contract_svc.update_signature_status(
            contract.id, tenant_id=tenant_id, status=ContractStatus.SIGNED, signed_at=datetime.utcnow()
        )
        assert contract.status == ContractStatus.SIGNED
        assert contract.signed_at is not None

    async def test_contract_requires_signed_quote(self, db_schema, tenant_id, async_session):
        customer = Customer(name="Test Customer", tenant_id=tenant_id)
        async_session.add(customer)
        await async_session.flush()
        opp = Opportunity(customer_id=customer.id, tenant_id=tenant_id, name="Test Opp", stage="proposal")
        async_session.add(opp)
        await async_session.flush()

        quote_svc = QuoteService(async_session)
        quote = await quote_svc.create_quote(
            opportunity_id=opp.id, customer_id=customer.id, tenant_id=tenant_id,
            items=[{"product_id": 1, "unit_price": "100.00"}],
        )
        contract_svc = ContractService(async_session)
        with pytest.raises(ValidationException, match="signed quote"):
            await contract_svc.create_contract(quote.id, tenant_id=tenant_id)

    async def test_duplicate_contract_raises_conflict(self, db_schema, tenant_id, async_session):
        customer = Customer(name="Test Customer", tenant_id=tenant_id)
        async_session.add(customer)
        await async_session.flush()
        opp = Opportunity(customer_id=customer.id, tenant_id=tenant_id, name="Test Opp", stage="proposal")
        async_session.add(opp)
        await async_session.flush()

        quote_svc = QuoteService(async_session)
        quote = await quote_svc.create_quote(opp.id, customer.id, tenant_id, [{"product_id": 1, "unit_price": "100.00"}])
        quote = await quote_svc.update_status(quote.id, tenant_id, QuoteStatus.SIGNED)

        contract_svc = ContractService(async_session)
        await contract_svc.create_contract(quote.id, tenant_id)
        with pytest.raises(ConflictException, match="already exists"):
            await contract_svc.create_contract(quote.id, tenant_id)
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" PYTHONPATH=src pytest tests/integration/test_quote_contract_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/quote_service.py src/services/contract_service.py src/api/routers/quotes.py src/api/routers/contracts.py src/services/opportunity_service.py src/api/routers/opportunities.py` → 0 errors
- [ ] `mypy src/services/quote_service.py src/services/contract_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_quote_service.py tests/unit/test_contract_service.py -v` → ≥ 12 passed
- [ ] `DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" PYTHONPATH=src pytest tests/integration/test_quote_contract_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic migration 中 `JSON` 写成 `JSONB` 导致 prod 数据丢失（若 prod 已存在 shadow JSON 列） | 低 | 高 | 回退 migration：`alembic downgrade <prev_rev>`；删除 JSON 列重建 |
| QuoteStatus / ContractStatus enum 变更需要 data migration | 低 | 中 | 写一次性 data migration 脚本，对齐现有 string 值到 enum |
| PDF 生成依赖 WeasyPrint 系统库（cairo / pango）在 Docker 环境缺失 | 中 | 中 | Dockerfile 添加 `apt-get install libpango-1.0-0 libpangocairo-1.0-0`；feature flag `PDF_ENABLED=false` 禁用 |
| Frontend 板块未就绪时后端 API 已合入，后续 schema 变更需额外 migration | 低 | 低 | API 保持向前兼容，不删字段仅新增；migration 按 additive 为主 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/quote.py src/db/models/contract.py \
        src/services/quote_service.py src/services/contract_service.py \
        src/services/opportunity_service.py \
        src/api/routers/quotes.py src/api/routers/contracts.py \
        src/api/routers/opportunities.py \
        alembic/versions/<id>_create_quotes_contracts_tables.py \
        tests/unit/test_quote_service.py tests/unit/test_contract_service.py \
        tests/integration/test_quote_contract_integration.py
git commit -m "feat(sales): quote-to-contract workflow — QuoteService, ContractService, REST APIs"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): Quote-to-Contract Workflow Automation" --body "Closes #72"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/opportunity_service.py` — 现有商机 service 结构，可作 QuoteService / ContractService 范式参考
- 父 issue / 关联：#72
- PROD_SPEC.md 中已定义 `quotes` / `contracts` 表 schema（见 issue Dependencies 段落）
