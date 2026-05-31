# Backend · User Profile & Password API

| 元数据 | 值 |
|---|---|
| Issue | #112 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 前端 Settings 页面 (#59) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

前端 Settings 页面 (#59) 已实现 "Save Profile" 按钮和 "Change Password" 表单，但后端对应接口缺失，导致功能无法真正生效。当前状态：前端仅切换本地 UI，无 API 调用；改密表单提交后无任何响应。这是 #59 的阻塞依赖，必须先完成后端才能联调。

### 1.2 做完后

- **用户视角**：在 Settings 页面点击 "Save Profile" 后，full_name / email / bio 实时更新到数据库并刷新 UI；输入旧密码和新密码后，密码成功修改并返回确认信息，无用户可见报错。
- **开发者视角**：`UserService` 新增 `update_profile()` 方法，`AuthService` 新增 `change_password()` 方法；`/api/v1/users/me` (PATCH) 和 `/api/v1/auth/change-password` (POST) 两个 router 端点注册到 FastAPI app，OpenAPI 文档自动更新。

### 1.3 不做什么（剔除）

- [ ] 前端 Settings 页面 UI 改动（属于 #59 范围）
- [ ] 管理员代改其他用户密码（属于 Admin API 范围）
- [ ] 邮箱唯一性校验（tenant 隔离场景下 email 不作全局唯一约束）
- [ ] 旧密码输错次数限制 / 账号锁定逻辑

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_user_service.py tests/unit/test_auth_service.py -v` → ≥ 10 passed（含 profile update + password change 各 success/validation/error 场景）
- `ruff check src/services/user_service.py src/services/auth_service.py src/api/routers/users.py src/api/routers/auth.py` → 0 errors
- `PYTHONPATH=src mypy src/services/user_service.py src/services/auth_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/users.py` L? — 现有 GET /users/me 实现；需确认 UserService 是否有 update 方法
TBD - 待验证：`src/services/user_service.py` L? — UserService 类定义；需确认 ORM model 为 User 还是另有 UserProfile
TBD - 待验证：`src/api/routers/auth.py` L? — 现有 auth router 结构；需确认 register/login 周边代码风格
TBD - 待验证：`src/services/auth_service.py` L? — AuthService 类；需确认密码哈希实现方式（bcrypt / argon2）

### 2.2 涉及文件清单

- 要改：
  - `src/services/user_service.py` — 新增 `update_profile()` 方法
  - `src/api/routers/users.py` — 新增 `PATCH /users/me` 端点
  - `src/services/auth_service.py` — 新增 `change_password()` 方法
  - `src/api/routers/auth.py` — 新增 `POST /auth/change-password` 端点
  - `src/api/__init__.py` 或 `src/main.py` — 注册新路由
  - `tests/unit/conftest.py` — 新增 mock 辅助函数（如需要）
  - `tests/unit/test_user_service.py` — 新增 profile update 测试用例
  - `tests/unit/test_auth_service.py` — 新增 change_password 测试用例
- 要建：
  - `tests/unit/test_users_router.py` — PATCH /users/me 端点测试
  - `tests/unit/test_auth_change_password.py` — POST /auth/change-password 端点测试

### 2.3 缺什么

- [ ] `UserService.update_profile(session, user_id, tenant_id, full_name, email, bio)` — 当前 UserService 无此方法
- [ ] `AuthService.change_password(session, user_id, tenant_id, old_password, new_password)` — AuthService 无此方法
- [ ] `PATCH /api/v1/users/me` router 端点 — users router 中不存在
- [ ] `POST /api/v1/auth/change-password` router 端点 — auth router 中不存在
- [ ] email 格式校验（当前 ORM model 的 email 字段可能无 Pydantic validator）
- [ ] 新密码最小长度校验（8 字符）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-----|
| `tests/unit/test_users_router.py` | `PATCH /users/me` 端点单元测试（mock session） |
| `tests/unit/test_auth_change_password.py` | `POST /auth/change-password` 端点单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/user_service.py` | 新增 `update_profile()` 方法：校验 email 格式，按 tenant_id 过滤，UPDATE user 表 |
| `src/services/auth_service.py` | 新增 `change_password()` 方法：校验 old_password hash，bcrypt 哈希新密码，更新 DB |
| `src/api/routers/users.py` | 新增 `PATCH /users/me` 路由：依赖 `require_auth`，调用 `UserService.update_profile()` |
| `src/api/routers/auth.py` | 新增 `POST /auth/change-password` 路由：依赖 `require_auth`，调用 `AuthService.change_password()` |

### 3.3 新增能力

- **Service method**：`UserService.update_profile(self, user_id: int, tenant_id: int, full_name: str | None, email: str, bio: str | None) -> UserModel`
- **Service method**：`AuthService.change_password(self, user_id: int, tenant_id: int, old_password: str, new_password: str) -> dict`
- **API endpoint**：`PATCH /api/v1/users/me` → `{"success": true, "data": {...user.to_dict()...}}`
- **API endpoint**：`POST /api/v1/auth/change-password` → `{"success": true, "data": {"message": "Password updated successfully"}}`
- **Validation**：email format（Pydantic EmailStr）、new_password ≥ 8 chars、old_password hash match

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **bcrypt 而非 argon2**：项目 auth_service.py 已使用 bcrypt（`passlib[bcrypt]`）；保持一致避免引入新依赖。
- **change-password 返回 dict 而非 ORM 对象**：密码修改是动作而非资源查询，返回 `{"message": "..."}` 更语义化；Service 仍抛出 `AppException` 子类表示失败。
- **email 不做全局唯一性校验**：multi-tenant 场景下同一 email 可出现在不同 tenant；唯一性仅在当前 tenant 内校验（如果业务需要，可在后续迭代添加）。
- **PATCH 而非 PUT**：profile 更新是部分更新（可只改 bio），语义上 PATCH 更准确。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `passlib[bcrypt]` | 兼容 `1.7.x` | 项目已有，bcrypt 哈希 + 校验 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`，user_service.py 和 auth_service.py 所有方法签名已含 `tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- Router inject session：`session: AsyncSession = Depends(get_db)`，禁止 `async with get_db()`
- 新增 service 方法需遵守现有 `__init__(self, session: AsyncSession)` 签名（无默认值）

### 4.4 已知坑

1. **bcrypt 校验慢（O(n) GPU 抗力）** → 规避：单次 hash 校验无法优化，但 change-password 操作频率极低（用户主动发起），无需缓存
2. **UserService.update_profile 中 email 重复校验** → 规避：如果 email 已在当前 tenant 存在，抛 `ConflictException("Email already in use")`

---

## 5. 实现步骤（按顺序）

### Step 1: 新增 UserService.update_profile 方法

在 `src/services/user_service.py` 新增 `update_profile` 方法。

操作：
- a) 确认 User ORM model 中有 `full_name`、`email`、`bio` 字段（若缺 bio 列需另起 migration）
- b) 在 `UserService` 类中添加方法：接收 `(self, user_id, tenant_id, full_name, email, bio)`，执行 `UPDATE users SET full_name=..., email=..., bio=... WHERE id=:user_id AND tenant_id=:tenant_id`
- c) 用 `result.scalar_one_or_none()` 确认记录存在，不存在则 `raise NotFoundException("User")`
- d) email 格式由 Pydantic validator 保证，service 层不重复校验；如需 tenant 内唯一性在此校验并抛 `ConflictException`

```python
# src/services/user_service.py
async def update_profile(
    self,
    user_id: int,
    tenant_id: int,
    full_name: str | None,
    email: str,
    bio: str | None,
) -> User:
    stmt = (
        update(User)
        .where(User.id == user_id, User.tenant_id == tenant_id)
        .values(full_name=full_name, email=email, bio=bio)
        .returning(User)
    )
    result = await self.session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("User")
    return user
```

**完成判定**：`ruff check src/services/user_service.py` → 0 errors

---

### Step 2: 新增 PATCH /users/me router 端点

在 `src/api/routers/users.py` 新增路由，在 `src/main.py` 注册路由（若尚未注册 `users` router）。

操作：
- a) 新增 `UserUpdatePayload` Pydantic model（或在现有 schemas 中添加）：
  ```python
  class UserUpdatePayload(BaseModel):
      full_name: str | None = None
      email: EmailStr
      bio: str | None = None
  ```
- b) 新增 router 方法：
  ```python
  @router.patch("/me", response_model=ApiResponse[dict])
  async def update_my_profile(
      payload: UserUpdatePayload,
      ctx: AuthContext = Depends(require_auth),
      session: AsyncSession = Depends(get_db),
  ):
      svc = UserService(session)
      user = await svc.update_profile(
          user_id=ctx.user_id,
          tenant_id=ctx.tenant_id,
          full_name=payload.full_name,
          email=payload.email,
          bio=payload.bio,
      )
      return ApiResponse(success=True, data=user.to_dict())
  ```

**完成判定**：`ruff check src/api/routers/users.py` → 0 errors

---

### Step 3: 新增 AuthService.change_password 方法

在 `src/services/auth_service.py` 新增 `change_password` 方法。

操作：
- a) 确认已 import `CryptContext`（bcrypt 配置）
- b) 在 `AuthService` 类中添加方法：
  ```python
  async def change_password(
      self,
      user_id: int,
      tenant_id: int,
      old_password: str,
      new_password: str,
  ) -> dict:
      # fetch user
      stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
      result = await self.session.execute(stmt)
      user = result.scalar_one_or_none()
      if user is None:
          raise NotFoundException("User")
      # verify old password
      if not self.pwd_context.verify(old_password, user.hashed_password):
          raise ValidationException("Old password is incorrect")
      # validate new password length
      if len(new_password) < 8:
          raise ValidationException("New password must be at least 8 characters")
      # hash and update
      user.hashed_password = self.pwd_context.hash(new_password)
      self.session.add(user)
      await self.session.flush()
      return {"message": "Password updated successfully"}
  ```
- c) 若 `AuthService.__init__` 尚未持有 `pwd_context`，从 `src/core/security.py`（或相应路径）获取其实例并保存为 `self.pwd_context`

**完成判定**：`ruff check src/services/auth_service.py` → 0 errors

---

### Step 4: 新增 POST /auth/change-password router 端点

在 `src/api/routers/auth.py` 新增路由。

操作：
- a) 新增 `ChangePasswordPayload` Pydantic model：
  ```python
  class ChangePasswordPayload(BaseModel):
      old_password: str
      new_password: Annotated[str, Field(min_length=8)]
  ```
- b) 新增 router 方法：
  ```python
  @router.post("/change-password", response_model=ApiResponse[dict])
  async def change_password(
      payload: ChangePasswordPayload,
      ctx: AuthContext = Depends(require_auth),
      session: AsyncSession = Depends(get_db),
  ):
      svc = AuthService(session)
      result = await svc.change_password(
          user_id=ctx.user_id,
          tenant_id=ctx.tenant_id,
          old_password=payload.old_password,
          new_password=payload.new_password,
      )
      return ApiResponse(success=True, data=result)
  ```

**完成判定**：`ruff check src/api/routers/auth.py` → 0 errors

---

### Step 5: 编写 UserService.update_profile 单元测试

在 `tests/unit/test_user_service.py` 中新增测试用例。

操作：
- a) 在现有 `mock_db_session` fixture 或新建组合中 mock `UPDATE` / `SELECT` / `RETURNING` SQL 行为
- b) 添加 `test_update_profile_success`：传入 valid payload，返回更新后的 User ORM 对象
- c) 添加 `test_update_profile_not_found`：user_id 不存在时抛 `NotFoundException`
- d) 添加 `test_update_profile_partial`：只传 `bio`，`full_name` / `email` 不传，验证 partial update 行为

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_user_service.py -v -k update_profile` → 3 passed

---

### Step 6: 编写 AuthService.change_password 单元测试

在 `tests/unit/test_auth_service.py` 中新增测试用例。

操作：
- a) Mock `select(User)` 返回带 bcrypt 哈希密码的 mock User 对象
- b) 添加 `test_change_password_success`：old_password 正确 → 返回 dict，hashed_password 更新
- c) 添加 `test_change_password_wrong_old`：old_password 错误 → 抛 `ValidationException`
- d) 添加 `test_change_password_too_short`：new_password < 8 字符 → 抛 `ValidationException`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_auth_service.py -v -k change_password` → 3 passed

---

### Step 7: 编写 router 端点测试

新建 `tests/unit/test_users_router.py` 和 `tests/unit/test_auth_change_password.py`。

操作：
- a) `test_users_router.py`：`test_patch_me_success`、`test_patch_me_validation_error`（invalid email）
- b) `test_auth_change_password.py`：`test_change_password_success`、`test_change_password_unauthorized`（无 token）
- c) 使用 `tests.unit.conftest.make_mock_session` 组合 handler，无需真实 DB

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_users_router.py tests/unit/test_auth_change_password.py -v` → 4 passed

---

### Step 8: 类型检查与 lint

操作：
- a) `ruff check src/services/user_service.py src/services/auth_service.py src/api/routers/users.py src/api/routers/auth.py`
- b) `PYTHONPATH=src mypy src/services/user_service.py src/services/auth_service.py`
- c) 修正所有 type error 和 lint error

**完成判定**：`ruff check src/ && mypy src/services/user_service.py src/services/auth_service.py` → 0 errors / 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/user_service.py src/services/auth_service.py src/api/routers/users.py src/api/routers/auth.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/services/user_service.py src/services/auth_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_user_service.py -v -k update_profile` → ≥ 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_auth_service.py -v -k change_password` → ≥ 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_users_router.py tests/unit/test_auth_change_password.py -v` → ≥ 4 passed
- [ ] OpenAPI 文档访问 `GET /docs` 显示 `PATCH /api/v1/users/me` 和 `POST /api/v1/auth/change-password` 两个端点（schema 包含正确 request body 字段）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| User model 缺少 `bio` 列，需迁移 | 低 | 中 | 若 bio 列不存在，在 `src/db/models/` 对应文件中添加 `bio: Mapped[str | None] = mapped_column(Text, nullable=True)`，执行 alembic migration 生成修订文件；前端暂不支持 bio 字段，后端保持向后兼容 |
| bcrypt 性能问题导致测试超时 | 极低 | 低 | 测试 mock 绕过 bcrypt，实际路由中 bcrypt 单次校验 < 50ms，无优化必要 |
| 旧密码校验引入 timing attack 微小差异 | 极低 | 低 | `passlib` bcrypt backend 内部使用恒定时间比较；暂不做额外处理 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/user_service.py src/services/auth_service.py \
       src/api/routers/users.py src/api/routers/auth.py \
       tests/unit/test_user_service.py tests/unit/test_auth_service.py \
       tests/unit/test_users_router.py tests/unit/test_auth_change_password.py
git commit -m "feat(user): add PATCH /users/me and POST /auth/change-password endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(user): profile update & password change endpoints" --body "Closes #112"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/api/routers/auth.py` — 现有 POST /login、POST /register 实现（router 层结构一致）
- 同类参考实现：`src/services/user_service.py` — 现有 GET 方法（service 层结构一致）
- 父 issue / 关联：#59（前端 Settings 页面，依赖本板块完成后端联调）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
