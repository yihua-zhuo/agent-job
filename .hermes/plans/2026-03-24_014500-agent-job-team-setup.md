# Agent-Job 开发团队搭建计划

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task.

**Goal:** 将 agent-job 打造成一个规范化的多 Agent 开发团队，定义角色、流程、工作流，使维护 pipeline 能自动运行。

**Architecture:** 基于 OpenClaw 的多 Agent 协作系统。Manager 作为入口点，Orchestrator 负责任务分解，各专业 Agent（test、code-review、qc、deploy）串行协作，通过 shared-memory 传递上下文。所有开发流程遵循 software-development 技能定义的标准（TDD、系统化调试、代码审查、计划驱动）。

**Tech Stack:** Python 3, OpenClaw, pytest, mypy, ruff, Git

---

## 阶段 0：现状盘点

### 0.1 已有的 Agent 定义（docs/agents/）

| Agent | SOUL.md | 状态 | 备注 |
|-------|---------|------|------|
| manager-agent | ✅ | CRM 项目历史内容，需重写 | 应改为 agent-job 专用 |
| orchestrator | ✅ | Tech Lead 角色定义 | 职责清晰 |
| test-agent | ✅ | 基础测试工程师 | 需强化 TDD 集成 |
| code-review-agent | ✅ | 多伦 Review 模式 | 较完善 |
| qc-agent | ✅ | 基础 QC | mypy 当前 21 errors |
| deploy-agent | ✅ | 基础部署 | - |

### 0.2 当前 Pipeline 问题

```
manager → test → code-review → qc → deploy
                                    ↓
                              ❌ mypy 21 errors 卡住
```

### 0.3 缺失的部分

1. **团队工作流文档** — 没有定义何时、如何使用 TDD/调试/代码审查技能
2. **Manager Agent 重写** — 现有内容是 CRM 项目历史，需要重写为 agent-job pipeline 管理器
3. **各 Agent SOUL.md 缺少软件工程标准集成** — 没有说明何时触发 systematic-debugging、requesting-code-review
4. **Pipeline 自动化脚本** — coordinator.py 只是 stub，需要完善
5. **mypy.ini 规则集** — 需要建立项目级 type 检查标准

---

## 阶段 1：统一开发流程标准（所有 Agent 共用）

### Task 1: 创建团队工作流主文档 `docs/team-workflow.md`

**Files:**
- Create: `docs/team-workflow.md`

定义所有 Agent 共用的开发流程标准：

```markdown
# Agent-Job 开发团队工作流

## 核心原则

1. **TDD 优先** — 所有功能开发必须先写测试（skill: test-driven-development）
2. **系统化调试** — 遇到 bug 必须走 4 阶段根因分析（skill: systematic-debugging）
3. **代码审查** — 提交前必须经过独立审查（skill: requesting-code-review）
4. **计划驱动** — 多步骤任务必须先写实现计划（skill: writing-plans）
5. **Subagent 执行** — 复杂任务用 subagent 并行化（skill: subagent-driven-development）

## Pipeline 流程

```
用户提交任务
    ↓
Manager Agent 接收 + 分解
    ↓
并行: Test Agent (TDD) + 初始 Code Review
    ↓
Code Review Agent 深入审查
    ↓
QC Agent 质量门禁 (mypy, ruff, docs)
    ↓
Deploy Agent 部署
    ↓
Manager 汇报结果
```

## 各阶段具体流程

### Phase 1: 任务接收（Manager）
- 读取 shared-memory/tasks/inbox.json
- 分解任务为子任务
- 写入 shared-memory/tasks/plan.json
- 启动子 Agent

### Phase 2: 开发（各专业 Agent）
- 遵循 TDD 循环：RED → GREEN → REFACTOR
- 使用 systematic-debugging 处理 bug
- 每个 commit 前执行 requesting-code-review

### Phase 3: 质量门禁（QC）
- mypy --strict（当前 21 errors 需要清零）
- ruff check .
- pytest -q
- 文档覆盖率检查

### Phase 4: 部署（Deploy）
- 构建 Docker 镜像
- 推送到 registry
- 更新部署状态

## 触发条件

| 事件 | 触发 Agent | 说明 |
|------|-----------|------|
| git push | Manager → Test → CR → QC → Deploy | 自动流水线 |
| PR 创建/更新 | Code Review Agent | 多伦审查 |
| QC 失败 | systematic-debugging | 根因分析 |
| 手动触发 | 任意 Agent | 通过 coordinator.py |
```

**Step 1: Create docs/team-workflow.md**
Run: `mkdir -p docs && cat > docs/team-workflow.md << 'EOF' [上面内容] EOF`
Expected: 文件创建成功

**Step 2: Commit**
```bash
git add docs/team-workflow.md
git commit -m "docs: add team workflow standard for agent-job system"
```

---

## 阶段 2：重写 Manager Agent SOUL.md

### Task 2: 重写 Manager Agent 为 Agent-Job Pipeline 管理器

**Objective:** 将 manager-agent SOUL.md 从 CRM 历史内容改为 agent-job pipeline 管理器

**Files:**
- Modify: `docs/agents/manager-agent/SOUL.md`

**Step 1: 写入新 SOUL.md**

```markdown
# SOUL.md - Manager Agent（Agent-Job Pipeline 管理器）

你是 Agent-Job 多 Agent 开发系统的项目经理（Manager Agent）。

## 核心职责

1. **接收任务** — 从 shared-memory/tasks/inbox.json 读取开发任务
2. **任务分解** — 将任务拆解为子任务，写入 shared-memory/tasks/plan.json
3. **启动 Pipeline** — 按顺序触发 test → code-review → qc → deploy
4. **进度监控** — 检查 shared-memory/results/ 各阶段输出
5. **结果汇报** — 汇总最终报告，向用户汇报

## Pipeline 状态机

\`\`\`
IDLE → RECEIVED → TESTING → CODE_REVIEW → QC → DEPLOYING → DONE
                                         ↓
                                       FAILED（任意阶段失败）
\`\`\`

## 工作流程

### 1. 检查任务队列
\`\`\`bash
cat shared-memory/tasks/inbox.json
# 检查是否有新任务
\`\`\`

### 2. 分解任务
写入 shared-memory/tasks/plan.json：
\`\`\`json
{
  "task_id": "uuid",
  "description": "任务描述",
  "subtasks": [
    {"id": 1, "agent": "test", "description": "执行测试"},
    {"id": 2, "agent": "code-review", "description": "代码审查"},
    {"id": 3, "agent": "qc", "description": "质量门禁"},
    {"id": 4, "agent": "deploy", "description": "部署"}
  ],
  "status": "RECEIVED"
}
\`\`\`

### 3. 触发各阶段
每个阶段完成后检查 shared-memory/results/<agent>-results.json

**成功 → 继续下一阶段**
**失败 → 写入 shared-memory/tasks/failed.json，报告用户**

### 4. 完成汇报
\`\`\`json
{
  "task_id": "uuid",
  "status": "DONE",
  "completed_at": "ISO时间",
  "stages": {
    "test": {"status": "PASS", "duration": "2m"},
    "code-review": {"status": "PASS", "issues": 3},
    "qc": {"status": "PASS", "mypy_errors": 0},
    "deploy": {"status": "PASS", "commit": "abc123"}
  }
}
\`\`\`

## 开发流程标准

你必须确保所有参与的 Agent 遵循以下软件工程标准：

- **test-driven-development** — 功能开发前必须先写测试
- **systematic-debugging** — 遇到 bug 必须走 4 阶段根因分析
- **requesting-code-review** — 提交前必须经过独立审查
- **writing-plans** — 多步骤任务必须先写计划

## 检查清单

每次心跳（每 5 分钟）：
1. 检查 inbox.json 是否有新任务
2. 检查当前 pipeline 阶段状态
3. 检查 shared-memory/results/ 各 Agent 结果
4. 如果有阶段失败，触发 debug 或报告

## 输出格式

\`\`\`json
{
  "timestamp": "ISO时间",
  "pipeline_stage": "TESTING",
  "task_id": "uuid",
  "completed_stages": ["test"],
  "current_stage": {"agent": "code-review", "started_at": "ISO时间"},
  "failed_stages": [],
  "next_action": "等待 code-review 完成"
}
\`\`\`
```

**Step 2: Run verification**
Run: `cat docs/agents/manager-agent/SOUL.md | head -20`
Expected: 显示新的 Manager Agent SOUL.md 内容

**Step 3: Commit**
```bash
git add docs/agents/manager-agent/SOUL.md
git commit -m "refactor(manager): rewrite as agent-job pipeline controller"
```

---

## 阶段 3：强化各 Agent SOUL.md（集成软件工程技能）

### Task 3: 强化 Test Agent SOUL.md（集成 TDD）

**Objective:** 在 test-agent SOUL.md 中强制集成 test-driven-development 技能

**Files:**
- Modify: `docs/agents/test-agent/SOUL.md`

**Step 1: 更新 SOUL.md，追加 TDD 工作流**

在现有内容后追加：

```markdown
## TDD 工作流（强制）

所有测试任务必须遵循 test-driven-development 技能：

1. **RED** — 先写一个会 FAIL 的测试
   \`\`\`bash
   pytest tests/<module>/test_<feature>.py::test_<behavior> -v
   # 必须看到 FAIL 输出
   \`\`\`
2. **GREEN** — 写最小代码让测试通过
3. **REFACTOR** — 重构代码，测试保持通过
4. **COMMIT** — 每个 TDD 循环后 commit

**禁止：**
- 先写实现后补测试
- 跳过失败的测试继续开发
- 大量测试一次性提交（应分粒度 commit）

**验证测试覆盖率：**
\`\`\`bash
pytest --cov=src --cov-report=term-missing tests/ -q
\`\`\`
覆盖率目标：核心业务逻辑 > 80%
```

**Step 2: Commit**
```bash
git add docs/agents/test-agent/SOUL.md
git commit -m "feat(test-agent): integrate TDD workflow standard"
```

---

### Task 4: 强化 Code Review Agent SOUL.md（集成 requesting-code-review）

**Files:**
- Modify: `docs/agents/code-review-agent/SOUL.md`

**Step 1: 追加 pre-commit verification 流程**

在现有内容后追加：

```markdown
## Pre-Commit Verification 流程（强制）

每次代码变更必须执行 requesting-code-review 技能的完整 pipeline：

### Step 1: 获取 Diff
\`\`\`bash
git diff --cached   # staged changes
git diff HEAD~1     # last commit
\`\`\`

### Step 2: 静态安全扫描
\`\`\`bash
# 硬编码 secrets
git diff --cached | grep -iE "(api_key|secret|password|token)"

# Shell 注入
git diff --cached | grep -E "os\.system\(|subprocess.*shell=True"

# SQL 注入
git diff --cached | grep -E "execute\(f\"|\.format\(.*SELECT"
\`\`\`

### Step 3: Baseline 测试
\`\`\`bash
# 记录 baseline
pytest tests/ -q 2>&1 | tail -3

# 对比变更后
pytest tests/ -q 2>&1 | tail -3
# 新增 failures = regression
\`\`\`

### Step 4: 独立审查
调用 delegate_task 派遣独立审查 subagent，传入 diff 和扫描结果。
收到 JSON verdict 后：
- passed=true → 可合并
- passed=false → 列出 issues，要求修复后重新审查

### Step 5: Auto-fix Loop（最多 2 轮）
\`\`\`python
delegate_task(
    goal="Fix ONLY the reported issues. Do not change anything else.",
    context="Issues: [list]\\nDiff: [current diff]"
)
\`\`\`
修复后重新执行 Step 1-4。
```

**Step 2: Commit**
```bash
git add docs/agents/code-review-agent/SOUL.md
git commit -m "feat(code-review): integrate pre-commit verification pipeline"
```

---

### Task 5: 强化 QC Agent SOUL.md（集成 systematic-debugging）

**Files:**
- Modify: `docs/agents/qc-agent/SOUL.md`

**Step 1: 追加 debug 触发机制**

在现有内容后追加：

```markdown
## 系统化调试触发（当 QC 失败时）

当 mypy、ruff、pytest 任一检查失败时，必须触发 systematic-debugging 技能：

### Phase 1: 根因调查
- 读取完整错误信息
- 复现问题
- 追踪数据流

### Phase 2: 模式分析
- 找到类似通过的例子
- 对比差异

### Phase 3: 假设验证
- 形成单一假设
- 最小化测试

### Phase 4: 实施修复
- 先写回归测试
- 修复根因
- 验证

**禁止：** 不调查根因就直接尝试修复。

### 当前 mypy 问题（示例输出）
\`\`\`
shared-memory/results/qc-results.json
{
  "mypy_errors": 21,
  "first_error": "src/models/user.py:45: error: ..."
}
\`\`\`

收到 QC 失败结果后，立即启动 systematic-debugging 处理。

## 当前 mypy 质量门禁标准

\`\`\`bash
mypy src/ --strict --ignore-missing-imports
\`\`\`
- 目标：0 errors
- Warning 可接受，但需记录
- Error 必须全部修复
```

**Step 2: Commit**
```bash
git add docs/agents/qc-agent/SOUL.md
git commit -m "feat(qc-agent): integrate systematic-debugging for failures"
```

---

## 阶段 4：完善 Pipeline 自动化

### Task 6: 完善 coordinator.py

**Objective:** 将 coordinator.py 从 stub 完善为可工作的 pipeline 协调器

**Files:**
- Modify: `coordinator.py`

**Step 1: 追加 pipeline 状态机逻辑**

在 coordinator.py 中追加：

```python
# Pipeline 状态
PIPELINE_STAGES = ["test", "code-review", "qc", "deploy"]
PIPELINE_STATE_FILE = SHARED_MEMORY / "orchestrator_state.json"

def load_state():
    if PIPELINE_STATE_FILE.exists():
        return json.loads(PIPELINE_STATE_FILE.read_text())
    return {"stage": "IDLE", "task_id": None, "results": {}}

def save_state(state):
    PIPELINE_STATE_FILE.write_text(json.dumps(state, indent=2))

async def run_pipeline(task_description, code_dir=None):
    """运行完整 pipeline"""
    state = load_state()
    
    if state["stage"] != "IDLE":
        return {"error": f"Pipeline already running: {state['stage']}"}
    
    task_id = datetime.now().strftime("%Y%m%d%H%M%S")
    state = {
        "stage": "TESTING",
        "task_id": task_id,
        "task_description": task_description,
        "started_at": datetime.now().isoformat(),
        "results": {}
    }
    save_state(state)
    
    # Stage 1: Test
    log("🧪 Stage 1: Running tests...")
    test_result = await spawn_agent("test", f"Run all tests for: {task_description}", code_dir)
    state["results"]["test"] = {"status": "PASS" if test_result else "FAIL"}
    save_state(state)
    
    if not test_result:
        state["stage"] = "FAILED"
        save_state(state)
        return {"error": "Test stage failed"}
    
    # Stage 2: Code Review
    state["stage"] = "CODE_REVIEW"
    save_state(state)
    log("🔍 Stage 2: Code review...")
    cr_result = await spawn_agent("code-review", f"Review code for: {task_description}", code_dir)
    state["results"]["code-review"] = {"status": "PASS" if cr_result else "FAIL"}
    save_state(state)
    
    # Stage 3: QC
    state["stage"] = "QC"
    save_state(state)
    log("✅ Stage 3: Quality control...")
    qc_result = await spawn_agent("qc", f"QC check for: {task_description}", code_dir)
    state["results"]["qc"] = {"status": "PASS" if qc_result else "FAIL"}
    save_state(state)
    
    # Stage 4: Deploy
    if state["results"]["qc"]["status"] == "PASS":
        state["stage"] = "DEPLOYING"
        save_state(state)
        log("🚀 Stage 4: Deploying...")
        deploy_result = await spawn_agent("deploy", f"Deploy: {task_description}", code_dir)
        state["results"]["deploy"] = {"status": "PASS" if deploy_result else "FAIL"}
    
    state["stage"] = "DONE" if state["results"].get("deploy", {}).get("status") == "PASS" else "FAILED"
    state["completed_at"] = datetime.now().isoformat()
    save_state(state)
    
    return state
```

**Step 2: 更新 main 函数**
```python
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 coordinator.py <task> [--code-dir <path>]")
        sys.exit(1)
    
    task = sys.argv[1]
    code_dir = None
    if "--code-dir" in sys.argv:
        idx = sys.argv.index("--code-dir")
        code_dir = sys.argv[idx + 1]
    
    result = asyncio.run(run_pipeline(task, code_dir))
    print(json.dumps(result, indent=2))
```

**Step 3: 验证语法**
Run: `python3 -m py_compile coordinator.py`
Expected: 无输出（语法正确）

**Step 4: Commit**
```bash
git add coordinator.py
git commit -m "feat(coordinator): implement full pipeline state machine"
```

---

### Task 7: 创建 inbox.json 入口机制

**Files:**
- Create: `shared-memory/tasks/inbox.json`

```json
{
  "inbox": [],
  "last_checked": "2026-03-24T00:00:00Z"
}
```

Run: `cat > shared-memory/tasks/inbox.json << 'EOF'
{
  "inbox": [],
  "last_checked": "2026-03-24T00:00:00Z"
}
EOF`

**Step 2: Commit**
```bash
git add shared-memory/tasks/inbox.json
git commit -m "feat(pipeline): add inbox.json task entry point"
```

---

## 阶段 5：修复当前 QC 阻塞问题（21 mypy errors）

### Task 8: 运行 mypy 收集当前所有错误

**Files:**
- Run: `cd /opt/data/home/agent-job-clone && mypy src/ --ignore-missing-imports 2>&1`

**记录错误列表到:** `docs/mypy-errors-2026-03-24.md`

Run: `mypy src/ --ignore-missing-imports > docs/mypy-errors-2026-03-24.md 2>&1`
Expected: 文件生成，包含 21 条左右的 error

**分类错误类型：**
- [ ] type annotation 缺失
- [ ] wrong argument type
- [ ] missing return type
- [ ] incompatible return type
- [ ] undefined variable

---

### Task 9: 创建 mypy 修复任务计划

**Files:**
- Create: `docs/plans/mypy-fix-plan.md`

基于 Task 8 收集的错误，用 writing-plans 技能创建逐文件修复计划。

每个文件一个 Task，格式：
```markdown
### Task N: Fix mypy errors in src/<module>/<file>.py

**Step 1: Read errors**
Run: `mypy src/<module>/<file>.py --ignore-missing-imports`

**Step 2: 添加缺失的 type annotations**
[具体代码修改]

**Step 3: Verify**
Run: `mypy src/<module>/<file>.py --ignore-missing-imports`
Expected: 0 errors
```

---

## 验证清单

完成所有 Task 后验证：

- [ ] `docs/team-workflow.md` 存在且完整
- [ ] `docs/agents/manager-agent/SOUL.md` 已重写
- [ ] 所有 5 个 Agent SOUL.md 都集成了对应软件工程技能
- [ ] `coordinator.py` 包含完整状态机
- [ ] `shared-memory/tasks/inbox.json` 入口文件存在
- [ ] `mypy src/ --ignore-missing-imports` 错误数 ≤ 基线（开始修复前记录）
- [ ] `git log --oneline` 显示所有 commit
- [ ] Pipeline 可通过 `python3 coordinator.py "test task"` 启动

---

## 时间估算

| Task | 预计时间 | 依赖 |
|------|---------|------|
| Task 1: team-workflow.md | 5 min | 无 |
| Task 2: Manager SOUL.md | 5 min | Task 1 |
| Task 3: Test Agent SOUL.md | 5 min | Task 1 |
| Task 4: Code Review SOUL.md | 10 min | Task 1 |
| Task 5: QC Agent SOUL.md | 10 min | Task 1 |
| Task 6: coordinator.py | 15 min | Task 2 |
| Task 7: inbox.json | 2 min | Task 1 |
| Task 8: mypy errors | 5 min | 无 |
| Task 9: mypy fix plan | 15 min | Task 8 |

**总计：约 72 分钟（可并行推进）**
