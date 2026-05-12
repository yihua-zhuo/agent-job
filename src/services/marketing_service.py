"""营销服务 — DB-backed via SQLAlchemy async ORM."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.marketing import CampaignEventModel, CampaignModel
from models.marketing import CampaignStatus, CampaignType, TriggerType
from pkg.errors.app_exceptions import NotFoundException


def _enum_val(v) -> str | None:
    """Coerce enum or string to string."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


class MarketingService:
    """营销服务 — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_campaign(
        self,
        name: str,
        campaign_type: CampaignType | str,
        content: str,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> CampaignModel:
        """创建营销活动"""
        now = datetime.now(UTC)
        campaign = CampaignModel(
            tenant_id=tenant_id,
            name=name,
            type=_enum_val(campaign_type),
            status=CampaignStatus.DRAFT.value,
            subject=kwargs.get("subject"),
            content=content,
            target_audience=kwargs.get("target_audience"),
            trigger_type=_enum_val(kwargs.get("trigger_type")),
            trigger_days=kwargs.get("trigger_days"),
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(campaign)
        await self.session.flush()
        await self.session.refresh(campaign)
        await self.session.flush()
        return campaign

    async def get_campaign(self, campaign_id: int, tenant_id: int = 0) -> CampaignModel:
        """获取活动详情"""
        result = await self.session.execute(
            select(CampaignModel).where(and_(CampaignModel.id == campaign_id, CampaignModel.tenant_id == tenant_id))
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundException("Campaign")
        return campaign

    async def update_campaign(self, campaign_id: int, tenant_id: int = 0, **kwargs) -> CampaignModel:
        """更新活动"""
        campaign = await self.get_campaign(campaign_id, tenant_id)
        for key, value in kwargs.items():
            if hasattr(campaign, key):
                if key in ("type", "trigger_type", "status"):
                    value = _enum_val(value)
                setattr(campaign, key, value)
        campaign.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(campaign)
        return campaign

    async def launch_campaign(self, campaign_id: int, tenant_id: int = 0) -> CampaignModel:
        """启动活动"""
        return await self.update_campaign(campaign_id, tenant_id, status=CampaignStatus.ACTIVE)

    async def pause_campaign(self, campaign_id: int, tenant_id: int = 0) -> CampaignModel:
        """暂停活动"""
        return await self.update_campaign(campaign_id, tenant_id, status=CampaignStatus.PAUSED)

    async def get_campaign_stats(self, campaign_id: int, tenant_id: int = 0) -> dict[str, Any]:
        """获取活动统计"""
        campaign = await self.get_campaign(campaign_id, tenant_id)
        sent = campaign.sent_count
        open_rate = (campaign.open_count / sent * 100) if sent > 0 else 0
        click_rate = (campaign.click_count / sent * 100) if sent > 0 else 0
        return {
            "campaign_id": campaign_id,
            "sent_count": campaign.sent_count,
            "open_count": campaign.open_count,
            "click_count": campaign.click_count,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
        }

    async def list_campaigns(
        self,
        tenant_id: int = 0,
        page: int = 1,
        page_size: int = 20,
        status: CampaignStatus | str | None = None,
        campaign_type: CampaignType | str | None = None,
    ) -> tuple[list[CampaignModel], int]:
        """活动列表 — returns (items, total). Router serializes."""
        conditions = [CampaignModel.tenant_id == tenant_id]
        if status is not None:
            conditions.append(CampaignModel.status == _enum_val(status))
        if campaign_type is not None:
            conditions.append(CampaignModel.type == _enum_val(campaign_type))

        count_result = await self.session.execute(select(func.count(CampaignModel.id)).where(and_(*conditions)))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CampaignModel).where(and_(*conditions)).order_by(CampaignModel.id).offset(offset).limit(page_size)
        )
        return result.scalars().all(), total

    async def record_event(
        self,
        campaign_id: int,
        customer_id: int,
        event_type: str,
        tenant_id: int = 0,
    ) -> CampaignEventModel:
        """记录用户事件"""
        campaign = await self.get_campaign(campaign_id, tenant_id)

        event = CampaignEventModel(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            created_at=datetime.now(UTC),
        )
        self.session.add(event)

        if event_type == "sent":
            campaign.sent_count += 1
        elif event_type == "opened":
            campaign.open_count += 1
        elif event_type == "clicked":
            campaign.click_count += 1
        campaign.updated_at = datetime.now(UTC)

        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_user_events(self, customer_id: int, tenant_id: int = 0) -> list[CampaignEventModel]:
        """获取用户的所有营销事件"""
        result = await self.session.execute(
            select(CampaignEventModel)
            .where(
                and_(
                    CampaignEventModel.customer_id == customer_id,
                    CampaignEventModel.tenant_id == tenant_id,
                )
            )
            .order_by(CampaignEventModel.created_at.desc())
        )
        return result.scalars().all()

    async def setup_trigger(
        self,
        campaign_id: int,
        trigger_type: TriggerType,
        trigger_days: int | None = None,
        tenant_id: int = 0,
    ) -> CampaignModel:
        """设置触发器"""
        return await self.update_campaign(
            campaign_id,
            tenant_id,
            trigger_type=trigger_type,
            trigger_days=trigger_days,
        )
