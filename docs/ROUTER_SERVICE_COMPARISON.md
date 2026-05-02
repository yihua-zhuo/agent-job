# Router vs Service 对比分析报告

**项目：** agent-job (develop branch)  
**分析时间：** 2026-05-02  
**目标：** 找出未实现的 Router 和 Service，制定开发计划

---

## ✅ 已完成对照

### Activities 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_activity | create_activity | ✅ |
| get_activity | get_activity | ✅ |
| update_activity | update_activity | ✅ |
| delete_activity | delete_activity | ✅ |
| list_activities | list_activities | ✅ |
| get_customer_activities | get_customer_activities | ✅ |
| get_opportunity_activities | get_opportunity_activities | ✅ |
| search_activities | search_activities | ✅ |
| get_activity_summary | get_activity_summary | ✅ |

### Customers 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_customer | create_customer | ✅ |
| list_customers | list_customers | ✅ |
| search_customers | search_customers | ✅ |
| get_customer | get_customer | ✅ |
| update_customer | update_customer | ✅ |
| delete_customer | delete_customer | ✅ |
| add_tag | add_tag | ✅ |
| remove_tag | remove_tag | ✅ |
| change_status | change_status | ✅ |
| assign_owner | assign_owner | ✅ |
| bulk_import | bulk_import | ✅ |

### Sales (Pipeline + Opportunity) 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_pipeline | create_pipeline | ✅ |
| list_pipelines | list_pipelines | ✅ |
| get_pipeline | get_pipeline | ✅ |
| get_pipeline_stats | get_pipeline_stats | ✅ |
| get_pipeline_funnel | get_pipeline_funnel | ✅ |
| create_opportunity | create_opportunity | ✅ |
| list_opportunities | list_opportunities | ✅ |
| get_opportunity | get_opportunity | ✅ |
| update_opportunity | update_opportunity | ✅ |
| change_stage | change_stage | ✅ |
| get_forecast | get_forecast | ✅ |

### Tenants 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_tenant | create_tenant | ✅ |
| get_tenant | get_tenant | ✅ |
| list_tenants | list_tenants | ✅ |
| update_tenant | update_tenant | ✅ |
| delete_tenant | delete_tenant | ✅ |
| get_tenant_stats | get_tenant_stats | ✅ |
| get_tenant_usage | get_tenant_usage | ✅ |

### Tickets 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_ticket | create_ticket | ✅ |
| list_tickets | list_tickets | ✅ |
| get_ticket | get_ticket | ✅ |
| update_ticket | update_ticket | ✅ |
| assign_ticket | assign_ticket | ✅ |
| add_reply | add_reply | ✅ |
| change_ticket_status | change_status | ✅ |
| get_customer_tickets | get_customer_tickets | ✅ |
| get_sla_breaches | get_sla_breaches | ✅ |
| auto_assign_ticket | auto_assign | ✅ |
| check_sla_status | (SLA内部) | ✅ |
| get_sla_breach_tickets | get_sla_breaches | ✅ |

### Users 模块
| Router | Service | 状态 |
|--------|---------|------|
| create_user | create_user | ✅ |
| list_users | list_users | ✅ |
| get_user | get_user_by_id | ✅ |
| update_user | update_user | ✅ |
| delete_user | delete_user | ✅ |
| search_users | search_users | ✅ |
| change_password | change_password | ✅ |
| register | create_user | ✅ |
| login | (AuthService) | ✅ |

---

## ⚠️ 缺失功能分析

### 1. 缺少独立 Auth Router

**现状：**
- `src/services/auth_service.py` 存在，实现完整
- `src/dependencies/auth.py` 存在，提供 JWT 认证依赖
- `main.py` 已注册所有 router

**缺失：**
- 没有 `src/api/routers/auth.py`
- `/login` 和 `/register` 端点在 `users_router` 里
- 没有独立的认证 API 前缀（如 `/api/auth/login`）

**建议：** 如果需要独立的认证端点，创建 `auth.py` router；否则保持现状。

---

### 2. Service 层骨架服务（未实现业务逻辑）

以下服务存在但功能为占位符（mock/stub）：

| Service | 状态 | 说明 |
|---------|------|------|
| `analytics_service.py` | ⚠️ 部分实现 | 有方法签名但可能依赖未实现的底层服务 |
| `automation_rules.py` | ❌ 占位符 | 只有 `get_available_rules` 和 `apply_rule` 模板 |
| `churn_prediction.py` | ❌ Mock | 使用模拟数据，无真实预测逻辑 |
| `import_export_service.py` | ⚠️ 部分实现 | 有方法但需要数据库模型支持 |
| `marketing_service.py` | ⚠️ 部分实现 | Campaign/Lead 相关方法存在 |
| `notification_service.py` | ⚠️ 部分实现 | Notification 相关方法存在 |
| `rbac_service.py` | ❌ 占位符 | Permission Enum + 模板方法 |
| `report_service.py` | ❌ 占位符 | 模板方法，无实现 |
| `sales_recommendation.py` | ❌ Mock | 使用模拟数据 |
| `smart_categorization.py` | ❌ Mock | 使用规则判断，非 ML |
| `task_service.py` | ⚠️ 部分实现 | Task 相关方法存在 |
| `trigger_service.py` | ❌ 占位符 | 模板方法 |
| `workflow_service.py` | ⚠️ 部分实现 | Workflow 相关方法存在 |

---

## 📋 开发计划

### Phase 1: 核心功能完善（高优先级）

#### 1.1 补充缺失的 Router 端点
```
src/api/routers/
  ├── auth.py          # 新建：独立认证路由（可选）
  └── webhook.py       # 新建：Webhook 处理（GitHub CI/CD 集成）
```

#### 1.2 完善 Service 业务逻辑
```
src/services/
  ├── analytics_service.py     # 补充真实报表逻辑
  ├── automation_rules.py       # 实现规则引擎
  ├── import_export_service.py # 实现 CSV/Excel 导入导出
  ├── marketing_service.py      # 实现 Campaign 管理
  └── task_service.py          # 实现任务管理
```

### Phase 2: 高级功能（中优先级）

#### 2.1 AI/ML 功能
```
src/services/
  ├── churn_prediction.py      # 实现流失预测模型
  ├── sales_recommendation.py  # 实现销售推荐算法
  ├── smart_categorization.py  # 升级分类逻辑（可引入 ML）
  └── trigger_service.py       # 实现自动化触发器
```

#### 2.2 权限与工作流
```
src/services/
  ├── rbac_service.py         # 实现 RBAC 权限系统
  └── workflow_service.py     # 实现工作流引擎
```

### Phase 3: 集成与通知（低优先级）

#### 3.1 通知系统
```
src/services/
  ├── notification_service.py  # 实现邮件/短信/推送通知
  └── report_service.py       # 实现报告生成与发送
```

---

## 🎯 推荐开发顺序

1. **立即完善：** `automation_rules.py` — CI/CD 流程核心
2. **短期完善：** `import_export_service.py` — 数据迁移刚需
3. **中期完善：** `churn_prediction.py` + `sales_recommendation.py` — 差异化能力
4. **长期规划：** `workflow_service.py` + `rbac_service.py` — 企业级功能

---

## 📊 当前覆盖率统计

| 模块 | Router 数量 | Service 数量 | 匹配率 |
|------|-----------|-------------|--------|
| Activities | 9 | 9 | 100% |
| Customers | 11 | 12 | 100% |
| Sales | 11 | 11 | 100% |
| Tenants | 7 | 7 | 100% |
| Tickets | 12 | 11 | 100% |
| Users | 9 | 9 | 100% |
| **总计** | **59** | **59** | **100%** |

**结论：** 所有已定义的 Router 和 Service 方法已完全匹配。剩余工作为补充未实现业务逻辑的服务。

---

## 🔧 建议的测试优先级

1. **Unit Tests** — 已有 `tests/unit/` 覆盖核心服务
2. **Integration Tests** — 补充各模块的集成测试
3. **API Tests** — 用 FastAPI TestClient 测试所有 router 端点
4. **E2E Tests** — 覆盖完整的业务流程