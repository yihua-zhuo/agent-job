"""工单服务单元测试"""
import pytest
from datetime import datetime, timedelta

from src.services.ticket_service import TicketService
# 使用 service 内部导入的 enums 以确保一致性
from src.services.ticket_service import (
    TicketStatus,
    TicketPriority,
    TicketChannel,
    SLALevel,
    SLA_CONFIGS,
)


@pytest.fixture
def ticket_service():
    """创建工单服务实例"""
    return TicketService()


@pytest.fixture
def sample_ticket(ticket_service):
    """创建示例工单"""
    return ticket_service.create_ticket(
        subject="测试问题",
        description="这是测试工单的描述",
        customer_id=1,
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.MEDIUM,
        sla_level=SLALevel.STANDARD,
    )


class TestTicketServiceNormal:
    """正常场景测试"""

    def test_create_ticket(self, ticket_service):
        """测试创建工单"""
        ticket = ticket_service.create_ticket(
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

    def test_get_ticket(self, ticket_service, sample_ticket):
        """测试获取工单详情"""
        ticket = ticket_service.get_ticket(sample_ticket.id)
        assert ticket is not None
        assert ticket.id == sample_ticket.id
        assert ticket.subject == sample_ticket.subject

    def test_update_ticket(self, ticket_service, sample_ticket):
        """测试更新工单"""
        updated = ticket_service.update_ticket(
            sample_ticket.id,
            subject="更新后的主题",
            priority=TicketPriority.HIGH,
        )
        assert updated is not None
        assert updated.subject == "更新后的主题"
        assert updated.priority == TicketPriority.HIGH

    def test_delete_ticket(self, ticket_service, sample_ticket):
        """测试删除工单（通过直接删除数据）"""
        # 注意: TicketService 没有 delete_ticket 方法
        # 通过直接操作内部存储来模拟删除
        ticket_id = sample_ticket.id
        del ticket_service._tickets[ticket_id]
        ticket = ticket_service.get_ticket(ticket_id)
        assert ticket is None

    def test_assign_ticket(self, ticket_service, sample_ticket):
        """测试分配工单"""
        assigned = ticket_service.assign_ticket(sample_ticket.id, assigned_to=5)
        assert assigned is not None
        assert assigned.assigned_to == 5

    def test_add_reply(self, ticket_service, sample_ticket):
        """测试添加回复"""
        reply = ticket_service.add_reply(
            ticket_id=sample_ticket.id,
            content="这是客服回复内容",
            created_by=2,
        )
        assert reply is not None
        assert reply.content == "这是客服回复内容"

    def test_change_status(self, ticket_service, sample_ticket):
        """测试改变工单状态"""
        changed = ticket_service.change_status(
            sample_ticket.id,
            TicketStatus.IN_PROGRESS,
        )
        assert changed is not None
        assert changed.status == TicketStatus.IN_PROGRESS

    def test_get_customer_tickets(self, ticket_service):
        """测试获取客户的所有工单"""
        ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=10, channel=TicketChannel.EMAIL,
        )
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=10, channel=TicketChannel.CHAT,
        )
        tickets = ticket_service.get_customer_tickets(10)
        assert len(tickets) == 2

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
        tickets = ticket_service.list_tickets(page=1, page_size=10)
        assert len(tickets) == 2

    def test_get_sla_breaches(self, ticket_service):
        """测试获取SLA超时的工单"""
        # 创建一个会超时的工单
        ticket = ticket_service.create_ticket(
            subject="紧急问题", description="描述",
            customer_id=1, channel=TicketChannel.PHONE,
            sla_level=SLALevel.BASIC,
        )
        # 模拟SLA超时（修改response_deadline为过去时间）
        ticket.response_deadline = datetime.now() - timedelta(hours=25)
        breaches = ticket_service.get_sla_breaches()
        assert len(breaches) >= 1

    def test_auto_assign(self, ticket_service):
        """测试自动分配客服"""
        ticket = ticket_service.create_ticket(
            subject="自动分配测试", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
            assigned_to=None,  # 不手动分配
        )
        assert ticket.assigned_to is not None


class TestTicketServiceEdgeCases:
    """边界条件和错误测试"""

    def test_create_ticket_minimal_fields(self, ticket_service):
        """测试只提供必需字段创建工单"""
        ticket = ticket_service.create_ticket(
            subject="最小字段工单",
            description="描述",
            customer_id=1,
            channel=TicketChannel.EMAIL,
        )
        assert ticket.id == 1
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.sla_level == SLALevel.STANDARD

    def test_get_nonexistent_ticket(self, ticket_service):
        """测试获取不存在的工单"""
        ticket = ticket_service.get_ticket(9999)
        assert ticket is None

    def test_update_nonexistent_ticket(self, ticket_service):
        """测试更新不存在的工单"""
        result = ticket_service.update_ticket(9999, subject="新主题")
        assert result is None

    def test_delete_nonexistent_ticket(self, ticket_service):
        """测试删除不存在的工单（方法不存在，测试get返回None）"""
        # TicketService 没有 delete_ticket 方法
        # 测试获取不存在的工单
        ticket = ticket_service.get_ticket(9999)
        assert ticket is None

    def test_assign_nonexistent_ticket(self, ticket_service):
        """测试分配不存在的工单"""
        result = ticket_service.assign_ticket(9999, assigned_to=5)
        assert result is None

    def test_add_reply_nonexistent_ticket(self, ticket_service):
        """测试为不存在的工单添加回复"""
        reply = ticket_service.add_reply(9999, "内容", created_by=1)
        assert reply is None

    def test_add_internal_reply(self, ticket_service, sample_ticket):
        """测试添加内部回复"""
        reply = ticket_service.add_reply(
            ticket_id=sample_ticket.id,
            content="内部备注",
            created_by=2,
            is_internal=True,
        )
        assert reply is not None
        assert reply.is_internal is True

    def test_change_status_nonexistent_ticket(self, ticket_service):
        """测试改变不存在的工单状态"""
        result = ticket_service.change_status(9999, TicketStatus.RESOLVED)
        assert result is None

    def test_change_status_to_resolved(self, ticket_service, sample_ticket):
        """测试将工单状态改为已解决"""
        changed = ticket_service.change_status(
            sample_ticket.id,
            TicketStatus.RESOLVED,
        )
        assert changed is not None
        assert changed.resolved_at is not None

    def test_list_tickets_with_status_filter(self, ticket_service):
        """测试按状态筛选工单列表"""
        ticket1 = ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        ticket_service.change_status(ticket1.id, TicketStatus.RESOLVED)
        resolved_tickets = ticket_service.list_tickets(status=TicketStatus.RESOLVED)
        assert len(resolved_tickets) == 1

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
        urgent_tickets = ticket_service.list_tickets(priority=TicketPriority.URGENT)
        assert len(urgent_tickets) == 1

    def test_list_tickets_with_assignment_filter(self, ticket_service):
        """测试按分配客服筛选工单列表"""
        t1 = ticket_service.create_ticket(
            subject="问题1", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        ticket_service.assign_ticket(t1.id, assigned_to=99)
        ticket_service.create_ticket(
            subject="问题2", description="描述",
            customer_id=2, channel=TicketChannel.CHAT,
        )
        assigned_tickets = ticket_service.list_tickets(assigned_to=99)
        assert len(assigned_tickets) == 1

    def test_list_tickets_pagination(self, ticket_service):
        """测试工单列表分页"""
        for i in range(25):
            ticket_service.create_ticket(
                subject=f"问题{i}", description="描述",
                customer_id=i, channel=TicketChannel.EMAIL,
            )
        result = ticket_service.list_tickets(page=2, page_size=10)
        assert len(result) == 10
        # 验证id降序排列（第2页的id应该大于第1页的id，因为第2页是更早的记录）
        assert result[0].id > result[9].id

    def test_get_sla_breaches_empty(self, ticket_service):
        """测试没有SLA超时的工单"""
        ticket_service.create_ticket(
            subject="正常工单", description="描述",
            customer_id=1, channel=TicketChannel.EMAIL,
        )
        breaches = ticket_service.get_sla_breaches()
        assert len(breaches) == 0

    def test_auto_assign_already_assigned(self, ticket_service, sample_ticket):
        """测试已分配的工单不重新分配"""
        original_agent = sample_ticket.assigned_to
        new_agent = ticket_service.auto_assign(sample_ticket.id)
        assert new_agent == original_agent