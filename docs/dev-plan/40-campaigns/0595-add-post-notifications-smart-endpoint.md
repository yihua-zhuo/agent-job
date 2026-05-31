# 1. commit + PR
git add src/api/routers/notifications.py src/db/models/notification.py alembic/versions/ tests/unit/test_notifications.py
git commit -m "feat(campaigns): add POST /notifications/smart endpointCloses #595"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#595): add POST /notifications/smart endpoint" --body "Closes #595"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

<!-- 参考的具体形式（按需选）：
  - 同类已有实现（本仓库内）
  - 第三方文档：仅当确实需要时
  - 父 issue / 关联 issue
  Do NOT 编造 https://github.com/.../issues/N 这种占位 URL。
-->

- 同类参考实现（路由模式）：TBD - 待验证：`src/api/routers/customer.py` — router + AuthContext + Depends(get_db) 标准模式
- 父 issue：#47
- 关联 issue：#41（LLM 分类集成 TODO），#594（依赖的前置板块）
