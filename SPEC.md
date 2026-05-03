# 共享记忆多 Agent 系统 — SPEC.md

> 🔄 2026-05-03 更新：共享记忆从 Redis 迁移至 GitHub Issues

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
          ┌───────────────┴───────────────┐
          │    Shared Memory (GitHub)     │
          │    yihua-zhuo/agent-job        │
          │    Issues as KV Database      │
          └───────────────────────────────┘
```

## 3. 共享记忆设计 (GitHub Issues)

### 核心原理

用 GitHub Issues 作为分布式 KV 数据库：
- 每条任务 = 1 个 Issue（Body = JSON，Comments = 执行日志）
- Labels 实现状态机（pending → running → done）和 Agent 路由
- 无需自建 Redis，任何能访问 GitHub 的 Agent 都能参与
- GitHub API 提供 ETAG 乐观锁，天然支持分布式

### Issue 标题约定

| 前缀 | 用途 |
|------|------|
| `[task] task-{timestamp}` | 单个任务 |
| `[context] {key}` | 全局上下文 KV |

### 标签约定

| 标签 | 含义 |
|------|------|
| `type:task` | 内容类型：任务 |
| `type:context` | 内容类型：上下文 |
| `status:pending` | 任务状态：等待执行 |
| `status:running` | 任务状态：执行中 |
| `status:done` | 任务状态：已完成 |
| `agent:supervisor` | 负责 Agent：Supervisor |
| `agent:code-review` | 负责 Agent：Code Review |
| `agent:test` | 负责 Agent：Test |
| `agent:qc` | 负责 Agent：QC |
| `agent:deploy` | 负责 Agent：Deploy |

### GitHub Issues 作为 KV 的读写模型

```
提交任务  →  gh_post("/issues", {title, body, labels})
轮询任务  →  gh_get("/search/issues?q=label:status:pending label:agent:xxx")
认领任务  →  gh_patch("/issues/{n}", {body, labels: add/remove})
写入结果  →  gh_post("/issues/{n}/comments", {body})
读取结果  →  gh_get("/issues/{n}/comments")
更新状态  →  gh_relabel(issue_number, add: [done], remove: [running])
```

## 4. Agent 角色定义

### Supervisor (协调者)
- 接收用户任务请求（通过 Telegram 或直接调用）
- 分解任务为子任务，submit_task() 创建 GitHub Issues
- 轮询 task comments，收集所有 Agent 结果
- 通过 Telegram 实时推送进度
- 汇总报告发给用户

### Code Review Agent
- 轮询自己的 pending 任务（get_pending_tasks("code-review")）
- 执行 git diff 分析
- complete_task() + write_memory() 写入结果
- 读取共享记忆：read_task_comments() 读取同伴结果

### Test Agent
- 执行单元/集成测试
- 解析失败测试，写入 memory comment

### QC Agent
- 检查代码风格（flake8）、类型（mypy）、覆盖率
- 读取 memory 中的 review 和 test 结果做综合判断
- 写入最终 QC gate 结果

### Deploy Agent
- 检查所有 gate 通过后执行 git push
- 写入部署日志

## 5. 核心流程

### 任务执行流程
1. 用户通过 Telegram `/submit <任务>` 提交
2. Supervisor 分解任务 → 循环调用 submit_task() 为每个子任务创建 GitHub Issue
3. 各 Agent 轮询 get_pending_tasks(agent=xxx) 认领任务
4. Agent 执行，complete_task() + write_memory() 写入结果到 comment
5. Supervisor 轮询 read_task_comments() 收集所有 Agent 结果
6. 汇总报告通过 Telegram 发送给用户

### 共享记忆读写规则
- **写**: write_memory() 追加 comment 到父 task issue
- **读**: read_task_comments() 读取同伴写入的 comments
- **上下文**: write_context() / read_context() 读写全局配置（独立 issue）
- **状态**: 通过 labels（pending/running/done）追踪，无需额外写入

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

- **共享记忆**: GitHub Issues + Comments（REST API，aiohttp）
- **任务队列**: GitHub Search API 按标签查询（`is:open label:status:pending label:agent:xxx`）
- **状态机**: Issue Labels（type:task + status:pending/running/done + agent:xxx）
- **结果传递**: Issue Comments（各 Agent 写入 JSON 格式结果）
- **上下文存储**: 独立 `[context]` Issue（键值对）
- **轮询间隔**: 3 秒（受 GitHub API rate limit 5000 req/hr 限制）

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
│   └── __init__.py           GitHub Issues 共享记忆实现
├── bot/
│   └── telegram_bot.py       Telegram 命令处理
├── run_agents.py             启动脚本
└── SPEC.md
```

### GitHub Project V2 看板

除了 GitHub Issues 作为任务存储，还可以用 yihua-zhuo/agent-job 的 **Project V2** 看板来可视化每个 Agent 的实时状态。

实现文件：`shared_memory/project_board.py`

**看板布局：**
- Column "Todo"        → 有 pending 任务的 Agent（作为 draft issue）
- Column "In Progress" → 有 running 任务的 Agent（不在 board 上留 item，任务在 Issue 上可见）
- Column "Done"        → 空闲 / 已完成当日任务的 Agent

**同步逻辑：**
- `sync_all_agents_to_board()` 从 GitHub Issues 统计各 Agent 的 pending/running/done 数量
- 根据状态将对应 draft issue 移动到正确列
- 每个 Agent 在 Todo 列最多 1 个 item
- `setProjectV2ItemFieldValue` mutation 更新 Status 字段

**调用方式（每次心跳或 cron）：**
```python
import asyncio, subprocess, os
os.environ["GITHUB_TOKEN"] = subprocess.check_output(["gh", "auth", "token"]).decode().strip()
from shared_memory.project_board import sync_all_agents_to_board
asyncio.run(sync_all_agents_to_board())
```

## 9. 为什么从 Redis 改为 GitHub Issues？

| | Redis | GitHub Issues |
|---|---|---|
| 部署 | 需自建/托管 | 零成本，天然存在 |
| 访问控制 | 需网络隔离 | GitHub 权限体系 |
| 持久化 | 内存易丢 | 自动持久化 |
| 审计 | 需额外日志 | 原生 issue history |
| 多仓库 | 需区分 DB | 天然支持多 repo |
| 冲突 | 需分布式锁 | GitHub ETAG 乐观锁 |
| 外部可见性 | 内部 | 其他服务可见可查 |

## 10. 验收标准

- [ ] Supervisor 能接收任务并分解为子任务（创建 GitHub Issues）
- [ ] 多个 Agent 可以并发认领不同子任务
- [ ] Agent 之间能通过 issue comments 交换信息
- [ ] 用户通过 Telegram 可以提交任务和查看进度
- [ ] 任务完成后用户能收到最终汇总报告
- [ ] Agent 崩溃后下次轮询仍能重新认领 pending 任务
- [ ] GitHub Issues 自动保留所有执行日志（无需 TTL 管理）