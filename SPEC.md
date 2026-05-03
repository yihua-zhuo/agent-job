# 共享记忆多 Agent 系统 — SPEC.md

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
│  - 负责任务分解                         │
│  - 分发给子 Agent                        │
│  - 聚合结果                             │
│  - 向用户报告                           │
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
                 ┌────────┴────────┐
                 │  Shared Memory  │
                 │  (Redis 6379)   │
                 │                 │
                 │  - tasks/       │
                 │  - context/     │
                 │  - results/     │
                 │  - lock/         │
                 └─────────────────┘
```

## 3. 共享记忆设计 (Redis)

### Key 命名规范
```
agent-system:
  tasks:pending          → List[Task]      待执行任务
  tasks:running          → Set[TaskId]      正在执行的任务
  tasks:completed        → List[TaskResult] 已完成任务结果
  context:global         → Dict             全局上下文（代码库状态等）
  context:agent:<name>   → Dict             各 Agent 专用上下文
  memory:shared          → Dict             共享记忆（Agent 间交换的信息）
  lock:task:<task_id>    → String           任务锁（防止重复执行）
```

### 共享记忆内容
- **代码库快照**: 当前分支、commit hash、最近修改的文件
- **任务上下文**: 当前任务描述、相关文件列表、已完成的子步骤
- **中间结果**: code-review 发现的问题、test 覆盖率数据、qc 检查结果
- **协调信息**: 哪个 Agent 正在处理什么、依赖关系、阻塞条件

## 4. Agent 角色定义

### Supervisor (协调者)
- 接收用户任务请求
- 分解任务为子任务，写入 `tasks:pending`
- 监听 `tasks:completed`，聚合结果
- 通过 Telegram 实时推送进度
- 决策：重试、跳过、终止

### Code Review Agent
- 读取共享上下文（任务描述 + 代码变更）
- 扫描代码问题，写入 `context:agent:code-review`
- 标记发现的问题到 `memory:shared`
- 支持 /review 命令手动触发

### Test Agent
- 执行单元/集成测试
- 上传测试结果到 `results:test`
- 解析失败测试，写入 `memory:shared` 供 QC 参考

### QC Agent
- 检查代码风格、类型提示、文档
- 验证测试覆盖率阈值
- 读取 `memory:shared` 中的 review 和 test 结果做综合判断

### Deploy Agent
- 检查所有 gate 通过后执行部署
- 写入部署日志到 `context:agent:deploy`

## 5. 核心流程

### 任务执行流程
1. 用户发送任务描述
2. Supervisor 分解任务，写入 `tasks:pending`
3. 各 Agent 竞争获取任务（LPOP + 锁）
4. Agent 执行，写入 `context:agent:<name>` + `memory:shared`
5. Supervisor 监听完成事件，聚合报告
6. 最终结果通过 Telegram 发送给用户

### 共享记忆读写规则
- **写**: Agent 只写自己的 `context:agent:<name>` + `memory:shared`
- **读**: 所有 Agent 可以读所有共享记忆
- **原子性**: 任务锁 `lock:task:<id>` 确保不重复执行
- **过期**: 任务结果 24h 后自动过期

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

- **Agent 通信**: Redis Pub/Sub（agent-system:events 频道）
- **任务队列**: Redis List（LPOP 原子获取任务）
- **共享上下文**: Redis Hash + JSON 序列化
- **状态同步**: 每 10s 更新心跳到 `context:agent:<name>:heartbeat`
- **Supervisor**: 主循环每 5s 检查 `tasks:pending` 和 `tasks:completed`

## 8. 文件结构

```
dev-agent-system/
├── agents/
│   ├── supervisor/          Supervisor Agent（主编排器）
│   │   ├── __init__.py
│   │   ├── supervisor.py     主循环 + 任务分解
│   │   └── coordinator.py   子任务分发逻辑
│   ├── code_review/          Code Review Agent
│   │   ├── __init__.py
│   │   └── review_agent.py
│   ├── test/                 Test Agent
│   │   ├── __init__.py
│   │   └── test_agent.py
│   ├── qc/                   QC Agent
│   │   └── qc_agent.py
│   └── deploy/               Deploy Agent
│       └── deploy_agent.py
├── shared_memory/
│   ├── __init__.py
│   ├── redis_client.py       Redis 连接管理
│   ├── memory_store.py       读写接口
│   ├── tasks.py              任务队列操作
│   └── context.py            上下文管理
├── bot/
│   └── telegram_bot.py       Telegram 命令处理
├── run_agents.py             启动脚本（Supervisor + 所有子 Agent）
└── SPEC.md
```

## 9. 验收标准

- [ ] Supervisor 能接收任务并分解为子任务
- [ ] 多个 Agent 可以并发获取不同子任务
- [ ] Agent 之间能通过共享记忆交换信息
- [ ] 用户通过 Telegram 可以查看任务进度
- [ ] 任务完成后用户能收到最终报告
- [ ] Agent 崩溃后任务可以重新分配
- [ ] 共享记忆中的数据有 TTL 自动清理