.PHONY: help test test-unit test-integration test-web test-all lint format check db-up db-down migrate migrate-new fix format-check db-shell install install-dev venv trigger-fix

# Create a local virtualenv on demand and use it by default.
VENV_DIR := .venv
VENV_READY := $(VENV_DIR)/.dev-installed
ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV_DIR)/Scripts/python.exe
PYTHON ?= $(VENV_PY)
else
VENV_PY := $(VENV_DIR)/bin/python
PYTHON ?= $(VENV_PY)
endif

PYTHONPATH := src
export PYTHONPATH

TEST_DB_URL ?= postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db
COMPOSE := docker compose -f configs/docker-compose.test.yml

# Export DATABASE_URL into the child-process environment for targets that need
# it. The POSIX `VAR=value command` inline form does NOT work in Windows
# cmd.exe (Make's default shell on Windows), so use Make's per-target export
# directive — works on Linux, macOS, and Windows without forcing a shell.
test-integration test-web migrate migrate-new: export DATABASE_URL = $(TEST_DB_URL)

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────
venv: $(VENV_READY) ## Create the local virtualenv and install dev dependencies

$(VENV_READY): pyproject.toml
	python3 -m venv "$(VENV_DIR)"
	$(VENV_PY) -m pip install -e ".[dev]"
	@touch "$@"

install: ## Install the project into the venv (runtime deps only)
install: venv
	$(PYTHON) -m pip install -e .

install-dev: ## Install runtime + dev extras (pytest, pytest-asyncio, ruff, mypy, …)
install-dev: venv

# ── Tests ──────────────────────────────────────────────────────────────────
test: test-unit ## Alias for test-unit

test-unit: ## Run unit tests (no DB)
test-unit: venv
	$(PYTHON) -m pytest tests/unit/ -v

test-integration: db-up ## Run all integration tests against docker test-db
test-integration: venv
	$(PYTHON) -m pytest tests/integration/ -v

test-web: db-up ## Run web integration tests only
test-web: venv
	$(PYTHON) -m pytest tests/integration/test_web_integration.py -v

test-all: test-unit test-integration ## Run unit + integration tests

# ── Lint / format ──────────────────────────────────────────────────────────
lint: ## Run ruff check
lint: venv
	$(PYTHON) -m ruff check src/

format: ## Run ruff format (in place)
format: venv
	$(PYTHON) -m ruff format src/

format-check: ## Verify formatting without writing
format-check: venv
	$(PYTHON) -m ruff format --check src/

check: lint format-check ## Run lint + format check (CI-style)

fix: ## Run ruff with --fix
fix: venv
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
migrate: venv
	$(PYTHON) -m alembic upgrade head

migrate-new: ## Autogenerate a new migration: make migrate-new MSG="..."
migrate-new: venv
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-new MSG=\"describe change\""; exit 1; fi
	$(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

trigger-fix: venv
	@if [ -z "$(ISSUE)" ]; then echo "Usage: make trigger-fix ISSUE=123"; exit 1; fi
	$(PYTHON) "scripts/ci/trigger_fix_for_issue.py" $(ISSUE)
