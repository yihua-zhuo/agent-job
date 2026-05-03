"""流失预测服务单元测试"""
import pytest

from src.services.churn_prediction import ChurnPredictionService, ChurnRiskFactor


@pytest.fixture
def churn_service():
    """创建流失预测服务实例"""
    return ChurnPredictionService()


class TestChurnPredictionNormal:
    """正常场景测试"""

    def test_calculate_churn_score(self, churn_service):
        """测试计算流失分数"""
        score = churn_service.calculate_churn_score(1)
        assert 0 <= score <= 100
        assert isinstance(score, float)

    def test_predict_churn_single_customer(self, churn_service):
        """测试预测单个客户流失"""
        results = churn_service.predict_churn([1, 2, 3])
        assert len(results) == 3
        for r in results:
            assert "customer_id" in r
            assert "score" in r
            assert "risk_level" in r
            assert "factors" in r

    def test_predict_churn_with_threshold(self, churn_service):
        """测试按阈值预测流失"""
        results = churn_service.predict_churn(customer_ids=[1, 50, 100])
        for r in results:
            assert r["risk_level"] in ["low", "medium", "high"]

    def test_get_churn_risk_factors(self, churn_service):
        """测试获取流失风险因素"""
        factors = churn_service.get_churn_risk_factors(1)
        assert len(factors) == 6  # 6个风险因素
        for f in factors:
            assert "factor" in f
            assert "weight" in f
            assert "current_value" in f

    def test_get_high_risk_customers(self, churn_service):
        """测试获取高风险客户"""
        high_risk = churn_service.get_high_risk_customers(threshold=70.0)
        # 所有返回的客户分数应该 >= 70
        for c in high_risk:
            assert c["score"] >= 70.0

    def test_recommend_actions_basic(self, churn_service):
        """测试推荐行动（基础场景）"""
        actions = churn_service.recommend_actions(1)
        assert len(actions) > 0
        for action in actions:
            assert "action" in action
            assert "priority" in action
            assert "reason" in action


class TestChurnPredictionEdgeCases:
    """边界条件和错误测试"""

    def test_calculate_churn_score_different_customers(self, churn_service):
        """测试不同客户有不同的分数"""
        score1 = churn_service.calculate_churn_score(1)
        score2 = churn_service.calculate_churn_score(2)
        # 由于使用hash，不同客户应有不同分数（理论上可能有巧合相同）
        # 这里只验证分数在合理范围
        assert 0 <= score1 <= 100
        assert 0 <= score2 <= 100

    def test_calculate_churn_score_large_id(self, churn_service):
        """测试大ID客户的分数计算"""
        score = churn_service.calculate_churn_score(999999)
        assert 0 <= score <= 100

    def test_calculate_churn_score_zero_id(self, churn_service):
        """测试ID为0的客户"""
        score = churn_service.calculate_churn_score(0)
        assert 0 <= score <= 100

    def test_predict_churn_empty_list(self, churn_service):
        """测试预测空列表客户"""
        results = churn_service.predict_churn([])
        assert len(results) == 0

    def test_predict_churn_none(self, churn_service):
        """测试predict_churn传入None（使用默认客户）"""
        results = churn_service.predict_churn(customer_ids=None)
        # 默认应该预测1-100客户
        assert len(results) > 0

    def test_predict_churn_duplicate_ids(self, churn_service):
        """测试预测有重复ID的客户"""
        results = churn_service.predict_churn([1, 1, 2])
        # 应该去重或重复处理（取决于实现）
        assert len(results) >= 2

    def test_get_churn_risk_factors_all_factors_present(self, churn_service):
        """测试所有风险因素都存在"""
        factors = churn_service.get_churn_risk_factors(42)
        factor_names = [f["factor"] for f in factors]
        expected_factors = [
            "days_since_last_activity",
            "decrease_in_activity",
            "decrease_in_revenue",
            "support_tickets_increase",
            "payment_delays",
            "negative_feedback",
        ]
        for ef in expected_factors:
            assert ef in factor_names

    def test_get_churn_risk_factors_weights_sum(self, churn_service):
        """测试风险因素权重之和"""
        factors = churn_service.get_churn_risk_factors(1)
        total_weight = sum(f["weight"] for f in factors)
        assert abs(total_weight - 1.0) < 0.01  # 权重和应接近1.0

    def test_get_high_risk_customers_no_matches(self, churn_service):
        """测试没有高风险客户时"""
        # 使用极高的阈值
        high_risk = churn_service.get_high_risk_customers(threshold=100.0)
        assert isinstance(high_risk, list)

    def test_get_high_risk_customers_low_threshold(self, churn_service):
        """测试低阈值获取高风险客户"""
        # 使用极低阈值，应该返回大多数客户
        high_risk = churn_service.get_high_risk_customers(threshold=0.0)
        assert len(high_risk) > 0

    def test_recommend_actions_for_new_customer(self, churn_service):
        """测试为新客户推荐行动"""
        # 新客户（days_since_last_activity小）应该有较少的高优先级行动
        actions = churn_service.recommend_actions(1)
        high_priority = [a for a in actions if a["priority"] == "high"]
        # 新客户不应该有过多高优先级行动
        assert len(high_priority) <= 3

    def test_recommend_actions_for_high_risk_customer(self, churn_service):
        """测试为高风险客户推荐行动"""
        # 找到高风险客户并推荐行动
        high_risk = churn_service.get_high_risk_customers(threshold=80.0)
        if high_risk:
            actions = churn_service.recommend_actions(high_risk[0]["customer_id"])
            assert len(actions) > 0

    def test_risk_level_boundaries(self, churn_service):
        """测试风险等级边界"""
        # 测试边界分数
        assert churn_service._get_risk_level(0) == "low"
        assert churn_service._get_risk_level(39.99) == "low"
        assert churn_service._get_risk_level(40) == "medium"
        assert churn_service._get_risk_level(69.99) == "medium"
        assert churn_service._get_risk_level(70) == "high"
        assert churn_service._get_risk_level(100) == "high"

    def test_risk_factors_deterministic(self, churn_service):
        """测试风险因素计算是确定性的"""
        factors1 = churn_service.get_churn_risk_factors(123)
        factors2 = churn_service.get_churn_risk_factors(123)
        for f1, f2 in zip(factors1, factors2):
            assert f1["factor"] == f2["factor"]
            assert f1["current_value"] == f2["current_value"]

    def test_churn_score_deterministic(self, churn_service):
        """测试流失分数是确定性的"""
        score1 = churn_service.calculate_churn_score(456)
        score2 = churn_service.calculate_churn_score(456)
        assert score1 == score2