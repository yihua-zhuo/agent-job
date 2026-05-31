# Implementation Plan — Issue #662

## Goal

Create `NotificationTemplateModel` ORM class in `src/db/models/notification_template.py` with fields `id`, `name`, `channel`, `subject`, `body_html`, `body_text`, `created_at`, and generate the corresponding Alembic migration to create the `notification_templates` table. No service, router, or API layer is included — this is purely the data model + migration step of the notification system (parent issue #646).

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0662-add-notificationtemplatemodel-and-migration.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/40-campaigns/0662-add-notificationtemplatemodel-and-migration.md`

## Affected Files

- `src/db/models/notification_template.py` — **new file** — `NotificationTemplateModel` ORM class
- `alembic/versions/merge_nt_662.py` — **new file** — merge migration converging two heads (52b19ee00eaf and 5d575a161b5d) into a single timeline head
- `tests/unit/test_notification_template_model.py` — **new file** — unit tests for the model
- `src/db/models/__init__.py` — no changes needed (auto-discovery via `pkgutil.iter_modules`)
- `alembic/env.py` — no changes needed (imports `db.models` which triggers auto-discovery)

## Implementation Steps

### Step 1: Create `NotificationTemplateModel` ORM class

Write `src/db/models/notification_template.py` with the exact content specified in the dev-plan §5 Step 1.

```python
"""NotificationTemplate ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationTemplateModel(Base):
    """NotificationTemplate entity mapped to the `notification_templates` table."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_tenant_id", "tenant_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "channel": self.channel,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**Verification**: `ruff check src/db/models/notification_template.py` → 0 errors

---

### Step 2: Generate Alembic migration

Ensure `alembic_dev` database is clean and up-to-date, then run `--autogenerate`.

```bash
# a) Start test-db if not running
docker compose -f configs/docker-compose.test.yml up -d test-db

# b) Reset alembic_dev
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# c) Stamp head on the new DB so autogenerate sees a clean baseline
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic stamp e7f6a5b3c12d

# d) Generate the migration
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic revision --autogenerate -m "add_notification_templates"
```

Then manually review the generated `alembic/versions/<id>_add_notification_templates.py`:
- `created_at` column must use `DateTime(timezone=True)` (not bare `DateTime`)
- `created_at` must have `server_default=sa.text('now()')` (not `server_default=func.now()`)
- `down_revision` must reference `e7f6a5b3c12d`
- `name`, `channel`, `subject`, `body_html`, `body_text` column types must match the model (String/Text)

If any type is wrong (e.g., autogen wrote bare `DateTime` instead of `DateTime(timezone=True)`), fix the migration file manually before proceeding.

```bash
# e) Verify migrate-up → migrate-down → migrate-up cycle
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic upgrade head
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic downgrade -1
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic upgrade head
```

**Verification**: all three commands exit 0.

---

### Step 3: Write unit tests

Write `tests/unit/test_notification_template_model.py` with the three test cases from the dev-plan §5 Step 3: `test_to_dict_returns_all_fields`, `test_to_dict_with_null_optional_fields`, `test_table_name`.

**Verification**: `PYTHONPATH=src pytest tests/unit/test_notification_template_model.py -v` → 3 passed

---

### Step 4: Drift check

Re-run autogenerate against the same DB to confirm no additional diff exists.

```bash
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" \
  alembic revision --autogenerate -m "drift_check"
```

Inspect the generated `alembic/versions/<id>_drift_check.py` — both `up()` and `down()` must contain only `pass`. If they contain any `create_table` / `drop_table` calls, the model and DB are out of sync; return to Step 1.

**Verification**: drift_check migration up/down contain only `pass`, then delete the drift_check file.

---

## Test Plan

- Unit tests in `tests/unit/`: `tests/unit/test_notification_template_model.py` (new) — 6 passing tests covering `to_dict()` serialization of all fields including `updated_at`, null optional fields, `__tablename__`, name/subject length, and invalid-input acceptance boundaries
- Integration tests in `tests/integration/`: none (model-only issue; integration tests belong to the service/router layer in a later issue)
- Dev-plan verification commands:
  - `ruff check src/db/models/notification_template.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_notification_template_model.py -v` → 3 passed
  - `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
  - `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic downgrade -1` → exit 0
  - `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
  - drift check autogenerate → empty migration (up/down only `pass`)

## Acceptance Criteria

- `src/db/models/notification_template.py` exists, defines `NotificationTemplateModel` with fields: `id`, `tenant_id`, `name`, `channel`, `subject`, `body_html`, `body_text`, `created_at`
- `ruff check src/db/models/notification_template.py` exits 0
- `alembic/versions/5d575a161b5d_add_notification_templates.py` exists and creates `notification_templates` table with correct column types and FK constraint on `tenant_id`
- `alembic/versions/merge_heads_notification_templates_662.py` exists as a merge revision with `down_revision = (52b19ee00eaf, 5d575a161b5d)`, allowing `alembic upgrade head` to succeed on a fresh database
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all exit 0 on the `alembic_dev` database
- `tests/unit/test_notification_template_model.py` has 6 passing tests covering `to_dict`, null optionals, `updated_at`, `__tablename__`, length boundaries, and invalid-input acceptance
- Drift check produces an empty migration (confirms model and DB schema are in sync)
