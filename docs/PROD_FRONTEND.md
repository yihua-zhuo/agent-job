# CRM 生产前台开发文档 v1.0

## 一、项目概述

**生产地址**: https://agent-job-production.up.railway.app/

CRM Agent 系统后端 API 服务，基于 Flask + Gunicorn，提供客户管理、销售管道、工单等企业级 REST API。

---

## 二、快速开始

### 2.1 本地运行

```bash
cd dev-agent-system
pip install flask gunicorn python-dotenv pymysql

# 设置环境变量
export DATABASE_URL="mysql+pymysql://user:pass@host:3306/crm"
export SECRET_KEY="your-secret-key"

# 启动服务
gunicorn --bind 0.0.0.0:8080 src.app:app
```

### 2.2 Docker 运行

```bash
docker build -t crm-api .
docker run -p 8080:8080 \
  -e DATABASE_URL="mysql+pymysql://user:pass@host:3306/crm" \
  crm-api
```

---

## 三、API 文档

### 3.1 健康检查

```
GET /
```

**响应:**
```json
{
  "status": "ok",
  "service": "agent-job"
}
```

---

### 3.2 客户管理

#### 创建客户
```
POST /api/v1/customers
```

**请求体:**
```json
{
  "name": "北京科技有限公司",
  "email": "contact@company.com",
  "phone": "+86-138-0000-0000",
  "industry": "互联网",
  "status": "active"
}
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "北京科技有限公司",
    "email": "contact@company.com",
    "phone": "+86-138-0000-0000",
    "industry": "互联网",
    "status": "active",
    "created_at": "2026-04-12T00:00:00Z"
  }
}
```

---

#### 客户列表
```
GET /api/v1/customers
```

**查询参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码，默认 1 |
| page_size | int | 每页数量，默认 20 |
| status | string | 客户状态筛选 |
| owner_id | int | 负责人 ID |
| search | string | 关键词搜索 |

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

---

#### 获取客户详情
```
GET /api/v1/customers/{customer_id}
```

---

#### 更新客户
```
PUT /api/v1/customers/{customer_id}
```

**请求体:**
```json
{
  "name": "新名称",
  "status": "inactive"
}
```

---

#### 删除客户（软删除）
```
DELETE /api/v1/customers/{customer_id}
```

---

#### 客户搜索
```
GET /api/v1/customers/search?keyword=北京
```

---

#### 客户标签管理
```
POST /api/v1/customers/{customer_id}/tags
Body: { "tag": "VIP" }

DELETE /api/v1/customers/{customer_id}/tags/{tag}
```

---

#### 客户状态更新
```
PUT /api/v1/customers/{customer_id}/status
Body: { "status": "active" | "inactive" | "blocked" }
```

---

#### 客户负责人变更
```
PUT /api/v1/customers/{customer_id}/owner
Body: { "owner_id": 1 }
```

---

#### 客户导入
```
POST /api/v1/customers/import
Body: FormData (CSV 文件)
```

---

### 3.3 销售管道

#### 创建管道
```
POST /api/v1/pipelines
```

**请求体:**
```json
{
  "name": "标准销售管道",
  "stages": [
    { "name": "线索", "order": 1 },
    { "name": "意向", "order": 2 },
    { "name": "方案", "order": 3 },
    { "name": "成交", "order": 4 }
  ]
}
```

---

#### 管道列表
```
GET /api/v1/pipelines
```

---

#### 管道详情
```
GET /api/v1/pipelines/{pipeline_id}
```

---

#### 管道统计
```
GET /api/v1/pipelines/{pipeline_id}/stats
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_amount": 1000000,
    "opportunity_count": 50,
    "stage_distribution": [
      { "stage": "线索", "count": 20, "amount": 200000 },
      { "stage": "意向", "count": 15, "amount": 300000 }
    ]
  }
}
```

---

#### 管道漏斗
```
GET /api/v1/pipelines/{pipeline_id}/funnel
```

---

### 3.4 商机管理

#### 创建商机
```
POST /api/v1/opportunities
```

**请求体:**
```json
{
  "name": "XX公司采购项目",
  "customer_id": 1,
  "pipeline_id": 1,
  "stage_id": 1,
  "amount": 500000,
  "expected_close_date": "2026-06-30",
  "owner_id": 1
}
```

---

#### 商机列表
```
GET /api/v1/opportunities
```

**查询参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| pipeline_id | int | 管道 ID |
| stage_id | int | 阶段 ID |
| owner_id | int | 负责人 |

---

#### 商机详情
```
GET /api/v1/opportunities/{opp_id}
```

---

#### 更新商机
```
PUT /api/v1/opportunities/{opp_id}
```

---

#### 商机阶段变更
```
PUT /api/v1/opportunities/{opp_id}/stage
Body: { "stage_id": 2, "probability": 50 }
```

---

### 3.5 销售预测

```
GET /api/v1/forecast?pipeline_id=1&period=quarter
```

**响应:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "predicted_revenue": 2500000,
    "confidence": 0.85,
    "by_stage": {
      "线索": 500000,
      "意向": 800000,
      "方案": 700000,
      "成交": 500000
    }
  }
}
```

---

## 四、数据模型

### 4.1 核心实体

```
Tenant (租户)
  └── Organization (组织)
       └── Department (部门)
            └── User (用户) ←→ Role (角色) ←→ Permission (权限)

Customer (客户) ←→ CustomerContact, CustomerAddress, Tag
Opportunity (商机) ←→ Quote ←→ Contract
Ticket (工单)
Activity (活动)
Campaign (营销活动)
```

### 4.2 客户字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| tenant_id | BIGINT | 租户 ID（多租户隔离） |
| name | VARCHAR(255) | 客户名称 |
| email | VARCHAR(255) | 邮箱 |
| phone | VARCHAR(50) | 电话 |
| industry | VARCHAR(100) | 行业 |
| status | ENUM | active/inactive/blocked |
| owner_id | BIGINT | 负责人 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| deleted_at | TIMESTAMP | 软删除时间 |

### 4.3 商机阶段

| 阶段 | 概率 | 说明 |
|------|------|------|
| 线索 | 10% | 初始线索 |
| 意向 | 30% | 明确意向 |
| 方案 | 60% | 提供方案 |
| 谈判 | 80% | 商务谈判 |
| 成交 | 100% | 签约完成 |

---

## 五、前端集成指南

### 5.1 基础配置

```javascript
const API_BASE = 'https://agent-job-production.up.railway.app/api/v1';

// Axios 配置示例
import axios from 'axios';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}` // 如需认证
  },
  timeout: 10000
});
```

### 5.2 API 调用示例

```javascript
// 获取客户列表
async function getCustomers(page = 1, pageSize = 20) {
  const response = await api.get('/customers', {
    params: { page, page_size: pageSize }
  });
  return response.data;
}

// 创建客户
async function createCustomer(data) {
  const response = await api.post('/customers', data);
  return response.data;
}

// 更新客户状态
async function updateCustomerStatus(id, status) {
  const response = await api.put(`/customers/${id}/status`, { status });
  return response.data;
}
```

### 5.3 错误处理

```javascript
async function apiRequest(fn) {
  try {
    return await fn();
  } catch (error) {
    if (error.response) {
      const { code, message } = error.response.data;
      switch (code) {
        case 1000: // 参数错误
          alert(`参数错误: ${message}`);
          break;
        case 2000: // 业务错误
          alert(`业务错误: ${message}`);
          break;
        case 3000: // 权限错误
          alert(`权限不足: ${message}`);
          break;
        case 5000: // 系统错误
          alert(`系统繁忙，请稍后重试`);
          break;
      }
    } else {
      alert('网络错误，请检查连接');
    }
  }
}
```

---

## 六、响应格式规范

### 成功响应
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 错误响应
```json
{
  "code": 1000,
  "message": "参数错误: name 不能为空",
  "data": null
}
```

### 错误码定义

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1000 | 参数错误 |
| 2000 | 业务错误 |
| 3000 | 权限错误 |
| 5000 | 系统错误 |

---

## 七、开发分支策略

```
master      ← 正式环境部署
develop     ← 开发分支
feature/*   ← 功能分支
```

- 所有功能开发在 `feature/*` 分支
- 合并到 `develop` 触发 CI
- 合并到 `master` 触发生产部署

---

## 八、CI/CD 流程

```
Push → Lint (flake8/mypy) → Unit Tests → Code Review → Build → Deploy
```

- **质量控制**: pylint + mypy
- **单元测试**: pytest (230+ tests)
- **自动部署**: Railway (master 分支 push 时触发)

---

## 九、环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| DATABASE_URL | MySQL 连接字符串 | mysql+pymysql://user:pass@host:3306/crm |
| SECRET_KEY | Flask 密钥 | dev-secret-key |
| PORT | 监听端口 | 8080 |
| HOST | 监听地址 | 0.0.0.0 |

---

## 十、常见问题

### Q: 看不到客户列表？
检查 `tenant_id` 是否正确传入，多租户数据隔离。

### Q: 商机阶段变更失败？
确保 `probability` 与 `stage_id` 对应关系正确。

### Q: 部署后 API 无响应？
检查 Railway 日志确认容器健康检查通过（`/` 返回 200）。

### Q: 如何清理测试数据？
软删除客户会自动设置 `deleted_at`，数据不会真正删除。
