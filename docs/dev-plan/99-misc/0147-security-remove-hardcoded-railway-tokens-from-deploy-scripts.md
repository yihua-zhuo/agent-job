# [Security] Remove hardcoded Railway tokens from deploy scripts

| 元数据 | 值 |
|---|---|
| Issue | #147 |
| 分类 | 00-meta |
| 优先级 | 必做 |
| 工作量 | 0.25 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Two deploy scripts (`deploy.js` and `railway-deploy.js`) contain a hardcoded Railway API token (`2dc2f4ae-4e33-4ec4-a715-474a16792c00`). This is a critical security issue: the token has been exposed in the repository history and could be scraped by anyone with repo read access. Long-lived API tokens in source control violate security best practices and must be removed immediately.

### 1.2 做完后

- **用户视角**：无用户-visible changes — this is a pure backend security fix.
- **开发者视角**：Deploy scripts now require `RAILWAY_TOKEN` to be set as an environment variable. Attempts to run either script without it will throw a clear error rather than silently using the (now-absent) hardcoded credential.

### 1.3 不做什么（剔除）

- [ ] Adding new deploy capabilities or altering the deployment pipeline logic — only the token handling changes.
- [ ] Rotating or regenerating the exposed token — that is a separate operational action outside this repo's scope.

### 1.4 关键 KPI

- [ ] `grep -r "2dc2f4ae-4e33-4ec4-a715-474a16792c00" .` → 0 matches in `deploy.js` and `railway-deploy.js`
- [ ] `git ls-files --cached shared-memory/logs/latest.diff` → 0 output (file removed from git index)
- [ ] `ruff check deploy.js railway-deploy.js` → 0 errors (if applicable to JS files)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`deploy.js` L{?} — 存在 `const TOKEN = "2dc2f4ae-4e33-4ec4-a715-474a16792c00";` 硬编码 token

TBD - 待验证：`railway-deploy.js` L{?} — 存在 `const token = process.env.RAILWAY_TOKEN || "2dc2f4ae-4e33-4ec4-a715-474a16792c00";` 拼贴式 fallback

TBD - 待验证：`.gitignore` 是否已包含 `shared-memory/logs/` 等路径

TBD - 待验证：`shared-memory/logs/latest.diff` 是否已被 git 跟踪（已提交但未从 index 移除）

### 2.2 涉及文件清单

- 要改：
  - `deploy.js` — 移除硬编码 token，改为从 `process.env.RAILWAY_TOKEN` 读取
  - `railway-deploy.js` — 同上
  - `.gitignore` — 新增 `shared-memory/logs/`、`shared-memory/results/`、`shared-memory/reports/`

### 2.3 缺什么

- [ ] `deploy.js` 中硬编码 token 仍在源码中，任何有 repo 访问权限的人都能看到
- [ ] `railway-deploy.js` 中硬编码 token 仍在源码中
- [ ] `shared-memory/logs/latest.diff` 已被 git 跟踪并在历史中保留，需要从 index 清除
- [ ] `.gitignore` 缺少 `shared-memory/` 子目录，导致临时产物持续污染 git

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| N/A — 本次无新文件 | |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `deploy.js` | 移除 `const TOKEN = "2dc2f4ae-4e33-4ec4-a715-474a16792c00"`；替换为从 `process.env.RAILWAY_TOKEN` 读取并在缺失时抛错 |
| `railway-deploy.js` | 同上，移除 fallback 并在缺失时 `process.exit(1)` |
| `.gitignore` | 新增 `shared-memory/logs/`、`shared-memory/results/`、`shared-memory/reports/` |
| git index | `git rm --cached shared-memory/logs/latest.diff` 从 index 移除已提交的日志文件 |

### 3.3 新增能力

- **Runtime check**：任何未设置 `RAILWAY_TOKEN` 环境变量而调用 `deploy.js` 或 `railway-deploy.js` 的行为会立即失败并输出明确错误信息

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Fail-fast 而非 silent fallback**：不使用 `|| "token"` 的拼贴式 fallback，而要求环境变量必须存在。理由：silent fallback 在 token 已泄露的情况下仍会"工作"，掩盖安全问题，直到 CI/CD 流水线以无 token 状态运行并失败才会暴露 — fail-fast 迫使调用方显式提供凭证，更安全。
- **在脚本顶层检查而非运行时延迟检查**：在模块加载时检查并抛错，而非等到第一次 API 调用才报错。理由：CI/CD 流水线启动早期就能发现问题。

### 4.2 版本约束

<!-- 无新依赖 -->

### 4.3 兼容性约束

- N/A — 本次仅修改 Node.js deploy 脚本，无 Python 服务改动，无需遵循 Service 模式或 SQLAlchemy 约定
- 若后续 Python 代码需要读取 Railway token，应通过 `os.environ["RAILWAY_TOKEN"]` 而非硬编码

### 4.4 已知坑

1. **Git 历史无法通过 `.gitignore` 回溯清除** → 规避：移除 index 中的文件 (`git rm --cached`) 后，该文件仍存在于历史提交中；需在 issue 中注明运维人员应在 GitHub Secrets 中轮换该 token，且此次改动仅保护未来代码不被污染
2. **Alembic / Python 迁移不受影响** → 本次不涉及 DB migration，无需关注 SQLAlchemy Base 列名或 JSONB 等坑

---

## 5. 实现步骤（按顺序）

### Step 1: 修复 deploy.js token 硬编码

在 `deploy.js` 中找到硬编码 token 赋值行，替换为环境变量读取 + 空值检查。

操作：
a) 编辑 `deploy.js`，将 `const TOKEN = "2dc2f4ae-4e33-4ec4-a715-474a16792c00";` 替换为：

```javascript
const TOKEN = process.env.RAILWAY_TOKEN;
if (!TOKEN) {
  throw new Error("RAILWAY_TOKEN environment variable is required");
}
```

**完成判定**：`grep -n "2dc2f4ae-4e33-4ec4-a715-474a16792c00" deploy.js` → 0 output

---

### Step 2: 修复 railway-deploy.js token 硬编码

在 `railway-deploy.js` 中移除 `||` fallback 拼贴式 token，替换为显式环境变量检查。

操作：
a) 编辑 `railway-deploy.js`，将 `const token = process.env.RAILWAY_TOKEN || "2dc2f4ae-4e33-4ec4-a715-474a16792c00";` 替换为：

```javascript
const token = process.env.RAILWAY_TOKEN;
if (!token) {
  console.error("RAILWAY_TOKEN environment variable is required");
  process.exit(1);
}
```

**完成判定**：`grep -n "2dc2f4ae-4e33-4ec4-a715-474a16792c00" railway-deploy.js` → 0 output

---

### Step 3: 更新 .gitignore

在 `.gitignore` 末尾追加三个共享内存目录。

操作：
a) 在 `.gitignore` 末尾插入新行：
```
shared-memory/logs/
shared-memory/results/
shared-memory/reports/
```

**完成判定**：`grep -E "shared-memory/(logs|results|reports)/" .gitignore` → 3 lines output

---

### Step 4: 从 git index 移除已提交的日志文件

执行 `git rm --cached` 从 index 删除已提交的 `shared-memory/logs/latest.diff`，防止其继续被跟踪。

操作：
a) 运行 `git rm --cached shared-memory/logs/latest.diff`

**完成判定**：`git ls-files --cached shared-memory/logs/latest.diff` → 0 output

---

## 6. 验收

- [ ] `grep -r "2dc2f4ae-4e33-4ec4-a715-474a16792c00" deploy.js railway-deploy.js` → 0 output
- [ ] `grep -E "process\.env\.RAILWAY_TOKEN" deploy.js railway-deploy.js` → 2 lines output（两个文件各 1 行）
- [ ] `git ls-files --cached shared-memory/logs/latest.diff` → 0 output
- [ ] `grep -E "shared-memory/(logs|results|reports)/" .gitignore` → 3 lines output
- [ ] `git diff origin/master -- .gitignore deploy.js railway-deploy.js` → 显示 4 个文件的预期改动

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 现有 CI/CD 流水线未设置 `RAILWAY_TOKEN` 环境变量 | 中 | 中 | 临时在 CI secrets 中添加 `RAILWAY_TOKEN`；本 PR 仅修安全漏洞，不应阻断其他功能 |
| 开发者本地运行 deploy 脚本时缺少 env var | 中 | 低 | 脚本在启动时立即报错（throw Error / process.exit(1)），错误信息清晰，不污染 git history；设置 env var 后重试即可 |
| 已泄露 token 仍在 Git 历史中 | 中 | 高 | 本次改动无法清除历史 — 需运维在 Railway 仪表板中轮换 token；本 PR 阻止问题继续恶化 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add .gitignore deploy.js railway-deploy.js
git rm --cached shared-memory/logs/latest.diff
git commit -m "fix(security): remove hardcoded Railway API token from deploy scripts"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "fix(security): remove hardcoded Railway tokens from deploy scripts" --body "Closes #147

## Summary
- Remove hardcoded Railway API token from \`deploy.js\` and \`railway-deploy.js\` — replaced with \`process.env.RAILWAY_TOKEN\` + fail-fast check
- Add \`shared-memory/logs/\`, \`shared-memory/results/\`, \`shared-memory/reports/\` to \`.gitignore\`
- Remove \`shared-memory/logs/latest.diff\` from git index

## Note
The token \`2dc2f4ae-4e33-4ec4-a715-474a16792c00\` existed in git history. This change prevents future commits from adding it back. The token should be rotated in Railway dashboard as a separate operational step.

Closes #147"
```

---

## 9. 参考

- 同类参考实现：N/A — 本次为一次性安全修复，无同类参考
- 第三方文档：[Railway Environment Variables](https://docs.railway.app/develop/infrastructure/reference/variables)
- 父 issue / 关联：#147

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
