"""营销服务单元测试"""
import pytest
from datetime import datetime

from src.services.marketing_service import MarketingService
from src.models.marketing import (
    Campaign,
    CampaignEvent,
    CampaignStatus,
    CampaignType,
    TriggerType,
)


@pytest.fixture
def marketing_service():
    """创建营销服务实例"""
    return MarketingService()


@pytest.fixture
def sample_campaign(marketing_service):
    """创建示例营销活动"""
    return marketing_service.create_campaign(
        name="测试活动",
        campaign_type=CampaignType.EMAIL,
        content="测试内容",
        created_by=1,
        subject="测试主题",
        target_audience="所有用户",
    )


class TestMarketingServiceNormal:
    """正常场景测试"""

    def test_create_campaign(self, marketing_service):
        """测试创建营销活动"""
        campaign = marketing_service.create_campaign(
            name="新品发布",
            campaign_type=CampaignType.EMAIL,
            content="新品发布通知",
            created_by=1,
            subject="新品发布",
            target_audience="所有用户",
        )
        assert campaign.id == 1
        assert campaign.name == "新品发布"
        assert campaign.type == CampaignType.EMAIL
        assert campaign.status == CampaignStatus.DRAFT

    def test_get_campaign(self, marketing_service, sample_campaign):
        """测试获取活动详情"""
        campaign = marketing_service.get_campaign(sample_campaign.id)
        assert campaign is not None
        assert campaign.id == sample_campaign.id
        assert campaign.name == sample_campaign.name

    def test_update_campaign(self, marketing_service, sample_campaign):
        """测试更新活动"""
        updated = marketing_service.update_campaign(
            sample_campaign.id,
            name="更新后的活动",
            subject="更新后的主题",
        )
        assert updated is not None
        assert updated.name == "更新后的活动"
        assert updated.subject == "更新后的主题"

    def test_launch_campaign(self, marketing_service, sample_campaign):
        """测试启动活动"""
        launched = marketing_service.launch_campaign(sample_campaign.id)
        assert launched is not None
        assert launched.status == CampaignStatus.ACTIVE

    def test_pause_campaign(self, marketing_service, sample_campaign):
        """测试暂停活动"""
        marketing_service.launch_campaign(sample_campaign.id)
        paused = marketing_service.pause_campaign(sample_campaign.id)
        assert paused is not None
        assert paused.status == CampaignStatus.PAUSED

    def test_list_campaigns(self, marketing_service):
        """测试活动列表"""
        marketing_service.create_campaign(
            name="活动1", campaign_type=CampaignType.EMAIL,
            content="内容1", created_by=1,
        )
        marketing_service.create_campaign(
            name="活动2", campaign_type=CampaignType.SMS,
            content="内容2", created_by=1,
        )
        result = marketing_service.list_campaigns(page=1, page_size=10)
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_get_campaign_stats(self, marketing_service, sample_campaign):
        """测试获取活动统计"""
        marketing_service.record_event(sample_campaign.id, 1, "sent")
        marketing_service.record_event(sample_campaign.id, 1, "opened")
        stats = marketing_service.get_campaign_stats(sample_campaign.id)
        assert stats is not None
        assert stats["sent_count"] == 1
        assert stats["open_count"] == 1

    def test_record_event(self, marketing_service, sample_campaign):
        """测试记录用户事件"""
        event = marketing_service.record_event(sample_campaign.id, 1, "sent")
        assert event is not None
        assert event.event_type == "sent"
        assert event.customer_id == 1

    def test_get_user_events(self, marketing_service, sample_campaign):
        """测试获取用户事件"""
        marketing_service.record_event(sample_campaign.id, 1, "sent")
        marketing_service.record_event(sample_campaign.id, 1, "opened")
        events = marketing_service.get_user_events(1)
        assert len(events) == 2

    def test_setup_trigger(self, marketing_service, sample_campaign):
        """测试设置触发器"""
        configured = marketing_service.setup_trigger(
            sample_campaign.id,
            trigger_type=TriggerType.USER_INACTIVE,
            trigger_days=7,
        )
        assert configured is not None
        assert configured.trigger_type == TriggerType.USER_INACTIVE
        assert configured.trigger_days == 7

    def test_get_trigger_config(self, marketing_service, sample_campaign):
        """测试获取触发器配置（通过setup_trigger设置后获取）"""
        marketing_service.setup_trigger(
            sample_campaign.id,
            trigger_type=TriggerType.PURCHASE_MADE,
            trigger_days=3,
        )
        campaign = marketing_service.get_campaign(sample_campaign.id)
        assert campaign.trigger_type == TriggerType.PURCHASE_MADE
        assert campaign.trigger_days == 3


class TestMarketingServiceEdgeCases:
    """边界条件和错误测试"""

    def test_create_campaign_minimal_fields(self, marketing_service):
        """测试只提供必需字段创建活动"""
        campaign = marketing_service.create_campaign(
            name="最小字段活动",
            campaign_type=CampaignType.SMS,
            content="内容",
            created_by=1,
        )
        assert campaign.id == 1
        assert campaign.name == "最小字段活动"

    def test_get_nonexistent_campaign(self, marketing_service):
        """测试获取不存在的活动"""
        campaign = marketing_service.get_campaign(9999)
        assert campaign is None

    def test_update_nonexistent_campaign(self, marketing_service):
        """测试更新不存在的活动"""
        result = marketing_service.update_campaign(9999, name="新名称")
        assert result is None

    def test_launch_nonexistent_campaign(self, marketing_service):
        """测试启动不存在的活动"""
        result = marketing_service.launch_campaign(9999)
        assert result is None

    def test_pause_nonexistent_campaign(self, marketing_service):
        """测试暂停不存在的活动"""
        result = marketing_service.pause_campaign(9999)
        assert result is None

    def test_list_campaigns_with_status_filter(self, marketing_service):
        """测试按状态筛选活动列表"""
        c1 = marketing_service.create_campaign(
            name="活动1", campaign_type=CampaignType.EMAIL,
            content="内容", created_by=1,
        )
        marketing_service.create_campaign(
            name="活动2", campaign_type=CampaignType.EMAIL,
            content="内容", created_by=1,
        )
        marketing_service.launch_campaign(c1.id)
        result = marketing_service.list_campaigns(status=CampaignStatus.ACTIVE)
        assert result["total"] == 1
        assert result["items"][0]["status"] == "active"

    def test_list_campaigns_with_type_filter(self, marketing_service):
        """测试按类型筛选活动列表"""
        marketing_service.create_campaign(
            name="邮件活动", campaign_type=CampaignType.EMAIL,
            content="内容", created_by=1,
        )
        marketing_service.create_campaign(
            name="短信活动", campaign_type=CampaignType.SMS,
            content="内容", created_by=1,
        )
        result = marketing_service.list_campaigns(campaign_type=CampaignType.EMAIL)
        assert result["total"] == 1

    def test_list_campaigns_pagination(self, marketing_service):
        """测试活动列表分页"""
        for i in range(25):
            marketing_service.create_campaign(
                name=f"活动{i}", campaign_type=CampaignType.EMAIL,
                content="内容", created_by=1,
            )
        result = marketing_service.list_campaigns(page=2, page_size=10)
        assert len(result["items"]) == 10
        assert result["total"] == 25
        assert result["page"] == 2

    def test_record_event_nonexistent_campaign(self, marketing_service):
        """测试为不存在的活动记录事件"""
        event = marketing_service.record_event(9999, 1, "sent")
        assert event is None

    def test_record_event_invalid_type(self, marketing_service, sample_campaign):
        """测试记录无效事件类型"""
        event = marketing_service.record_event(sample_campaign.id, 1, "invalid_type")
        assert event is not None

    def test_get_user_events_no_events(self, marketing_service):
        """测试获取没有事件的用户"""
        events = marketing_service.get_user_events(9999)
        assert len(events) == 0

    def test_setup_trigger_nonexistent_campaign(self, marketing_service):
        """测试为不存在的活动设置触发器"""
        result = marketing_service.setup_trigger(9999, TriggerType.USER_REGISTER, 5)
        assert result is None

    def test_get_campaign_stats_no_sent(self, marketing_service, sample_campaign):
        """测试没有发送记录的活动统计"""
        stats = marketing_service.get_campaign_stats(sample_campaign.id)
        assert stats["sent_count"] == 0
        assert stats["open_rate"] == 0
        assert stats["click_rate"] == 0