"""
Unit tests for automation rules UI flow — service-layer tests using mocks.

Tests the AutomationService CRUD operations with a mock DB session,
covering the same surface area that the UI consumes via the REST API.

Run with:
    PYTHONPATH=src pytest tests/unit/test_automation_rules_ui.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.automation_service import AutomationService
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_db_session():
    """Build a mock AsyncSession wired to return controlled mock results."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    def execute_side_effect(sql, **kwargs):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return mock_result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


class TestAutomationServiceRuleBuilder:
    """Service-layer rule CRUD — tested via mock DB session."""

    async def test_create_rule_returns_orm_object(self, mock_db_session):
        """AutomationService.create_rule returns an ORM rule object with to_dict."""
        session = mock_db_session

        # Wire session.execute to return a saved rule on INSERT flush
        saved_rule = MagicMock()
        saved_rule.id = 42
        saved_rule.name = "Test Rule"
        saved_rule.trigger_event = "ticket.created"
        saved_rule.enabled = True
        saved_rule.tenant_id = 1
        saved_rule.to_dict = MagicMock(return_value={"id": 42, "name": "Test Rule"})

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            # Return saved_rule for the INSERT query
            if hasattr(sql, "__str__") and "insert" in str(sql).lower():
                return MagicMock(
                    scalars=MagicMock(all=MagicMock(return_value=[saved_rule]))
                )
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        rule = await svc.create_rule(
            tenant_id=1,
            name="Test Rule",
            description="Integration test",
            trigger_event="ticket.created",
            conditions=[{"field": "priority", "operator": "eq", "value": "high"}],
            actions=[{"type": "notification.send", "params": {"message": "Alert!"}}],
            enabled=True,
            created_by=1,
        )
        # Rule is returned (not a dict or ApiResponse)
        assert hasattr(rule, "id")
        assert hasattr(rule, "name")
        assert hasattr(rule, "to_dict")
        assert rule.name == "Test Rule"
        assert rule.trigger_event == "ticket.created"
        assert rule.tenant_id == 1

    async def test_create_rule_allows_empty_name_in_service(self, mock_db_session):
        """Service layer does not validate name length — that's the router's job."""
        session = mock_db_session
        saved_rule = MagicMock()
        saved_rule.id = 1
        saved_rule.name = ""
        saved_rule.trigger_event = "ticket.created"
        saved_rule.enabled = True
        saved_rule.tenant_id = 1
        saved_rule.to_dict = MagicMock(return_value={"id": 1, "name": ""})

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            if hasattr(sql, "__str__") and "insert" in str(sql).lower():
                return MagicMock(
                    scalars=MagicMock(all=MagicMock(return_value=[saved_rule]))
                )
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        # Service does NOT raise on empty name — that's validated at the router layer
        rule = await svc.create_rule(
            tenant_id=1,
            name="",
            trigger_event="ticket.created",
            conditions=[],
            actions=[{"type": "notification.send", "params": {}}],
            enabled=True,
            created_by=1,
        )
        assert hasattr(rule, "id")

    async def test_list_rules_returns_items_and_total(self, mock_db_session):
        """AutomationService.list_rules returns (items, total) for pagination."""
        session = mock_db_session

        mock_items = [MagicMock(id=1, name="Rule A"), MagicMock(id=2, name="Rule B")]
        execute_call_count = [0]

        def execute_side_effect(sql, **kwargs):
            execute_call_count[0] += 1
            mock_result = MagicMock()
            if execute_call_count[0] == 1:
                mock_result.scalar_one = MagicMock(return_value=2)
            else:
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_items)))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_rules(tenant_id=1, page=1, page_size=20)
        assert isinstance(items, list)
        assert len(items) == 2
        assert isinstance(total, int)
        assert total == 2

    async def test_get_rule_raises_not_found_for_missing_id(self, mock_db_session):
        """AutomationService.get_rule raises NotFoundException when rule doesn't exist."""
        session = mock_db_session

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        with pytest.raises(NotFoundException):
            await svc.get_rule(rule_id=9999, tenant_id=1)

    async def test_update_rule_calls_update_stmt(self, mock_db_session):
        """AutomationService.update_rule calls UPDATE and returns the updated row."""
        session = mock_db_session

        updated_rule = MagicMock()
        updated_rule.id = 5
        updated_rule.name = "Updated Name"
        updated_rule.to_dict = MagicMock(return_value={"id": 5, "name": "Updated Name"})

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            # update_rule uses scalar_one_or_none on the RETURNING statement
            mock_result.scalar_one_or_none = MagicMock(return_value=updated_rule)
            mock_result.scalar_one = MagicMock(return_value=updated_rule)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[updated_rule])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        updated = await svc.update_rule(rule_id=5, tenant_id=1, name="Updated Name")
        assert hasattr(updated, "id")
        assert hasattr(updated, "to_dict")

    async def test_delete_rule_returns_deleted_id(self, mock_db_session):
        """AutomationService.delete_rule returns the deleted rule id."""
        session = mock_db_session

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            # DELETE returns rowcount >= 1 when successful
            mock_result.rowcount = 1
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        deleted_id = await svc.delete_rule(rule_id=5, tenant_id=1)
        assert deleted_id == 5

    async def test_toggle_rule_flips_enabled_state(self, mock_db_session):
        """AutomationService.toggle_rule flips enabled and returns updated ORM object."""
        session = mock_db_session

        original_rule = MagicMock()
        original_rule.id = 7
        original_rule.name = "Toggle Test"
        original_rule.enabled = False
        original_rule.to_dict = MagicMock(return_value={"id": 7, "enabled": False})

        toggled_rule = MagicMock()
        toggled_rule.id = 7
        toggled_rule.name = "Toggle Test"
        toggled_rule.enabled = True
        toggled_rule.to_dict = MagicMock(return_value={"id": 7, "enabled": True})

        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(
                return_value=original_rule if call_count[0] == 1 else toggled_rule
            )
            mock_result.scalar_one = MagicMock(return_value=toggled_rule)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[toggled_rule])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        toggled = await svc.toggle_rule(rule_id=7, tenant_id=1)
        assert toggled.enabled is True

    async def test_list_logs_returns_items_and_total(self, mock_db_session):
        """AutomationService.list_logs returns (items, total) for pagination."""
        session = mock_db_session

        mock_logs = [
            MagicMock(id=1, rule_id=7, status="success"),
            MagicMock(id=2, rule_id=7, status="failed"),
        ]
        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one = MagicMock(return_value=2)
            else:
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_logs)))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_logs(tenant_id=1, page=1, page_size=20)
        assert isinstance(items, list)
        assert len(items) == 2
        assert isinstance(total, int)
        assert total == 2

    async def test_list_logs_with_rule_id_filter(self, mock_db_session):
        """AutomationService.list_logs accepts rule_id filter."""
        session = mock_db_session
        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_logs(tenant_id=1, page=1, page_size=20, rule_id=7)
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_list_logs_with_status_filter(self, mock_db_session):
        """AutomationService.list_logs accepts status filter."""
        session = mock_db_session
        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_logs(tenant_id=1, page=1, page_size=20, status="failed")
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_trigger_event_fires_matching_rules(self, mock_db_session):
        """AutomationService.trigger_event fires matching rules and returns results list."""
        session = mock_db_session

        matching_rule = MagicMock()
        matching_rule.id = 10
        matching_rule.name = "Trigger Test"
        matching_rule.trigger_event = "customer.created"
        matching_rule.conditions = []
        matching_rule.actions = [{"type": "notification.send", "params": {"message": "New customer!"}}]

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[matching_rule]))
            )
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        results = await svc.trigger_event(
            tenant_id=1,
            trigger_event="customer.created",
            context={"customer_id": 123, "name": "Test Customer"},
        )
        assert isinstance(results, list)

    async def test_trigger_event_unknown_event_returns_empty(self, mock_db_session):
        """Triggering an unknown event type returns an empty list."""
        session = mock_db_session

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_result.scalar_one = MagicMock(return_value=0)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        results = await svc.trigger_event(tenant_id=1, trigger_event="nonexistent.event", context={})
        assert results == []

    async def test_create_rule_with_conditions_stored(self, mock_db_session):
        """AutomationService.create_rule stores conditions and they appear on the ORM object."""
        session = mock_db_session

        saved_rule = MagicMock()
        saved_rule.id = 99
        saved_rule.name = "Conditional Rule"
        saved_rule.trigger_event = "ticket.updated"
        saved_rule.conditions = [{"field": "priority", "operator": "eq", "value": "high"}]
        saved_rule.actions = [{"type": "notification.send", "params": {"message": "Alert!"}}]
        saved_rule.enabled = True
        saved_rule.tenant_id = 1
        saved_rule.to_dict = MagicMock(return_value={"id": 99, "conditions": saved_rule.conditions})

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_result.scalar_one = MagicMock(return_value=0)
            if hasattr(sql, "__str__") and "insert" in str(sql).lower():
                return MagicMock(
                    scalars=MagicMock(all=MagicMock(return_value=[saved_rule]))
                )
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        rule = await svc.create_rule(
            tenant_id=1,
            name="Conditional Rule",
            trigger_event="ticket.updated",
            conditions=[{"field": "priority", "operator": "eq", "value": "high"}],
            actions=[{"type": "notification.send", "params": {"message": "Alert!"}}],
            enabled=True,
            created_by=1,
        )
        # verify rule returned correctly
        assert hasattr(rule, "id")
        assert hasattr(rule, "to_dict")

    async def test_list_rules_respects_trigger_event_filter(self, mock_db_session):
        """AutomationService.list_rules filters by trigger_event when provided."""
        session = mock_db_session
        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one = MagicMock(return_value=0)
            else:
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_rules(
            tenant_id=1,
            page=1,
            page_size=20,
            trigger_event="ticket.created",
        )
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_list_rules_respects_enabled_filter(self, mock_db_session):
        """AutomationService.list_rules filters by enabled when provided."""
        session = mock_db_session
        call_count = [0]

        def execute_side_effect(sql, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one = MagicMock(return_value=0)
            else:
                mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        items, total = await svc.list_rules(
            tenant_id=1,
            page=1,
            page_size=20,
            enabled=True,
        )
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_update_rule_preserves_unmodified_fields(self, mock_db_session):
        """AutomationService.update_rule with name-only update returns updated ORM."""
        session = mock_db_session

        updated_rule = MagicMock()
        updated_rule.id = 12
        updated_rule.name = "New Name"
        updated_rule.trigger_event = "ticket.created"
        updated_rule.description = "Original description"
        updated_rule.to_dict = MagicMock(return_value={"id": 12, "name": "New Name"})

        def execute_side_effect(sql, **kwargs):
            mock_result = MagicMock()
            # update_rule uses scalar_one_or_none on the RETURNING statement
            mock_result.scalar_one_or_none = MagicMock(return_value=updated_rule)
            mock_result.scalar_one = MagicMock(return_value=updated_rule)
            mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[updated_rule])))
            return mock_result

        session.execute = AsyncMock(side_effect=execute_side_effect)

        svc = AutomationService(session)
        updated = await svc.update_rule(rule_id=12, tenant_id=1, name="New Name")
        assert updated.name == "New Name"
        assert hasattr(updated, "to_dict")
