"""Unit tests for MarketingService."""
import pytest
from src.services.marketing_service import MarketingService


@pytest.fixture
def marketing_service():
    return MarketingService()


@pytest.fixture
async def sample_campaign():
    svc = MarketingService()
    result = await svc.create_campaign(
        name="Test Campaign",
        campaign_type="email",
        content="Test content",
        created_by=1,
        subject="Test Subject",
        target_audience="all",
    )
    return result.data["id"]


@pytest.mark.asyncio
class TestMarketingService:
    async def test_create_campaign(self, marketing_service):
        result = await marketing_service.create_campaign(
            name="New Campaign",
            campaign_type="email",
            content="Content",
            created_by=1,
            subject="Subject",
            target_audience="all",
        )
        assert bool(result) is True
        assert result.data["name"] == "New Campaign"

    async def test_get_campaign(self, marketing_service, sample_campaign):
        result = await marketing_service.get_campaign(sample_campaign)
        assert bool(result) is True
        assert result.data["id"] == sample_campaign

    async def test_update_campaign(self, marketing_service, sample_campaign):
        result = await marketing_service.update_campaign(
            sample_campaign, {"name": "Updated Campaign"}
        )
        assert bool(result) is True
        assert result.data["name"] == "Updated Campaign"

    async def test_launch_campaign(self, marketing_service, sample_campaign):
        result = await marketing_service.launch_campaign(sample_campaign)
        assert bool(result) is True

    async def test_pause_campaign(self, marketing_service, sample_campaign):
        result = await marketing_service.pause_campaign(sample_campaign)
        assert bool(result) is True

    async def test_list_campaigns(self, marketing_service):
        result = await marketing_service.list_campaigns()
        assert bool(result) is True

    async def test_get_campaign_stats(self, marketing_service, sample_campaign):
        result = await marketing_service.get_campaign_stats(sample_campaign)
        assert bool(result) is True

    async def test_record_event(self, marketing_service, sample_campaign):
        result = await marketing_service.record_event(
            sample_campaign, "open", user_id=1
        )
        assert bool(result) is True

    async def test_get_user_events(self, marketing_service):
        result = await marketing_service.get_user_events(user_id=1)
        assert bool(result) is True

    async def test_setup_trigger(self, marketing_service, sample_campaign):
        result = await marketing_service.setup_trigger(
            sample_campaign, trigger_type="time", config={"delay": 60}
        )
        assert bool(result) is True

    async def test_create_campaign_minimal_fields(self, marketing_service):
        result = await marketing_service.create_campaign(
            name="Minimal Campaign",
            campaign_type="email",
            content="Content",
            created_by=1,
        )
        assert bool(result) is True

    async def test_get_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.get_campaign(99999)
        assert bool(result) is False

    async def test_update_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.update_campaign(99999, {"name": "X"})
        assert bool(result) is False

    async def test_launch_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.launch_campaign(99999)
        assert bool(result) is False

    async def test_pause_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.pause_campaign(99999)
        assert bool(result) is False

    async def test_list_campaigns_with_status_filter(self, marketing_service):
        result = await marketing_service.list_campaigns(status="draft")
        assert bool(result) is True

    async def test_list_campaigns_with_type_filter(self, marketing_service):
        result = await marketing_service.list_campaigns(campaign_type="email")
        assert bool(result) is True

    async def test_list_campaigns_pagination(self, marketing_service):
        result = await marketing_service.list_campaigns(page=1, page_size=5)
        assert bool(result) is True

    async def test_record_event_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.record_event(99999, "open", user_id=1)
        assert bool(result) is False

    async def test_get_user_events_no_events(self, marketing_service):
        result = await marketing_service.get_user_events(user_id=99999)
        assert bool(result) is True

    async def test_setup_trigger_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.setup_trigger(99999, "time", {})
        assert bool(result) is False

    async def test_get_campaign_stats_no_sent(self, marketing_service):
        result = await marketing_service.get_campaign_stats(99999)
        assert bool(result) is False
