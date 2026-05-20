# Alembic Migrations

Migrations live in `alembic/versions/` and target Postgres via the asyncpg driver.

## Environment Setup (once per shell)

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"  # if alembic not on PATH
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
```

⚠️ Use a **dedicated `alembic_dev` database** — never the test DB (`test_db`), which is already at the
model state via `create_all`. Mixing them produces phantom diffs.

---

## Generate a New Migration

```bash
# 1. Spin up a clean DB
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres \
  -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres \
  -c "CREATE DATABASE alembic_dev;"

# 2. Bring it to current head
alembic upgrade head

# 3. Autogenerate the diff
alembic revision --autogenerate -m "describe_change_here"

# 4. REVIEW the generated file in alembic/versions/
#    Autogen misses: data migrations, enum changes, server defaults,
#    indexes on JSON keys. Always read it before applying.

# 5. Verify round-trip
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# 6. Drift check — second autogen must be empty; delete it if so
alembic revision --autogenerate -m "drift_check"
# If both up/down have only `pass` → delete the file. Otherwise your migration is incomplete.
```

---

## Other Useful Commands

```bash
alembic current               # show applied revision
alembic history --verbose     # list all revisions
alembic upgrade head          # apply all pending migrations
alembic upgrade <rev>         # apply up to a specific revision
alembic downgrade -1          # revert the last migration
alembic downgrade base        # revert all migrations
alembic stamp head            # mark DB as up-to-date without running migrations (use with care)
```

---

## Adding a New Model

1. Create `src/db/models/my_model.py` with your `Base`-derived class.
2. Do not edit `src/db/models/__init__.py` or `alembic/env.py`; `db.models`
   auto-imports model modules so `Base.metadata` and Alembic see the new table.
3. Follow the generate steps above.

---

## Rules

- Every new SQLAlchemy model must live in `src/db/models/<domain>.py` and inherit
  from `db.base.Base`; model discovery depends on that.
- Migrations must be **reversible** — fill in `downgrade()` even if autogen left it blank.
- **Never edit** a migration that has shipped to any environment; write a new one instead.
- **Never run** autogenerate against `test_db` — you'll get an empty diff and miss real drift.
