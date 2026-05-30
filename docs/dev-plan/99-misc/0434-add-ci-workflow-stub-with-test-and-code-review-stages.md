# CI 工作流存根 · 添加 test + code-review 双 stage| 元数据 | 值 |
|---|---|
| Issue | #434 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 所有下游板块（统一 CI gate，无需各自手动跑 lint/unit test） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

本仓库目前没有机器可验证的 CI pipeline——每次合入代码依赖人工运行测试和 lint，效率低且容易遗漏。issue #198（父 issue）要求建立统一的自动化 gate；本期先实现两层 gate：单元测试 + lint（`test` job）和代码审查（`code-review` job）。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层 CI/automation改动。
- **开发者视角**：每次 push 到 `master`/`develop` 自动触发 `pytest`单元测试 + `ruff check`，通过后自动调度 code-review agent。开发者在 GitHub Actions UI 查看 `test` 阶段的 artifacts（pytest log）和 `code-review` 阶段的审查意见。

### 1.3 不做什么（剔除）

- [ ] 不实现 `integration`标记测试的运行（该 job 需要真实数据库，不是本期 scope）
- [ ] 不实现部署 stage（deploy/rollback），由后续 issue 处理
- [ ] 不实现 Slack/邮件通知，GitHub Actions 内置 status check 已足够

### 1.4 关键 KPI

- [指标1：`git log --oneline .github/workflows/ci.yml | wc -l` → `≥ 1`（文件已创建）]
- [指标 2：`ruff check src/` 在 CI job 中 exit 0（本地手动验证同一命令）]
- [指标 3：`pytest tests/unit/ -m "not integration" -v` 在 CI job 中 exit 0（本地手动验证同一命令）]
- [指标 4：workflow 语法 `actionlint` 无报错（可用 `docker run … actionlint/tool actionlint` 本地验证）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。

本仓库**目前没有** `.github/workflows/` 目录，也没有运行任何 GitHub Actions workflow（从 git history 和仓库结构均可确认）。

### 2.2 涉及文件清单

- 要改：无- 要建：
  - `.github/workflows/ci.yml` — CI pipeline 定义，含 `test` 和 `code-review` 两个 job

### 2.3 缺什么

- [ ] 无 CI workflow，无法在 push 时自动 gate 测试/lint
- [ ] 无 code-review stage，无法在每次 PR/commit 时自动调用 code-review agent
- [ ] 无 artifact 上传，pytest 失败时没有日志供审查- [ ] gateway URL / token 以占位符形式注入（CI 配置由 infra team 提供真实值）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `.github/workflows/ci.yml` | 定义 `test`（pytest+ruff）与 `code-review`（gateway 调用）两个 job，push 到 master/develop 时触发 |

### 3.2 修改文件

（无）

### 3.3 新增能力

- **CI Job**：`test` — 运行 `pytest tests/ -m "not integration" -v` + `ruff check src/`，上传 pytest artifacts- **CI Job**：`code-review` — 依赖 `test`，携带 gateway URL/token 调用 code-review agent
- **Trigger**：`on: push: branches: [master, develop]` + `pull_request`
- **Artifact**：`pytest-logs.zip`（pytest XML + log 输出）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `github-token: ${{ secrets.GITHUB_TOKEN }}` 而非 PAT**：GitHub 提供开箱即用的 `GITHUB_TOKEN`，无需手动创建 secret，满足最小权限原则。
- **用 `needs: test`**：代码审查是代价较高的 LLM 调用，理性设计要求等测试/lint 通过后再触发。
- **用 artifacts 传递上下文**：pytest log 作为 ZIP artifact 上传，workflow run页面可直接下载，无需额外的存储backend。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `actions/checkout` | `v4` | 当前稳定版，支持 `fetch-depth: 0`（code-review agent 可能需要历史） |
| `actions/setup-python` | `v5` | 当前稳定版 |
| `pytest` | 以 `pyproject.toml` 为准 | 与项目现有 lock 一致 |
| `ruff` | 以 `pyproject.toml` 为准 | 与项目现有 lock 一致 |

### 4.3 兼容性约束

- Workflow file 必须位于 `.github/workflows/`目录，文件名 `.yml` 后缀，GitHub Actions才会识别。
- ` PYTHONPATH=src` 必须在每个 step 中显式 `env:` 设置，不能依赖隐式默认值。
- `code-review` job 的 gateway URL/token 用 `${{ vars.CLAUDE_GATEWAY_URL }}` 和 `${{ secrets.CLAUDE_GATEWAY_TOKEN }}`，不在 workflow源码中硬编码明文。
- `test` job 必须显式 `continue-on-error: false`，确保失败时 workflow正确 fail 而不是静默通过。

### 4.4 已知坑

1. **Gateway URL 占位符未替换** → 症状：workflow 能跑，但 code-review job报401/403。→ 规避：infra team 添加真实 `CLAUDE_GATEWAY_URL` variable 和 `CLAUDE_GATEWAY_TOKEN` secret 后自然解决；文档中明确说明占位符性质。
2. **pytest exit code 在 ruff 失败后未捕获** → 规避：`ruff check` 和 `pytest` 使用同一 `run:` 块内的 `&&`，任一失败则 job 失败；避免用 separated steps 导致部分通过。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `.github/workflows/` 目录结构在仓库根目录创建 `.github/workflows/` 子目录（如果不存在）。

**完成判定**：`.github/workflows/`目录存在（`ls .github/workflows/` exit 0）

### Step 2: 编写 `.github/workflows/ci.yml`

创建文件，内容如下：

```yaml
name: CI

on:
  push:
    branches:
      - master
      - develop
  pull_request:

env:
  PYTHONPATH: src

jobs:
  test:
    name: Test & Lint
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 支持 code-review agent 需要 history 的场景

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pytest ruff      - name: Lint
        run: ruff check src/

      - name: Run unit tests
        run: pytest tests/ -m "not integration" -v --junitxml=pytest-report.xml

      - name: Upload pytest artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pytest-logs
          path: pytest-report.xml
          retention-days: 7

  code-review:
    name: Code Review
    runs-on: ubuntu-latest
    needs: test
    steps:
      - name: Checkout        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run code-review agent
        env:
          CLAUDE_GATEWAY_URL: ${{ vars.CLAUDE_GATEWAY_URL }}
          CLAUDE_GATEWAY_TOKEN: ${{ secrets.CLAUDE_GATEWAY_TOKEN }}
        run: |
          curl -X POST \
            "$CLAUDE_GATEWAY_URL/v1/code_review" \
            -H "Authorization: Bearer $CLAUDE_GATEWAY_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{
              "repo": "${{ github.repository }}",
              "sha": "${{ github.sha }}",
              "ref": "${{ github.ref }}",
              "run_id": "${{ github.run_id }}"
            }'
```

**完成判定**：文件 `.github/workflows/ci.yml`存在且非空（`wc -l .github/workflows/ci.yml` → `≥ 20`）

### Step 3: 本地验证 workflow 语法

使用 `actionlint` 或等效工具验证 YAML 语法正确性（无可用工具时，可跳过此 step，直接由 PR review 捕获）。

**完成判定**：`grep -E "^\s+(name|runs-on|steps|uses|run|if|needs|on)" .github/workflows/ci.yml | wc -l` → `≥ 10`（关键 key齐备）

### Step 4: 提交并推送到远端分支

```bash
git checkout -b ci/issue-434git add .github/workflows/ci.yml
git commit -m "feat(ci): add test and code-review GitHub Actions workflow

Closes #434"
git push -u origin ci/issue-434
```

**完成判定**：`git log --oneline -1` 显示 commit，包含 `#434`引用；`git ls-remote origin ci/issue-434` 非空

---

## 6. 验收

- [ ] `.github/workflows/ci.yml` 存在且包含 `test` 和 `code-review` 两个 job 定义
- [ ] `needs: test` 存在于 `code-review` job，`continue-on-error: false` 存在于 `test` job
- [ ] `on: push: branches: [master, develop]` 触发器存在- [ ] `PYTHONPATH: src` 环境变量在 `test` job 的 steps 中设置
- [ ] `ruff check src/` 命令存在于 workflow 中
- [ ] `pytest tests/ -m "not integration" -v` 命令存在于 workflow 中
- [ ] `actions/upload-artifact@v4` artifact 上传步骤存在（pytest report）
- [ ] `${{ vars.CLAUDE_GATEWAY_URL }}` 和 `${{ secrets.CLAUDE_GATEWAY_TOKEN }}` 占位符存在于 `code-review` job
- [ ] 本地 `ruff check .github/workflows/` →0 errors（如 ruff 配置允许对 yml 文件运行；否则可跳过）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Gateway URL/token 占位符值未配置导致 code-review job 失败 | 低 | 低（不影响 test gate） | infra team 添加真实 variable/secret 后重跑 workflow；如临时不可用，在 workflow 中加 `if: vars.CLAUDE_GATEWAY_URL != ''` 跳过 |
| Workflow YAML语法错误导致整个 workflow 不识别 | 中 | 中（CI 完全失效） | 提交前用 `actionlint` 本地验证；PR review 可捕获 |
| Pytest exit code 与 ruff 在同一 `&&` 链，无法区分哪个失败 | 低 | 低（两者都应 pass） | 如果需要单独捕获，两者拆为独立 step 并各自加 `|| exit 1` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add .github/workflows/ci.yml
git commit -m "feat(ci): add test and code-review GitHub Actions workflow

Closes #434"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ci): add test and code-review GitHub Actions workflow" --body "Closes #434"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml)（上线后本文件即为同类参考）
- 第三方文档：[GitHub Actions workflow syntax](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)
- 父 issue / 关联：#198---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
