# 1. commit + PR
git add src/services/analytics_service.py tests/unit/test_analytics_service.py
git commit -m "feat(analytics): add MoM/WoW/DoD comparison and 2σ anomaly detection for sales_summary"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#589): trend comparison and anomaly detection for sales_summary" --body "Closes #589"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/` 下是否存在其他 trending / comparison 方法（如 pipeline统计逻辑）
- 父 issue：#48
- 依赖 issue：#588（趋势看板基础实现 — 新增 compare_period_metrics 的前置上下文）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
