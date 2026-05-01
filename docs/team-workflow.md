# Agent-Job 开发团队工作流

本文档定义了 agent-job 多智能体开发系统的工作流标准。

---

## 1. 核心原则

| # | 原则 | 说明 | 关联技能 |
|---|------|------|----------|
| 1 | **TDD 优先** | 所有功能开发必须先写测试，再实现功能 | `test-driven-development` |
| 2 | **系统化调试** | 遇到 bug 必须走 4 阶段根因分析 | `systematic-debugging` |
| 3 | **代码审查** | 提交前必须经过独立审查 | `requesting-code-review` |
| 4 | **计划驱动** | 多步骤任务必须先写实现计划 | `writing-plans` |
| 5 | **Subagent 执行** | 复杂任务用 subagent 并行化 | `subagent-driven-development` |

---

## 2. 流水线流程

```
用户提交任务
     │
     ▼
┌─────────────────┐
│  Manager Agent  │  ← 接收任务，写计划，协调各 Agent
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │ 并行执行 │  ← Test Agent + 初始 Code Review 并行
    └────┬────┘
         │
         ▼
┌─────────────────┐
│ Code Review Agent │  ← 多轮审查，直到达标
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   QC Agent      │  ← 质量门禁：mypy, ruff, pytest
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deploy Agent    │  ← 部署到目标环境
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Manager Agent  │  ← 汇总结果，汇报给用户
└─────────────────┘
```

---

## 3. 阶段详情

### Phase 1: 任务接收（Manager Agent）

- **输入**: `inbox.json` — 用户提交的任务描述
- **输出**: `plan.json` — 分解后的实现计划
- **职责**:
  - 解析任务需求
  - 识别依赖关系
  - 分配给专业 Agent
  - 监控进度

### Phase 2: 开发（各专业 Agent）

遵循 TDD 流程：

```
RED    → 写一个会失败的测试
GREEN  → 写最少的代码让测试通过
REFACTOR → 重构优化代码
```

- **Test Agent**: 编写测试用例
- **开发者 Agent**: 实现功能
- **Code Review Agent**: 审查代码质量

### Phase 3: 质量门禁（QC Agent）

质量门禁检查项：

| 检查项 | 工具 | 标准 |
|--------|------|------|
| 类型检查 | `mypy` | 100% 类型注解，无错误 |
| 代码风格 | `ruff` | 0 violations |
| 单元测试 | `pytest` | 100% 通过率 |
| 覆盖率 | `pytest --cov` | 核心模块 ≥ 80% |

### Phase 4: 部署（Deploy Agent）

- 构建产物
- 执行部署脚本
- 验证部署结果
- 通知 Manager 完成状态

---

## 4. 触发事件表

| 事件 | 触发 Agent 链 | 说明 |
|------|--------------|------|
| `git push` | Manager → Test → CR → QC → Deploy | 自动流水线触发 |
| `PR 创建/更新` | Code Review Agent | 多轮审查直到通过 |
| `QC 失败` | systematic-debugging | 启动 4 阶段根因分析 |
| `手动触发` | 任意 Agent | 通过 `coordinator.py` 交互 |

---

## 5. 软件工程技能参考

### test-driven-development
- **何时使用**: 开发任何新功能或修改现有功能时
- **流程**: RED → GREEN → REFACTOR
- **要求**: 测试覆盖所有核心逻辑

### systematic-debugging
- **何时使用**: 发现 bug 时
- **4 阶段根因分析**:
  1. 复现问题
  2. 定位根因
  3. 修复代码
  4. 验证修复

### requesting-code-review
- **何时使用**: 代码合并前
- **流程**: 作者提交 → Reviewer 审查 → 修改 → 再次审查 → 合并

### writing-plans
- **何时使用**: 任何多步骤任务开始前
- **要求**: 包含任务分解、依赖关系、验收标准

### subagent-driven-development
- **何时使用**: 复杂任务可以并行处理时
- **优势**: 加速开发，充分利用多 Agent 并行能力

---

## 6. 文件结构

```
agent-job/
├── docs/
│   ├── agents/              # 各 Agent 的定义和技能
│   │   ├── manager-agent/
│   │   ├── orchestrator/
│   │   ├── test-agent/
│   │   ├── code-review-agent/
│   │   ├── qc-agent/
│   │   └── deploy-agent/
│   ├── team-workflow.md     # 本文档
│   └── MULTI_AGENT_DESIGN.md
├── src/
│   └── agent_job/
└── tests/
```

---

*本文档随系统迭代更新，最后更新于 2026-04-22*