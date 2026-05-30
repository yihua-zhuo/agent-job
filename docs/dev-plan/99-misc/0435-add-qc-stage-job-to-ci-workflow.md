# CI 工作流增强 · 为 CI 添加 qc 阶段任务

| 元数据 | 值 |
|---|---|
| Issue | #435 |
| 分类 | [99-misc](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [0434-add-lint-and-mypy-to-ci-workflow](0434-add-ci-workflow-stub-with-test-and-code-review-stages.md) |
| 启用后赋能 | TBD - 待验证：关联父 issue #198 的其他子任务 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CI 工作流已具备 `lint` 阶段（`ruff check`）和 `code-review` 阶段，但没有专门的质量控制（QC）阶段来 gate 格式化和类型检查。issue #434 引入了 `ruff check` 和 `mypy` 作为独立 lint/type 步骤；#435 需要在 `code-review` 之后串联一个 `qc` job，将 `ruff format --check src/` 和 `mypy src/` 作为正式 CI gate，并上传 artifacts 以便后续 job 消费或人工审查。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯 CI 基础设施增强。
- **开发者视角**：`code-review` 通过后，`qc` job 自动执行格式化和类型检查。若有违规，CI 在 artifacts 中留存详细日志；格式检查失败会导致后续 job 被阻断。

### 1.3 不做什么（剔除）

- [ ] 不修改 `ruff check` 的执行位置（保持在 `lint` job 中，由 #434 管理）
- [ ] 不引入新的脚本路径（如 `script/lint/` 或 `script/typecheck/`）；直接在 job 中使用 `ruff format --check` / `mypy` 命令
- [ ] 不实现 Slack/邮件通知（#435 scope 仅为 CI workflow 修改）

### 1.4 关键 KPI

- [KPI 1：`ruff format --check src/` 在当前 HEAD 执行 exit 0（无格式违规基线）]
- [KPI 2：`mypy src/` 在当前 HEAD 执行 exit 0（无新类型错误基线）]
- [KPI 3：新增 `qc` job 在 `.github/workflows/ci.yml` 中正确声明 `needs: code-review`，且 `ruff format --check` / `mypy` 步骤均有 artifact 上传]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`.github/workflows/ci.yml` — 需确认现有 job 列表（`lint`、`code-review` 等）及 artifact 上传约定（是否有现有模式可参考）

当前 CI 结构（根据 issue 描述推断）：

```yaml
# 推断的现有结构（需验证）
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run ruff check
        run: ruff check src/
  code-review:
    runs-on: ubuntu-latest
    needs: lint
    # ... existing code-review steps ...
```

### 2.2 涉及文件清单

- 要改：
  - [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — 新增 `qc` job（依赖 `code-review`，执行 `ruff format --check` 和 `mypy`，上传 artifacts）

### 2.3 缺什么

- [ ] `.github/workflows/ci.yml` 中缺少 `qc` job 定义
- [ ] `ruff format --check src/` 未作为 CI gate（#434 可能已添加 `mypy` 步骤，但格式检查尚未在 workflow 中体现）
- [ ] 缺少格式化 / 类型检查 artifacts 上传步骤

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| N/A — 本次无新文件 | — |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) | 新增 `qc` job（`needs: code-review`），包含 `ruff format --check` 和 `mypy` 两个步骤，并上传 artifacts；保持 gateway URL 和 token placeholder 与其他 job 一致 |

### 3.3 新增能力

- **CI job**：`qc` — 在 `code-review` 之后运行，串联格式检查 + 类型检查
- **CI artifact**：上传 `qc-logs`（包含 ruff format 和 mypy 输出），可供后续 job 或人工审查使用

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `ruff format --check` 而非 `ruff check --fix`**：`--check` 仅报告违规不修改文件，适合 CI gate；`--fix` 会修改文件，属于 lint job 范畴（已在 #434 处理）
- **选 `qc` 作为 job 名而非 `format-check` 或 `lint-quality`**：`qc` 与父 issue #198 中的 "QC pipeline" 命名一致，便于理解系列 job 的演进路径

### 4.2 版本约束

<!-- 本次不引入新的 Python 依赖 -->

| 依赖 | 版本 | 理由 |
|------|------|------|
| `ruff` | `latest`（via actions） | 与现有 `lint` job 保持一致；CI 安装而非 pinned |
| `mypy` | `latest`（via actions） | 与 #434 引入的 mypy 步骤一致 |

### 4.3 兼容性约束

- Gateway URL 和 token placeholder 必须与 CI 中其他 job 保持一致（避免硬编码/不一致）
- 后续 job（若 #198 有后续子任务）可以 `needs: qc` 依赖本次新增 job
- 不破坏现有 job 拓扑：`qc` 依赖 `code-review`，不阻断 `lint`

### 4.4 已知坑

1. **若源代码已存在格式违规，`ruff format --check` 会 exit non-zero** → 规避：先在本地或单独 PR 中运行 `ruff format src/`，确认基线 clean 后再合入 `qc` job；或通过 feature flag 在初期仅记录结果不上报失败
2. **若 `mypy` 在当前 HEAD 有未修复的类型错误（与本次改动无关），`qc` job 会失败** → 规避：确认 `#435` 的 scope 仅添加 job 本身，不要求修复既有类型错误；类型错误修复应由 #434 或后续子任务处理

---

## 5. 实现步骤（按顺序）

### Step 1: 读取现有 CI workflow 结构

操作：
- a) 读取 [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) 全文
- b) 记录现有 job 列表、`code-review` job 的声明方式、artifact 上传模式（`actions/upload-artifact` 版本和命名约定）、gateway URL placeholder 格式

完成判定：`cat .github/workflows/ci.yml | grep -E "^  [a-z]+:"` 列出所有 job 名称

### Step 2: 在 `code-review` job 之后插入 `qc` job

操作：
- a) 在 `ci.yml` 文件中，在 `code-review` job 定义之后新增 `qc` job
- b) `qc` job 声明 `needs: code-review`
- c) 添加 `runs-on: ubuntu-latest`（与其他 job 一致）
- d) 添加 `setup-python` 步骤（使用与现有 job 相同的 Python 版本和缓存策略）
- e) 安装依赖：`pip install ruff mypy`（或使用 actions 安装，版本与现有 job 一致）

完成判定：`.github/workflows/ci.yml` 包含 `qc:` key，且 `qc:` 出现在 `code-review:` 之后

### Step 3: 在 `qc` job 中添加 `ruff format --check` 步骤

操作：
- a) 在 `qc` job 的 steps 中添加 `name: Check code formatting`
- b) `run: ruff format --check src/`
- c) 使用 `if: failure()` 或 `continue-on-error: false` 确保失败时 job 失败（不做软降级）

完成判定：`grep -A 5 "Check code formatting" .github/workflows/ci.yml` 显示步骤定义

### Step 4: 在 `qc` job 中添加 `mypy` 步骤

操作：
- a) 添加 `name: Run mypy type check`
- b) `run: PYTHONPATH=src mypy src/`
- c) 与 Step 3 一致，`continue-on-error: false`

完成判定：`grep -A 5 "mypy" .github/workflows/ci.yml` 显示步骤定义

### Step 5: 上传 QC logs 作为 artifacts

操作：
- a) 在 `ruff format --check` 步骤后添加 `name: Upload format check logs`
- b) 使用 `actions/upload-artifact@v4` 上传 ruff 输出（`ruff-format-check.log`）
- c) 在 `mypy` 步骤后添加 artifact 上传步骤（`mypy-report.log`）
- d) artifact 命名与现有模式一致（如 `qc-ruff-format`、`qc-mypy`）

完成判定：`grep "upload-artifact" .github/workflows/ci.yml` 至少显示 2 个 artifact 上传条目

---

## 6. 验收

- [ ] `.github/workflows/ci.yml` 包含 `qc` job，且 `qc.needs = code-review`
- [ ] `ruff format --check src/` 在当前 HEAD exit 0（基线 clean；若有格式问题，先 `ruff format src/` 再继续）
- [ ] `PYTHONPATH=src mypy src/` 在当前 HEAD exit 0（基线 clean；若有类型错误，确认是否由本次 job 定义引入）
- [ ] `ruff check .github/workflows/ci.yml` exit 0（workflow YAML 语法 valid）
- [ ] `grep -E "upload-artifact" .github/workflows/ci.yml` 至少显示 2 个 artifact 上传步骤（ruff + mypy 各一）
- [ ] Gateway URL placeholder 格式与 `lint` / `code-review` job 中的格式保持一致

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ruff format --check` 在当前 HEAD 有格式违规（与本次改动无关） | 低 | 中 | 由负责 #434 或相关 lint 清理的子任务修复；`qc` job 保持运行但标记为 blocker，文档中注明基线需先 clean |
| `mypy src/` 在当前 HEAD 有类型错误 | 中 | 中 | 由 #434 的 mypy 修复工作覆盖；若短时间无法修复，将 `mypy` 步骤改为 `continue-on-error: true` 并在 artifact 中记录，阻止 merge gate 暂缓 |
| 引入 `qc` job 后 CI 总时长增加 > 2 分钟 | 低 | 低 | 优化：若 `mypy` 和 `ruff format --check` 可并行运行（分 two-step），但需考虑 artifact 依赖；当前方案（顺序）可接受 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add .github/workflows/ci.yml
git commit -m "ci: add qc job to ci.yml (#435)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "ci: add qc stage job to CI workflow (#435)" --body "Closes #435"

# 2. 更新进度
# 在本板块文档 §Changelog 表格新增一行
# PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — 当前 CI workflow（需验证）
- 父 issue / 关联：#198, #434

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
