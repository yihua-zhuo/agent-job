.PHONY: help test test-unit test-integration test-web test-all lint format check db-up db-down migrate

PYTHON ?= python3
PYTHONPATH := src
export PYTHONPATH

TEST_DB_URL ?= postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db
COMPOSE := docker compose -f configs/docker-compose.test.yml

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Tests ──────────────────────────────────────────────────────────────────
test: test-unit ## Alias for test-unit

test-unit: ## Run unit tests (no DB)
	$(PYTHON) -m pytest tests/unit/ -v

test-integration: db-up ## Run all integration tests against docker test-db
	DATABASE_URL=$(TEST_DB_URL) $(PYTHON) -m pytest tests/integration/ -v

test-web: db-up ## Run web integration tests only
	DATABASE_URL=$(TEST_DB_URL) $(PYTHON) -m pytest tests/integration/test_web_integration.py -v

test-all: test-unit test-integration ## Run unit + integration tests

# ── Lint / format ──────────────────────────────────────────────────────────
lint: ## Run ruff check
	$(PYTHON) -m ruff check src/

format: ## Run ruff format (in place)
	$(PYTHON) -m ruff format src/

format-check: ## Verify formatting without writing
	$(PYTHON) -m ruff format --check src/

check: lint format-check ## Run lint + format check (CI-style)

fix: ## Run ruff with --fix
	$(PYTHON) -m ruff check --fix src/
	$(PYTHON) -m ruff format src/

# ── Docker test DB ─────────────────────────────────────────────────────────
db-up: ## Start the docker test-db container
	$(COMPOSE) up -d test-db

db-down: ## Stop the docker test-db container
	$(COMPOSE) down

db-shell: ## Open a psql shell against the test-db
	$(COMPOSE) exec test-db psql -U test_user -d test_db

# ── Alembic ────────────────────────────────────────────────────────────────
migrate: ## Apply all alembic migrations to the test-db
	DATABASE_URL=$(TEST_DB_URL) alembic upgrade head

migrate-new: ## Autogenerate a new migration: make migrate-new MSG="..."
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-new MSG=\"describe change\""; exit 1; fi
	DATABASE_URL=$(TEST_DB_URL) alembic revision --autogenerate -m "$(MSG)"
