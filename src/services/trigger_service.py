"""自动化触发器"""
from models.marketing import TriggerType
from pkg.errors.app_exceptions import NotFoundException


class TriggerService:
    """自动化触发器 — orchestrates MarketingService (real DB)."""

    TRIGGERS = {
        TriggerType.USER_REGISTER: "欢迎邮件",
        TriggerType.USER_INACTIVE: "沉睡用户唤醒",
        TriggerType.PURCHASE_MADE: "购买感谢",
    }

    def __init__(self, marketing_service=None):
        self._marketing_service = marketing_service

    async def check_triggers(self, event_type: str, customer_data: dict, tenant_id: int = 0) -> list[int]:
        """检查触发的活动"""
        event_to_trigger = {
            "user_register": TriggerType.USER_REGISTER,
            "user_inactive": TriggerType.USER_INACTIVE,
            "purchase_made": TriggerType.PURCHASE_MADE,
        }

        trigger_type = event_to_trigger.get(event_type)
        if not trigger_type:
            return []

        if not self._marketing_service:
            return []

        campaigns, _ = await self._marketing_service.list_campaigns(
            tenant_id=tenant_id, page=1, page_size=10000,
        )
        return [c.id for c in campaigns if c.trigger_type == trigger_type.value]

    async def execute_trigger(self, campaign_id: int, customer_ids: list[int], tenant_id: int = 0) -> dict:
        """执行触发"""
        if not self._marketing_service:
            return {"success": False, "message": "Marketing service not configured"}

        try:
            campaign = await self._marketing_service.get_campaign(campaign_id, tenant_id=tenant_id)
        except NotFoundException:
            return {"success": False, "message": "Campaign not found"}

        if campaign.trigger_type is None:
            return {"success": False, "message": "No trigger configured"}

        trigger_enum = TriggerType(campaign.trigger_type) if isinstance(campaign.trigger_type, str) else campaign.trigger_type
        trigger_name = self.TRIGGERS.get(trigger_enum, "未知触发")
        sent_count = 0

        for customer_id in customer_ids:
            event = await self._marketing_service.record_event(
                campaign_id=campaign_id,
                customer_id=customer_id,
                event_type="sent",
                tenant_id=tenant_id,
            )
            if event:
                sent_count += 1

        return {
            "success": True,
            "campaign_id": campaign_id,
            "trigger_type": campaign.trigger_type if isinstance(campaign.trigger_type, str) else campaign.trigger_type.value,
            "trigger_name": trigger_name,
            "target_customer_count": len(customer_ids),
            "sent_count": sent_count,
        }
