"""营销服务"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.models.marketing import (
    Campaign,
    CampaignEvent,
    CampaignStatus,
    CampaignType,
    TriggerType,
)
from src.models.response import ApiResponse, PaginatedData


class MarketingService:
    """营销服务"""

    def __init__(self):
        self._campaigns: Dict[int, Campaign] = {}
        self._events: Dict[int, List[CampaignEvent]] = {}
        self._next_id: int = 1

    def create_campaign(
        self,
        name: str,
        campaign_type: CampaignType,
        content: str,
        created_by: int,
        **kwargs
    ) -> ApiResponse[Campaign]:
        """创建营销活动"""
        now = datetime.now()
        campaign = Campaign(
            id=self._next_id,
            name=name,
            type=campaign_type,
            status=CampaignStatus.DRAFT,
            subject=kwargs.get("subject"),
            content=content,
            target_audience=kwargs.get("target_audience", ""),
            trigger_type=kwargs.get("trigger_type"),
            trigger_days=kwargs.get("trigger_days"),
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._campaigns[self._next_id] = campaign
        self._next_id += 1
        if campaign.id is not None:
            self._events[campaign.id] = []
        return ApiResponse.success(data=campaign, message='营销活动创建成功')

    def get_campaign(self, campaign_id: int) -> ApiResponse[Campaign]:
        """获取活动详情"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)
        return ApiResponse.success(data=campaign)

    def update_campaign(self, campaign_id: int, **kwargs) -> ApiResponse[Campaign]:
        """更新活动"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        for key, value in kwargs.items():
            if hasattr(campaign, key):
                setattr(campaign, key, value)
        campaign.updated_at = datetime.now()
        return ApiResponse.success(data=campaign, message='营销活动更新成功')

    def launch_campaign(self, campaign_id: int) -> ApiResponse[Campaign]:
        """启动活动"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        campaign.status = CampaignStatus.ACTIVE
        campaign.updated_at = datetime.now()
        return ApiResponse.success(data=campaign, message='营销活动已启动')

    def pause_campaign(self, campaign_id: int) -> ApiResponse[Campaign]:
        """暂停活动"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = datetime.now()
        return ApiResponse.success(data=campaign, message='营销活动已暂停')

    def get_campaign_stats(self, campaign_id: int) -> ApiResponse[Dict[str, Any]]:
        """获取活动统计"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        sent = campaign.sent_count
        open_rate = (campaign.open_count / sent * 100) if sent > 0 else 0
        click_rate = (campaign.click_count / sent * 100) if sent > 0 else 0

        stats = {
            "campaign_id": campaign_id,
            "sent_count": campaign.sent_count,
            "open_count": campaign.open_count,
            "click_count": campaign.click_count,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
        }
        return ApiResponse.success(data=stats)

    def list_campaigns(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[CampaignStatus] = None,
        campaign_type: Optional[CampaignType] = None,
    ) -> ApiResponse[PaginatedData[Campaign]]:
        """活动列表"""
        filtered = list(self._campaigns.values())

        if status:
            filtered = [c for c in filtered if c.status == status]
        if campaign_type:
            filtered = [c for c in filtered if c.type == campaign_type]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered[start:end]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message='查询成功'
        )

    def record_event(
        self,
        campaign_id: int,
        customer_id: int,
        event_type: str,
    ) -> ApiResponse[CampaignEvent]:
        """记录用户事件"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        event = CampaignEvent(
            id=len(self._events.get(campaign_id, [])) + 1,
            campaign_id=campaign_id,
            customer_id=customer_id,
            event_type=event_type,
            created_at=datetime.now(),
        )

        if campaign_id not in self._events:
            self._events[campaign_id] = []
        self._events[campaign_id].append(event)

        # 更新计数
        if event_type == "sent":
            campaign.sent_count += 1
        elif event_type == "opened":
            campaign.open_count += 1
        elif event_type == "clicked":
            campaign.click_count += 1

        return ApiResponse.success(data=event, message='事件记录成功')

    def get_user_events(self, customer_id: int) -> List[CampaignEvent]:
        """获取用户的所有营销事件"""
        result = []
        for events in self._events.values():
            for event in events:
                if event.customer_id == customer_id:
                    result.append(event)
        return result

    def setup_trigger(
        self,
        campaign_id: int,
        trigger_type: TriggerType,
        trigger_days: Optional[int] = None,
    ) -> ApiResponse[Campaign]:
        """设置触发器"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return ApiResponse.error(message='营销活动不存在', code=1404)

        campaign.trigger_type = trigger_type
        campaign.trigger_days = trigger_days
        campaign.updated_at = datetime.now()
        return ApiResponse.success(data=campaign, message='触发器设置成功')
