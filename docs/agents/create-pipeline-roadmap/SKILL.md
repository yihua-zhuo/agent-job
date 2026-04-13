---
name: create-pipeline-roadmap
description: >
  Decompose a multi-PR feature into N sequenced pipeline-task JSON files
  under shared-memory/tasks/, so the autonomous implementer can land them
  one PR at a time. Use whenever the user describes a multi-step feature,
  refactor, or migration that obviously won't fit in one PR (e.g. "migrate
  services to use a real database", "add audit logging across all services",
  "convert all sync code to async"). Companion to create-pipeline-task,
  which authors a single task; this skill authors a roadmap of related ones.
version: 1.0.0
author: agent-job pipeline
license: MIT
metadata:
  hermes:
    tags: [task-authoring, pipeline, agent-job, roadmap, decomposition]
    related_skills: [create-pipeline-task, writing-plans, subagent-driven-development]
---

# Create Pipeline Roadmap

Convert a feature spec into a sequence of small, mechanically-checkable
tasks the autonomous pipeline can land one PR at a time.

**Core principle:** The user describes the *outcome*; this skill produces
an ordered list of tasks each scoped to a single PR (≤ 400 line diff,
≤ 30 minutes, target files under `src/` + `tests/`). Sort order encodes
dependency order — older sort key = lands first.

## When to Use

Trigger on phrases that imply *multi-PR* work:

- "migrate all X to Y" / "convert all services to …" / "add Z everywhere"
- "rewrite the … layer" / "refactor … across services"
- "implement <big feature spanning multiple modules>"
- Anything where you'd reasonably expect 5+ PRs

**Use `create-pipeline-task` instead** when:

- The work is one method, one file, or one test addition
- The user is explicit: "add a method", "fix one bug", "queue a task for X"

**Do NOT trigger** for:

- "show me the roadmap so far" — that's an inspection, not authoring
- General questions about how the pipeline works
- Any feature whose first task requires editing files outside the
  implementer allowlist (`pyproject.toml`, `.github/`, deploy scripts,
  credentials). For those, STOP and tell the user the manual prep work
  needed before the roadmap can begin.

## Repository Context

Pipeline lives at `/home/node/.openclaw/workspace/dev-agent-system`.
Tasks land in `shared-memory/tasks/`. Each task gets picked up by:

1. `pipeline.py task` (planner) — adds an execution plan
2. `pipeline.py implement` (implementer) — writes code, opens PR

The implementer enforces:

- Files under `src/` or `tests/` only — no `.github/`, no root config
- Diff ≤ 400 lines vs `origin/develop`
- Tests must pass in a worktree before commit
- Pre-commit hook (flake8 / mypy) must pass

These same constraints govern what each task in your roadmap can ask for.

## Task Schema (one entry per task in the roadmap)

```json
{
  "task_id": "roadmap-<feature-slug>-<NN>-<task-slug>",
  "created_at": "<utc ISO8601 with Z>",
  "source": "roadmap",
  "claimed_at": null,
  "result_path": null,
  "title": "<<=80 chars, imperative>",
  "kind": "bugfix|test|refactor|docs|security",
  "priority": "high|medium|low",
  "target_files": ["<path>", "..."],
  "description": "<>=40 chars, cites exact new symbols + which task it depends on>",
  "acceptance": "<>=40 chars, mechanical checks only>",
  "roadmap": "<feature-slug>",
  "roadmap_index": <int>,
  "roadmap_total": <int>
}
```

The extra fields (`roadmap`, `roadmap_index`, `roadmap_total`) help the
manager-stats command surface progress on a feature. They are optional
metadata — the existing `_research_task_is_implementable` filter ignores
them.

## Hard Constraints (the LLM will FAIL if violated)

1. **Maximum 12 tasks per roadmap.** If the feature naturally needs
   more, split it into sub-roadmaps (e.g. `roadmap-db-models` and
   `roadmap-db-services`) and tell the user to invoke this skill twice.

2. **Sort-order = dependency order.** Use 2-digit zero-padded indexes
   (`-01-`, `-02-` …) so file glob order matches execution order. The
   implementer picks the alphabetically-first eligible task.

3. **Every target_files entry under `src/` or `tests/`.** No exceptions.
   If a roadmap step genuinely needs a non-allowlist edit (deps, CI,
   schema files), make it the FIRST item with `priority: "high"` and a
   description starting with `"MANUAL: "` — the implementer will skip
   it and the user will know to handle it themselves.

4. **Each task fits the 400-line diff cap.** When in doubt, split.
   Better 12 small tasks than 6 oversized rejections.

5. **Acceptance must be mechanical.** Every task's `acceptance` must
   include at least one signal a script can verify: a function name to
   import, a test name that runs, a numeric assert, a `grep` count, etc.
   Vague phrases like "works correctly" or "tests pass" are NOT enough.

6. **First task is the lowest-risk infrastructure piece.** Set up
   foundations (engine, base classes, fixtures) before anything that
   depends on them.

7. **Each task description must cite which earlier roadmap task(s)
   it depends on**, by `task_id`. The implementer doesn't enforce this
   today, but it's documentation for humans and future tooling.

## Workflow

### Step 1 — survey the codebase

Use your `read` tool to inspect what already exists. For database work,
read `sql/001_schema.sql`. For service refactors, read `src/services/`.
Don't skip this — every roadmap step must reference real file paths.

### Step 2 — choose the feature slug

Lowercase, kebab-case, 2–4 tokens. Examples:

- "migrate services to db" → `db-migration`
- "add audit logging everywhere" → `audit-logging`
- "convert services to async" → `services-async`

### Step 3 — design the roadmap

Sketch the dependency graph mentally. Group related work into single
PRs where possible (e.g. all identity-table ORM models in one PR, not
one PR per table). Bias toward 5–10 tasks for most features. If you
need 13+, you're probably trying to do too much — split.

For each task, decide:

- `target_files` — actual paths under src/ + tests/
- `kind` — refactor (most decomposition), test (when adding coverage
  is the deliverable), bugfix (rare for roadmaps), security, docs
- `priority` — `medium` for bot-implementable, `high` ONLY for the
  MANUAL prep tasks at index 00 if any
- exact new symbol names (class names, method names, test names)

### Step 4 — author the JSON files

For each task, use your `write` tool to create:

```
/home/node/.openclaw/workspace/dev-agent-system/shared-memory/tasks/<task_id>.json
```

`<task_id>` follows the format `roadmap-<feature-slug>-<NN>-<task-slug>`.
Verify each file with `read` afterwards.

### Step 5 — write the roadmap summary

Also drop a markdown summary at:

```
/home/node/.openclaw/workspace/dev-agent-system/shared-memory/roadmaps/<feature-slug>.md
```

(Create the `roadmaps/` dir first if it doesn't exist.)

Format:

```markdown
# Roadmap: <feature title>

Created: <utc>
Total tasks: <N>

## Dependencies

```
01 → 02 → 03 ↘
              06 → 07 → 08
03 → 04 → 05 ↗
```

## Tasks

| # | task_id | title | depends_on |
|---|---------|-------|------------|
| 01 | roadmap-…-01-… | … | (none) |
| 02 | roadmap-…-02-… | … | 01 |
…

## Manual prerequisites
- (list any priority=high MANUAL tasks the user must handle themselves)

## Out of scope
- (anything you considered but rejected from this roadmap)
```

### Step 6 — confirm back

Reply with a short summary:

```
✅ roadmap "<feature-slug>" created
   tasks queued: <N>  (manual: <M>, bot-implementable: <N-M>)
   first task: <task_id> — <title>
   summary: shared-memory/roadmaps/<feature-slug>.md
   next: pipeline.py task → plans the first one
   then: pipeline.py implement → opens PRs in order
```

If you couldn't author the roadmap (out-of-scope feature, requires too
much manual prep, etc.), reply with ❌ and one paragraph explaining
why.

## Examples

### Example: "migrate services to use a real database"

You'd produce something like:

| # | task_id | title | priority |
|---|---------|-------|----------|
| 00 | roadmap-db-migration-00-deps | MANUAL: add sqlalchemy + psycopg2-binary to pyproject.toml | high |
| 01 | roadmap-db-migration-01-engine | Add SQLAlchemy engine/session/Base in src/internal/db/ | medium |
| 02 | roadmap-db-migration-02-models-identity | ORM models for tenants/users/roles (8 tables) | medium |
| 03 | roadmap-db-migration-03-models-customers | ORM models for customers/leads/opportunities (11 tables) | medium |
| 04 | roadmap-db-migration-04-models-marketing | ORM models for marketing/activity/ticket (15 tables) | medium |
| 05 | roadmap-db-migration-05-models-analytics | ORM models for analytics/automation (15 tables) | medium |
| 06 | roadmap-db-migration-06-repository-base | Base repository pattern in src/internal/repository/ | medium |
| 07 | roadmap-db-migration-07-customer-service-rewire | Replace dict mock in CustomerService with CustomerRepository | medium |
| 08 | roadmap-db-migration-08-ticket-service-rewire | Replace dict mock in TicketService with TicketRepository | medium |
| 09 | roadmap-db-migration-09-sales-service-rewire | Replace dict mock in SalesService with SalesRepository | medium |
| 10 | roadmap-db-migration-10-remaining-services | Replace dict mocks in the remaining 6 services | medium |

### Example: refusal — "rewrite all the deploy scripts in Go"

```
❌ roadmap rejected — every target file would be outside the implementer
allowlist (deploy.js, railway-deploy.js, deployment Dockerfiles all live
at the repo root, not under src/ or tests/). The autonomous pipeline
cannot land deploy/CI changes. Hand this to a human.
```

## Behavioural Rules

- **Never embed actual code in `description` or `acceptance`.** That's
  the implementer's job. You describe *what* to build, not *how*.
- **Never propose a roadmap with overlapping target_files between
  consecutive tasks.** If task 02 and 03 both edit `src/x.py`, they
  WILL conflict at merge time. Either merge them into one task or
  ensure they touch disjoint sections.
- **Never re-author an existing roadmap.** Read `shared-memory/tasks/`
  first; if `roadmap-<slug>-*` files already exist, tell the user the
  roadmap is in progress and refuse.
- **Never echo secrets** the user types — strip and replace with
  `<redacted>` in any field that might end up in the JSON.
