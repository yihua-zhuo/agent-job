"""工单服务单元测试"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import src.services.ticket_service as ticket_mod
from src.services.ticket_service import TicketService
from src.services.ticket_service import (
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
    SLA_CONFIGS,
    _tickets_db,
    _ticket_replies_db,
    _ticket_next_id,
)
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture(autouse=True)
def _reset_ticket_state():
    """Reset module-level state before each test."""
    ticket_mod._tickets_db.clear()
    ticket_mod._ticket_replies_db.clear()
    ticket_mod._ticket_next_id = 1
    ticket_mod._ticket_agent_index = 0
    yield
    ticket_mod._tickets_db.clear()
    ticket_mod._ticket_replies_db.clear()
    ticket_mod._ticket_next_id = 1
    ticket_mod._ticket_agent_index = 0


@pytest.fixture
def ticket_service():
    """创建工单服务实例"""
    return TicketService(MagicMock())


@pytest.fixture
async def sample_ticket(ticket_service):
    """创建示例工单"""
    ticket = await ticket_service.create_ticket(
        subject="测试问题",
        description="这是测试工单的描述",
        customer_id=1,
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.MEDIUM,
        sla_level=SLALevel.STANDARD,
    )
    return ticket


class TestTicketServiceNormal:
    """正常场景测试"""

    async def test_create_ticket(self, ticket_service):
        """测试创建工单"""
        ticket = await ticket_service.create_ticket(
            subject="新问题",
            description="问题描述",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            sla_level=SLALevel.STANDARD,
        )
        assert ticket.id == 1
        assert ticket.subject == "新问题"
        assert ticket.status == TicketStatus.OPEN

    async def test_get_ticket(self, ticket_service, sample_ticket):
        """测试获取工单详情"""
        ticket = await ticket_service.get_ticket(sample_ticket.id)
        assert ticket is not None
        assert ticket.id == sample_ticket.id
        assert ticket.subject == sample_ticket.subject

    async def test_update_ticket(self, ticket_service, sample_ticket):
        """测试更新工单"""
        ticket = await ticket_service.update_ticket(
            sample_ticket.id,
            subject="更新后的主题",
            priority=TicketPriority.HIGH,
        )
        assert ticket is not None
        assert ticket.subject == "更新后的主题"
        assert ticket.priority == TicketPriority.HIGH

    async def test_delete_ticket(self, ticket_service, sample_ticket):
        """测试删除工单（通过直接删除数据）"""
        # 注意: TicketService 没有 delete_ticket 方法
        # 通过直接操作内部存储来模拟删除
        ticket_id = sample_ticket.id
        del _tickets_db[ticket_id]
        with pytest.raises(NotFoundException):
            await ticket_service.get_ticket(ticket_id)

    async def test_assign_ticket(self, ticket_service, sample_ticket):
        """测试分配工单"""
        ticket = await ticket_service.assign_ticket(sample_ticket.id, assigned_to=5)
        assert ticket is not None
        assert ticket.assigned_to == 5

    async def test_add_reply(self, ticket_service, sample_ticket):
        """测试添加回复"""
        reply = await ticket_service.add_reply(
            ticket_id=sample_ticket.id,
            content="这是客服回复内容",
            created_by=2,
        )
        assert reply is not None
        assert reply.content == "这是客服回复内容"

    async def test_change_status(self, ticket_service, sample_ticket):
        """测试改变工单状态"""
        ticket = await ticket_service.change_status(
            sample_ticket.id,
            TicketStatus.IN_PROGRESS,
        )
        assert ticket is not None
        assert ticket.status == TicketStatus.IN_PROGRESS

    async def test_get_customer_tickets(self, ticket_service):
        """测试获取客户的所有工单"""
        await ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=10, channel=TicketChannel.EMAIL,
        )
        await ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=10, channel=TicketChannel.CHAT,
        )
        tickets = await ticket_service.get_customer_tickets(10)
        assert len(tickets) == 2

    async def test_list_tickets(self, ticket_service):
        """测试工单列表"""
        await ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        await ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        items, total = await ticket_service.list_tickets(page=1, page_size=10)
        assert len(items) == 2

    async def test_get_sla_breaches(self, ticket_service):
        """测试获取SLA超时的工单"""
        # 创建一个会超时的工单
        ticket = await ticket_service.create_ticket(
            subject="紧急问题", description="描述",
            customer_id=1, channel=TicketChannel.PHONE,
            sla_level=SLALevel.BASIC,
        )
        # 模拟SLA超时（修改response_deadline为过去时间）
        _tickets_db[ticket.id].response_deadline = datetime.now() - timedelta(hours=25)
        breaches = await ticket_service.get_sla_breaches()
        assert len(breaches) >= 1

    async def test_auto_assign(self, ticket_service):
        """测试自动分配客服"""
        ticket = await ticket_service.create_ticket(
            subject="自动分配测试", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
            assigned_to=None,  # 不手动分配
        )
        assert ticket.assigned_to is not None


class TestTicketServiceEdgeCases:
    """边界条件和错误测试"""

    async def test_create_ticket_minimal_fields(self, ticket_service):
        """测试只提供必需字段创建工单"""
        ticket = await ticket_service.create_ticket(
            subject="最小字段工单",
            description="描述",
            customer_id=1,
            channel=TicketChannel.EMAIL,
        )
        # Stub uses module-level counter; just verify id > 0 and defaults are set
        assert ticket.id > 0
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.sla_level == SLALevel.STANDARD

    async def test_get_nonexistent_ticket(self, ticket_service):
        """测试获取不存在的工单"""
        with pytest.raises(NotFoundException):
            await ticket_service.get_ticket(9999)

    async def test_update_nonexistent_ticket(self, ticket_service):
        """测试更新不存在的工单"""
        with pytest.raises(NotFoundException):
            await ticket_service.update_ticket(9999, subject="新主题")

    async def test_delete_nonexistent_ticket(self, ticket_service):
        """测试删除不存在的工单（方法不存在，测试get抛出异常）"""
        # TicketService 没有 delete_ticket 方法
        # 测试获取不存在的工单
        with pytest.raises(NotFoundException):
            await ticket_service.get_ticket(9999)

    async def test_assign_nonexistent_ticket(self, ticket_service):
        """测试分配不存在的工单"""
        with pytest.raises(NotFoundException):
            await ticket_service.assign_ticket(9999, assigned_to=5)

    async def test_add_reply_nonexistent_ticket(self, ticket_service):
        """测试为不存在的工单添加回复"""
        with pytest.raises(NotFoundException):
            await ticket_service.add_reply(9999, "内容", created_by=1)

    async def test_add_internal_reply(self, ticket_service, sample_ticket):
        """测试添加内部回复"""
        reply = await ticket_service.add_reply(
            ticket_id=sample_ticket.id,
            content="内部备注",
            created_by=2,
            is_internal=True,
        )
        assert reply is not None
        assert reply.is_internal is True

    async def test_change_status_nonexistent_ticket(self, ticket_service):
        """测试改变不存在的工单状态"""
        with pytest.raises(NotFoundException):
            await ticket_service.change_status(9999, TicketStatus.RESOLVED)

    async def test_change_status_to_resolved(self, ticket_service, sample_ticket):
        """测试将工单状态改为已解决"""
        ticket = await ticket_service.change_status(
            sample_ticket.id,
            TicketStatus.RESOLVED,
        )
        assert ticket is not None
        assert ticket.resolved_at is not None

    async def test_list_tickets_with_status_filter(self, ticket_service):
        """测试按状态筛选工单列表"""
        ticket1 = await ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        # Create a second ticket and change its status to something different
        await ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        await ticket_service.change_status(ticket1.id, TicketStatus.RESOLVED)
        items, total = await ticket_service.list_tickets(status=TicketStatus.RESOLVED)
        # Only the ticket we explicitly resolved should be in RESOLVED status
        assert len(items) >= 1
        assert all(t.status == TicketStatus.RESOLVED for t in items)

    async def test_list_tickets_with_priority_filter(self, ticket_service):
        """测试按优先级筛选工单列表"""
        await ticket_service.create_ticket(
            subject="普通问题", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
        )
        await ticket_service.create_ticket(
            subject="紧急问题", description="描述",
            customer_id=2, channel=TicketChannel.PHONE,
            priority=TicketPriority.URGENT,
        )
        items, total = await ticket_service.list_tickets(priority=TicketPriority.URGENT)
        assert len(items) == 1

    async def test_list_tickets_with_assignment_filter(self, ticket_service):
        """测试按分配客服筛选工单列表"""
        t1 = await ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        await ticket_service.assign_ticket(t1.id, assigned_to=99)
        await ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        items, total = await ticket_service.list_tickets(assigned_to=99)
        assert len(items) == 1

    async def test_list_tickets_pagination(self, ticket_service):
        """测试工单列表分页"""
        for i in range(25):
            await ticket_service.create_ticket(
                subject=f"问题{i}", description="描述",
                customer_id=i, channel=TicketChannel.EMAIL,
            )
        items, total = await ticket_service.list_tickets(page=2, page_size=10)
        assert len(items) == 10
        # 验证id降序排列（第2页的id应该大于第1页的id，因为第2页是更早的记录）
        assert items[0].id > items[9].id

    async def test_get_sla_breaches_empty(self, ticket_service):
        """测试没有SLA超时的工单"""
        await ticket_service.create_ticket(
            subject="正常工单", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        breaches = await ticket_service.get_sla_breaches()
        assert len(breaches) == 0

    async def test_auto_assign_already_assigned(self, ticket_service, sample_ticket):
        """测试已分配的工单不重新分配"""
        original_agent = sample_ticket.assigned_to
        result = await ticket_service.auto_assign(sample_ticket.id)
        assert result["assigned_to"] == original_agent
