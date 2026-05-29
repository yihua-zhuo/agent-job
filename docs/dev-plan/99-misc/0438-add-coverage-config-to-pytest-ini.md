# 1. commit + PR
git add pytest.ini pyproject.toml
git commit -m "feat(ci): add pytest-cov addopts to pytest.ini"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(infra): add coverage config to pytest.ini (#438)" --body "Closes #438"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`tests/conftest.py` 或 `pytest.ini` 中 pytest-cov 使用示例
- 第三方文档：[pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- 父 issue /关联：#198, #437
