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
    result = marketing_service.create_campaign(
        name="测试活动",
        campaign_type=CampaignType.EMAIL,
        content="测试内容",
        created_by=1,
        subject="测试主题",
        target_audience="所有用户",
    )
    return result.data.id


class TestMarketingServiceNormal:
    """正常场景测试"""

    def test_create_campaign(self, marketing_service):
        """测试创建营销活动"""
        result = marketing_service.create_campaign(
            name="新品发布",
            campaign_type=CampaignType.EMAIL,
            content="新品发布通知",
            created_by=1,
            subject="新品发布",
            target_audience="所有用户",
        )
        assert bool(result) is True
        assert result.data.name == "新品发布"
        assert result.data.type == CampaignType.EMAIL
        assert result.data.status == CampaignStatus.DRAFT

    def test_get_campaign(self, marketing_service, sample_campaign):
        """测试获取活动详情"""
        result = marketing_service.get_campaign(sample_campaign)
        assert bool(result) is True
        assert result.data.name == "测试活动"

    def test_update_campaign(self, marketing_service, sample_campaign):
        """测试更新活动"""
        result = marketing_service.update_campaign(
            sample_campaign,
            name="更新后的活动",
            subject="更新后的主题",
        )
        assert bool(result) is True
        assert result.data.name == "更新后的活动"
        assert result.data.subject == "更新后的主题"

    def test_launch_campaign(self, marketing_service, sample_campaign):
        """测试启动活动"""
        result = marketing_service.launch_campaign(sample_campaign)
        assert bool(result) is True
        assert result.data.status == CampaignStatus.ACTIVE

    def test_pause_campaign(self, marketing_service, sample_campaign):
        """测试暂停活动"""
        marketing_service.launch_campaign(sample_campaign)
        result = marketing_service.pause_campaign(sample_campaign)
        assert bool(result) is True
        assert result.data.status == CampaignStatus.PAUSED

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
        assert bool(result) is True
        assert result.data.total == 2
        assert len(result.data.items) == 2

    def test_get_campaign_stats(self, marketing_service, sample_campaign):
        """测试获取活动统计"""
        marketing_service.record_event(sample_campaign, 1, "sent")
        marketing_service.record_event(sample_campaign, 1, "opened")
        result = marketing_service.get_campaign_stats(sample_campaign)
        assert bool(result) is True
        assert result.data["sent_count"] == 1
        assert result.data["open_count"] == 1

    def test_record_event(self, marketing_service, sample_campaign):
        """测试记录用户事件"""
        result = marketing_service.record_event(sample_campaign, 1, "sent")
        assert bool(result) is True
        assert result.data.event_type == "sent"
        assert result.data.customer_id == 1

    def test_get_user_events(self, marketing_service, sample_campaign):
        """测试获取用户事件"""
        marketing_service.record_event(sample_campaign, 1, "sent")
        marketing_service.record_event(sample_campaign, 1, "opened")
        result = marketing_service.get_user_events(1)
        assert len(result) == 2

    def test_setup_trigger(self, marketing_service, sample_campaign):
        """测试设置触发器"""
        result = marketing_service.setup_trigger(
            sample_campaign,
            trigger_type=TriggerType.USER_INACTIVE,
            trigger_days=7,
        )
        assert bool(result) is True
        assert result.data.trigger_type == TriggerType.USER_INACTIVE
        assert result.data.trigger_days == 7


class TestMarketingServiceEdgeCases:
    """边界条件和错误测试"""

    def test_create_campaign_minimal_fields(self, marketing_service):
        """测试只提供必需字段创建活动"""
        result = marketing_service.create_campaign(
            name="最小字段活动",
            campaign_type=CampaignType.SMS,
            content="内容",
            created_by=1,
        )
        assert bool(result) is True
        assert result.data.name == "最小字段活动"

    def test_get_nonexistent_campaign(self, marketing_service):
        """测试获取不存在的活动"""
        result = marketing_service.get_campaign(9999)
        assert bool(result) is False

    def test_update_nonexistent_campaign(self, marketing_service):
        """测试更新不存在的活动"""
        result = marketing_service.update_campaign(9999, name="新名称")
        assert bool(result) is False

    def test_launch_nonexistent_campaign(self, marketing_service):
        """测试启动不存在的活动"""
        result = marketing_service.launch_campaign(9999)
        assert bool(result) is False

    def test_pause_nonexistent_campaign(self, marketing_service):
        """测试暂停不存在的活动"""
        result = marketing_service.pause_campaign(9999)
        assert bool(result) is False

    def test_list_campaigns_with_status_filter(self, marketing_service):
        """测试按状态筛选活动列表"""
        r1 = marketing_service.create_campaign(
            name="活动1", campaign_type=CampaignType.EMAIL,
            content="内容", created_by=1,
        )
        c1_id = r1.data.id
        marketing_service.create_campaign(
            name="活动2", campaign_type=CampaignType.EMAIL,
            content="内容", created_by=1,
        )
        marketing_service.launch_campaign(c1_id)
        result = marketing_service.list_campaigns(status=CampaignStatus.ACTIVE)
        assert bool(result) is True
        assert result.data.total == 1

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
        assert bool(result) is True
        assert result.data.total == 1

    def test_list_campaigns_pagination(self, marketing_service):
        """测试活动列表分页"""
        for i in range(25):
            marketing_service.create_campaign(
                name=f"活动{i}", campaign_type=CampaignType.EMAIL,
                content="内容", created_by=1,
            )
        result = marketing_service.list_campaigns(page=2, page_size=10)
        assert bool(result) is True
        assert len(result.data.items) == 10
        assert result.data.total == 25
        assert result.data.page == 2

    def test_record_event_nonexistent_campaign(self, marketing_service):
        """测试为不存在的活动记录事件"""
        result = marketing_service.record_event(9999, 1, "sent")
        assert bool(result) is False

    def test_get_user_events_no_events(self, marketing_service):
        """测试获取没有事件的用户"""
        result = marketing_service.get_user_events(9999)
        assert len(result) == 0

    def test_setup_trigger_nonexistent_campaign(self, marketing_service):
        """测试为不存在的活动设置触发器"""
        result = marketing_service.setup_trigger(9999, TriggerType.USER_REGISTER, 5)
        assert bool(result) is False

    def test_get_campaign_stats_no_sent(self, marketing_service, sample_campaign):
        """测试没有发送记录的活动统计"""
        result = marketing_service.get_campaign_stats(sample_campaign)
        assert bool(result) is True
        assert result.data["sent_count"] == 0
