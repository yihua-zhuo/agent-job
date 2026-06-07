# Email · 发送邮件 & 创建任务 agent工具

| 元数据 | 值 |
|---|---|
| Issue | #508 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：Agent工具基座实现文档路径 |
| 启用后赋能 | TBD - 待验证：Agent执行引擎文档路径, TBD - 待验证：Copilot路由文档路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CopilotService 的工具注册表中仅有基础工具，缺少 `send_email`（发送邮件）和 `create_task`（创建任务）两个高价值工具。Agent 在处理用户请求（如"给张三分发任务"）时必须能够调用这两个能力才能完成端到端业务流程。此需求是 #76（Copilot Agent 系统）的核心细粒度能力单元。

### 1.2 做完后

- **用户视角**：「无用户可见变化 — 纯 Agent 后端能力」
- **开发者视角**：`CopilotService` 新增 `send_email_tool` 和 `create_task_tool` 两个可执行工具，注册在工具注册表中并可通过 OpenAI tool-calling 协议调用；获得两个对应的单元测试覆盖。

### 1.3 不做什么（剔除）

- [ ] 不实现完整的 SMTP发送逻辑（仅 stub/validate，存在真实 infra 时再接入）
- [ ] 不实现 `create_lead`、`update_ticket` 等其他 Agent 工具
- [ ] 不实现 Slack/飞书等通知渠道

### 1.4 关键 KPI

- [指标1：`PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → 新增 2 个 passed（send_email_tool + create_task_tool）]
- [指标 2：`ruff check src/services/copilot_service.py` → 0 errors]
- [指标 3：`ruff check tests/unit/test_copilot_service.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/copilot_service.py` —查找 CopilotService 类定义及 tool_registry字典所在行（预期约 L{10}-L{80} 范围），现有工具注册字典结构应类似 `{"send_message": ..., "search_kb": ...}` 形式

TBD - 待验证：`src/services/task_service.py` —查找 `TaskService` 类是否存在、`create_task` 方法签名及是否返回 ORM 对象（如已存在可直接复用）

TBD - 待验证：邮件发送相关 infrastructure 是否存在（预期在 `src/services/email_service.py` 或类似位置），如不存在则 stub### 2.2 涉及文件清单

- 要改：
  - `src/services/copilot_service.py` — 新增 `send_email_tool` 和 `create_task_tool` 注册到 `tool_registry` dict
- 要建：
  - `tests/unit/test_copilot_service.py` — 新增 `test_send_email_tool_valid` 和 `test_create_task_tool_valid` 两个测试用例

### 2.3 缺什么

- [ ] `CopilotService` 缺少 `send_email` tool handler（需 validate recipients 列表并调用邮件 infra）
- [ ] `CopilotService` 缺少 `create_task` tool handler（需调用 TaskService 插入 tasks 表）
- [ ] 两者均未在 `tool_registry` 字典中注册，Agent 无法通过 tool-calling 调用
- [ ] 无对应单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_copilot_service.py` |覆盖 send_email_tool 和 create_task_tool 的单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/copilot_service.py`](../../../src/services/copilot_service.py) | 新增 `send_email_tool` 和 `create_task_tool` 两个 async 方法 + 注册到 `tool_registry` dict |

### 3.3 新增能力

- **`CopilotService.send_email_tool(self, recipients: list[str], subject: str, body: str, ctx: AuthContext) -> dict`**：验证 recipients 非空且格式合法，调用邮件 infra（stub 模式），返回发送结果 dict；输入非法时抛 `ValidationException`
- **`CopilotService.create_task_tool(self, title: str, description: str, assignee_id: int, tenant_id: int) -> dict`**：封装 TaskService.insert_task，插入 tasks 表；字段非法时抛 `ValidationException`
- **Tool registry entry**：`{"send_email": send_email_tool, "create_task": create_task_tool}` 追加到 `tool_registry` dict

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 TaskService 不自建 SQL**：利用现有 `TaskService`插入 tasks 表，避免在 copilot_service 中重复 SQL逻辑。
- **邮件 stub 模式**：当前阶段邮件 infra状态未知，采用 stub（返回成功结构）而非阻塞等待 infra 接入，保证 tool 可执行。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- Tool handler 必须接收 `ctx: AuthContext` 以提取 `tenant_id`，所有 DB 操作必须以 `tenant_id` 过滤
- Service 层错误抛 `AppException` 子类（`ValidationException`），**不**返回 dict with error key
- Tool 方法用 `async def` 定义，签名与 `tool_registry` 中已有方法保持一致

### 4.4 已知坑

1. **Tool handler 内直接调用 `.to_dict()`** → 规避：tool handler 在 service 层之后，故可安全调用 `.to_dict()` 序列化返回结果
2. **TaskService 尚未实现** →规避：先检查 TaskService 是否存在，如不存在则 `create_task_tool` 内部直接执行 INSERT（多租户过滤），避免阻塞3. **验收时 copilot_service.py 可能有 lint 错误** →规避：每步完成后立即 `ruff check src/services/copilot_service.py` 自验证

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 TaskService 现有接口

检查 `src/services/task_service.py` 是否有 `insert_task` 或 `create_task` 方法。

**完成判定**：`grep -n "async def.*task" src/services/task_service.py` 有输出 /确认文件不存在需要内联 SQL### Step 2: 在 copilot_service.py 新增 send_email_tool

在 `CopilotService` 类中添加 `send_email_tool` 方法：

```python
async def send_email_tool(
    self,
    recipients: list[str],
    subject: str,
    body: str,
    ctx: AuthContext,
) -> dict:
    if not recipients:
        raise ValidationException("recipients cannot be empty")
    for r in recipients:
        if not isinstance(r, str) or "@" not in r:
            raise ValidationException(f"Invalid email address: {r}")
    # stub: call email_service if exists, else return dummy    return {"success": True, "recipients": recipients, "message_id": "stub"}
```

同时在 `tool_registry` dict 中注册：`"send_email": self.send_email_tool`

**完成判定**：`ruff check src/services/copilot_service.py` → 0 errors

### Step 3: 在 copilot_service.py 新增 create_task_tool

追加 `create_task_tool` 方法，利用 TaskService 或直接 INSERT：

```python
async def create_task_tool(
    self,
    title: str,
    description: str,
    assignee_id: int,
    tenant_id: int,
) -> dict:
    if not title or not title.strip():
        raise ValidationException("title cannot be empty")
    if assignee_id <= 0:
        raise ValidationException("assignee_id must be positive")
    # reuse TaskService if available    svc = TaskService(self.session)
    task = await svc.create_task(
        title=title.strip(),
        description=description,
        assignee_id=assignee_id,
        tenant_id=tenant_id,
    )
    return {"success": True, "task": task.to_dict()}
```

`tool_registry` 注册：`"create_task": self.create_task_tool`

**完成判定**：`ruff check src/services/copilot_service.py` →0 errors

### Step 4: 添加单元测试

在 `tests/unit/test_copilot_service.py` 中新增两个 fixture 和两个测试函数：

```python
@pytest.fixture
def copilot_service(mock_db_session):
    return CopilotService(mock_db_session)

@pytest.mark.parametrize("tool_name,input_dict", [
    ("send_email", {"recipients": ["a@b.com"], "subject": "Hi", "body": "Hello"}),
    ("create_task", {"title": "Do it", "description": "...", "assignee_id": 1}),
])
async def test_copilot_tool_valid(mock_db_session, tool_name, input_dict):
    svc = CopilotService(mock_db_session)
    # set up tenant via mock AuthContext if needed
    ...

async def test_send_email_tool_invalid_recipients(mock_db_session):
    svc = CopilotService(mock_db_session)
    with pytest.raises(ValidationException):
        await svc.send_email_tool(recipients=[], subject="s", body="b", ctx=mock_ctx)

async def test_create_task_tool_empty_title(mock_db_session):
    svc = CopilotService(mock_db_session)
    with pytest.raises(ValidationException):
        await svc.create_task_tool(title="   ", description="", assignee_id=1, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → 新增 4 passed（含 valid + invalid 各 2 个）

---

## 6. 验收

- [ ] `ruff check src/services/copilot_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_copilot_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_copilot_service.py -v` → 全 passed（含 send_email_tool + create_task_tool 各自 valid/invalid 共 4 个新用例）
- [ ] 确认 `tool_registry` 字典中包含 `"send_email"` 和 `"create_task"` 两个 key（`grep "send_email\|create_task" src/services/copilot_service.py` 有输出）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| TaskService 尚未实现，create_task_tool 需内联 SQL | 中 | 低 | 内联 INSERT tasks SQL（含 tenant_id 过滤），与 TaskService 完成后重构复用 |
| 邮件 infra stub 导致生产发送失败 | 低 | 中 | 运行时环境变量 AGENT_EMAIL_STUB=true 切换 stub/smtp模式 |
| 单元测试 mock覆盖不足 | 低 | 中 | 后续集成测试覆盖两端点 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/copilot_service.py tests/unit/test_copilot_service.py
git commit -m "feat(copilot): add send_email and create_task agent tools"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#508): add send_email and create_task agent tools" --body "Closes #508"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/task_service.py`](../../../src/services/task_service.py) — TaskService.insert_task 参考- 同类参考实现：[`src/services/copilot_service.py`](../../../src/services/copilot_service.py) — 现有 tool_registry结构和工具方法签名参考
- 父 issue /关联：#76, #507---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
