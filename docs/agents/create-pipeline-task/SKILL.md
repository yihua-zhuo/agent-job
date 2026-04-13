---
name: create-pipeline-task
description: >
  Convert a user's natural-language requirement into a valid pipeline task
  JSON file under shared-memory/tasks/, so the autonomous implementer
  (scripts/cron/pipeline.py implement) can pick it up on its next run. Use
  whenever the user asks to "create a task", "queue a task", "add a task
  for...", "I need X implemented", or otherwise describes work that should
  be tracked by the CRM pipeline.
version: 1.0.0
author: agent-job pipeline
license: MIT
metadata:
  hermes:
    tags: [task-authoring, pipeline, agent-job, crm]
    related_skills: [subagent-driven-development, requesting-code-review]
---

# Create Pipeline Task

Turn a human requirement into a task the autonomous pipeline can execute.

**Core principle:** The user describes *what* they want; this skill authors the
scoped, machine-actionable task file the implementer agent will consume.

## When to Use

Trigger on phrases like:

- "create a task to..." / "add a task for..." / "queue a new task..."
- "I need X added to..." / "please implement..."
- "add a test for..." / "refactor the Y method..."
- any request that describes a specific code change to track

**Do not** trigger for:

- General questions about the pipeline ("how does research work?")
- Asking to see existing tasks (use `pipeline.py stats` instead)
- Requirements that belong to humans only (security rotations, prod deploys,
  anything involving credentials or infra outside the repo)

## Repository Context

The pipeline lives at:

```
/home/node/.openclaw/workspace/dev-agent-system
```

Tasks land in `shared-memory/tasks/` and are picked up by the implementer
agent (`pipeline.py implement`). Fire-and-forget — the pipeline handles
worktree creation, testing, commit, push, and PR.

## The Task Schema

Every task is a JSON file at `shared-memory/tasks/research-manual-<slug>.json`
with exactly these fields:

```json
{
  "task_id": "research-manual-<slug>",
  "created_at": "<utc ISO8601 with Z suffix>",
  "source": "manual",
  "claimed_at": null,
  "result_path": null,
  "title": "<<=80 chars, imperative>",
  "kind": "bugfix|test|refactor|docs|security",
  "priority": "high|medium|low",
  "target_files": ["<path>", "..."],
  "description": "<>=40 chars, cites exact new symbol name>",
  "acceptance": "<>=40 chars, at least one mechanical check>"
}
```

## Hard Constraints

The implementer's guardrails will reject any task that violates these.
Honour them at authoring time:

1. **target_files MUST be under `src/` or `tests/`.**
   Anything else (`.github/`, `.gitignore`, root `*.js`, `scripts/`, `docs/`,
   `shared-memory/`, `pyproject.toml`) will be filtered out at pre-flight.
   If the user asks for something outside this scope, explain that it needs
   a human and STOP — do not create the file.

2. **Priority `high` means "for human review only".** The implementer
   auto-skips high-priority tasks. Only use `high` if the user explicitly
   says this is a human task; default to `medium`.

3. **description MUST cite the new symbol.** E.g., "Add method
   `get_by_email(email: str, tenant_id: int) -> Optional[Customer]`" not
   "add an email lookup". This lets the implementer distinguish "already
   done" (method exists) from "real work".

4. **acceptance MUST be mechanically checkable.** Accepted signals include:
   `method exists`, `test_foo passes`, `pytest tests/unit/... returns 0`,
   `assert x == y`, `returns Dict[...]`, `grep X shows N matches`. Do NOT
   accept vague wording like "works correctly" or "tests exist and pass" —
   those are the exact false-positive failures the pipeline already hit.

5. **Scope <= ~60 lines of diff.** If the request is larger, split it into
   multiple tasks with clear dependency notes in the description.

## Workflow

### Step 1 — clarify if needed

Before writing anything, check that you have enough to author a valid task.
Ask the user only if critical info is missing:

- What file should this go in? (`target_files`)
- What's the specific method/function/test name?
- What's the exact behaviour? (description)
- How do we know it's done? (acceptance)

If the user's input already has all of this, skip the clarification.

### Step 2 — classify

- `kind`:
  - **bugfix** — fixes an existing defect in `src/`
  - **test** — adds unit tests in `tests/unit/`
  - **refactor** — restructures existing code in `src/`
  - **docs** — docstrings only (rare — most doc tasks are out-of-scope)
  - **security** — hardening in `src/` (input validation, auth checks,
    tenant isolation). If the fix is in infra/config/deploy, STOP and tell
    the user it needs a human.
- `priority`:
  - **medium** — default
  - **low** — polish / nice-to-have
  - **high** — DO NOT auto-implement; sets the "human review" flag

### Step 3 — build the file

Compute:

- `slug` — short kebab-case summary of the title, 3-6 tokens. Example:
  "Add count_by_status to CustomerService" → `count-by-status`.
- `task_id` — `research-manual-<slug>`. If the slug would collide, append
  `-<YYYYMMDDHHMM>`.
- `created_at` — current UTC in ISO8601 with trailing `Z`. Use your
  `exec` tool: `date -u +%Y-%m-%dT%H:%M:%SZ`.

### Step 4 — write the file

Use the `write` tool to create:

```
/home/node/.openclaw/workspace/dev-agent-system/shared-memory/tasks/<task_id>.json
```

with the JSON payload. Verify with `read` that it landed.

### Step 5 — confirm back

Reply with a short confirmation:

```
✅ task_id=<id> queued → shared-memory/tasks/<id>.json
   title: <title>
   next: pipeline.py task  → plans this
   then: pipeline.py implement  → edits, tests, commits, opens PR
```

If the user's requirement was rejected (wrong scope, needs human, etc.),
reply with ❌ plus one sentence explaining why.

## Examples

### Good user input → one task

> "add a `get_by_email` method to CustomerService that looks up a customer
> by email for a given tenant"

Authored:

```json
{
  "task_id": "research-manual-customer-get-by-email",
  "created_at": "...Z",
  "source": "manual",
  "claimed_at": null,
  "result_path": null,
  "title": "Add CustomerService.get_by_email for tenant-scoped lookup",
  "kind": "refactor",
  "priority": "medium",
  "target_files": [
    "src/services/customer_service.py",
    "tests/unit/test_customer_service.py"
  ],
  "description": "Add method get_by_email(email: str, tenant_id: int) -> Optional[Customer] to CustomerService. Must return None if email not found or if the matching customer is in a different tenant. Case-insensitive email match.",
  "acceptance": "CustomerService.get_by_email returns the matching Customer for (email,tenant_id); returns None for missing email; returns None for a match in a different tenant; test_get_by_email_* tests pass."
}
```

### Out-of-scope user input → refuse

> "change the GitHub Actions CI workflow to run on push to develop"

Reply:

```
❌ out of scope — .github/workflows/ is outside the implementer's allowlist
(src/ and tests/ only). This needs a human or an opt-in security-task
workflow (not currently enabled). I did NOT create a task.
```

### Ambiguous input → ask ONE question

> "add tests for the auth service"

Reply:

```
Quick clarification before I queue this: which methods?
AuthService already has a unit test file (tests/unit/test_auth_service.py).
Are we adding coverage for a specific method (e.g. change_password,
verify_token) or something new?
```

## Behavioural Rules

- **One task per user request** unless they explicitly ask for multiple.
- **Never write code** in the task file — `description` is a spec, not an
  implementation. The implementer agent does the coding.
- **Never promise the task will succeed.** Pipeline may reject it for
  reasons you can't foresee (e.g. filesystem allowlist updates, cooldowns).
- **Never echo secrets** the user types — if they paste a token in their
  requirement, strip it and note "<redacted>" in the description.
