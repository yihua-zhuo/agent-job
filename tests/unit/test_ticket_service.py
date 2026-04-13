"""工单服务单元测试"""
import pytest
from datetime import datetime, timedelta

from src.services.ticket_service import TicketService
from src.services.ticket_service import (
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
)


@pytest.fixture
def ticket_service():
    """创建工单服务实例"""
    return TicketService()


@pytest.fixture
def sample_ticket(ticket_service):
    """创建示例工单"""
    result = ticket_service.create_ticket(
        subject="测试问题",
        description="这是测试工单的描述",
        customer_id=1,
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.MEDIUM,
        sla_level=SLALevel.STANDARD,
    )
    return result.data.id


class TestTicketServiceNormal:
    """正常场景测试"""

    def test_create_ticket(self, ticket_service):
        """测试创建工单"""
        result = ticket_service.create_ticket(
            subject="新问题",
            description="问题描述",
            customer_id=1,
            channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
            sla_level=SLALevel.STANDARD,
        )
        assert bool(result) is True
        assert result.data.subject == "新问题"
        assert result.data.status == TicketStatus.OPEN

    def test_get_ticket(self, ticket_service, sample_ticket):
        """测试获取工单详情"""
        result = ticket_service.get_ticket(sample_ticket)
        assert bool(result) is True
        assert result.data.subject == "测试问题"

    def test_update_ticket(self, ticket_service, sample_ticket):
        """测试更新工单"""
        result = ticket_service.update_ticket(
            sample_ticket,
            subject="更新后的主题",
            priority=TicketPriority.HIGH,
        )
        assert bool(result) is True
        assert result.data.subject == "更新后的主题"
        assert result.data.priority == TicketPriority.HIGH

    def test_assign_ticket(self, ticket_service, sample_ticket):
        """测试分配工单"""
        result = ticket_service.assign_ticket(sample_ticket, assigned_to=5)
        assert bool(result) is True
        assert result.data.assigned_to == 5

    def test_add_reply(self, ticket_service, sample_ticket):
        """测试添加回复"""
        result = ticket_service.add_reply(
            ticket_id=sample_ticket,
            content="这是客服回复内容",
            created_by=2,
        )
        assert bool(result) is True
        assert result.data.content == "这是客服回复内容"

    def test_change_status(self, ticket_service, sample_ticket):
        """测试改变工单状态"""
        result = ticket_service.change_status(
            sample_ticket,
            TicketStatus.IN_PROGRESS,
        )
        assert bool(result) is True
        assert result.data.status == TicketStatus.IN_PROGRESS

    def test_get_customer_tickets(self, ticket_service):
        """"测试获取客户的所有工单"""
        ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=10, channel=TicketChannel.EMAIL,
        )
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=10, channel=TicketChannel.CHAT,
        )
        result = ticket_service.get_customer_tickets(10)
        assert len(result) == 2

    def test_list_tickets(self, ticket_service):
        """测试工单列表"""
        ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        result = ticket_service.list_tickets(page=1, page_size=10)
        assert bool(result) is True
        assert len(result.data.items) == 2

    def test_change_status_to_resolved(self, ticket_service, sample_ticket):
        """测试将工单状态改为已解决"""
        result = ticket_service.change_status(
            sample_ticket,
            TicketStatus.RESOLVED,
        )
        assert bool(result) is True
        assert result.data.resolved_at is not None


class TestTicketServiceEdgeCases:
    """边界条件和错误测试"""

    def test_create_ticket_minimal_fields(self, ticket_service):
        """测试只提供必需字段创建工单"""
        result = ticket_service.create_ticket(
            subject="最小字段工单",
            description="描述",
            customer_id=1,
            channel=TicketChannel.EMAIL,
        )
        assert bool(result) is True
        assert result.data.priority == TicketPriority.MEDIUM
        assert result.data.sla_level == SLALevel.STANDARD

    def test_get_nonexistent_ticket(self, ticket_service):
        """测试获取不存在的工单"""
        result = ticket_service.get_ticket(9999)
        assert bool(result) is False

    def test_update_nonexistent_ticket(self, ticket_service):
        """测试更新不存在的工单"""
        result = ticket_service.update_ticket(9999, subject="新主题")
        assert bool(result) is False

    def test_assign_nonexistent_ticket(self, ticket_service):
        """测试分配不存在的工单"""
        result = ticket_service.assign_ticket(9999, assigned_to=5)
        assert bool(result) is False

    def test_add_reply_nonexistent_ticket(self, ticket_service):
        """测试为不存在的工单添加回复"""
        result = ticket_service.add_reply(9999, "内容", created_by=1)
        assert bool(result) is False

    def test_add_internal_reply(self, ticket_service, sample_ticket):
        """测试添加内部回复"""
        result = ticket_service.add_reply(
            ticket_id=sample_ticket,
            content="内部备注",
            created_by=2,
            is_internal=True,
        )
        assert bool(result) is True
        assert result.data.is_internal is True

    def test_change_status_nonexistent_ticket(self, ticket_service):
        """测试改变不存在的工单状态"""
        result = ticket_service.change_status(9999, TicketStatus.RESOLVED)
        assert bool(result) is False

    def test_list_tickets_with_status_filter(self, ticket_service):
        """测试按状态筛选工单列表"""
        r1 = ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        t1_id = r1.data.id
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        ticket_service.change_status(t1_id, TicketStatus.RESOLVED)
        result = ticket_service.list_tickets(status=TicketStatus.RESOLVED)
        assert bool(result) is True
        assert len(result.data.items) == 1

    def test_list_tickets_with_priority_filter(self, ticket_service):
        """测试按优先级筛选工单列表"""
        ticket_service.create_ticket(
            subject="普通问题", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
            priority=TicketPriority.MEDIUM,
        )
        ticket_service.create_ticket(
            subject="紧急问题", description="描述",
            customer_id=2, channel=TicketChannel.PHONE,
            priority=TicketPriority.URGENT,
        )
        result = ticket_service.list_tickets(priority=TicketPriority.URGENT)
        assert bool(result) is True
        assert len(result.data.items) == 1

    def test_list_tickets_pagination(self, ticket_service):
        """测试工单列表分页"""
        for i in range(25):
            ticket_service.create_ticket(
                subject=f"问题{i}", description="描述",
                customer_id=i, channel=TicketChannel.EMAIL,
            )
        result = ticket_service.list_tickets(page=2, page_size=10)
        assert bool(result) is True
        assert len(result.data.items) == 10
