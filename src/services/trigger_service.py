"""自动化触发器"""
from typing import Dict, List, Optional
from src.models.marketing import TriggerType


class TriggerService:
    """自动化触发器"""

    TRIGGERS = {
        TriggerType.USER_REGISTER: "欢迎邮件",
        TriggerType.USER_INACTIVE: "沉睡用户唤醒",
        TriggerType.PURCHASE_MADE: "购买感谢",
    }

    def __init__(self, marketing_service=None):
        self._marketing_service = marketing_service

    def check_triggers(self, event_type: str, customer_data: Dict) -> List[int]:
        """检查触发的活动"""
        triggered_campaign_ids = []

        # 映射事件类型到触发器类型
        event_to_trigger = {
            "user_register": TriggerType.USER_REGISTER,
            "user_inactive": TriggerType.USER_INACTIVE,
            "purchase_made": TriggerType.PURCHASE_MADE,
        }

        trigger_type = event_to_trigger.get(event_type)
        if not trigger_type:
            return []

        # 检查所有活动，找到匹配触发类型的活动
        if self._marketing_service:
            campaigns_response = self._marketing_service.list_campaigns(
                page=1, page_size=1000
            )
            # campaigns_response is an ApiResponse; extract items from data.paginated_data
            if campaigns_response.data is not None:
                campaigns = campaigns_response.data.items
            else:
                campaigns = []

            for campaign_data in campaigns:
                campaign_trigger = getattr(campaign_data, "trigger_type", None)
                if campaign_trigger is not None and campaign_trigger == trigger_type.value:
                    triggered_campaign_ids.append(campaign_data.id)

        return triggered_campaign_ids

    def execute_trigger(self, campaign_id: int, customer_ids: List[int]) -> Dict:
        """执行触发"""
        if not self._marketing_service:
            return {"success": False, "message": "Marketing service not configured"}

        campaign_response = self._marketing_service.get_campaign(campaign_id)
        if not campaign_response or not campaign_response.data:
            return {"success": False, "message": "Campaign not found"}

        campaign = campaign_response.data
        if campaign.trigger_type is None:
            return {"success": False, "message": "No trigger configured"}

        trigger_name = self.TRIGGERS.get(campaign.trigger_type, "未知触发")
        sent_count = 0

        for customer_id in customer_ids:
            event_response = self._marketing_service.record_event(
                campaign_id=campaign_id,
                customer_id=customer_id,
                event_type="sent",
            )
            if event_response and event_response.status.value == "success":
                sent_count += 1

        return {
            "success": True,
            "campaign_id": campaign_id,
            "trigger_type": campaign.trigger_type.value,
            "trigger_name": trigger_name,
            "target_customer_count": len(customer_ids),
            "sent_count": sent_count,
        }
