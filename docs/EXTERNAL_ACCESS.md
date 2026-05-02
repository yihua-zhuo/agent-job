# CRM 系统外部访问指南

## 🔗 访问地址

**临时 Tunnel（开发测试用）：**
```
https://rain-mistress-corporations-fonts.trycloudflare.com
```

> ⚠️ 每次重启 tunnel 会变化，临时链接不保证长期可用

---

## 🏥 健康检查

```bash
curl https://rain-mistress-corporations-fonts.trycloudflare.com/
```

返回：
```json
{"service":"agent-job","status":"ok"}
```

---

## 🔐 认证流程

### 1. 获取 Token

```bash
curl -X POST https://rain-mistress-corporations-fonts.trycloudflare.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "你的用户名", "password": "你的密码"}'
```

返回：
```json
{
  "code": 200,
  "data": {
    "token": "eyJhbGc...",
    "expires_at": "..."
  }
}
```

### 2. 使用 Token 访问受保护接口

```bash
curl https://rain-mistress-corporations-fonts.trycloudflare.com/api/customers \
  -H "Authorization: Bearer <your_token>"
```

---

## 📡 主要 API 端点

| 模块 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 认证 | `/api/auth/login` | POST | 登录 |
| 认证 | `/api/auth/register` | POST | 注册 |
| 客户 | `/api/customers` | GET | 客户列表 |
| 客户 | `/api/customers/:id` | GET | 客户详情 |
| 客户 | `/api/customers` | POST | 创建客户 |
| 客户 | `/api/customers/:id` | PUT | 更新客户 |
| 客户 | `/api/customers/:id` | DELETE | 删除客户 |
| 销售 | `/api/sales/*` | - | 销售管道相关 |
| 营销 | `/api/marketing/*` | - | 营销活动相关 |
| 客服 | `/api/tickets/*` | - | 工单/客服相关 |

---

## 🛠️ 本地开发

### 启动服务

```bash
cd /home/node/.openclaw/workspace/dev-agent-system
source .env
export PYTHONPATH=src
gunicorn --bind 0.0.0.0:8080 src.app:app
```

### 重启 Cloudflare Tunnel

```bash
cd /home/node/.openclaw/workspace
./cloudflared tunnel --url http://localhost:8080
```

---

## 📝 环境变量

项目根目录 `.env` 文件包含：

```env
DATABASE_URL=postgresql+psycopg2://postgres.xxx:xxx@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
DATABASE_DIALECT=postgresql+asyncpg
FLASK_ENV=production
SECRET_KEY=xxx
JWT_SECRET_KEY=xxx
CORS_ORIGINS=*
```

---

## 🐛 故障排查

### 1. 连接失败
```bash
# 检查 CRM 服务是否运行
curl http://localhost:8080/

# 检查 gunicorn 进程
ps aux | grep gunicorn
```

### 2. 数据库连接失败
```bash
# 测试数据库连接
cd /home/node/.openclaw/workspace/dev-agent-system
python3 -c "
import asyncio, os, urllib.parse
import asyncpg
url = os.environ.get('DATABASE_URL','').replace('postgresql+psycopg2://','postgresql+asyncpg://')
p = urllib.parse.urlparse(url)
conn = asyncpg.connect(host=p.hostname, port=p.port, user=p.username, password=urllib.parse.unquote(p.password), database=p.path.lstrip('/'))
print(asyncio.run(conn.fetchval('SELECT 1')))
"
```

### 3. Tunnel 链接失效
每次重启 cloudflared 会生成新链接，查看当前链接：
```bash
ps aux | grep cloudflared
# 或者重新运行 ./cloudflared tunnel --url http://localhost:8080
```

---

## 🚀 正式部署建议

1. **使用 Cloudflare 账号创建 Named Tunnel**（有 uptime 保证）
2. **配置自定义域名**（通过 Cloudflare DNS 绑定）
3. **启用 Cloudflare Access**（额外的身份验证层）

---

**最后更新：** 2026-04-30
