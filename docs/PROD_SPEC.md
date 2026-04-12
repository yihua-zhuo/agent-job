# Enterprise CRM 生产级规范 v2.0

## 一、数据库设计（50+张核心表）

### 1. 租户与组织（8张）
- tenants, organizations, departments
- users, roles, permissions
- role_permissions, user_roles

### 2. 客户核心（10张）
- customers, customer_contacts, customer_addresses
- customer_tags, tags, customer_owner_history
- customer_merge_log, customer_followers
- customer_custom_fields, customer_field_values

### 3. 销售与商机（10张）
- leads, lead_sources, lead_assignments
- opportunities, opportunity_stages, opportunity_stage_history
- opportunity_products, quotes, quote_items, contracts

### 4. 跟进与任务（10张）
- activities, activity_types, tasks, task_comments
- meetings, call_logs, email_logs, reminders
- calendar_events, event_attendees

### 5. 营销自动化（8张）
- campaigns, campaign_members, email_templates
- email_sends, email_events, sms_sends
- marketing_segments, segment_filters

### 6. 客服/工单（5张）
- tickets, ticket_comments, ticket_status_history
- ticket_sla, ticket_assignments

**累计：51张表**

---

## 二、设计重点

### 1. 多租户隔离
所有核心表必须有 `tenant_id`，防止数据串租户（SaaS必须）

### 2. 软删除
`deleted_at` 字段，避免误删

### 3. 审计字段
- created_at, updated_at
- created_by, updated_by

### 4. 扩展字段设计
- customer_custom_fields（字段定义）
- customer_field_values（字段值）
- 实现动态字段，无需改表结构

---

## 三、企业级开发规范

### 代码结构（分层）
```
/cmd           # 入口
/internal
  /api        # 路由控制器
  /service    # 业务逻辑
  /repository # 数据访问
  /domain     # 实体模型
  /dto        # 输入输出
  /middleware # 中间件
/pkg          # 公共库
```

### API 设计规范
```
GET    /api/v1/customers          # 列表
POST   /api/v1/customers          # 创建
GET    /api/v1/customers/{id}     # 详情
PUT    /api/v1/customers/{id}     # 更新
DELETE /api/v1/customers/{id}     # 删除
```

### 响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 错误码规范
```
1000 - 参数错误
2000 - 业务错误
3000 - 权限错误
5000 - 系统错误
```

### 权限控制（RBAC）
- 用户 → 角色 → 权限
- API级权限 + 数据级权限（owner_id）

---

## 四、架构关键点

### 1. 客户去重
- 手机 + email hash
- ES 模糊匹配

### 2. 高并发设计
- 分库分表（客户数据）
- 读写分离（CQRS）

### 3. 报表系统
- OLTP → OLAP（ClickHouse）

### 4. 搜索能力
- Elasticsearch

### 5. 缓存规范（Redis）
```
crm:customer:{id}
crm:user:{id}:roles
```

### 6. 异步规范（MQ/Kafka）
- 邮件发送
- 短信发送
- 行为日志
- 数据同步

### 7. 测试规范
- 单元测试 > 70%
- 集成测试
- API 测试

### 8. CI/CD 规范
- Git Flow：main / develop / feature/*
- 自动：lint → test → build → deploy

---

## 五、核心表结构示例

### customers
```sql
CREATE TABLE customers (
  id BIGINT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  name VARCHAR(255),
  email VARCHAR(255),
  phone VARCHAR(50),
  status VARCHAR(50),
  owner_id BIGINT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  deleted_at TIMESTAMP
);
```

### opportunities
```sql
CREATE TABLE opportunities (
  id BIGINT PRIMARY KEY,
  tenant_id BIGINT,
  customer_id BIGINT,
  name VARCHAR(255),
  amount DECIMAL(12,2),
  stage_id BIGINT,
  probability INT,
  expected_close_date DATE,
  owner_id BIGINT,
  created_at TIMESTAMP
);
```

### tickets
```sql
CREATE TABLE tickets (
  id BIGINT PRIMARY KEY,
  tenant_id BIGINT,
  customer_id BIGINT,
  subject VARCHAR(255),
  description TEXT,
  status VARCHAR(50),
  priority VARCHAR(50),
  assigned_to BIGINT,
  created_at TIMESTAMP
);
```
