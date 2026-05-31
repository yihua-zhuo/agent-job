Now I have everything I need. Let me write the implementation plan.

# Implementation Plan — Issue #718

## Goal

Add three retry-scheduling columns (`next_retry_at`, `last_attempt_at`, `error_message`) to `WebhookDeliveryModel` and generate a corrected Alembic migration that includes a partial index on `next_retry_at`. This is prerequisite groundwork for the background retry scheduler (#721).

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0718-add-retry-scheduling-columns-to-webhookdeliverymodel-and-mig.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/50-automation/0718-add-retry-scheduling-columns-to-webhookdeliverymodel-and-mig.md`

## Affected Files

- `src/db/models/webhook.py` — add three `Mapped` fields to `WebhookDeliveryModel` and extend `to_dict()`
- `alembic/versions/<id>_add_webhook_delivery_retry_columns.py` — **new** migration, adds three columns + partial index `ix_delivery_next_retry`
- `tests/unit/test_webhook_model.py` — add three test cases for new columns in `TestWebhookDeliveryModel`

## Implementation Steps

### Step 1: Update `WebhookDeliveryModel` in `src/db/models/webhook.py`

Add three new `Mapped` fields to `WebhookDeliveryModel` (insert after `delivered_at` at line 62, before the `__table_args__` at line 64). Also extend `to_dict()` to cover the new fields.

**Fields to add (after line 62):**
```python
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**`to_dict()` extension (inside the existing dict at line 68-79):** add three keys:
```python
    "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
    "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
    "error_message": self.error_message,
```

Also add `Text` to the top-level `from sqlalchemy import ...` line (line 5 currently imports `String, text`; add `Text`).

**Verification:** `ruff check src/db/models/webhook.py` → 0 errors.

---

### Step 2: Generate Alembic migration

**Prerequisite:** `src/db/models/webhook.py` must be updated (Step 1 complete).

1. Start clean `alembic_dev` database:
   ```bash
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   ```

2. Set env and run autogenerate:
   ```bash
   export PYTHONPATH=src
   export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   alembic upgrade head   # bring alembic_dev to current head first
   alembic revision --autogenerate -m "add webhook delivery retry columns"
   ```

3. Manually fix the generated migration (autogen never gets types/partial indexes right):
   - Replace any `sa.JSON()` in the webhook_deliveries table with `postgresql.JSON(astext_type=sa.Text())` (matching the existing migration `add_webhook_tables.py` style)
   - Ensure all `DateTime` columns use `DateTime(timezone=True)` (existing `add_webhook_tables.py` already does this correctly; verify the new columns do too)
   - Add the partial index inside `upgrade()` (before the final `op.execute` if any):
     ```python
     from sqlalchemy import column
     op.create_index(
         "ix_delivery_next_retry", "webhook_deliveries", ["next_retry_at"],
         postgresql_where=column("next_retry_at").is_(None)
     )
     ```
   - Fill in `downgrade()`:
     ```python
     op.drop_index("ix_delivery_next_retry", table_name="webhook_deliveries")
     op.drop_column("next_retry_at")
     op.drop_column("last_attempt_at")
     op.drop_column("error_message")
     ```

4. Verify migration is clean:
   ```bash
   alembic upgrade head && alembic downgrade -1 && alembic upgrade head
   ```

5. Drift check (should produce empty migration, delete it if so):
   ```bash
   alembic revision --autogenerate -m "drift_check"
   ```

**Verification:** all three alembic commands exit 0; drift check migration has `pass` in both upgrade/downgrade and is deleted.

---

### Step 3: Update `tests/unit/test_webhook_model.py`

In the `TestWebhookDeliveryModel` class (line 67), add three test methods after the existing `test_index_on_webhook_id` (line 158):

```python
    def test_retry_columns_present(self):
        """next_retry_at, last_attempt_at, and error_message are defined."""
        fields = {"next_retry_at", "last_attempt_at", "error_message"}
        assert fields.issubset(WebhookDeliveryModel.__annotations__.keys())

    def test_to_dict_includes_retry_fields(self):
        """to_dict serialises the three new fields."""
        delivery = WebhookDeliveryModel(
            id=8, webhook_id=1, tenant_id=1,
            event_type="customer.created", payload={}, status="failed",
            next_retry_at=datetime(2026, 6, 1, 12, 0, 0),
            last_attempt_at=datetime(2026, 5, 30, 10, 0, 0),
            error_message="Connection refused",
        )
        d = delivery.to_dict()
        assert d["next_retry_at"] == "2026-06-01T12:00:00"
        assert d["last_attempt_at"] == "2026-05-30T10:00:00"
        assert d["error_message"] == "Connection refused"

    def test_to_dict_retry_fields_null(self):
        """Nullable retry fields None in to_dict when not set."""
        delivery = WebhookDeliveryModel(
            id=9, webhook_id=1, tenant_id=1,
            event_type="customer.created", payload={}, status="pending",
        )
        d = delivery.to_dict()
        assert d["next_retry_at"] is None
        assert d["last_attempt_at"] is None
        assert d["error_message"] is None
```

Also update `test_columns_present` (line 68) to include the three new field names in the expected set on line 70-73.

**Verification:** `PYTHONPATH=src pytest tests/unit/test_webhook_model.py -v` → all passed.

---

### Step 4: Lint check

```bash
ruff check src/db/models/webhook.py && ruff format --check src/db/models/webhook.py
```

**Verification:** both commands exit 0.

## Test Plan

- **Unit tests in `tests/unit/`**: `tests/unit/test_webhook_model.py` — add 3 new test methods to `TestWebhookDeliveryModel` covering field presence, `to_dict()` serialisation, and null-edge cases. Existing tests remain untouched and must still pass.
- **No integration test changes**: #718 only adds schema columns; persistence/routing of these fields is handled in #720 and #721.
- **Dev-plan verification**:
  - `ruff check src/db/models/webhook.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_webhook_model.py -v` → all passed
  - `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → all exit 0 (run against the provisioned `alembic_dev` DB)

## Acceptance Criteria

- `src/db/models/webhook.py` defines `next_retry_at`, `last_attempt_at`, and `error_message` as `Mapped` fields on `WebhookDeliveryModel`, each nullable, `next_retry_at` and `last_attempt_at` as `DateTime(timezone=True)`, `error_message` as `Text`.
- `WebhookDeliveryModel.to_dict()` includes the three new fields in its return dict.
- The Alembic migration adds the three columns to `webhook_deliveries` and creates partial index `ix_delivery_next_retry` (`WHERE next_retry_at IS NOT NULL`).
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all exit 0 with no drift.
- `ruff check src/db/models/webhook.py` → 0 errors.
- `PYTHONPATH=src pytest tests/unit/test_webhook_model.py -v` → all passed.
