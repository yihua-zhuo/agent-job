# 多 Agent 协作开发修复系统设计

## 一、系统架构

```
用户任务
    │
    ▼
┌─────────────────┐
│  Orchestrator   │ ← 任务编排器（主入口）
│  (任务分解 & 调度)│
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Test   │ │ Code   │ │ Deploy │ │ QC     │
│ Agent  │ │ Review │ │ Agent  │ │ Agent  │
│        │ │ Agent  │ │        │ │        │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │
    └──────────┴──────────┴──────────┘
                   │
                   ▼
           ┌──────────────┐
           │ Manager Agent│ ← 结果汇总 & 最终决策
           └──────────────┘
```

---

## 二、Agent 职责定义

### 2.1 Orchestrator（主编排器）
**职责**: 接收自然语言任务，分解为可执行子任务，调度各 Agent

**能力**:
- 任务解析（自然语言 → 结构化任务）
- 工作流编排（决定执行顺序和依赖）
- 状态跟踪（记录每个子任务进度）
- 异常处理（失败重试或升级）

**输入**: `{"task": "修复用户登录的 SQL 注入漏洞"}`
**输出**: `{"task_id": "T001", "subtasks": [...], "workflow": [...]}`

---

### 2.2 Test Agent（测试工程师）
**职责**: 编写和执行测试用例，验证修复正确性

**能力**:
- 单元测试生成
- 集成测试编写
- 测试覆盖率分析
- 失败用例定位

**输入**: `{"file": "src/auth.py", "type": "security_test"}`
**输出**: `{"test_results": {...}, "coverage": 0.85}`

---

### 2.3 Code Review Agent（代码审查）
**职责**: 代码质量审查，安全漏洞检测

**能力**:
- 代码规范检查
- 安全漏洞扫描（SQL注入、XSS等）
- 性能问题识别
- 多伦审查模式

**输入**: `{"files": ["src/auth.py"], "review_type": "security"}`
**输出**: `{"issues": [...], "severity": "critical", "suggestions": [...]}`

---

### 2.4 Deploy Agent（部署工程师）
**职责**: 负责代码部署和环境配置

**能力**:
- 构建镜像
- 部署到目标环境
- 回滚机制
- 环境验证

**输入**: `{"commit": "abc123", "environment": "staging"}`
**输出**: `{"deployment_id": "...", "status": "success"}`

---

### 2.5 QC Agent（质量控制）
**职责**: 最终质量把关，决定是否允许合并

**能力**:
- 合规性检查
- 文档完整性
- 测试通过验证
- 最终审批

**输入**: `{"task_id": "T001", "all_results": {...}}`
**输出**: `{"approved": true/false, "blocker_issues": [...]}`

---

### 2.6 Manager Agent（管理器）
**职责**: 汇总各 Agent 结果，做出最终决策

**能力**:
- 结果聚合
- 决策生成
- 报告输出
- 人工升级

**输入**: 各 Agent 的执行结果
**输出**: `{"final_decision": "MERGE/REJECT", "summary": "...", "next_actions": [...]}`

---

## 三、工作流程

### 3.1 完整开发修复流程

```
阶段 1: 任务接收
┌────────────────────────────────────────────┐
│ Orchestrator                               │
│ 1. 接收任务描述                            │
│ 2. 解析任务类型（bugfix/feature/refactor） │
│ 3. 识别涉及代码组件                        │
│ 4. 生成子任务列表                          │
└────────────────────────────────────────────┘
                    │
                    ▼
阶段 2: 代码修复
┌────────────────────────────────────────────┐
│ Code Fixer Agent                           │
│ 1. 分析问题根因                            │
│ 2. 编写修复代码                            │
│ 3. 自测验证                                │
└────────────────────────────────────────────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
阶段 3a: 并行测试         阶段 3b: 安全审查
┌────────────────┐      ┌────────────────────┐
│ Test Agent     │      │ Code Review Agent │
│ - 单元测试     │      │ - 安全漏洞扫描    │
│ - 集成测试     │      │ - 代码规范检查    │
│ - 覆盖率验证   │      │ - 性能分析        │
└────────────────┘      └────────────────────┘
          │                   │
          └─────────┬────────┘
                    ▼
阶段 4: QC 验证
┌────────────────────────────────────────────┐
│ QC Agent                                   │
│ 1. 验证测试通过                            │
│ 2. 检查安全审查结果                        │
│ 3. 确认文档更新                            │
│ 4. 输出审批决策                            │
└────────────────────────────────────────────┘
                    │
                    ▼
阶段 5: 部署
┌────────────────────────────────────────────┐
│ Deploy Agent                               │
│ 1. 构建 Docker 镜像                       │
│ 2. 部署到目标环境                          │
│ 3. 验证部署成功                            │
│ 4. 更新任务状态                            │
└────────────────────────────────────────────┘
                    │
                    ▼
阶段 6: 完成
┌────────────────────────────────────────────┐
│ Manager Agent                              │
│ 1. 汇总所有结果                            │
│ 2. 生成最终报告                            │
│ 3. 通知相关人员                            │
└────────────────────────────────────────────┘
```

---

### 3.2 并行执行示例

```
Task: 修复客户列表 API 性能问题

Orchestrator 分解:
├── Task 1: 代码修复 (Code Fixer)          [串行]
├── Task 2: 安全审查 (Code Review)         [与 Task1 并行]
└── Task 3: 单元测试 (Test Agent)         [与 Task1 并行]

执行顺序:
T1 ─┬─▶ T2 (并行)
    │
    └─▶ T3 (并行) ─▶ T4 (QC) ─▶ T5 (Deploy) ─▶ T6 (Done)
```

---

### 3.3 失败重试机制

```
Agent 执行失败
       │
       ▼
   重试次数 < 3?
       │
  是 ◀─┘
       ▼
   等待 5s 后重试
       │
       ▼
   仍然失败?
       │
  是 ──┴──▶ 升级到 Manager Agent
               │
               ▼
           人工介入
```

---

## 四、任务数据结构

### 4.1 任务定义
```json
{
  "task_id": "T001",
  "type": "bugfix",
  "priority": "high",
  "description": "修复用户登录 SQL 注入漏洞",
  "components": ["src/auth.py", "src/models/user.py"],
  "subtasks": [
    {
      "subtask_id": "S001",
      "agent": "code_fixer",
      "description": "修复 auth.py 中的 SQL 拼接",
      "status": "pending",
      "dependencies": []
    },
    {
      "subtask_id": "S002",
      "agent": "code_review",
      "description": "安全审查 auth.py",
      "status": "pending",
      "dependencies": ["S001"]
    },
    {
      "subtask_id": "S003",
      "agent": "test",
      "description": "执行安全测试",
      "status": "pending",
      "dependencies": ["S001"]
    },
    {
      "subtask_id": "S004",
      "agent": "qc",
      "description": "最终质量检查",
      "status": "pending",
      "dependencies": ["S002", "S003"]
    }
  ],
  "workflow": [
    {"from": "S001", "to": ["S002", "S003"], "type": "parallel"},
    {"from": ["S002", "S003"], "to": "S004", "type": "sequential"},
    {"from": "S004", "to": null, "type": "end"}
  ]
}
```

### 4.2 Agent 执行结果
```json
{
  "agent": "code_review",
  "subtask_id": "S002",
  "status": "completed",
  "result": {
    "issues": [
      {
        "file": "src/auth.py",
        "line": 42,
        "type": "sql_injection",
        "severity": "critical",
        "message": "直接拼接用户输入到 SQL 查询",
        "fix": "使用参数化查询"
      }
    ],
    "summary": "发现 1 个严重安全问题",
    "approval": "CHANGES_REQUESTED"
  },
  "timestamp": "2026-04-13T00:00:00Z",
  "duration_ms": 2500
}
```

---

## 五、Agent 间通信

### 5.1 消息格式
```json
{
  "msg_id": "MSG001",
  "from": "orchestrator",
  "to": "test_agent",
  "type": "task_dispatch",
  "payload": {
    "subtask_id": "S003",
    "task": "安全测试",
    "files": ["src/auth.py"],
    "context": {...}
  },
  "timestamp": "2026-04-13T00:00:00Z"
}
```

### 5.2 消息类型
| 消息类型 | 说明 |
|---------|------|
| task_dispatch | 分发任务 |
| task_result | 返回结果 |
| status_update | 状态更新 |
| error_report | 错误报告 |
| approval_request | 审批请求 |

---

## 六、实际调用示例

### 6.1 Bugfix 场景

**输入**:
```
用户: "修复客户搜索的 XSS 漏洞"
```

**Orchestrator 解析**:
```python
{
  "task_id": "T002",
  "type": "bugfix",
  "priority": "high",
  "components": ["src/api/customers.py"],
  "subtasks": [
    {"agent": "code_fixer", "description": "修复 XSS"},
    {"agent": "test", "description": "安全测试"},
    {"agent": "code_review", "description": "安全审查"},
    {"agent": "qc", "description": "QC 验证"}
  ]
}
```

**执行流程**:
```
code_fixer: 修复 XSS → 修复完成
test: 安全测试 → 通过 ✅
code_review: 安全审查 → 发现 1 个问题 → 修复
test: 复测 → 通过 ✅
qc: 最终验证 → 批准 ✅
manager: 汇总 → 完成
```

---

### 6.2 Feature 开发场景

**输入**:
```
用户: "新增客户标签功能"
```

**执行流程**:
```
orchestrator: 分解任务
code_fixer: 开发标签 API (CRUD)
test: 单元测试 + 集成测试
code_review: 代码审查 + 安全审查
qc: 功能验证 + 文档检查
deploy: 部署到 staging
manager: 报告完成
```

---

## 七、部署状态

| Agent | 状态 | 路径 |
|-------|------|------|
| Orchestrator | ✅ 已有基础 | `scripts/coordinator.py` |
| Test Agent | ✅ 已有基础 | `docs/agents/test-agent/` |
| Code Review Agent | ✅ 已有（多伦模式） | `docs/agents/code-review-agent/` |
| Deploy Agent | ✅ 已有基础 | `scripts/deploy.py` |
| QC Agent | ✅ 已有基础 | `docs/agents/qc-agent/` |
| Manager Agent | 🆕 待实现 | `docs/agents/manager-agent/` |

---

## 八、文件结构

```
dev-agent-system/
├── scripts/
│   ├── coordinator.py    ← Orchestrator 主入口
│   └── run_agents.py     ← Agent 调度脚本
├── docs/agents/
│   ├── orchestrator/     ← 编排器配置
│   ├── test-agent/       ← 测试工程师
│   ├── code-review-agent/← 代码审查（多伦模式）
│   ├── deploy-agent/     ← 部署工程师
│   ├── qc-agent/         ← 质量控制
│   └── manager-agent/    ← 管理器（新）
└── shared-memory/
    ├── tasks/            ← 任务队列
    ├── results/          ← 各 Agent 结果
    └── workflows/        ← 工作流定义
```

---

## 九、后续任务

- [ ] 实现 Manager Agent（结果汇总 & 决策）
- [ ] 实现 Orchestrator 的工作流编排
- [ ] 添加 Agent 间消息队列（Redis 或文件）
- [ ] 开发 Web 监控面板查看任务进度
- [ ] 集成到 CI Pipeline