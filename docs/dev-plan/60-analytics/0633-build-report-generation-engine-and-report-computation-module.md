# 1. commit + PR
git add src/services/report_generation/ tests/unit/test_report_computation.py tests/unit/domain_handlers/report_computation.py tests/integration/test_report_computation_integration.py src/services/report_service.py
git commit -m "feat(analytics): report compute engine —5 report types"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): report compute engine for 5 report types" --body "Closes #633"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/sales_service.py`](../../src/services/sales_service.py) — `get_forecast()` 按 stage 分组统计的 SQL 模式，可作为 `pipeline_forecast` 实现参考
- 同类参考实现：[`src/services/activity_service.py`](../../src/services/activity_service.py) — `get_activity_summary()` 按 type 分组聚合的 SQL 模式
- 同类参考实现：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) — `check_sla_breach()` 与 SLA breach统计 SQL
- 母 issue /关联：#40（analytics基础设施整体规划）
- 依赖 issue：#632（构建 REST 路由与 API 终端 — 本板块的计算结果将路由到该板块的 API 端点）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
