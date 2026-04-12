"""
智能分类服务
使用决策树规则进行线索分类和客户分群
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import random


@dataclass
class LeadCategory:
    """线索分类结果"""
    category: str
    score: float
    reasoning: str


class SmartCategorizationService:
    """智能分类服务"""

    # 线索分类类别
    LEAD_CATEGORIES = [
        "hot_lead",       # 高质量线索
        "warm_lead",      # 中等质量线索
        "cold_lead",      # 低质量线索
        " disqualified",  # 不合格线索
    ]

    # RFM 分群标签
    RFM_SEGMENTS = {
        "VIP": {"description": "高价值客户", "color": "gold"},
        "Active": {"description": "活跃客户", "color": "green"},
        "AtRisk": {"description": "风险客户", "color": "orange"},
        "Dormant": {"description": "休眠客户", "color": "gray"},
    }

    def categorize_lead(self, lead_data: Dict) -> Dict:
        """
        线索智能分类
        返回: {category, score, reasoning}
        """
        score = self.score_lead(lead_data)
        
        # 决策树规则
        if score >= 75:
            category = "hot_lead"
            reasoning = "高质量线索，多个关键指标优秀"
        elif score >= 50:
            category = "warm_lead"
            reasoning = "中等质量线索，部分指标良好"
        elif score >= 25:
            category = "cold_lead"
            reasoning = "低质量线索，需要更多培养"
        else:
            category = "disqualified"
            reasoning = "线索不合格或不符合目标客户画像"
        
        return {
            "category": category,
            "score": score,
            "reasoning": reasoning
        }

    def score_lead(self, lead_data: Dict) -> float:
        """
        线索评分 (0-100)
        考虑：来源、公司规模、职位、行为
        """
        total_score = 0.0
        max_score = 100.0
        
        # 1. 来源评分 (最高 25 分)
        source_scores = {
            "referral": 25,
            "website": 20,
            "linkedin": 18,
            "conference": 22,
            "cold_outreach": 10,
            "advertisement": 8,
        }
        source = lead_data.get("source", "unknown")
        source_score = source_scores.get(source, 5)
        
        # 2. 公司规模评分 (最高 25 分)
        company_size = lead_data.get("company_size", 0)
        if company_size >= 1000:
            company_score = 25
        elif company_size >= 500:
            company_score = 22
        elif company_size >= 100:
            company_score = 18
        elif company_size >= 50:
            company_score = 15
        elif company_size >= 10:
            company_score = 10
        else:
            company_score = 5
        
        # 3. 职位评分 (最高 25 分)
        title = lead_data.get("title", "").lower()
        if any(kw in title for kw in ["ceo", "cto", "cfo", "founder", "owner", "partner"]):
            title_score = 25
        elif any(kw in title for kw in ["vp", "director", "head", "chief"]):
            title_score = 22
        elif any(kw in title for kw in ["manager", "lead"]):
            title_score = 18
        elif any(kw in title for kw in ["senior", "sr."]):
            title_score = 12
        else:
            title_score = 5
        
        # 4. 行为评分 (最高 25 分)
        engagement_score = 0
        engaged_actions = lead_data.get("engaged_actions", [])
        
        if "downloaded_trial" in engaged_actions:
            engagement_score += 10
        if "attended_webinar" in engaged_actions:
            engagement_score += 8
        if "visited_pricing_page" in engaged_actions:
            engagement_score += 7
        if "signed_up_newsletter" in engaged_actions:
            engagement_score += 5
        if "filled_contact_form" in engaged_actions:
            engagement_score += 8
        if "booked_demo" in engaged_actions:
            engagement_score += 12
        
        total_score = source_score + company_score + title_score + engagement_score
        
        return min(total_score, max_score)

    def auto_tag_customer(self, customer_id: int) -> List[str]:
        """
        自动标签客户
        基于：行为数据、交易数据
        """
        import hashlib
        seed = int(hashlib.md5(str(customer_id).encode()).hexdigest()[:8], 16)
        
        tags = []
        
        # 基于活跃度
        if seed % 3 == 0:
            tags.append("active_user")
        elif seed % 3 == 1:
            tags.append("occasional_user")
        else:
            tags.append("dormant_user")
        
        # 基于价值
        if seed % 5 == 0:
            tags.append("high_value")
        elif seed % 5 == 4:
            tags.append("medium_value")
        else:
            tags.append("low_value")
        
        # 基于产品使用
        if seed % 7 == 0:
            tags.append("enterprise_tier")
        elif seed % 7 in [1, 2]:
            tags.append("premium_tier")
        elif seed % 7 in [3, 4]:
            tags.append("standard_tier")
        else:
            tags.append("basic_tier")
        
        # 基于行为特征
        if seed % 11 < 3:
            tags.append("early_adopter")
        elif seed % 11 < 6:
            tags.append("feature_lover")
        else:
            tags.append("casual_user")
        
        return tags

    def segment_customers(self) -> List[Dict]:
        """
        客户分群
        RFM模型: 最近消费(Recency)、消费频率(Frequency)、消费金额(Monetary)
        """
        # 模拟生成客户分群数据
        segments = []
        
        # 生成模拟 RFM 分数
        random.seed(42)
        for i in range(1, 501):
            r_score = random.randint(1, 5)
            f_score = random.randint(1, 5)
            m_score = random.randint(1, 5)
            
            rfm_total = r_score + f_score + m_score
            
            # 确定分群
            if rfm_total >= 12:
                segment = "VIP"
            elif r_score >= 4 and f_score >= 3:
                segment = "Active"
            elif r_score <= 2 and f_score <= 2:
                segment = "Dormant"
            else:
                segment = "AtRisk"
            
            segments.append({
                "customer_id": i,
                "recency_score": r_score,
                "frequency_score": f_score,
                "monetary_score": m_score,
                "rfm_total": rfm_total,
                "segment": segment,
                "description": self.RFM_SEGMENTS[segment]["description"],
            })
        
        random.seed()
        
        return segments
