# Roadmap: db-migration — services-to-database migration

**Created:** 2026-04-13T12:53 UTC
**Total tasks:** 11 (roadmap indices 06–11; indices 00–05 are done or in-flight)
**Feature slug:** `db-migration`
**Status:** in progress — ORM batch 1 (identity tables) PR in flight

## What is done (out of scope for this roadmap)

| # | task_id | Title | Status |
|---|---------|-------|--------|
| 00 | — | MANUAL: add sqlalchemy + psycopg2-binary to pyproject.toml | ✅ PR #8 merged |
| 01 | research-manual-db-engine | SQLAlchemy engine/session/Base infra in src/internal/db/ | ✅ committed (0b93259) |
| 02 | research-manual-orm-identity | ORM models batch 1 — identity tables (tenants/users/roles) | 🔄 PR in flight |

## Remaining roadmap (06–11)

```
06 ──► 07 ──► 08 ──► 09 ──► 10 ──► 11
                                └──────┘
```

| # | task_id | Title | Kind | Depends |
|---|---------|-------|------|---------|
| 06 | roadmap-db-migration-06-orm-batch2-customers-sales | ORM models batch 2 — customer & sales tables (16 tables) | refactor | 02 (identity batch) |
| 07 | roadmap-db-migration-07-orm-batch3-marketing-activity | ORM models batch 3 — marketing, activity & ticket tables (19 tables) | refactor | 06 |
| 08 | roadmap-db-migration-08-orm-batch4-analytics-automation | ORM models batch 4 — analytics, automation & product tables | refactor | 07 |
| 09 | roadmap-db-migration-09-repository-base | Add GenericRepository[T] base class with CRUD + tenant isolation | refactor | 08 |
| 10 | roadmap-db-migration-10-customer-service-rewire | Rewire CustomerService to use CustomerRepository | refactor | 09 |
| 11 | roadmap-db-migration-11-services-rewire-remaining | Rewire TicketService + remaining 5 services to use repositories | refactor | 09 |

## Task summaries

### 06 — ORM batch 2 (customer & sales, 16 tables)
**target_files:** `src/internal/db/models/customer.py`, `models/sales.py`, `models/__init__.py`, 2 test files
**Tables:** Customer, CustomerContact, CustomerAddress, CustomerTag, Tag, CustomerOwnerHistory, CustomerMergeLog, CustomerFollower, CustomerCustomField, CustomerFieldValue, Lead, LeadSource, LeadAssignment, Opportunity, OpportunityStage, OpportunityStageHistory, OpportunityProduct, Quote, QuoteItem, Contract

### 07 — ORM batch 3 (marketing, activity & ticket, 23 tables)
**target_files:** `src/internal/db/models/marketing.py`, `activity.py`, `ticket.py`, 3 test files
**Tables:** Campaign, CampaignMember, EmailTemplate, EmailSend, EmailEvent, SmsSend, MarketingSegment, SegmentFilter (8); Activity, ActivityType, Task, TaskComment, Meeting, CallLog, EmailLog, Reminder, CalendarEvent, EventAttendee (10); Ticket, TicketComment, TicketStatusHistory, TicketSla, TicketAssignment (5)

### 08 — ORM batch 4 (analytics, automation, product)
**target_files:** `src/internal/db/models/analytics.py`, `automation.py`, `product.py`, 3 test files
**Covers:** all tables not yet modelled in batches 1–3 (sections 7+ of 001_schema.sql)

### 09 — GenericRepository[T] base class
**target_files:** `src/internal/repository/base.py`, `__init__.py`, `tests/unit/test_repository_base.py`
**Symbols:** `GenericRepository[T]`, `create()`, `get_by_id()`, `update()`, `delete()`, `list()`, `count()`, `_apply_tenant_filter()` — raises `PermissionError` on cross-tenant access

### 10 — CustomerService rewire
**target_files:** `src/services/customer_service.py`, `src/internal/repository/customer_repository.py`, `tests/unit/test_customer_service.py`
**New symbols:** `CustomerRepository(GenericRepository[Customer])`, `find_by_owner(owner_id, tenant_id)`, `find_by_status(status, tenant_id)`, `search(keyword, tenant_id)`

### 11 — Remaining services rewire (7 services in one task)
**target_files:** 16 files — ticket/activity/marketing/sales/analytics services + 6 repository files + 4 test files
**New symbols per service:** `<Name>Repository(GenericRepository[<Model>])` + domain finders per service
**Services:** TicketService, ActivityService, MarketingService, SalesService, AnalyticsService, NotificationService, ChurnPredictionService

## Manual prerequisites

None — all implementable by the autonomous pipeline.

## Out of scope (per roadmap spec)

- Any change to `pyproject.toml`, `.github/`, `deploy.js`, `railway-deploy.js`
- `scripts/` pipeline infrastructure files
- Actual Supabase migration runs (all ORM work is schema-declaration only)
- API route changes to wire new repositories into HTTP endpoints

## Diff budget notes

| Task | Est. model lines | Est. test lines | Risk |
|------|-----------------|-----------------|------|
| 06 | ~220 | ~120 | Split into 2 test files to stay ≤400 lines |
| 07 | ~280 | ~120 | Likely needs split into marketing/activity/ticket test files |
| 08 | ~150 | ~100 | Smaller batch, lower risk |
| 09 | ~100 | ~80 | Simple base class, low risk |
| 10 | ~100 | ~50 | One service, low risk |
| 11 | ~300 | ~100 | Most complex task; if >400 lines, split into two tasks |


## Roadmap update (added 2026-04-13 13:10)

After deciding the MySQL/Postgres mismatch resolution: ORM models are the source of truth, alembic owns migrations, sql/001_schema.sql gets archived. Adds tasks 12 and 13.

| # | task_id | Title | Kind | Priority | Depends |
|---|---------|-------|------|----------|---------|
| 12 | roadmap-db-migration-12-alembic-init | Alembic init + autogenerated initial migration applied to Supabase | refactor | medium | 06, 07, 08 (all ORM batches) |
| 13 | roadmap-db-migration-13-archive-legacy-sql | MANUAL: archive sql/001_schema.sql + write MIGRATION_NOTES.md | docs | high (HUMAN) | 12 |

### Manual prerequisite for Task 12
- PR #11 (deps/add-alembic) must merge first — adds alembic to pyproject.toml.

### Why this approach
- Single source of truth: ORM in `src/internal/db/models/` -> alembic autogen -> applied to Postgres.
- Avoids translating 1644 lines of MySQL DDL by hand.
- Future schema changes follow `alembic revision --autogenerate -m "..." && alembic upgrade head`.
- sql/001_schema.sql remains as legacy reference until Task 13.
