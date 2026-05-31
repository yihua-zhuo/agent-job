# Redis
redis_url: str = Field(
    default="redis://localhost:6379/0",
    description="Redis connection string for Celery broker/backend",
)
```

**完成判定**：`docker compose -f configs/docker-compose.test.yml up -d redis && docker compose -f configs/docker-compose.test.yml ps` 返回 `redis | running | healthy`

### Step 2: 新增 celery 依赖

操作：
- a) 在 `pyproject.toml` 的 `dependencies` 数组中新增一行：

```
 "celery[redis]>=5.3",
```

- b) 安装依赖：`cd /Users/yihuazhuo/Desktop/git/github/agent-job && pip install "celery[redis]>=5.3"`

**完成判定**：`python -c "import celery; print(celery.__version__)"` 输出版本号，且 `ruff check pyproject.toml` exit 0

### Step 3: 创建 src/tasks/config.py

创建 `src/tasks/config.py`，定义 queue names、default retry policy、Celery Beat schedule。

```python:1-25:src/tasks/config.py
"""Celery configuration — queue names, retry policy, beat schedule."""

from celery.schedules import crontab

# Queue names
QUEUE_DEFAULT = "default"
QUEUE_HIGH = "high"
QUEUE_LOW = "low"

# Per-task retry defaults (passed to @shared_task)
RETRY_CONFIG = dict(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)

# Celery Beat periodic schedule
BEAT_SCHEDULE = {
    "daily-digest": {
        "task": "src.tasks.notification_tasks.daily_digest_task",
        "schedule": crontab(hour=8, minute=0),  # 08:00 UTC = 16:00 CST        "options": {"queue": QUEUE_LOW},
    },
}
```

操作：
- a) `mkdir -p src/tasks`
- b)写入 `src/tasks/__init__.py`（可空，package marker）
- c) 写入 `src/tasks/config.py`

**完成判定**：`test -f src/tasks/config.py && ruff check src/tasks/config.py` exit 0

### Step 4: 创建 src/tasks/celery_app.py

创建 Celery app 实例，加载 `src.tasks.config` 中的 `BEAT_SCHEDULE`。

```python:1-10:src/tasks/celery_app.py
"""Celery app — broker + result backend via Redis."""
from celery import Celery
from celery.signals import worker_process_initfrom src.configs.settings import settings
from src.tasks.config import BEAT_SCHEDULE

celery_app = Celery("agent-job")

celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule=BEAT_SCHEDULE,
)
```

操作：
- a) 写入 `src/tasks/celery_app.py`

**完成判定**：`python -c "from src.tasks.celery_app import celery_app; print(celery_app.main)"` 输出 `agent-job`

### Step 5: 创建 src/tasks/notification_tasks.py

定义三个 task：`deliver_notification_task`（普通）、`urgent_notification_task`（高优）、`daily_digest_task`（定时批）。

```python:1-60:src/tasks/notification_tasks.py
"""Notification Celery tasks."""
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from db.connection import get_db_session
from services.notification_service import NotificationService
from src.tasks.config import QUEUE_HIGH, QUEUE_LOW, RETRY_CONFIG


@shared_task(**RETRY_CONFIG)
def deliver_notification_task(
    user_id: int,
    notification_type: str,
    title: str,
    content: str,
    tenant_id: int,
    related_type: str | None = None,
    related_id: int | None = None,
):
    """Wrap NotificationService.send_notification for async Celery execution."""
    async def _send():
        async for session in get_db_session():
            svc = NotificationService(session)
            return await svc.send_notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                content=content,
                tenant_id=tenant_id,
                related_type=related_type,
                related_id=related_id,
            )
    import asyncio
    return asyncio.run(_send())


@shared_task(bind=True, **RETRY_CONFIG)
def urgent_notification_task(self, user_id: int, notification_type: str, title: str, content: str, tenant_id: int):
    """High-priority notification: route to high-priority queue."""
    try:
        async def _send():
            async for session in get_db_session():
                svc = NotificationService(session)
                return await svc.send_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    content=content,
                    tenant_id=tenant_id,
                )
        import asyncio
        return asyncio.run(_send())
    except MaxRetriesExceededError:
        # log to sentry / dead-letter queue (deferred)
        return {"status": "failed", "retries_exhausted": True}


@shared_task(queue=QUEUE_LOW)
def daily_digest_task(batch_size: int = 100):
    """Batch-process low-priority notifications. Scheduled daily via Celery Beat."""
    # Future: query low-priority pending notifications, batch insert via session    return {"status": "batched", "count": 0}
```

操作：
- a) 写入 `src/tasks/notification_tasks.py`

**完成判定**：`python -c "from src.tasks.notification_tasks import deliver_notification_task, urgent_notification_task, daily_digest_task; print('ok')"` 输出 `ok`

### Step 6: 新增 POST /notifications/send-async endpoint

在 `src/api/routers/notifications.py` 新增 endpoint，将任务入队并立即返回 task_id。

操作：
- a) 在 `src/api/routers/notifications.py`顶部 import 部分追加：

```python
from src.tasks.notification_tasks import deliver_notification_task, urgent_notification_task
```

- b) 在 `PreferencesData` class 后（第 51 行附近）新增 request schema：

```python
class NotificationAsyncCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    notification_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    related_type: str | None = Field(None, max_length=50)
    related_id: int | None = Field(None, ge=1)
    urgent: bool = Field(False, description="If true, route to high-priority queue")
```

- c) 在 `send_notification` 函数后（第 116 行后）插入新 endpoint：

```python
@notifications_router.post(
    "/notifications/send-async",
    summary="Enqueue a notification for async delivery",
)
async def send_notification_async(
    body: NotificationAsyncCreate,
    current_user: AuthContext = Depends(require_auth),
):
    """Enqueue a notification task and return immediately with task_id."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")

    if body.urgent:
        task = urgent_notification_task.apply_async(
            kwargs=dict(
                user_id=body.user_id,
                notification_type=body.notification_type,
                title=body.title,
                content=body.content,
                tenant_id=current_user.tenant_id,
            )
        )
    else:
        task = deliver_notification_task.apply_async(
            kwargs=dict(
                user_id=body.user_id,
                notification_type=body.notification_type,
                title=body.title,
                content=body.content,
                tenant_id=current_user.tenant_id,
                related_type=body.related_type,
                related_id=body.related_id,
            )
        )
    return {
        "success": True,
        "data": {"task_id": task.id, "status": "queued"},
 "message": "通知已入队",
    }
```

**完成判定**：`ruff check src/api/routers/notifications.py` exit 0；endpoint 函数存在且被导出### Step 7: 编写单元测试 tests/unit/test_notification_tasks.py

操作：
- a) 创建 `tests/unit/test_notification_tasks.py`：

```python:1-70:tests/unit/test_notification_tasks.py
"""Unit tests for notification Celery tasks."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure PYTHONPATH=src for imports
import sys
sys.path.insert(0, "src")


class TestDeliverNotificationTask:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_notification_model(self, mock_session):
        class FakeNotification:
            id = 42
            tenant_id = 1
            user_id = 10
        return FakeNotification()

    @pytest.mark.asyncio
    async def test_deliver_notification_task_returns_notification_model(self, mock_session, mock_notification_model):
        with patch("src.tasks.notification_tasks.get_db_session") as mock_get_db:
            mock_svc = AsyncMock()
            mock_svc.send_notification.return_value = mock_notification_model
            async def fake_gen():
                yield mock_session
 mock_get_db.return_value = fake_gen()
            # import here to avoid top-level side-effects
            from src.tasks.notification_tasks import deliver_notification_task
            result = deliver_notification_task(
                user_id=10,
                notification_type="alert",
                title="Test",
                content="Test content",
                tenant_id=1,
            )
            assert result.id == 42


class TestUrgentNotificationTask:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_urgent_notification_task_calls_service(self, mock_session, mock_notification_model):
        with patch("src.tasks.notification_tasks.get_db_session") as mock_get_db:
            mock_svc = AsyncMock()
            mock_svc.send_notification.return_value = mock_notification_model
            async def fake_gen():
                yield mock_session
            mock_get_db.return_value = fake_gen()
            from src.tasks.notification_tasks import urgent_notification_task
            result = urgent_notification_task(
                user_id=10,
                notification_type="urgent",
                title="Urgent",
                content="Urgent content",
                tenant_id=1,
            )
            mock_svc.send_notification.assert_called_once()


class TestDailyDigestTask:
    def test_daily_digest_task_returns_empty_batch(self):
        from src.tasks.notification_tasks import daily_digest_task
        result = daily_digest_task(batch_size=50)
        assert result["status"] == "batched"
        assert result["count"] == 0
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_tasks.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/tasks/ src/api/routers/notifications.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/tasks/` →0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_tasks.py -v` → ≥ 3 passed
- [ ] `docker compose -f configs/docker-compose.test.yml up -d redis && docker compose -f configs/docker-compose.test.yml ps redis` → `healthy`
- [ ] `curl -X POST http://localhost:8000/api/v1/notifications/send-async -H "Content-Type: application/json" -d '{"user_id":1,"notification_type":"test","title":"hi","content":"hello"}'` → `{"success":true,"data":{"status":"queued","task_id":"..."}}`
- [ ] `python -c "from src.tasks.notification_tasks import deliver_notification_task, urgent_notification_task, daily_digest_task; print('import ok')"` → `import ok`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Redis启动失败或 `REDIS_URL` 配置错误导致 Celery 无法连接 broker | 中 | 高 | 回退：Celery tasks改为同步调用（移除 async endpoint）；业务不受影响，只是无异步保障 |
| `daily_digest_task` 在 Beat调度前 worker 未就绪导致定时任务错过一周期 | 低 | 中 | 下一周期自动触发；任务内不做 critical 操作；不影响其他功能 |
| task 内新建 AsyncSession 与 FastAPI 主 session池产生连接数竞争 | 低 | 中 | `settings.database_pool_size` 已在 .env 设为 5；生产部署时调高连接池上限 |
| `deliver_notification_task` 的 `asyncio.run()` 在 Celery worker fork 后主线程已退出的情况下卡住 | 低 | 高 | 改用 `celery.contrib.abortable` +显式 `run_in_executor`；验证 worker启动日志无卡阻 |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/tasks/ src/api/routers/notifications.py src/configs/settings.py pyproject.toml .env configs/docker-compose.test.yml tests/unit/test_notification_tasks.py
git commit -m "feat(automation): add Celery background queue with retry, priority routing and /send-async endpoint"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#650): add Celery background queue with retry and priority" --body "Closes #650"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待补充：参考其他 service 层 task集成模式（本仓库目前无 Celery 用例，属全新实现）
- 第三方文档：[Celery Documentation](https://docs.celeryq.dev/en/stable/)
- 父 issue /关联：#39, #649

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
