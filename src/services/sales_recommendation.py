"""
销售推荐服务
使用协同过滤 + 规则进行销售推荐
"""

import hashlib
import random
from dataclasses import dataclass


@dataclass
class ProductRecommendation:
    """产品推荐"""

    product_id: str
    product_name: str
    score: float
    reason: str
    price_increase: int | None = None


@dataclass
class SalesActionRecommendation:
    """下一步销售行动推荐"""

    action: str
    target: str
    reason: str
    confidence: float


@dataclass
class SimilarCustomer:
    """相似客户摘要"""

    customer_id: int
    current_tier: str
    monthly_revenue: int
    usage_rate: float
    satisfaction_score: float


class SalesRecommendationService:
    """销售推荐服务"""

    # 产品目录
    PRODUCTS = {
        "basic": {"name": "基础版", "price": 100, "tier": 1},
        "standard": {"name": "标准版", "price": 300, "tier": 2},
        "premium": {"name": "高级版", "price": 500, "tier": 3},
        "enterprise": {"name": "企业版", "price": 1000, "tier": 4},
    }

    # 交叉销售产品映射
    CROSS_SELL_MAP = {
        "basic": ["standard", "premium"],
        "standard": ["premium", "basic"],
        "premium": ["enterprise", "standard"],
        "enterprise": ["premium"],
    }

    def __init__(self):
        """初始化服务"""
        self._customer_cache: dict[int, dict] = {}

    def _get_mock_customer_data(self, tenant_id: int, customer_id: int) -> dict:
        """获取模拟客户数据"""
        import hashlib

        seed = int(hashlib.sha256(f"{tenant_id}:{customer_id}".encode()).hexdigest()[:8], 16)

        tier_index = seed % 4
        tiers = list(self.PRODUCTS.keys())
        current_tier = tiers[tier_index]

        return {
            "customer_id": customer_id,
            "current_tier": current_tier,
            "usage_rate": (seed % 80 + 20) / 100.0,
            "monthly_revenue": self.PRODUCTS[current_tier]["price"],
            "purchase_history": random.sample(tiers, (seed % 3) + 1),
            "browsing_history": random.sample(tiers, (seed % 4) + 1),
            "satisfaction_score": (seed % 100) / 100.0,
        }

    def _get_similar_customers_by_tier(self, tenant_id: int, tier: str, limit: int = 5) -> list[int]:
        """基于层级获取相似客户ID"""
        random.seed(42)  # 固定随机种子保证一致性
        tier_index = list(self.PRODUCTS.keys()).index(tier)
        similar = [
            i
            for i in range(1, 1000)
            if int(hashlib.sha256(f"{tenant_id}:{i}".encode()).hexdigest()[:8], 16) % 4 == tier_index
        ][:limit]
        random.seed()  # 重置随机种子
        return similar

    def get_next_best_action(self, tenant_id: int, customer_id: int) -> SalesActionRecommendation:
        """
        获取最佳下一步行动
        """
        data = self._get_mock_customer_data(tenant_id, customer_id)
        current_tier = data["current_tier"]
        usage_rate = data["usage_rate"]
        satisfaction = data["satisfaction_score"]

        # 决策逻辑
        if usage_rate > 0.8 and current_tier != "enterprise":
            action = "up_sell"
            target = list(self.PRODUCTS.keys())[list(self.PRODUCTS.keys()).index(current_tier) + 1]
            reason = "高使用率，推荐升级"
        elif satisfaction < 0.4:
            action = "retention"
            target = current_tier
            reason = "满意度低，需要客户挽留"
        elif len(data["browsing_history"]) > 2:
            action = "cross_sell"
            target = (
                [p for p in data["browsing_history"] if p != current_tier][0]
                if [p for p in data["browsing_history"] if p != current_tier]
                else current_tier
            )
            reason = "客户浏览了其他产品"
        else:
            action = "maintain"
            target = current_tier
            reason = "保持当前状态"

        return SalesActionRecommendation(
            action=action,
            target=target,
            reason=reason,
            confidence=round(random.uniform(0.6, 0.95), 2),  # noqa: S311 - non-security recommendation scoring
        )

    def recommend_cross_sell(self, tenant_id: int, customer_id: int) -> list[ProductRecommendation]:
        """
        推荐交叉销售产品
        基于：购买历史、浏览历史、相似客户
        """
        data = self._get_mock_customer_data(tenant_id, customer_id)
        current_tier = data["current_tier"]

        # 获取推荐产品
        recommendations = []

        # 1. 基于浏览历史的推荐
        browsing_scores = {}
        for product in data["browsing_history"]:
            browsing_scores[product] = browsing_scores.get(product, 0) + 0.3

        # 2. 基于购买历史的相关产品
        for product in data["purchase_history"]:
            if product in self.CROSS_SELL_MAP:
                for related in self.CROSS_SELL_MAP[product]:
                    browsing_scores[related] = browsing_scores.get(related, 0) + 0.2

        # 3. 基于相似客户的推荐
        similar_customers = self._get_similar_customers_by_tier(tenant_id, current_tier, limit=10)
        for sim_cid in similar_customers:
            sim_data = self._get_mock_customer_data(tenant_id, sim_cid)
            for product in sim_data["purchase_history"]:
                if product != current_tier:
                    browsing_scores[product] = browsing_scores.get(product, 0) + 0.15

        # 生成推荐列表
        for product_id, score in sorted(browsing_scores.items(), key=lambda x: x[1], reverse=True):
            if product_id != current_tier and score > 0:
                product_info = self.PRODUCTS[product_id]
                recommendations.append(
                    ProductRecommendation(
                        product_id=product_id,
                        product_name=product_info["name"],
                        score=round(min(score, 1.0), 2),
                        reason=self._get_cross_sell_reason(product_id, data),
                    )
                )

        return recommendations[:5]  # 最多返回5个推荐

    def _get_cross_sell_reason(self, product_id: str, data: dict) -> str:
        """生成推荐理由"""
        reasons = []

        if product_id in data["browsing_history"]:
            reasons.append("客户浏览过此产品")

        if product_id in self.CROSS_SELL_MAP.get(data["current_tier"], []):
            reasons.append("与当前产品互补")

        return "; ".join(reasons) if reasons else "提升用户体验"

    def recommend_up_sell(self, tenant_id: int, customer_id: int) -> list[ProductRecommendation]:
        """
        推荐升级销售
        基于：当前套餐、使用量
        """
        data = self._get_mock_customer_data(tenant_id, customer_id)
        current_tier = data["current_tier"]
        usage_rate = data["usage_rate"]

        current_tier_index = list(self.PRODUCTS.keys()).index(current_tier)

        # 只有非最高级别才推荐升级
        recommendations = []
        if current_tier_index < len(self.PRODUCTS) - 1:
            next_tier = list(self.PRODUCTS.keys())[current_tier_index + 1]
            next_product = self.PRODUCTS[next_tier]

            score = usage_rate * 0.7 + data["satisfaction_score"] * 0.3

            recommendations.append(
                ProductRecommendation(
                    product_id=next_tier,
                    product_name=next_product["name"],
                    score=round(min(score, 1.0), 2),
                    reason=f"使用率 {int(usage_rate * 100)}%，推荐升级到{next_product['name']}",
                    price_increase=next_product["price"] - self.PRODUCTS[current_tier]["price"],
                )
            )

        return recommendations

    def get_similar_customers(self, tenant_id: int, customer_id: int, limit: int = 5) -> list[SimilarCustomer]:
        """
        获取相似客户
        用于：成功案例推荐
        """
        data = self._get_mock_customer_data(tenant_id, customer_id)
        current_tier = data["current_tier"]

        similar_ids = self._get_similar_customers_by_tier(tenant_id, current_tier, limit)

        similar_customers = []
        for cid in similar_ids:
            cid_data = self._get_mock_customer_data(tenant_id, cid)
            similar_customers.append(
                SimilarCustomer(
                    customer_id=cid,
                    current_tier=cid_data["current_tier"],
                    monthly_revenue=cid_data["monthly_revenue"],
                    usage_rate=cid_data["usage_rate"],
                    satisfaction_score=cid_data["satisfaction_score"],
                )
            )

        return similar_customers

    def predict_conversion_probability(self, opportunity_id: int) -> float:
        """
        预测商机成交概率（增强版）
        结合：历史数据、市场情绪、竞争分析
        """
        import hashlib

        seed = int(hashlib.sha256(str(opportunity_id).encode()).hexdigest()[:8], 16)

        # 基础概率 (历史数据)
        base_prob = 0.3 + (seed % 50) / 100.0

        # 市场情绪因子 (模拟)
        market_sentiment = 0.8 + (seed % 40) / 100.0

        # 竞争因子 (模拟)
        competition_factor = 0.7 + (seed % 60) / 100.0

        # 综合计算
        conversion_prob = base_prob * market_sentiment * competition_factor

        return round(min(max(conversion_prob, 0.0), 1.0), 2)
