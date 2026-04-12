# OpenClaw 多 Agent 开发系统

基于 OpenClaw 原生架构的多 Agent 协作开发系统，实现 CI/CD + 测试 + 代码审查的完全自动化。

---

## 🏗️ 系统架构

```
用户/触发器
    ↓
Orchestrator（协调者）
    ├── 🧪 Test Agent（测试工程师）
    ├── 🔍 Code Review Agent（代码审查）
    ├── ✅ QC Agent（质量控制）
    └── 🚀 Deploy Agent（部署工程师）
```

---

## 📁 目录结构

```
dev-agent-system/
├── orchestrator/              # 协调者 Agent
│   └── SOUL.md              # Agent 灵魂定义
├── test-agent/               # 测试工程师
│   └── SOUL.md
├── code-review-agent/        # 代码审查
│   └── SOUL.md
├── qc-agent/                # 质量控制
│   └── SOUL.md
├── deploy-agent/             # 部署工程师
│   └── SOUL.md
├── shared-memory/            # 共享记忆
│   ├── tasks/               # 任务队列
│   ├── results/             # 各 Agent 结果
│   └── reports/             # 最终报告
├── src/                      # 示例源代码
├── tests/                    # 测试代码
│   ├── unit/
│   └── integration/
└── coordinator.py            # 协调器脚本
```

---

## 🚀 使用方式

### 方式1: 直接运行协调器

```bash
cd dev-agent-system
python3 coordinator.py "开发任务描述" --code-dir ./src
```

### 方式2: 通过 OpenClaw sessions_spawn 启动子 Agent

```bash
# 启动测试工程师
openclaw sessions spawn \
  --label test-engineer \
  --runtime subagent \
  --task "执行 src/ 下的单元测试" \
  --cwd ./test-agent

# 启动代码审查
openclaw sessions spawn \
  --label code-reviewer \
  --runtime subagent \
  --task "审查 src/ 代码质量问题" \
  --cwd ./code-review-agent
```

### 方式3: 配置 Cron 定时任务

```bash
# 每天早上9点自动运行代码审查
0 9 * * * cd /home/node/.openclaw/workspace/dev-agent-system && python3 coordinator.py "daily-code-review"
```

---

## 🤖 Agent 职责

| Agent | 职责 | 输出 |
|-------|------|------|
| **Orchestrator** | 任务分解、协调流程 | 汇总报告 |
| **Test Agent** | 单元测试、集成测试 | test-results.json |
| **Code Review Agent** | 代码质量、安全审查 | code-review-results.json |
| **QC Agent** | 文档、风格、类型检查 | qc-results.json |
| **Deploy Agent** | 构建、部署、验证 | deploy-report.json |

---

## 📊 工作流程

1. **任务接收** → Orchestrator 解析用户任务
2. **任务分解** → 拆分为测试、审查、QC 子任务
3. **并行执行** → 同时启动多个子 Agent
4. **结果汇总** → 收集各 Agent 执行结果
5. **质量门禁** → QC Agent 进行最终验收
6. **部署决策** → 通过则触发部署，失败则返回修复建议

---

## 🔧 配置要求

```bash
# 启用 Agent 间通信
openclaw config set agentToAgent.enabled true
openclaw config set agentToAgent.timeout 30000

# 使用 MiniMax-M2.7 作为默认模型
openclaw config set models.default "ai-gateway/MiniMax-M2.7"
```

---

## 📝 示例输出

```json
{
  "report_id": "task_20260412_090000",
  "generated_at": "2026-04-12T09:00:00Z",
  "summary": {
    "test": "✅ 通过 (38/40 通过, 覆盖率 85%)",
    "code_review": "✅ 通过 (发现 2 个优化建议)",
    "qc": "✅ 通过",
    "deploy": "✅ 完成"
  },
  "recommendation": "通过验收，发布生产"
}
```

---

## 🎯 扩展方向

- 添加更多专业 Agent（安全扫描、性能测试）
- 集成 GitHub Actions / GitLab CI
- 对接更多平台（钉钉、企业微信通知）
- 添加人工审批节点（关键部署前需确认）

---

更多信息请参考：[OpenClaw 多 Agent 文档](https://docs.openclaw.ai)
