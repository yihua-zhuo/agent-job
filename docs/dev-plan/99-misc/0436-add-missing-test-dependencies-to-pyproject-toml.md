# 测试依赖补全 · 为 pyproject.toml 添加缺失的测试/检查依赖

| 元数据 | 值 |
|---|---|
| Issue | #436 |
| 分类 | 99-misc |
| 优先级 | 推荐 |
| 工作量 | 0.25 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 所有依赖测试/检查的板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `pyproject.toml` 的 `[project.optional-dependencies]` 中缺少部分已在 CI/本地验证流程中实际使用的测试和检查工具。这些依赖没有声明，导致 `pip install -e ".[dev]"` 无法拉全依赖，新克隆仓库的开发者会遭遇 `ModuleNotFoundError` 或 `command not found` 错误。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯开发工具链维护。
- **开发者视角**：执行 `pip install -e ".[dev]"` 后可直接运行 `pytest`、`ruff`、`mypy`，无需手动追加依赖。

### 1.3 不做什么（剔除）

- 不在 `pyproject.toml` 中添加 `bcrypt`，除非测试套件明确要求（CI 原生构建失败风险）。
- 不修改任何应用代码或数据库 schema。

### 1.4 关键 KPI

- `python -c "import toml; t = toml.load('pyproject.toml'); print(len(t['project']['optional-dependencies'].get('dev', [])))"` → 输出 ≥ 4（pytest, pytest-cov, mypy, ruff）
- `pip install -e ".[dev]"` → exit 0
- `ruff check src/` → 0 errors
- `mypy src/` → 0 errors（允许已存在的类型警告，不要求零警告）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`pyproject.toml`](../../../pyproject.toml) L{1}-L{50}

```toml
# pyproject.toml（相关片段）
[project]
name = "dev-agent-system"
version = "0.1.0"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]
```

TBD - 待验证：`pyproject.toml` 中 `[project.optional-dependencies]` 是否已有 `dev` 键及其中是否已列出 `pytest-cov`、`mypy`、`ruff`（grep "pytest-cov" / "mypy" / "ruff" 在 pyproject.toml 中）

### 2.2 涉及文件清单

- 要改：
  - [`pyproject.toml`](../../../pyproject.toml) — 扩充 `[project.optional-dependencies].dev` 列表

### 2.3 缺什么

- [ ] `pytest>=7.0` 可能已声明但 `pytest-cov`（覆盖率报告）缺失
- [ ] `mypy` 缺失 — 类型检查依赖
- [ ] `ruff` 缺失 — 代码检查/格式化工具
- [ ] 无 TOML 语法验证步骤

---

## 3. 目标产物（终点）

### 3.1 新文件

无新建文件。

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`pyproject.toml`](../../../pyproject.toml) | 在 `[project.optional-dependencies].dev` 中追加 `pytest-cov`、`mypy`、`ruff`（`pytest>=7.0` 如已存在则保留） |

### 3.3 新增能力

- `pip install -e ".[dev]"` 拉全 pytest + pytest-cov + mypy + ruff
- `tomli` 或 `tomllib`（Python 3.11+ 内置）用于 TOML 验证脚本

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **列出版本下限而非精确版本**：`pytest>=7.0`、`ruff>=0.1.0` 等，允许次版本更新，减少维护摩擦。
- **不添加 bcrypt**：bcrypt 在某些 GitHub Actions Runner 镜像上需要编译工具链（Rust/cargo），可能污染 CI 环境；测试套件如不强制依赖则不引入。
- **不添加 `pytest-asyncio`**：如 CI 已正常跑异步测试，说明该依赖已通过其他路径满足，暂不主动添加。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest` | `>=7.0` | 已在 CLAUDE.md 中规定，CI 可能已依赖 |
| `pytest-cov` | `>=4.0` | 当前 pytest-cov 主流版本 |
| `mypy` | `>=1.0` | 支持 `from __future__ import annotations` 下的字符串化类型 |
| `ruff` | `>=0.1.0` | ruff 0.1.0 之后稳定，支持大量内置规则无需额外插件 |

### 4.3 兼容性约束

- `pyproject.toml` 须符合 PEP 621（`[project]` 表）规范。
- `[project.optional-dependencies]` 中每项须为字符串。
- 不得将同一包的不同版本约束重复列出。

### 4.4 已知坑

1. **TOML 语法错误难以肉眼发现** → 规避：用 `python -c "import toml; toml.load('pyproject.toml')"` 或 `pip install toml && toml-complete` 验证语法
2. **ruff 版本差异导致规则集不一致** → 规避：指定 `>=0.1.0` 下限，与 CI 中已安装版本对齐

---

## 5. 实现步骤（按顺序）

### Step 1: 读取现有 pyproject.toml 的 [project.optional-dependencies] 结构

读取 `pyproject.toml`，确认 `dev` 键是否已存在，以及其中已列出哪些包。

操作：
- a) 用 Read 工具读取 `pyproject.toml` 全文
- b) 定位 `[project.optional-dependencies]` 和 `dev` 块

**完成判定**：`grep -n "optional-dependencies\|dev\s*=" pyproject.toml` 输出非空

### Step 2: 在 dev 列表中添加缺失依赖

在 `dev` 列表中追加以下条目（如 `pytest>=7.0` 已存在则保留）：

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1.0",
]
```

操作：
- a) 如果 `dev` 键不存在：在 `[project.optional-dependencies]` 下新增 `dev` 块
- b) 如果 `dev` 键存在但缺少条目：追加缺失项，去重

**完成判定**：`ruff check pyproject.toml` exit 0（如 ruff 版本支持 TOML 检查）或 `python -c "import toml; t = toml.load('pyproject.toml'); print(sorted(t['project']['optional-dependencies'].get('dev', [])))"` 输出包含 pytest-cov, mypy, ruff

### Step 3: 验证 pyproject.toml 是合法 TOML 且依赖可解析

```bash
pip install toml
python -c "import toml; t = toml.load('pyproject.toml'); print('valid TOML, dev deps:', sorted(t['project']['optional-dependencies'].get('dev', [])))"
```

**完成判定**：输出 `valid TOML` 且列表长度 ≥ 4

---

## 6. 验收

- [ ] `python -c "import toml; t = toml.load('pyproject.toml'); deps = t['project']['optional-dependencies'].get('dev', []); assert len(deps) >= 4; print('OK:', sorted(deps))"` → exit 0，输出包含 pytest-cov, mypy, ruff
- [ ] `ruff check pyproject.toml` → 0 errors（如支持 TOML）
- [ ] `pip install -e ".[dev]" -q` → exit 0（网络原因超时可重试一次）
- [ ] `ruff --version` → 输出版本号
- [ ] `mypy --version` → 输出版本号
- [ ] `pytest --version` → 输出版本号

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 新增依赖与已有约束冲突（版本互斥） | 低 | 中 | 从 dev 列表中删除冲突条目，保留 pytest/mypy/ruff 中的两个 |
| ruff 新版本引入非向后兼容规则导致 CI lint 失败 | 低 | 中 | 将 ruff 上限锁定在当前 CI 已验证版本 |
| pip install -e ".[dev]" 因某依赖构建失败（bcrypt 类） | 低 | 高 | 降级方案：删除可疑条目，仅保留纯 Python 工具 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add pyproject.toml
git commit -m "chore(deps): add pytest-cov mypy ruff to dev extras in pyproject.toml"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "chore(deps): add missing test dependencies to pyproject.toml" --body "Closes #436"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：CLAUDE.md §关键命令 — 已引用 `ruff check`、`mypy src/`、`pytest tests/unit/` 等命令，说明这些工具已在工具链中
- 父 issue：#198
- 前置依赖：#435

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
