# Analytics · Replace mock churn rules with real sklearn ML model

| 元数据 | 值 |
|---|---|
| Issue | #75 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 3-5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 90-frontend |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `churn_prediction.py` 使用 hash-based mock 规则模拟，结果非真实预测，无法用于生产环境。销售团队反馈 mock 分数缺乏可信度，无法驱动客户挽留行动。真实 ML 模型可量化流失概率、输出可解释风险因素，直接支撑客户成功团队的运营决策。

### 1.2 做完后

- **用户视角**：客户详情页显示真实流失风险等级（🔴 高 / 🟡 中 / 🟢 低）及其成因因子；支持定时批量预测任务，自动刷新全量客户风险评分。
- **开发者视角**：新增 `src/ml/churn/` 模块（model + train），`ChurnPredictionService` 加载真实 `joblib` 模型并返回结构化预测结果；新增 `/api/v1/churn/` REST 端点；`customer_churn_scores` 表持久化每次预测记录（含 model_version）。

### 1.3 不做什么（剔除）

- [ ] 前端 UI 集成（流失风险徽章、因子图表、行动推荐按钮）— 归入 90-frontend 板块
- [ ] S3 模型存储 — 第一期仅使用本地 `models/` 目录；S3 集成在后续独立 issue
- [ ] A/B testing framework for model comparison — 模型版本管理（v1/v2）为基础，A/B 框架在独立 issue
- [ ] 实时流式特征计算（Kafka / CDC）— 训练数据来源限定为 customers + activities 批查

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → ≥ 8 passed
- `PYTHONPATH=src pytest tests/unit/test_churn_ml.py -v` → ≥ 5 passed
- `ruff check src/ml/churn/ src/services/churn_prediction.py` → 0 errors
- `ruff check src/api/routers/churn.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `GET /api/v1/churn/predict/{customer_id}` → HTTP 200，body 含 `score`、`risk_level`、`factors`
- `POST /api/v1/churn/batch_predict` → HTTP 200，body 含分页 items
- `GET /api/v1/churn/high_risk` → HTTP 200，items 非空时 risk_level 均为 high

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/churn_prediction.py` — 需确认当前 mock 实现入口文件路径及关键方法签名（L 行号待查）

TBD - 待验证：`src/db/models/` 中是否存在 `customer_churn_scores` 表定义（L 行号待查）

TBD - 待验证：`src/db/models/` 中 `customers` 表 schema（含 `tenant_id`、`created_at`、`status` 字段，L 行号待查）

TBD - 待验证：`src/db/models/` 中 `activities` 表 schema（含 `tenant_id`、`customer_id`、`created_at`、`type` 字段，L 行号待查）

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/churn_prediction.py` — mock 规则替换为真实模型调用
  - TBD - 待验证：`src/api/routers/` — 新增或扩展 churn router（需确认现有 router 名称）
  - TBD - 待验证：`tests/unit/test_churn_prediction.py` — 覆盖重构后的 service 逻辑
- 要建：
  - `src/ml/churn/model.py` — sklearn RandomForest/XGBoost 模型类，特征工程逻辑
  - `src/ml/churn/train.py` — 训练脚本：数据提取 → 特征工程 → 训练 → 评估 → 持久化
  - `src/ml/churn/features.py` — 特征工程工具函数（days_since_last_activity、activity_trend 等）
  - `src/db/models/customer_churn_score.py` — ORM model for customer_churn_scores 表
  - `alembic/versions/<id>_create_customer_churn_scores.py` — 创建表及索引
  - `src/services/churn_prediction.py` — 若现有文件不存在则新建
  - `src/api/routers/churn.py` — 若现有 router 不存在则新建
  - `tests/unit/test_churn_ml.py` — 特征工程 + 模型加载单元测试
  - `tests/unit/test_churn_prediction_service.py` — service 层单元测试
  - `tests/integration/test_churn_integration.py` — 端到端集成测试
  - `models/` 目录（存放 churn_v1.joblib 模型文件）

### 2.3 缺什么

- [ ] 真实 sklearn ML 模型（RandomForest 或 XGBoost）替代 hash mock 规则
- [ ] 特征工程函数：从 customers + activities 表计算流失相关特征
- [ ] 模型训练 pipeline（含 AUC-ROC、Precision@Recall、Feature Importance 评估）
- [ ] 模型版本化管理（joblib 文件 + model_version 字段）
- [ ] `customer_churn_scores` 持久化表（score、risk_level、factors_json、model_version、predicted_at）
- [ ] REST API 端点：实时预测 / 批量预测 / 高风险列表
- [ ] 单元测试覆盖特征工程、模型推理、service 层逻辑

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/ml/churn/model.py` | ChurnModel 类：特征预处理、模型加载、推理、特征重要性输出 |
| `src/ml/churn/features.py` | 特征工程函数：build_features(customer_id, tenant_id, session) |
| `src/ml/churn/train.py` | 训练脚本：数据提取→特征工程→训练→评估→持久化为 joblib |
| `src/ml/churn/score_store.py` | 模型版本管理：记录每次训练的 metrics + 文件路径 |
| `src/db/models/customer_churn_score.py` | CustomerChurnScore ORM model，含 score、risk_level、factors_json、model_version |
| `alembic/versions/<id>_create_customer_churn_scores.py` | 创建 customer_churn_scores 表，含 tenant_id 索引 |
| `tests/unit/test_churn_ml.py` | 特征工程函数 + 模型推理单元测试 |
| `tests/unit/test_churn_prediction_service.py` | ChurnPredictionService 单元测试 |
| `tests/integration/test_churn_integration.py` | 端到端集成测试（真实 DB） |
| `models/churn_v1.joblib` | 训练产出的模型文件（gitignore） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/churn_prediction.py` | 重构 __init__：注入 session + model_path；新增 predict(customer_id, tenant_id)、batch_predict(tenant_id, page, page_size)、get_high_risk(tenant_id) 方法 |
| `src/api/routers/churn.py` | 新建 router：GET /predict/{customer_id}、POST /batch_predict、GET /high_risk；依赖 require_auth |
| `src/main.py` | 注册 /api/v1/churn router（若 router 为新建） |

### 3.3 新增能力

- **Service method**：`ChurnPredictionService.predict(self, customer_id: int, tenant_id: int) -> CustomerChurnScore`
- **Service method**：`ChurnPredictionService.batch_predict(self, tenant_id: int, page: int, page_size: int) -> tuple[list[CustomerChurnScore], int]`
- **Service method**：`ChurnPredictionService.get_high_risk(self, tenant_id: int, threshold: float = 70.0) -> list[CustomerChurnScore]`
- **API endpoint**：`GET /api/v1/churn/predict/{customer_id}` → `{"success": true, "data": {"score": 78.5, "risk_level": "high", "factors": [...], "model_version": "v1"}}`
- **API endpoint**：`POST /api/v1/churn/batch_predict` → `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20}}`
- **API endpoint**：`GET /api/v1/churn/high_risk?threshold=70` → `{"success": true, "data": {"items": [...], "total": N}}`
- **ORM model**：`CustomerChurnScore` in `src/db/models/customer_churn_score.py`
- **ML Module**：`ChurnModel` in `src/ml/churn/model.py`，`build_features` in `src/ml/churn/features.py`
- **Migration**：`alembic upgrade head` 创建 `customer_churn_scores` 表（含 `tenant_id` 索引、`customer_id` 唯一索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 RandomForest 不选 XGBoost**：CRM 场景下 RandomForest 调参简单、Feature Importance 内置、无需 GPU，且 baseline 够用；XGBoost 作为 v2 可选项
- **选 joblib 不选 pickle**：joblib 对 sklearn 对象序列化更稳定，支持大 numpy 数组压缩
- **选本地 models/ 不选 S3**：第一期避免引入 S3 依赖；S3 集成通过配置切换 model_path 支持
- **流失标签定义：90天无活动 OR 已删除账号**：参考行业标准（Recency/Frequency/Monetary），90天窗口可覆盖大多数慢速流失场景

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `scikit-learn` | `>=1.4,<2.0` | 最新稳定版，RandomForest + cross_val_score API 稳定 |
| `pandas` | `>=2.0,<3.0` | 特征工程使用 pd.DataFrame.groupby；2.0 以上 pyarrow 引擎加速 |
| `joblib` | `>=1.3,<2.0` | sklearn 配套，模型持久化标准方式 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- `ChurnPredictionService.__init__` 接受 `session: AsyncSession`（无默认值），`model_path: str`（可选，默认 `models/churn_v1.joblib`）
- `customer_churn_scores.score` 存储 0-100 浮点数；`factors_json` 存储 JSON 字符串（factors list）
- 模型文件 `models/` 目录加入 `.gitignore`；CI 环境中通过训练 step 生成或挂载

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ `CustomerChurnScore` 表使用 `factors_json` 作为列名，不使用 `metadata`
2. **Alembic autogenerate 会把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 手动在 migration 中改回 `sa.JSONB()` 和 `DateTime(timezone=True)`；在 `downgrade()` 中也要确认 drop table 顺序
3. **PYTHONPATH=src**，import 写 `from db.models.customer_churn_score import CustomerChurnScore`，不写 `from src.db.models...`
4. **Async session 注入**：router 中使用 `session: AsyncSession = Depends(get_db)`，service 构造时直接赋值；不使用 `async with get_db() as session:`
5. **batch_predict 大表性能**：activities 表大时 `build_features` 需分批查询（`yield_per=500`），避免内存爆炸

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 DB model + migration

新建 `src/db/models/customer_churn_score.py`，定义 `CustomerChurnScore` ORM model：

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CustomerChurnScore(Base):
    __tablename__ = "customer_churn_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    factors_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_customer_churn_scores_tenant_customer", "tenant_id", "customer_id", unique=True),
    )
```

操作：
- a) 创建 `src/db/models/customer_churn_score.py` 写入上述 model
- b) 在 `src/db/models/__init__.py` 新增 `from .customer_churn_score import CustomerChurnScore`
- c) 启动 test-db：`docker compose -f configs/docker-compose.test.yml up -d test-db`
- d) 创建 alembic_dev DB：
  `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
  `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- e) 运行 `alembic upgrade head` 确保连接正常
- f) 生成 migration：`alembic revision --autogenerate -m "create customer_churn_scores"`
- g) 手动检查生成的 migration 文件：将 `sa.JSON()` 改为 `sa.JSONB().astext` 对应 Text 列（若 factors_json 用 Text），确认 `DateTime(timezone=True)` 有 timezone flag
- h) 验证 migrate + rollback + migrate 三次 exit 0

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 2: 创建 ML 模块（model + features）

创建 `src/ml/churn/features.py`，实现特征工程函数：

```python
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Customer, Activity


async def build_features(session: AsyncSession, customer_id: int, tenant_id: int) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=90)

    act_result = await session.execute(
        select(
            func.count(Activity.id).label("total_activities"),
            func.min(Activity.created_at).label("last_activity"),
        )
        .where(Activity.customer_id == customer_id)
        .where(Activity.tenant_id == tenant_id)
    )
    row = act_result.one()
    last_activity = row.last_activity or datetime.utcnow()
    days_since_last = (datetime.utcnow() - last_activity).days

    return {
        "days_since_last_activity": days_since_last,
        "activity_trend": 0.0,  # v2: compute rolling 30d vs 60d
        "revenue_trend": 0.0,    # v2: from payments table
        "support_tickets_count": 0,  # v2: count tickets
        "payment_delays_count": 0,    # v2: from payments table
        "is_churned_label": 1 if days_since_last > 90 else 0,
    }
```

创建 `src/ml/churn/model.py`：

```python
import joblib
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from sklearn.ensemble import RandomForestClassifier


@dataclass
class ChurnPrediction:
    score: float          # 0-100
    risk_level: str       # high / medium / low
    factors: list[dict]  # [{"name": "...", "value": ..., "importance": ...}]
    model_version: str


class ChurnModel:
    RISK_THRESHOLDS = {"high": 70.0, "medium": 40.0}

    def __init__(self, model_path: str):
        self.model = joblib.load(model_path)
        self.version = Path(model_path).stem  # e.g. "churn_v1"

    def predict_proba(self, features: dict) -> ChurnPrediction:
        X = self._dict_to_array(features)
        proba = self.model.predict_proba(X)[0]
        churn_prob = float(proba[1]) * 100

        risk_level = "low"
        if churn_prob >= self.RISK_THRESHOLDS["high"]:
            risk_level = "high"
        elif churn_prob >= self.RISK_THRESHOLDS["medium"]:
            risk_level = "medium"

        factors = self._build_factors(features, proba)
        return ChurnPrediction(score=round(churn_prob, 1), risk_level=risk_level, factors=factors, model_version=self.version)

    def _dict_to_array(self, features: dict) -> np.ndarray:
        keys = ["days_since_last_activity", "activity_trend", "revenue_trend", "support_tickets_count", "payment_delays_count"]
        return np.array([[features.get(k, 0.0) for k in keys]])

    def _build_factors(self, features: dict, proba: np.ndarray) -> list[dict]:
        importances = self.model.feature_importances_
        keys = ["days_since_last_activity", "activity_trend", "revenue_trend", "support_tickets_count", "payment_delays_count"]
        return [
            {"name": k, "value": features.get(k, 0.0), "importance": float(importances[i])}
            for i, k in enumerate(keys)
        ]
```

创建 `src/ml/churn/score_store.py` 管理模型版本记录：

```python
from pathlib import Path


DEFAULT_MODEL_DIR = Path("models")


def get_latest_model_path() -> str:
    candidates = sorted(DEFAULT_MODEL_DIR.glob("churn_v*.joblib"), reverse=True)
    if not candidates:
        raise FileNotFoundError("No churn model found in models/")
    return str(candidates[0])
```

**完成判定**：`ruff check src/ml/churn/` → 0 errors；`python -c "from src.ml.churn.model import ChurnModel; print('import ok')"` exit 0

---

### Step 3: 创建训练脚本

创建 `src/ml/churn/train.py`：

```python
import json
import joblib
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sqlalchemy import select, func

from db.connection import async_session_maker
from db.models import Customer, Activity
from src.ml.churn.features import build_features


async def extract_training_data() -> pd.DataFrame:
    records = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(Customer.id, Customer.tenant_id, Customer.status)
        )
        customers = result.all()
        for cid, tid, status in customers:
            f = await build_features(session, cid, tid)
            f["customer_id"] = cid
            f["tenant_id"] = tid
            f["account_status_deleted"] = int(status == "deleted")
            records.append(f)
    return pd.DataFrame(records)


def train(df: pd.DataFrame) -> RandomForestClassifier:
    feature_cols = ["days_since_last_activity", "activity_trend", "revenue_trend",
                    "support_tickets_count", "payment_delays_count"]
    label_col = "is_churned_label"
    df["is_churned_label"] = df["is_churned_label"] | df["account_status_deleted"]

    X = df[feature_cols].fillna(0)
    y = df[label_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    scores = cross_val_score(model, X, y, cv=5, scoring="roc_auc")
    print(f"AUC-ROC: {scores.mean():.3f} ± {scores.std():.3f}")

    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    print(f"Train acc: {train_score:.3f}, Test acc: {test_score:.3f}")

    fi = dict(zip(feature_cols, model.feature_importances_.round(4)))
    print(f"Feature Importance: {json.dumps(fi, indent=2)}")

    return model


if __name__ == "__main__":
    asyncio.run(extract_training_data()).pipe(train)
```

操作：
- a) 创建 `src/ml/churn/train.py` 写入训练脚本
- b) 安装依赖：`pip install scikit-learn pandas joblib`
- c) 运行训练：`PYTHONPATH=src python src/ml/churn/train.py`
- d) 确认输出 AUC-ROC 数值及 Feature Importance
- e) 模型保存至 `models/churn_v1.joblib`（`models/` 目录需已存在或手动创建）
- f) 将 `models/` 加入 `.gitignore`

**完成判定**：`models/churn_v1.joblib` 存在且大小 > 100KB；`python -c "import joblib; m=joblib.load('models/churn_v1.joblib'); print(m.n_features_in_)"` 输出 5

---

### Step 4: 重构 ChurnPredictionService

重构 `src/services/churn_prediction.py`（若不存在则新建）：

```python
import json
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from db.models.customer_churn_score import CustomerChurnScore
from db.models.customer import Customer
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from src.ml.churn.model import ChurnModel, ChurnPrediction
from src.ml.churn.features import build_features


class ChurnPredictionService:
    def __init__(self, session: AsyncSession, model_path: str = "models/churn_v1.joblib"):
        self.session = session
        self.model = ChurnModel(model_path)

    async def predict(self, customer_id: int, tenant_id: int) -> CustomerChurnScore:
        customer = await self.session.get(Customer, customer_id)
        if customer is None or customer.tenant_id != tenant_id:
            raise NotFoundException("Customer")

        features = await build_features(self.session, customer_id, tenant_id)
        pred: ChurnPrediction = self.model.predict_proba(features)

        record = CustomerChurnScore(
            customer_id=customer_id,
            tenant_id=tenant_id,
            score=pred.score,
            risk_level=pred.risk_level,
            factors_json=json.dumps(pred.factors),
            model_version=pred.model_version,
            predicted_at=datetime.utcnow(),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def batch_predict(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[CustomerChurnScore], int]:
        result = await self.session.execute(
            select(CustomerChurnScore)
            .where(CustomerChurnScore.tenant_id == tenant_id)
            .order_by(CustomerChurnScore.score.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_result = await self.session.execute(
            select(func.count(CustomerChurnScore.id))
            .where(CustomerChurnScore.tenant_id == tenant_id)
        )
        total = count_result.scalar() or 0
        return list(result.scalars().all()), total

    async def get_high_risk(self, tenant_id: int, threshold: float = 70.0) -> list[CustomerChurnScore]:
        result = await self.session.execute(
            select(CustomerChurnScore)
            .where(CustomerChurnScore.tenant_id == tenant_id)
            .where(CustomerChurnScore.score >= threshold)
            .order_by(CustomerChurnScore.score.desc())
        )
        return list(result.scalars().all())
```

操作：
- a) 创建或覆写 `src/services/churn_prediction.py` 写入上述 service
- b) 在 `src/services/__init__.py` 新增 export（若已存在 churn 相关 export）

**完成判定**：`ruff check src/services/churn_prediction.py` → 0 errors；`python -c "from src.services.churn_prediction import ChurnPredictionService; print('import ok')"` exit 0

---

### Step 5: 新建 churn API router

创建 `src/api/routers/churn.py`：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from dependencies.fastapi_auth import AuthContext, require_auth
from services.churn_prediction import ChurnPredictionService

router = APIRouter(prefix="/api/v1/churn", tags=["Churn"])


@router.get("/predict/{customer_id}")
async def predict_churn(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    record = await svc.predict(customer_id, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {
            "score": float(record.score),
            "risk_level": record.risk_level,
            "factors": __parse_factors(record.factors_json),
            "model_version": record.model_version,
            "predicted_at": record.predicted_at.isoformat(),
        },
    }


@router.post("/batch_predict")
async def batch_predict(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    items, total = await svc.batch_predict(tenant_id=ctx.tenant_id, page=page, page_size=page_size)
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "customer_id": r.customer_id,
                    "score": float(r.score),
                    "risk_level": r.risk_level,
                    "factors": __parse_factors(r.factors_json),
                    "predicted_at": r.predicted_at.isoformat(),
                }
                for r in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/high_risk")
async def high_risk(
    threshold: float = Query(70.0, ge=0, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    records = await svc.get_high_risk(tenant_id=ctx.tenant_id, threshold=threshold)
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "customer_id": r.customer_id,
                    "score": float(r.score),
                    "risk_level": r.risk_level,
                    "factors": __parse_factors(r.factors_json),
                }
                for r in records
            ],
            "total": len(records),
        },
    }


def __parse_factors(factors_json: str | None) -> list[dict]:
    if not factors_json:
        return []
    import json
    return json.loads(factors_json)
```

操作：
- a) 创建 `src/api/routers/churn.py` 写入上述 router
- b) 在 `src/api/routers/__init__.py` 新增 `from .churn import router as churn_router`
- c) 在 `src/main.py` 注册 router：找到 `include_router` 调用处，新增 `include_router(churn_router)`

**完成判定**：`ruff check src/api/routers/churn.py` → 0 errors；`python -c "from src.api.routers.churn import router; print('router ok')"` exit 0

---

### Step 6: 单元测试

创建 `tests/unit/test_churn_ml.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
import numpy as np

from src.ml.churn.model import ChurnModel, ChurnPrediction
from src.ml.churn.features import build_features


class MockChurnModel(ChurnModel):
    def __init__(self):
        self._mock_model = MagicMock()
        self._mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        self._mock_model.feature_importances_ = np.array([0.4, 0.1, 0.1, 0.2, 0.2])
        self.version = "churn_v1"


@pytest.fixture
def mock_session():
    return AsyncMock()


def test_churn_model_predict_high_risk(mock_session):
    model = MockChurnModel()
    features = {
        "days_since_last_activity": 100,
        "activity_trend": -0.2,
        "revenue_trend": -0.1,
        "support_tickets_count": 5,
        "payment_delays_count": 3,
    }
    pred = model.predict_proba(features)
    assert isinstance(pred, ChurnPrediction)
    assert pred.score == 70.0
    assert pred.risk_level == "high"
    assert len(pred.factors) == 5
    assert pred.model_version == "churn_v1"


def test_churn_model_predict_low_risk(mock_session):
    model = MockChurnModel()
    model._mock_model.predict_proba.return_value = np.array([[0.95, 0.05]])
    features = {"days_since_last_activity": 5, "activity_trend": 0.1, "revenue_trend": 0.05, "support_tickets_count": 0, "payment_delays_count": 0}
    pred = model.predict_proba(features)
    assert pred.score == 5.0
    assert pred.risk_level == "low"


@pytest.mark.asyncio
async def test_build_features_returns_dict(mock_session):
    features = await build_features(mock_session, customer_id=1, tenant_id=1)
    assert isinstance(features, dict)
    assert "days_since_last_activity" in features
    assert "is_churned_label" in features
```

创建 `tests/unit/test_churn_prediction_service.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.churn_prediction import ChurnPredictionService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_predict_returns_record(mock_session):
    mock_customer = MagicMock()
    mock_customer.tenant_id = 1
    with patch("src.services.churn_prediction.ChurnModel") as MockModel:
        MockModel.return_value.predict_proba.return_value = MagicMock(
            score=75.0, risk_level="high", factors=[], model_version="churn_v1"
        )
        svc = ChurnPredictionService(mock_session, "models/churn_v1.joblib")
        svc.session.get = AsyncMock(return_value=mock_customer)
        record = await svc.predict(customer_id=1, tenant_id=1)
        assert record.score == 75.0
        assert record.risk_level == "high"
        mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_predict_raises_not_found(mock_session):
    with patch("src.services.churn_prediction.ChurnModel"):
        svc = ChurnPredictionService(mock_session)
        svc.session.get = AsyncMock(return_value=None)
        with pytest.raises(Exception):
            await svc.predict(customer_id=999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_ml.py tests/unit/test_churn_prediction_service.py -v` → ≥ 13 passed

---

### Step 7: 集成测试

创建 `tests/integration/test_churn_integration.py`：

```python
import pytest
from src.services.churn_prediction import ChurnPredictionService
from tests.integration.conftest import _seed_customer


@pytest.mark.integration
class TestChurnIntegration:
    async def test_predict_stores_record(self, db_schema, tenant_id, async_session):
        customer = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session, "models/churn_v1.joblib")
        record = await svc.predict(customer.id, tenant_id=tenant_id)
        assert record.customer_id == customer.id
        assert 0 <= record.score <= 100
        assert record.risk_level in ("high", "medium", "low")

    async def test_batch_predict_returns_paginated(self, db_schema, tenant_id, async_session):
        c1 = await _seed_customer(async_session, tenant_id)
        c2 = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session, "models/churn_v1.joblib")
        await svc.predict(c1.id, tenant_id=tenant_id)
        await svc.predict(c2.id, tenant_id=tenant_id)
        items, total = await svc.batch_predict(tenant_id=tenant_id, page=1, page_size=10)
        assert len(items) == 2
        assert total == 2

    async def test_high_risk_filter(self, db_schema, tenant_id, async_session):
        c1 = await _seed_customer(async_session, tenant_id)
        svc = ChurnPredictionService(async_session, "models/churn_v1.joblib")
        await svc.predict(c1.id, tenant_id=tenant_id)
        records = await svc.get_high_risk(tenant_id=tenant_id, threshold=0.0)
        assert all(r.score >= 0.0 for r in records)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/ml/churn/` → 0 errors
- [ ] `ruff check src/services/churn_prediction.py` → 0 errors
- [ ] `ruff check src/api/routers/churn.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_ml.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_churn_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `GET http://localhost:8000/api/v1/churn/predict/{customer_id}` → HTTP 200，body 含 `score`、`risk_level`、`factors`、`model_version`
- [ ] `POST http://localhost:8000/api/v1/churn/batch_predict?page=1&page_size=20` → HTTP 200，含分页 items
- [ ] `GET http://localhost:8000/api/v1/churn/high_risk?threshold=70` → HTTP 200，含 items

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 模型文件缺失（`models/churn_v1.joblib` 不存在）导致 service 启动失败 | 低 | 高 | `ChurnPredictionService.__init__` 捕获 `FileNotFoundError` 并写 warning log；同时 `predict` 方法在模型加载失败时回退到返回默认 risk_level="unknown" |
| activities 表数据不足导致训练 AUC-ROC < 0.6（模型无效） | 中 | 中 | 先完成 service/router/migration 的工程部分；ML 部分可先用 RandomForest 默认参数训练 v1，后续独立 issue 优化特征工程 |
| 特征工程 SQL 性能差（activities 表大表 JOIN 慢） | 中 | 中 | 添加 `yield_per=500` 流式查询 + DB 索引（`IX_activities_customer_id_tenant_id`）；batch_predict 走已有 `customer_churn_scores` 表，不重复计算特征 |
| Alembic migration 和 ORM model 列类型不一致导致 INSERT 报错 | 低 | 高 | migration 生成后人工对照 model 检查 JSONB / TIMESTAMPTZ 类型；integration test 覆盖 INSERT + SELECT 全流程 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/ml/churn/ src/services/churn_prediction.py src/api/routers/churn.py \
        src/db/models/customer_churn_score.py alembic/versions/ \
        tests/unit/test_churn_ml.py tests/unit/test_churn_prediction_service.py \
        tests/integration/test_churn_integration.py models/.gitignore
git commit -m "feat(churn): replace mock rules with sklearn RandomForest ML model

- Add ChurnModel + feature engineering in src/ml/churn/
- Add CustomerChurnScore ORM model + migration
- Add ChurnPredictionService (predict / batch_predict / get_high_risk)
- Add /api/v1/churn REST endpoints
- Add unit + integration tests

Closes #75"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(churn): real ML model for churn prediction" --body "## Summary
- Replace hash-based mock rules with sklearn RandomForest model
- New ML module: src/ml/churn/{model,features,train}.py
- New DB table: customer_churn_scores (score, risk_level, factors_json, model_version)
- New endpoints: GET /predict/{id}, POST /batch_predict, GET /high_risk
- All unit + integration tests pass

## Test plan
- [x] ruff check src/ml/churn/ src/services/churn_prediction.py src/api/routers/churn.py
- [x] pytest tests/unit/test_churn_ml.py tests/unit/test_churn_prediction_service.py
- [x] pytest tests/integration/test_churn_integration.py
- [x] alembic upgrade head && alembic downgrade -1 && alembic upgrade head

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/opportunity_*.py` 或 `src/services/analytics_*.py` — 参考 service 层结构及 ORM 返回模式
- 第三方文档：[scikit-learn RandomForestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html)
- 第三方文档：[joblib model persistence](https://joblib.readthedocs.io/en/stable/persistence.html)
- 父 issue / 关联：#75

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
