.PHONY: help test test-unit test-integration test-web test-all lint format check db-up db-down migrate migrate-new fix format-check db-shell install install-dev venv trigger-fix act-implement act-build act-review act-monitor act-repair

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
	$(PYTHON) ".agent-actions/scripts/trigger_fix_for_issue.py" $(ISSUE)

# ── Local CI via act ───────────────────────────────────────────────────────
# Runs the implement-ready-issues workflow in a local Docker runner via `act`.
# Pass ISSUE=<n> to target a specific issue; omit to pick the oldest ready one
# (same semantics as the scheduled run).
#
# Requirements:
#   • brew install act
#   • .secrets contains real ANTHROPIC_API_KEY and GITHUB_TOKEN (act cannot
#     read GitHub repo secrets; see .secrets.example).
#   • Docker is running — the workflow runs `docker compose` from inside the
#     runner, so we mount the host socket via --bind + -v.
#
# Side effects: in --bind mode act operates on the working tree directly. If
# the workflow gets to `git push`, it will push to the real origin and open a
# real PR with the token in .secrets. Use a throwaway issue/branch if testing.
ACT_IMAGE := act-runner-with-gh:latest

act-build: ## Build the custom act runner image (catthehacker + gh CLI)
	docker build --platform linux/amd64 -t $(ACT_IMAGE) -f .act/Dockerfile .act

act-implement: ## Trigger implement-ready-issues.yml locally via act (ISSUE=123 to target one)
	@command -v act >/dev/null 2>&1 || { echo "act not installed. Run: brew install act"; exit 1; }
	@docker image inspect $(ACT_IMAGE) >/dev/null 2>&1 || { echo "Runner image missing. Run: make act-build"; exit 1; }
	@test -s .secrets || { echo ".secrets is empty. Populate ANTHROPIC_API_KEY and GITHUB_TOKEN (see .secrets.example)."; exit 1; }
	act workflow_dispatch \
		-W .github/workflows/implement-ready-issues.yml \
		-j implement \
		$(if $(ISSUE),--input issue_number=$(ISSUE),) \
		--bind \
		--container-daemon-socket /var/run/docker.sock

# Triggers the PR-reviewer agent. Heads up: this can enable auto-merge on
# real open PRs and dispatch fix-pr-comments runs. Use a throwaway GH_TOKEN
# (or expect real side effects on github.com).
act-review: ## Trigger review-open-prs.yml locally via act (PR=123 logs intent; agent still scans all open PRs)
	@command -v act >/dev/null 2>&1 || { echo "act not installed. Run: brew install act"; exit 1; }
	@docker image inspect $(ACT_IMAGE) >/dev/null 2>&1 || { echo "Runner image missing. Run: make act-build"; exit 1; }
	@test -s .secrets || { echo ".secrets is empty. Populate ANTHROPIC_API_KEY and GITHUB_TOKEN (see .secrets.example)."; exit 1; }
	act workflow_dispatch \
		-W .github/workflows/review-open-prs.yml \
		-j review \
		$(if $(PR),--input pr_number=$(PR),) \
		--bind \
		--container-daemon-socket /var/run/docker.sock

# Triggers the issue-monitor agent (now also generates dev-plan boards for
# ready issues). By default writes boards to docs/dev-plan/issues/ and pushes
# to master via the .secrets GITHUB_TOKEN. Set DRY=1 to write to /tmp without
# committing — the recommended way to smoke-test changes to the generator.
act-monitor: ## Trigger monitor-issues.yml locally via act (DRY=1 to skip commit+push)
	@command -v act >/dev/null 2>&1 || { echo "act not installed. Run: brew install act"; exit 1; }
	@docker image inspect $(ACT_IMAGE) >/dev/null 2>&1 || { echo "Runner image missing. Run: make act-build"; exit 1; }
	@test -s .secrets || { echo ".secrets is empty. Populate ANTHROPIC_API_KEY and GITHUB_TOKEN (see .secrets.example)."; exit 1; }
	act workflow_dispatch \
		-W .github/workflows/monitor-issues.yml \
		-j validate \
		$(if $(DRY),--env DEV_PLAN_DRY_RUN=1,) \
		--bind \
		--container-daemon-socket /var/run/docker.sock

# Sweeps docs/dev-plan/ for boards with broken markdown links and asks Claude
# to repair them. MAX=N to override the per-run cap (default 5). DRY=1 to
# skip the final commit/push (boards are still rewritten in the working tree
# for inspection).
act-repair: ## Trigger repair-doc-links.yml locally via act (MAX=10 to lift cap; DRY=1 to skip commit)
	@command -v act >/dev/null 2>&1 || { echo "act not installed. Run: brew install act"; exit 1; }
	@docker image inspect $(ACT_IMAGE) >/dev/null 2>&1 || { echo "Runner image missing. Run: make act-build"; exit 1; }
	@test -s .secrets || { echo ".secrets is empty. Populate ANTHROPIC_API_KEY and GITHUB_TOKEN (see .secrets.example)."; exit 1; }
	act workflow_dispatch \
		-W .github/workflows/repair-doc-links.yml \
		-j repair \
		$(if $(MAX),--input max_repair=$(MAX),) \
		$(if $(DRY),--env DEV_PLAN_DRY_RUN=1,) \
		--bind \
		--container-daemon-socket /var/run/docker.sock
