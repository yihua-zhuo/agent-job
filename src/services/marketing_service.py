"""营销服务 — async PostgreSQL via SQLAlchemy."""
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any

from sqlalchemy import text, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.marketing import CampaignModel, CampaignEventModel
from models.marketing import (
    Campaign,
    CampaignEvent,
    CampaignStatus,
    CampaignType,
    TriggerType,
)
from models.response import ApiResponse, PaginatedData


def _row_to_campaign(row) -> Campaign:
    return Campaign(
        id=row[0],
        name=row[1],
        type=CampaignType(row[2]),
        status=CampaignStatus(row[3]),
        subject=row[4],
        content=row[5],
        target_audience=row[6],
        trigger_type=TriggerType(row[7]) if row[7] else None,
        trigger_days=row[8],
        created_by=row[9],
        sent_count=row[10],
        open_count=row[11],
        click_count=row[12],
        created_at=row[13],
        updated_at=row[14],
    )


def _row_to_event(row) -> CampaignEvent:
    return CampaignEvent(
        id=row[0],
        campaign_id=row[1],
        customer_id=row[2],
        event_type=row[3],
        created_at=row[4],
    )


class MarketingService:
    """营销服务 — backed by PostgreSQL."""

    def __init__(self, session: AsyncSession = None):
        self.session = session

    def _require_session(self):
        if self.session is None:
            raise TypeError(
                f"{self.__class__.__name__} requires an injected AsyncSession; "
                "construct with XxxService(async_session)."
            )

    async def create_campaign(
        self,
        name: str,
        campaign_type: CampaignType,
        content: str,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> ApiResponse[Campaign]:
        """创建营销活动"""
        self._require_session()
        now = datetime.now(UTC)
        async with self.session:
            stmt = text(
                """
                INSERT INTO campaigns (tenant_id, name, type, status, subject, content,
                    target_audience, trigger_type, trigger_days, created_by,
                    sent_count, open_count, click_count, created_at, updated_at)
                VALUES (:tenant_id, :name, :type, :status, :subject, :content,
                    :target_audience, :trigger_type, :trigger_days, :created_by,
                    0, 0, 0, :now, :now)
                RETURNING id, name, type, status, subject, content, target_audience,
                          trigger_type, trigger_days, created_by,
                          sent_count, open_count, click_count, created_at, updated_at
                """
            )
            result = await self.session.execute(
                stmt,
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "type": (
                        campaign_type.value
                        if hasattr(campaign_type, "value")
                        else campaign_type
                    ),
                    "status": CampaignStatus.DRAFT.value,
                    "subject": kwargs.get("subject"),
                    "content": content,
                    "target_audience": kwargs.get("target_audience", ""),
                    "trigger_type": (
                        kwargs["trigger_type"].value
                        if isinstance(kwargs.get("trigger_type"), TriggerType)
                        else kwargs.get("trigger_type")
                    ),
                    "trigger_days": kwargs.get("trigger_days"),
                    "created_by": created_by,
                    "now": now,
                },
            )
            await self.session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="创建营销活动失败", code=500)
            return ApiResponse.success(data=_row_to_campaign(row), message="营销活动创建成功")

    async def get_campaign(self, campaign_id: int, tenant_id: int = 0) -> ApiResponse[Campaign]:
        """获取活动详情"""
        self._require_session()
        async with self.session:
            stmt = text(
                """
                SELECT id, name, type, status, subject, content, target_audience,
                       trigger_type, trigger_days, created_by,
                       sent_count, open_count, click_count, created_at, updated_at
                FROM campaigns WHERE id = :id
                """
            )
            result = await self.session.execute(stmt, {"id": campaign_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="营销活动不存在", code=1404)
            return ApiResponse.success(data=_row_to_campaign(row))

    async def update_campaign(
        self, campaign_id: int, tenant_id: int = 0, **kwargs
    ) -> ApiResponse[Campaign]:
        """更新活动"""
        self._require_session()
        updates: List[str] = []
        params: Dict[str, Any] = {"id": campaign_id}
        for key in ["name", "type", "status", "subject", "content", "target_audience", "trigger_type", "trigger_days"]:
            if key in kwargs:
                val = kwargs[key]
                if hasattr(val, "value"):
                    val = val.value
                updates.append(f"{key} = :{key}")
                params[key] = val

        if not updates:
            return await self.get_campaign(campaign_id, tenant_id)

        async with self.session:
            where = "id = :id"
            if tenant_id > 0:
                where += " AND tenant_id = :tenant_id"
                params["tenant_id"] = tenant_id

            stmt = text(
                f"""
                UPDATE campaigns SET {', '.join(updates)}, updated_at = :now
                WHERE {where}
                RETURNING id, name, type, status, subject, content, target_audience,
                          trigger_type, trigger_days, created_by,
                          sent_count, open_count, click_count, created_at, updated_at
                """
            )
            params["now"] = datetime.now(UTC)
            result = await self.session.execute(stmt, params)
            await self.session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="营销活动不存在", code=1404)
            return ApiResponse.success(data=_row_to_campaign(row), message="营销活动更新成功")

    async def launch_campaign(self, campaign_id: int, tenant_id: int = 0) -> ApiResponse[Campaign]:
        """启动活动"""
        self._require_session()
        return await self.update_campaign(campaign_id, tenant_id, status=CampaignStatus.ACTIVE)

    async def pause_campaign(self, campaign_id: int, tenant_id: int = 0) -> ApiResponse[Campaign]:
        """暂停活动"""
        self._require_session()
        return await self.update_campaign(campaign_id, tenant_id, status=CampaignStatus.PAUSED)

    async def get_campaign_stats(self, campaign_id: int) -> ApiResponse[Dict[str, Any]]:
        """获取活动统计"""
        self._require_session()
        async with self.session:
            stmt = text(
                "SELECT sent_count, open_count, click_count FROM campaigns WHERE id = :id"
            )
            result = await self.session.execute(stmt, {"id": campaign_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="营销活动不存在", code=1404)

            sent, opens, clicks = row
            open_rate = (opens / sent * 100) if sent > 0 else 0.0
            click_rate = (clicks / sent * 100) if sent > 0 else 0.0
            return ApiResponse.success(
                data={
                    "campaign_id": campaign_id,
                    "sent_count": sent,
                    "open_count": opens,
                    "click_count": clicks,
                    "open_rate": round(open_rate, 2),
                    "click_rate": round(click_rate, 2),
                }
            )

    async def list_campaigns(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[CampaignStatus] = None,
        campaign_type: Optional[CampaignType] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[PaginatedData[Campaign]]:
        """活动列表"""
        self._require_session()
        async with self.session:
            conditions: List[str] = []
            params: Dict[str, Any] = {"offset": (page - 1) * page_size, "limit": page_size}
            if tenant_id > 0:
                conditions.append("tenant_id = :tenant_id")
                params["tenant_id"] = tenant_id
            if status:
                conditions.append("status = :status")
                params["status"] = status.value
            if campaign_type:
                conditions.append("type = :type")
                params["type"] = campaign_type.value

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            count_stmt = text(f"SELECT COUNT(*) FROM campaigns {where}")
            count_result = await self.session.execute(count_stmt, params)
            total = count_result.scalar() or 0

            select_stmt = text(
                f"""
                SELECT id, name, type, status, subject, content, target_audience,
                       trigger_type, trigger_days, created_by,
                       sent_count, open_count, click_count, created_at, updated_at
                FROM campaigns {where}
                ORDER BY created_at DESC
                OFFSET :offset LIMIT :limit
                """
            )
            result = await self.session.execute(select_stmt, params)
            rows = result.fetchall()

            items = [_row_to_campaign(r) for r in rows]
            return ApiResponse.paginated(
                items=items, total=total, page=page, page_size=page_size, message="查询成功"
            )

    async def record_event(
        self,
        campaign_id: int,
        customer_id: int,
        event_type: str,
        tenant_id: int = 0,
    ) -> ApiResponse[CampaignEvent]:
        """记录用户事件"""
        self._require_session()
        now = datetime.now(UTC)
        async with self.session:
            # Insert event
            stmt = text(
                """
                INSERT INTO campaign_events (campaign_id, tenant_id, customer_id, event_type, created_at)
                VALUES (:campaign_id, :tenant_id, :customer_id, :event_type, :now)
                RETURNING id, campaign_id, customer_id, event_type, created_at
                """
            )
            result = await self.session.execute(
                stmt,
                {
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id,
                    "customer_id": customer_id,
                    "event_type": event_type,
                    "now": now,
                },
            )
            await self.session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="记录事件失败", code=500)

            # Update counts
            count_col = {
                "sent": "sent_count",
                "opened": "open_count",
                "clicked": "click_count",
            }.get(event_type)
            if count_col:
                await self.session.execute(
                    text(
                        f"UPDATE campaigns SET {count_col} = {count_col} + 1 WHERE id = :id"
                    ),
                    {"id": campaign_id},
                )
                await self.session.commit()

            return ApiResponse.success(data=_row_to_event(row), message="事件记录成功")

    async def get_user_events(self, customer_id: int, tenant_id: int = 0) -> List[CampaignEvent]:
        """获取用户的所有营销事件"""
        self._require_session()
        async with self.session:
            stmt = text(
                """
                SELECT id, campaign_id, customer_id, event_type, created_at
                FROM campaign_events
                WHERE customer_id = :customer_id
                  AND (:tenant_id = 0 OR tenant_id = :tenant_id)
                ORDER BY created_at DESC
                """
            )
            result = await self.session.execute(stmt, {"customer_id": customer_id, "tenant_id": tenant_id})
            return [_row_to_event(r) for r in result.fetchall()]

    async def setup_trigger(
        self,
        campaign_id: int,
        trigger_type: TriggerType,
        trigger_days: Optional[int] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[Campaign]:
        """设置触发器"""
        self._require_session()
        return await self.update_campaign(
            campaign_id, tenant_id,
            trigger_type=trigger_type,
            trigger_days=trigger_days,
        )

    async def add_audience(self, campaign_id: int, audience_sql: str, tenant_id: int = 0) -> ApiResponse[Campaign]:
        """添加目标受众"""
        self._require_session()
        return await self.update_campaign(
            campaign_id, tenant_id, target_audience=audience_sql
        )

    async def trigger_campaign(
        self, campaign_id: int, customer_ids: List[int], tenant_id: int = 0
    ) -> Dict[str, Any]:
        """触发活动发送"""
        self._require_session()
        sent = 0
        for cid in customer_ids:
            resp = await self.record_event(campaign_id, cid, "sent", tenant_id)
            if resp.status.value == "success":
                sent += 1
        return {
            "campaign_id": campaign_id,
            "target_count": len(customer_ids),
            "sent_count": sent,
        }

    async def get_campaign_events(
        self, campaign_id: int, tenant_id: int = 0
    ) -> List[CampaignEvent]:
        """获取活动事件列表"""
        self._require_session()
        async with self.session:
            stmt = text(
                """
                SELECT id, campaign_id, customer_id, event_type, created_at
                FROM campaign_events
                WHERE campaign_id = :campaign_id
                  AND (:tenant_id = 0 OR tenant_id = :tenant_id)
                ORDER BY created_at DESC
                """
            )
            result = await self.session.execute(stmt, {"campaign_id": campaign_id, "tenant_id": tenant_id})
            return [_row_to_event(r) for r in result.fetchall()]
