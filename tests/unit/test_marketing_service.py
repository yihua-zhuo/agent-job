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













    async def test_launch_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.launch_campaign(99999)
        assert bool(result) is False

    async def test_pause_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.pause_campaign(99999)
        assert bool(result) is False






    async def test_setup_trigger_nonexistent_campaign(self, marketing_service):
        result = await marketing_service.setup_trigger(99999, "time", {})
        assert bool(result) is False

