# 规范部署阶段并添加至 CI 工作流

| 元数据 | 值 |
|---|---|
| Issue | #437 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [0436](.) (前置澄清) |
| 启用后赋能 | #198 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #437 is blocked on two clarification items before implementation can begin: (a) the target deployment environment (ECS, Cloud Run, bare server, etc.) and (b) whether a deployment secret or gateway token is available. The current `.github/workflows/ci.yml` has no `deploy` job, so a successful `qc` run does not propagate to any live environment. Adding the job — even with placeholder secrets — unblocks the delivery pipeline and gives the team a concrete slot to fill in with real deploy logic once the clarifications arrive.

### 1.2 做完后

- **用户视角**：No user-facing change — this is a pure CI/CD infrastructure change.
- **开发者视角**：After this lands, a passing `qc` job automatically triggers a `deploy` job (stubbed or real depending on which path is chosen in Step 1). Engineers can set `DEPLOY_TARGET`, `DEPLOY_SECRET`, and `DEPLOY_COMMAND` env vars in the GitHub Actions secrets UI without touching workflow YAML. A new `deploy` status badge appears on PRs.

### 1.3 不做什么（剔除）

- [ ] Actual deploy command implementation — only the job skeleton with placeholders is in scope. Real deploy logic (ECS task definition update, Cloud Run deploy, `ssh` + `Ansible`, etc.) is out of scope until #436 clarifies the target.
- [ ] Modifying any FastAPI router, service, or ORM model.
- [ ] Changing the Docker build process or adding new Dockerfile targets.
- [ ] Adding Slack notifications or external webhook calls.

### 1.4 关键 KPI

- [KPI 1：`.github/workflows/ci.yml` contains a `deploy` job with `needs: qc` and at least `DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` env var placeholders]
- [KPI 2：GitHub Actions lint passes — `act -l` or the dry-run shows `deploy` as a named job]
- [KPI 3：`ruff check .github/` → 0 errors (no Python files in workflow dir, but workflow YAML must remain valid YAML]

---

## 2. 当前现状（起点）

### 2.1 现有实现

CI workflow entry point: `.github/workflows/ci.yml` (path confirmed by git history and repo root listing)

TBD - 待验证：`.github/workflows/ci.yml` L? — current jobs block (likely `build`, `test`, `lint`, `qc` or similar; need to confirm job names and the `needs` graph before inserting `deploy`)

```{yaml}:.github/workflows/ci.yml
# placeholders — to be verified via Read tool before authoring Step 1
jobs:
  qc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... existing qc steps (lint + type check) ...
```

### 2.2 涉及文件清单

- 要改：
  - [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — add `deploy` job below `qc`; wire `needs: [qc]`
  - TBD - 待验证：`.env.example` 路径待确认 — document `DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` placeholder keys
- 要建：
  - `docs/dev-plan/99-misc/0437-clarify-deploy-stage-and-add-it-to-ci-workflow.md` — this board document

### 2.3 缺什么

- [ ] No `deploy` job in `.github/workflows/ci.yml` — pipeline ends at `qc`
- [ ] No documented deploy env var placeholders in `.env.example`
- [ ] No confirmation of deployment target (ECS / Cloud Run / bare server / other) — blocked by #436
- [ ] No deployment secret or gateway token confirmed — blocked by #436
- [ ] No revert / rollback step for a failed deploy run

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `docs/dev-plan/99-misc/0437-clarify-deploy-stage-and-add-it-to-ci-workflow.md` | This board document |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) | Add `deploy` job: `needs: qc`, env placeholders `DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` |
| TBD - 待验证：`.env.example` 路径待确认 | Document deploy-related env var placeholders for developer reference |

### 3.3 新增能力

- **CI job**：`deploy` in `.github/workflows/ci.yml`, gated behind `qc`
- **Env vars (placeholders)**：`DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` in the `deploy` job
- **Documentation**：TBD - 待验证：`.env.example` 路径待确认 section for deploy env vars

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Add `deploy` as a workflow job rather than a separate action/reusable workflow**: The deploy logic is expected to be simple (single command or one-liner call to a deploy agent) and may change frequently as the team iterates on the target. Keeping it inline in `ci.yml` makes it easy to review in the same PR as the service code that triggered it. A reusable workflow can be extracted later if the deploy logic grows beyond 30 lines.
- **Placeholder env vars over hard-coded dummy values**: `DEPLOY_TARGET`, `DEPLOY_SECRET`, and `DEPLOY_COMMAND` are left as `${{ secrets.DEPLOY_TARGET }}` etc. so that the workflow is immediately runnable once the team fills in GitHub Actions secrets — no code change required to switch targets.

### 4.2 版本约束

No new external dependencies are introduced by this issue.

| 依赖 | 版本 | 理由 |
|------|------|------|
| N/A | — | No new packages; only GitHub Actions YAML edits |

### 4.3 兼容性约束

- GitHub Actions YAML must remain valid: indentation uses 2 spaces; job names contain only `[a-zA-Z0-9_-]`
- The `deploy` job must use `needs: [qc]` to guarantee the quality gate has passed before any deploy runs
- `DEPLOY_SECRET` must be referenced as a GitHub Actions secret (`secrets.DEPLOY_SECRET`), never written as a plain string in the YAML
- No changes to any Python source, service, or model files — this is pure CI/CD infrastructure

### 4.4 已知坑

1. **GitHub Actions YAML indentation errors are silent at `git push` time — only visible in the Actions UI run** → 规避：Before pushing, run `yamllint .github/workflows/ci.yml` (or `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` in a CI-like environment) to catch structural errors early. The pre-push hook does not run YAML validation.
2. **If `DEPLOY_SECRET` is left unset in GitHub Actions secrets, the `deploy` job will fail at runtime with an unspecified secret error** → 规避：Document all three placeholders in TBD - 待验证：`.env.example` 路径待确认 with a comment that they must be added to GitHub Actions secrets before the job will succeed. Add a `if: false` commented-out step as a reminder until secrets are provisioned.
3. **Deploying to the wrong target by mistake (e.g., staging vs production) when `DEPLOY_TARGET` is not set** → 规避：The job should `echo "Deploying to $DEPLOY_TARGET"` in its first step so the target is visible in every run log. Fail-fast if the variable is empty.

---

## 5. 实现步骤（按顺序）

### Step 1: Read existing CI workflow and confirm job structure

Read `.github/workflows/ci.yml` to confirm:
- Current job names (especially `qc` or equivalent)
- Existing `needs` dependency graph
- Whether a `deploy` job already exists (it should not, but confirm)
- What `runs-on` label is used for existing jobs (to match for `deploy`)

Do not guess line numbers or job names — verify before proceeding.

**完成判定**：[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) has been read and job list confirmed.

---

### Step 2: Clarify deployment target (blocked by #436)

Before writing the `deploy` job, check whether #436 has been resolved and the deployment target is known. If not, add a commented-out `deploy` job skeleton with `TODO` markers for the target-specific section:

```yaml
  deploy:
    name: Deploy
    needs: [qc]
    runs-on: ubuntu-latest
    # TODO: replace with actual deploy command once #436 is resolved
    # target: ${{ secrets.DEPLOY_TARGET }}
    # command: ${{ secrets.DEPLOY_COMMAND }}
    steps:
      - name: Confirm secrets are set
        run: |
          if [ -z "$DEPLOY_TARGET" ]; then
            echo "ERROR: DEPLOY_TARGET secret is not set. Skipping deploy."
            exit 1
          fi
          echo "Deploying to $DEPLOY_TARGET"
      - name: Run deploy
        run: |
          echo "DEPLOY_COMMAND not yet configured — set secrets.DEPLOY_COMMAND in GitHub Actions"
          exit 1
```

**完成判定**：`.github/workflows/ci.yml` contains a `deploy` job with `needs: [qc]` and at least one shell guard that fails fast if env vars are unset.

---

### Step 3: Document placeholders in TBD - 待验证：`.env.example` 路径待确认

Open TBD - 待验证：`.env.example` 路径待确认 and append a commented deploy section:

```env
# =============================================================================
# Deploy (CI/CD)
# Set these in GitHub Actions → Settings → Secrets
# =============================================================================
DEPLOY_TARGET=          # e.g. ecs:cluster-prod, cloudrun:project-prod, ssh:deploy@host
DEPLOY_SECRET=          # token or key for the deploy target
DEPLOY_COMMAND=        # command to execute on the deploy target
```

Verify the section was appended without altering existing entries.

**完成判定**：TBD - 待验证：`.env.example` 路径待确认 contains `DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` entries under a `# Deploy (CI/CD)` header.

---

### Step 4: Validate YAML syntax

Run a Python YAML parse check locally:

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML valid"
```

If this fails, the YAML has a structural error that would prevent the Actions run from starting.

**完成判定**：Command exits with code 0 and prints `YAML valid`.

---

### Step 5: Update this board document — mark as done

Fill in the `Changelog` table at the bottom of this document with today's date and mark the status as ✅ done.

**完成判定**：§Changelog has one row with today's date; §metadata `状态` shows ✅ done.

---

## 6. 验收

- [ ] `.github/workflows/ci.yml` contains a `deploy` job with `needs: [qc]`
- [ ] `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits with code 0 (valid YAML)
- [ ] TBD - 待验证：`.env.example` 路径待确认 contains `DEPLOY_TARGET`, `DEPLOY_SECRET`, `DEPLOY_COMMAND` placeholders
- [ ] `DEPLOY_TARGET` guard is present: deploy job fails fast if the secret is unset
- [ ] No Python source files, services, models, or routers were modified

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#436` not resolved before merge — deploy job is a no-op stub | 高 | 低 | Deploy job contains a `run: exit 1` placeholder with a clear `TODO` comment directing engineers to fill in `secrets.DEPLOY_COMMAND`. Pipeline still passes `qc`; nothing breaks. |
| Deploy job added to wrong branch or conflicts with a simultaneous CI rewrite | 低 | 中 | Revert: `git revert <commit>` targeting the `deploy` job addition. The revert is a single YAML block removal; no data migration needed. |
| `DEPLOY_SECRET` accidentally exposed in workflow run logs | 低 | 高 | Immediately rotate the secret in GitHub Actions secrets UI. Add `shell: bash` with `set -x` stripped from any step that echoes secrets. |
| YAML syntax error silently merged (pre-push hook does not YAML-validate) | 中 | 中 | CI run on the PR will fail at the workflow parsing step with a clear error message. Fix in a follow-up PR. No deployed artifact affected. |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add .github/workflows/ci.yml docs/dev-plan/99-misc/0437-clarify-deploy-stage-and-add-it-to-ci-workflow.md
git commit -m "ci(github-actions): add deploy job stub to ci.yml

Closes #437

- adds deploy job with needs: [qc] and placeholder env vars
- documents DEPLOY_TARGET, DEPLOY_SECRET, DEPLOY_COMMAND in .env.example
- deploy command body is a TODO stub pending #436 clarification"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "ci: add deploy job stub to ci.yml (#437)" --body "Closes #437

Depends on #436 for real deploy command implementation."

# 2. Update progress
# - Mark this board document §metadata 状态 as ✅ done
# - docs/dev-plan/README.md §1.1 AUTO-INDEX is updated by the generator on merge
```

> **注意**：如果 `.env.example` 存在于仓库根目录，Step 3 应将其替换为正确的相对路径后再提交。路径待后续验证确认。

---

## 9. 参考

- 同类参考实现：[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — existing CI workflow structure
- 父 issue / 关联：#198, #436

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
