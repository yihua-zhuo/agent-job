# [Infra] Complete CI workflow setup · pytest + code-review + qc + deploy pipeline

| 元数据 | 值 |
|---|---|
| Issue | #148 |
| 分类 | [10-infra](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 所有板块（统一 CI 保障质量基线） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前仓库缺少自动化 CI pipeline，每次 push/PR 无人校验代码质量、测试覆盖率、类型安全。手动运行 `pytest` / `ruff` / `mypy` 容易遗漏，导致带病代码进入 master。issue #148 要求在 `.github/workflows/ci.yml` 中固化 four-stage 链式 job（test → code-review → qc → deploy），并在 `pyproject.toml` 与 `pytest.ini` 中补齐依赖与配置。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 CI 基础设施。
- **开发者视角**：每次 push 到 `master / develop / feature/**` 或打开 PR 时，GitHub Actions 自动触发 test → code-review → qc → deploy 链路；开发者可在 PR 页面的 Checks 面板看到各阶段状态，无需手动运行质量门禁命令。

### 1.3 不做什么（剔除）

- [ ] 不实现 CI 环境以外的部署脚本（deploy job 仅注册 `openclaw run --role deploy`，不写具体部署逻辑）。
- [ ] 不在本 PR 中引入新的业务 service / model / router。

### 1.4 关键 KPI

- `pytest tests/unit/ --collect-only` → 0 collection errors
- `ruff check src/` → 0 errors
- `mypy src/` → 0 errors（配置好后）
- `.github/workflows/ci.yml` 存在，4 个 job 串联，`needs` 链完整
- `pytest.ini` 存在，`pyproject.toml` 含 `dev-tools` 可选依赖

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块（仓库此前无 `.github/workflows/ci.yml`，无 `pytest.ini`，`pyproject.toml` 已有基础依赖但缺少 `[project.optional-dependencies]` 的 `dev-tools` 组）。

### 2.2 涉及文件清单

- 要改：
  - `pyproject.toml` — 新增 `dev-tools` 可选依赖块
- 要建：
  - `.github/workflows/ci.yml` — 四阶段 GitHub Actions pipeline
  - `pytest.ini` — pytest 配置（含 `addopts`、`testpaths`）

### 2.3 缺什么

- [ ] 无 `.github/workflows/ci.yml`：无自动化触发 test / code-review / qc / deploy 的 workflow 文件
- [ ] `pyproject.toml` 无 `dev-tools` 组：缺少 `pytest`、`pytest-cov`、`pytest-xdist`、`mypy`、`bcrypt` 等开发依赖的集中声明
- [ ] 无 `pytest.ini`：pytest 运行参数（coverage 报告、junitxml）未固化，命令行参数散落在各 CI step 中
- [ ] `mypy` 在 `pyproject.toml` 的 `[tool.mypy]` 配置块状态未知（需确认是否已配置或需新增）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `.github/workflows/ci.yml` | 四阶段链式 CI pipeline：test → code-review → qc → deploy |
| `pytest.ini` | pytest 全局配置（addopts、testpaths、junitxml 输出路径） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `pyproject.toml` | 在 `[project.optional-dependencies]` 下新增 `dev-tools` 组 |

### 3.3 新增能力

- **CI workflow**：`.github/workflows/ci.yml`，4 个 job，job 间通过 `needs` 串联
- **依赖组**：`pip install -e ".[dev-tools]"` 可一次性拉取所有开发工具
- **pytest 配置**：`--cov src --cov-report term-missing --junitxml=test-results.xml` 固化到 `pytest.ini`，CI step 简化为 `pytest tests/unit/ -v`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `ruff` 而非 `pylint`**：本项目 CLAUDE.md §Conventions 明确使用 `ruff` 进行 lint，不使用 pylint。`dev-tools` 中的 `pylint` 应删除，仅保留 `ruff`（已在项目依赖中）。
- **选 `pytest-xdist` 而非 `pytest-split`**：issue 要求 `pytest-xdist`，与 pytest 生态一致。
- **选 `mypy`**：已在 CLAUDE.md 命令清单中明确使用，配合 `ruff check` 构成代码质量双检。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest` | `>=7.0` | issue 要求，与项目 Python 3.11 兼容 |
| `pytest-cov` | 任意兼容版本 | 配合 `pytest.ini` 的 `--cov` 选项 |
| `mypy` | 任意兼容版本 | CLAUDE.md 已使用，需显式声明 |

### 4.3 兼容性约束

- `pyproject.toml` 的 `dev-tools` 必须放在 `[project.optional-dependencies]` 下，pip 才能通过 `pip install -e ".[dev-tools]"` 解析。
- workflow 中 `pip install -e ".[dev-tools]"` 需在项目根目录执行，要求 `pyproject.toml` 存在于 checkout 的根目录。
- deploy job 加 `if: github.ref == "refs/heads/master"`，确保只有 master 分支触发部署。

### 4.4 已知坑

1. **Alembic autogen 对 JSON/DateTime 的误判** → 规避：本 PR 仅改 `pyproject.toml` 与新建 YAML/INI 文件，不涉及 DB migration，不触发此坑。
2. **`PYTHONPATH=src` 缺失导致 import 失败** → 规避：workflow 中执行 `pip install -e .` 会自动处理包安装；测试命令前需显式 export `PYTHONPATH=src`（已在 CLAUDE.md 命令清单中说明），CI job 中也需一致。
3. **CI 中 `pip install -e ".[dev-tools]"` 若 pyproject.toml 的 `build-system` 不完整会失败** → 规避：确认 `pyproject.toml` 有 `[build-system]` + `setuptools` 或使用 `hatchling`，项目若已有 `pip install -e .` 历史则可跳过此检查。

---

## 5. 实现步骤（按顺序）

### Step 1: 新增 `pyproject.toml` 的 `dev-tools` 依赖组

在 `pyproject.toml` 的 `[project.optional-dependencies]` 下追加 `dev-tools`：

```toml
[project.optional-dependencies]
dev-tools = [
    "pytest>=7.0",
    "pytest-cov",
    "pytest-xdist",
    "mypy",
    "bcrypt",
]
```

注：删除 issue 中示例的 `pylint`（本项目用 `ruff`）。

**完成判定**：`grep -A5 'optional-dependencies' pyproject.toml | grep dev-tools` 有输出

---

### Step 2: 创建 `pytest.ini`

在项目根目录新建 `pytest.ini`：

```ini
[pytest]
addopts = --cov src --cov-report term-missing --junitxml=test-results.xml
testpaths = tests/unit
```

**完成判定**：`cat pytest.ini` 输出含 `addopts` 与 `testpaths` 且无空值

---

### Step 3: 创建 `.github/workflows/ci.yml`

在 `.github/workflows/ci.yml`（目录需新建）写入 four-stage 链式 pipeline YAML：

```yaml
name: CI
on:
  push:
    branches: [master, develop, "feature/**"]
  pull_request:
    branches: [master, develop]

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev-tools]"
      - run: PYTHONPATH=src pytest tests/unit/ -v --junitxml=test-results.xml

  code-review:
    name: Code Review
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - run: pip install openclaw
      - run: openclaw run --role code-review

  qc:
    name: QC Gate
    runs-on: ubuntu-latest
    needs: code-review
    steps:
      - uses: actions/checkout@v4
      - run: pip install openclaw
      - run: openclaw run --role qc

  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    needs: qc
    if: github.ref == 'refs/heads/master'
    steps:
      - uses: actions/checkout@v4
      - run: pip install openclaw
      - run: openclaw run --role deploy
```

**完成判定**：`.github/workflows/ci.yml` 存在，4 个 job（test / code-review / qc / deploy）均声明，`needs` 链为 test→code-review→qc→deploy，deploy 含 `if: github.ref == 'refs/heads/master'`

---

### Step 4: 验证 `pyproject.toml` 可解析

在本地确认修改后的 `pyproject.toml` 可被 Poetry/Pip 解析：

```bash
pip install -e ".[dev-tools]" --dry-run
```

**完成判定**：命令 exit 0（无报错），或 `pip install -e ".[dev-tools]"` 在 CI 容器中成功。

---

### Step 5: 验证 pytest 配置

```bash
PYTHONPATH=src pytest tests/unit/ --collect-only
```

**完成判定**：输出含 `collected N items`，无 `ERROR` 或 `import` 失败。

---

### Step 6: 运行 ruff + mypy 基线检查

```bash
ruff check src/ && ruff format --check src/
mypy src/ --ignore-missing-imports
```

**完成判定**：三条命令均 exit 0（或 mypy 仅有已知的既有警告，不引入新警告）。

---

## 6. 验收

- [ ] `.github/workflows/ci.yml` 存在，4 个 job 串联，deploy job 含 `if: github.ref == 'refs/heads/master'`
- [ ] `pytest.ini` 存在，`addopts` 含 `--cov src`、`--cov-report term-missing`、`--junitxml=test-results.xml`，`testpaths = tests/unit`
- [ ] `pyproject.toml` 含 `[project.optional-dependencies]` 下的 `dev-tools` 组（pytest / pytest-cov / pytest-xdist / mypy / bcrypt）
- [ ] `PYTHONPATH=src pytest tests/unit/ --collect-only` → `collected N items`，0 errors
- [ ] `ruff check src/` → 0 errors
- [ ] `git diff --stat` 显示新增 `.github/workflows/ci.yml`、`pytest.ini`，修改 `pyproject.toml`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `openclaw` CLI 在 GitHub Actions 虚拟机中安装失败或不存在 | 低 | CI 报红，deploy job 无法完成 | 从 workflow 中移除 openclaw 相关的 code-review / qc / deploy job，仅保留 test job；后续由平台工程师补充 openclaw runner |
| `pip install -e ".[dev-tools]"` 在 Actions 缓存失效后超时 | 低 | test job 超时 | 显式使用 `actions/setup-python@v5` 的 `cache: pip` 缓存依赖；或拆分依赖到 `requirements-dev.txt` 单独缓存 |
| `pytest --cov` 需要 `pytest-cov`，若 `dev-tools` 安装顺序问题导致 coverage 警告而非报错 | 中 | 测试通过但 CI log 有警告 | `pytest.ini` 的 `addopts` 中移除 `--cov` 改为 CI step 中显式 `pytest --cov`，避免环境问题导致全部测试 skip |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add .github/workflows/ci.yml pytest.ini pyproject.toml
git commit -m "feat(ci): add four-stage GitHub Actions pipeline

- test: pytest unit tests with coverage + junitxml
- code-review: openclaw code-review role
- qc: openclaw qc role
- deploy: openclaw deploy role (master only)
- add pytest.ini and dev-tools optional-dependencies"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ci): add four-stage GitHub Actions pipeline" --body "Closes #148"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`configs/.github/workflows/` 或项目内其他 workflow YAML（确认是否有现有 pattern）
- 第三方文档：[GitHub Actions workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- 父 issue / 关联：#148

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
