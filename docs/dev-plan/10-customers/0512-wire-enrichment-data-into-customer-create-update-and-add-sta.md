# 1. commit + PR
git add src/services/customer_service.py src/api/routers/enrichment.py tests/unit/test_customer_service.py tests/unit/test_enrichment_router.py
git commit -m "feat(customers): wire enrichment data into customer create/update, add refresh endpoint, Closes #512"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#512): wire enrichment data into customer create/update and add status indicator" --body "Closes #512"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/customer_service.py` —现有 create/update 模式，其他 service 的 upsert 参考
- 第三方文档：PostgreSQL upsert [`insert().on_conflict_do_update()`](https://docs.sqlalchemy.org/en/20/orm_queryguide.html#orm-upsert-statements) — SQLAlchemy 2.x 推荐写法
- 父 issue / 关联：#74
