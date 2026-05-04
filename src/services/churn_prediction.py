"""
客户流失预测服务
使用规则-based 模型预测客户流失风险
"""

from dataclasses import dataclass


@dataclass
class ChurnRiskFactor:
    """流失风险因素"""
    factor: str
    weight: float
    current_value: float
    description: str


class ChurnPredictionService:
    """客户流失预测服务"""

    # 流失风险因素及其权重
    RISK_FACTORS = [
        "days_since_last_activity",  # 距上次活动天数
        "decrease_in_activity",      # 活动频率下降
        "decrease_in_revenue",       # 收入下降
        "support_tickets_increase",  # 工单增加
        "payment_delays",            # 付款延迟
        "negative_feedback",         # 负面反馈
    ]

    # 因素权重配置
    FACTOR_WEIGHTS = {
        "days_since_last_activity": 0.20,
        "decrease_in_activity": 0.18,
        "decrease_in_revenue": 0.22,
        "support_tickets_increase": 0.15,
        "payment_delays": 0.15,
        "negative_feedback": 0.10,
    }

    def __init__(self):
        """初始化服务"""
        self._customer_cache: dict[int, dict] = {}

    def _get_mock_customer_data(self, customer_id: int) -> dict:
        """获取模拟客户数据"""
        # 模拟数据，实际环境应从数据库获取
        import hashlib
        seed = int(hashlib.md5(str(customer_id).encode()).hexdigest()[:8], 16)

        return {
            "customer_id": customer_id,
            "days_since_last_activity": (seed % 60) + 1,
            "activity_trend": (seed % 100) / 100.0,
            "revenue_trend": ((seed % 100) - 50) / 50.0,
            "support_tickets_count": (seed % 10),
            "payment_delays_count": (seed % 5),
            "negative_feedback_score": (seed % 100) / 100.0,
        }

    def calculate_churn_score(self, customer_id: int) -> float:
        """
        计算流失风险分数 (0-100)
        越高越可能流失
        """
        data = self._get_mock_customer_data(customer_id)

        # 各因素得分计算
        scores = {}

        # 1. 距上次活动天数 (越大风险越高)
        days = data["days_since_last_activity"]
        scores["days_since_last_activity"] = min(days / 90 * 100, 100)

        # 2. 活动频率下降 (下降越多风险越高)
        activity_trend = data["activity_trend"]
        scores["decrease_in_activity"] = max(0, (0.5 - activity_trend) * 200)

        # 3. 收入下降 (下降越多风险越高)
        revenue_trend = data["revenue_trend"]
        scores["decrease_in_revenue"] = max(0, (0 - revenue_trend) * 100)

        # 4. 工单增加 (工单越多风险越高)
        tickets = data["support_tickets_count"]
        scores["support_tickets_increase"] = min(tickets / 10 * 100, 100)

        # 5. 付款延迟 (延迟越多风险越高)
        delays = data["payment_delays_count"]
        scores["payment_delays"] = min(delays / 5 * 100, 100)

        # 6. 负面反馈 (负面反馈越多风险越高)
        feedback = data["negative_feedback_score"]
        scores["negative_feedback"] = feedback * 100

        # 加权计算总分
        total_score = sum(
            scores[factor] * self.FACTOR_WEIGHTS[factor]
            for factor in self.RISK_FACTORS
        )

        return round(total_score, 2)

    def predict_churn(self, customer_ids: list[int] = None) -> list[dict]:
        """
        批量预测流失风险
        返回: [{customer_id, score, risk_level, factors}]
        """
        if customer_ids is None:
            # 默认预测前100个客户
            customer_ids = list(range(1, 101))

        results = []
        for cid in customer_ids:
            score = self.calculate_churn_score(cid)
            risk_level = self._get_risk_level(score)
            factors = self.get_churn_risk_factors(cid)

            results.append({
                "customer_id": cid,
                "score": score,
                "risk_level": risk_level,
                "factors": factors,
            })

        return results

    def _get_risk_level(self, score: float) -> str:
        """根据分数确定风险等级"""
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

    def get_churn_risk_factors(self, customer_id: int) -> list[dict]:
        """
        获取流失风险因素详情
        返回: [{factor, weight, current_value}]
        """
        data = self._get_mock_customer_data(customer_id)

        # 各因素当前值计算
        current_values = {
            "days_since_last_activity": data["days_since_last_activity"],
            "decrease_in_activity": round(data["activity_trend"] * 100, 2),
            "decrease_in_revenue": round(data["revenue_trend"] * 100, 2),
            "support_tickets_increase": data["support_tickets_count"],
            "payment_delays": data["payment_delays_count"],
            "negative_feedback": round(data["negative_feedback_score"] * 100, 2),
        }

        factor_details = []
        for factor in self.RISK_FACTORS:
            factor_details.append({
                "factor": factor,
                "weight": self.FACTOR_WEIGHTS[factor],
                "current_value": current_values[factor],
            })

        return factor_details

    def get_high_risk_customers(self, threshold: float = 70.0) -> list[dict]:
        """
        获取高风险客户列表
        """
        # 获取所有客户预测结果
        all_results = self.predict_churn(list(range(1, 1001)))

        # 过滤高风险客户
        high_risk = [
            r for r in all_results
            if r["score"] >= threshold
        ]

        # 按分数降序排序
        high_risk.sort(key=lambda x: x["score"], reverse=True)

        return high_risk

    def recommend_actions(self, customer_id: int) -> list[dict]:
        """
        根据流失风险推荐行动
        返回: [{action, priority, reason}]
        """
        score = self.calculate_churn_score(customer_id)
        data = self._get_mock_customer_data(customer_id)
        risk_level = self._get_risk_level(score)

        actions = []

        # 基于风险因素生成行动建议
        if data["days_since_last_activity"] > 30:
            actions.append({
                "action": "主动联系客户",
                "priority": "high" if risk_level == "high" else "medium",
                "reason": f"客户已 {data['days_since_last_activity']} 天无活动"
            })

        if data["activity_trend"] < 0.3:
            actions.append({
                "action": "发送个性化优惠",
                "priority": "high" if risk_level == "high" else "medium",
                "reason": "活动频率显著下降，需要激活"
            })

        if data["revenue_trend"] < -0.2:
            actions.append({
                "action": "提供升级方案",
                "priority": "medium",
                "reason": "收入呈下降趋势"
            })

        if data["support_tickets_count"] > 5:
            actions.append({
                "action": "优先处理客户问题",
                "priority": "high",
                "reason": f"客户有 {data['support_tickets_count']} 个未解决工单"
            })

        if data["payment_delays_count"] > 2:
            actions.append({
                "action": "联系客户确认付款",
                "priority": "medium",
                "reason": f"客户有 {data['payment_delays_count']} 次付款延迟"
            })

        if data["negative_feedback_score"] > 0.5:
            actions.append({
                "action": "进行客户满意度回访",
                "priority": "high",
                "reason": "客户反馈负面情绪较高"
            })

        # 默认行动
        if not actions:
            actions.append({
                "action": "定期维护关系",
                "priority": "low",
                "reason": "客户状态正常，保持常规维护"
            })

        return actions
