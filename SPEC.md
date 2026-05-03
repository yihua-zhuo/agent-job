# 共享记忆多 Agent 系统 — SPEC.md

> 🔄 2026-05-03 更新：共享记忆从 Redis 迁移至本地文件（pipeline checkout 自 agent-job-shared-memory）

## 1. 概念与愿景

一个多 Agent 协作系统，多个专业化 Agent（code-review、test、qc、deploy）通过共享记忆库协作。每个 Agent 可以读写共享记忆，Supervisor Agent 负责任务分发和结果聚合。用户通过 Telegram 与系统交互，实时看到任务进度和 Agent 协作状态。

核心区别于单 Agent：记忆是共享的，不是每个 Agent 独立持有。所有 Agent 看到的上下文是同一个。

## 2. 系统架构

```
用户 (Telegram)
    │
    ▼
┌─────────────────────────────────────────┐
│        Supervisor Agent (Orchestrator)  │
│  - 负责任务分解                          │
│  - 分发给子 Agent（写 orchestrator_queue）│
│  - 聚合结果                              │
│  - 向用户报告                            │
└────────────────┬────────────────────────┘
                 │
          ┌──────┴───────┬──────────┬──────────┐
          ▼              ▼          ▼          ▼
     ┌─────────┐  ┌──────────┐  ┌──────┐  ┌─────────┐
     │ Code    │  │  Test    │  │  QC  │  │ Deploy  │
     │ Review  │  │  Agent   │  │Agent │  │  Agent  │
     └────┬────┘  └────┬─────┘  └──┬───┘  └────┬────┘
          │             │           │            │
          └─────────────┴───────────┴────────────┘
                          │
          ┌───────────────┴───────────────┐
          │  agent-job-shared-memory       │
          │  (pipeline 每次运行前 checkout) │
          │                                │
          │  orchestrator_queue.json       │
          │  orchestrator_state.json       │
          │  results/                       │
          │  reports/                       │
          │  tasks/                         │
          └────────────────────────────────┘
```

## 3. 共享记忆设计 (本地文件，pipeline checkout)

共享记忆仓库：[yihua-zhuo/agent-job-shared-memory](https://github.com/yihua-zhuo/agent-job-shared-memory)

**架构：**
- pipeline 每次运行前从 GitHub clone/checkout `agent-job-shared-memory` 到本地目录
- 所有 agent 通过读写该目录下的 JSON 文件协作，无需网络 API
- `AGENT_JOB_SHARED_MEMORY` 环境变量指定 checkout 路径（默认 `~/.openclaw/workspace/agent-job-shared-memory`）

**文件约定：**

| 文件 | 用途 |
|------|------|
| `orchestrator_queue.json` | 任务队列（待处理子任务列表）|
| `orchestrator_state.json` | 当前任务整体状态（running/completed）|
| `results/{agent_id}_result.json` | 各 agent 单次执行结果 |
| `reports/{task_id}_report.json` | 最终汇总报告 |
| `tasks/{task_id}.json` | 任务历史记录 |

**Agent 路由：** 通过 `orchestrator_queue.json` 中每个 agent 的 `agent_id` 路由：
- `supervisor` → 负责任务分解和汇总
- `code-review` → 代码审查
- `test` → 测试执行
- `qc` → 质量门禁
- `deploy` → 部署执行

**轮询流程：**
1. Supervisor 写 `orchestrator_queue.json`（enqueue_task）
2. 各子 Agent 轮询 `get_pending_agents(agent_id=xxx)` 认领任务
3. Agent 执行后写 `results/{agent_id}_result.json`
4. Agent 更新 `orchestrator_queue.json` 中自己的状态为 completed
5. Supervisor 全部完成后写 `orchestrator_state.json` + `reports/`

## 4. Agent 角色定义

### Supervisor (协调者)
- 接收用户任务请求（通过 Telegram 或直接调用）
- 分解任务为子任务，写入 `orchestrator_queue.json`
- 轮询 `orchestrator_queue.json`，收集所有 Agent 结果
- 通过 Telegram 实时推送进度
- 汇总报告发给用户

### Code Review Agent
- 轮询自己的 pending 任务（`get_pending_agents("code-review")`）
- 执行 git diff 分析
- 写入 `results/code_review_result.json`
- 更新 `orchestrator_queue.json` 中自己的状态

### Test Agent
- 执行单元/集成测试（pytest）
- 解析失败测试，写入 `results/test_result.json`

### QC Agent
- 检查代码风格（flake8）、类型（mypy）、覆盖率
- 读取 `results/` 中 review 和 test 结果做综合判断
- 写入 `results/qc_result.json`

### Deploy Agent
- 检查所有 gate 通过后执行 git push
- 写入 `results/deploy_result.json`

## 5. 核心流程

### 任务执行流程
1. 用户通过 Telegram `/submit <任务>` 提交
2. Supervisor 分解任务 → 循环调用 `enqueue_task()` 写入 `orchestrator_queue.json`
3. 各 Agent 轮询 `get_pending_agents(agent_id=xxx)` 认领任务
4. Agent 执行，写入 `results/{agent_id}_result.json`
5. Agent 更新 `orchestrator_queue.json` 中自己的状态为 completed
6. Supervisor 轮询检测所有 agent 完成，写入 `orchestrator_state.json` + `reports/`
7. 汇总报告通过 Telegram 发送给用户

### 共享记忆读写规则
- **写队列**: `enqueue_task()` / `update_task_status()`
- **读队列**: `read_queue()` / `get_pending_agents()`
- **写结果**: `write_result(agent_id, result_dict)`
- **读结果**: `read_result(agent_id)` / `read_all_results()`
- **状态**: `orchestrator_state.json`（init_state / patch_agent_state / complete_state）

## 6. Telegram 命令

| 命令 | 功能 |
|------|------|
| `/start` | 显示 Agent 团队状态 |
| `/status` | 查看所有 Agent 当前状态 |
| `/tasks` | 查看待处理/进行中/已完成任务 |
| `/submit <任务>` | 提交新任务 |
| `/result <task_id>` | 查看任务结果 |
| `/abort <task_id>` | 取消任务 |

## 7. 技术实现

- **共享记忆**: 本地 JSON 文件（checkout 自 agent-job-shared-memory）
- **任务队列**: `orchestrator_queue.json`（文件锁 `threading.Lock`）
- **状态机**: `orchestrator_queue.json` 中的 `status` 字段（pending → running → completed）
- **结果传递**: `results/{agent_id}_result.json`（JSON 文件）
- **上下文存储**: `orchestrator_state.json`
- **轮询间隔**: 3 秒
- **进程隔离**: 各 agent 运行于独立进程（`run_agents.py` multiprocessing）

## 8. 文件结构

```
dev-agent-system/
├── agents/
│   ├── supervisor/
│   │   └── supervisor.py     Supervisor 主循环 + 任务分解
│   ├── base_agent.py          BaseAgent 轮询基类
│   ├── code_review/
│   │   └── review_agent.py   Code Review Agent
│   ├── test/
│   │   └── test_agent.py     Test Agent
│   ├── qc/
│   │   └── qc_agent.py       QC Agent
│   └── deploy/
│       └── deploy_agent.py   Deploy Agent
├── shared_memory/
│   └── __init__.py           本地文件共享记忆实现
│                               (checkout 自 agent-job-shared-memory)
├── bot/
│   └── telegram_bot.py       Telegram 命令处理
├── run_agents.py             启动脚本
└── SPEC.md
```

## 9. 为什么从 Redis 改为本地文件？

| | Redis | 本地文件（agent-job-shared-memory checkout） |
|---|---|---|
| 部署 | 需自建/托管 | 零成本，pipeline checkout |
| 访问控制 | 需网络隔离 | 通过 GitHub 权限 |
| 持久化 | 内存易丢 | Git 历史永久保留 |
| 审计 | 需额外日志 | git log 原生审计 |
| 冲突 | 需分布式锁 | 文件锁（threading.Lock）|
| 多仓库 | 需区分 DB | 天然支持多 repo |
| 可见性 | 内部 | 其他服务可直接读文件 |

## 10. 验收标准

- [ ] pipeline 运行时自动 checkout agent-job-shared-memory 到本地
- [ ] Supervisor 能接收任务并分解为子任务（写入 orchestrator_queue.json）
- [ ] 多个 Agent 可以并发认领不同子任务（轮询 get_pending_agents）
- [ ] Agent 之间能通过 results/ 目录交换信息
- [ ] 用户通过 Telegram 可以提交任务和查看进度
- [ ] 任务完成后用户能收到最终汇总报告
- [ ] Agent 崩溃后下次轮询仍能重新认领 pending 任务
- [ ] 所有执行记录通过 git 永久保存在 agent-job-shared-memory
