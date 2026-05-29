# 1. commit + PR
git add src/db/models/recommendation.py src/db/models/risk_signal.py src/services/recommendation_service.py \
  tests/unit/test_recommendation_service.py tests/integration/test_recommendation_integration.py \
  tests/unit/domain_handlers/recommendations.py \
  alembic/versions/<id>_add_recommendations_and_risk_signals.py
git commit -m "feat(sales): add RecommendationModel and RiskSignalModel with persistent storage"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#597): add Recommendation and RiskSignal ORM models" --body "Closes #597"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/customer.py`](../../src/db/models/customer.py) — JSON 列（`tags`、`recycle_history`）模式一致- 同类参考实现：[`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) — 基础 model + FK 索引模式
- 关联：#46（父 issue — AI 推荐与风险信号系统）
- 第三方文档：[SQLAlchemy 2.x async](https://docs.sqlalchemy.org/en/20/), [Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
