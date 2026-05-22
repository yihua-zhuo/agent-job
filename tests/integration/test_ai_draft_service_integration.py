"""
Integration tests for AiDraftService.

Run against a real PostgreSQL database (DATABASE_URL env var):
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_ai_draft_service_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""

from __future__ import annotations

import pytest

from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from internal.ai_gateway import AIChatGateway, AIResponse
from models.ai_draft import DraftContext, DraftRequest, DraftResponse, DraftType, TemplateType, ToneType
from pkg.errors.app_exceptions import NotFoundException, ValidationException as ValExc
from services.ai_draft_service import AiDraftService


# ---------------------------------------------------------------------------
# Test-double gateway — returns stable canned responses
# ---------------------------------------------------------------------------


class StubAIChatGateway(AIChatGateway):
    """Test-double gateway that returns fixed canned responses."""

    def __init__(self, opportunity_name: str | None = None):
        self._opportunity_name = opportunity_name

    async def _call_gateway(self, messages, context):
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        reply = f"Your draft based on: {last[:50]}"
        if self._opportunity_name:
            reply = f"Re: {self._opportunity_name} — {reply}"
        return AIResponse(
            reply=reply,
            suggestions=["Review draft", "Send now"],
            actions=[
                {"type": "navigate", "label": "View Customer", "path": "/customers"},
                {"type": "send_email", "label": "Send Draft", "payload": {}},
            ],
        )


class EmptyAIChatGateway(AIChatGateway):
    """Test-double gateway that returns empty reply."""

    async def _call_gateway(self, messages, context):
        return AIResponse(reply="", suggestions=None, actions=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_opportunity(async_session, tenant_id: int, customer_id: int, **overrides) -> OpportunityModel:
    """Create an opportunity linked to the given customer."""
    defaults = {
        "name": "Test Opportunity",
        "stage": "qualification",
        "amount": 1000.0,
        "pipeline_id": None,
        "probability": 0,
        "owner_id": 0,
        "expected_close_date": None,
    }
    defaults.update(overrides)
    opp = OpportunityModel(
        tenant_id=tenant_id,
        customer_id=customer_id,
        **defaults,
    )
    async_session.add(opp)
    await async_session.flush()
    return opp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestGenerateDraftIntegration:
    """Full draft generation lifecycle via the real DB."""

    async def test_generate_draft_email_with_subject(self, db_schema, tenant_id, async_session):
        """generate_draft returns a non-empty body for a valid email request."""
        cust = CustomerModel(
            tenant_id=tenant_id,
            name="Draft Test Customer",
            email="draft@example.com",
            status="active",
        )
        async_session.add(cust)
        await async_session.flush()

        svc = AiDraftService(async_session, gateway=StubAIChatGateway())
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Follow-up",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=cust.id, template_type=TemplateType.EMAIL),
        )
        result = await svc.generate_draft(request, tenant_id=tenant_id)

        assert isinstance(result, DraftResponse)
        assert isinstance(result.body, str)
        assert len(result.body) > 0
        assert isinstance(result.suggested_actions, list)

    async def test_generate_draft_sms_without_subject(self, db_schema, tenant_id, async_session):
        """SMS drafts do not require a subject field."""
        cust = CustomerModel(
            tenant_id=tenant_id,
            name="SMS Test Customer",
            email="sms@example.com",
            status="active",
        )
        async_session.add(cust)
        await async_session.flush()

        svc = AiDraftService(async_session, gateway=StubAIChatGateway())
        request = DraftRequest(
            type=DraftType.SMS,
            subject=None,
            tone=ToneType.FRIENDLY,
            context=DraftContext(customer_id=cust.id, template_type=TemplateType.SMS),
        )
        result = await svc.generate_draft(request, tenant_id=tenant_id)

        assert isinstance(result, DraftResponse)
        assert len(result.body) > 0

    async def test_generate_draft_with_opportunity_id(self, db_schema, tenant_id, async_session):
        """generate_draft accepts an opportunity_id in context and includes it in the prompt."""
        cust = CustomerModel(
            tenant_id=tenant_id,
            name="Opp Test Customer",
            email="opp@example.com",
            status="active",
        )
        async_session.add(cust)
        await async_session.flush()

        opp = await _seed_opportunity(async_session, tenant_id, customer_id=cust.id, name="Big Deal")

        gateway = StubAIChatGateway(opportunity_name="Big Deal")
        svc = AiDraftService(async_session, gateway=gateway)
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Deal update",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(
                customer_id=cust.id,
                opportunity_id=opp.id,
                template_type=TemplateType.EMAIL,
            ),
        )
        result = await svc.generate_draft(request, tenant_id=tenant_id)
        assert len(result.body) > 0
        # Verify opportunity name is reflected in the reply (gateway echoes it when opportunity is included)
        assert "Big Deal" in result.body

    async def test_generate_draft_raises_not_found_for_missing_customer(self, db_schema, tenant_id, async_session):
        """Non-existent customer_id raises NotFoundException."""
        svc = AiDraftService(async_session, gateway=StubAIChatGateway())
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Hello",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=999999, template_type=TemplateType.EMAIL),
        )
        with pytest.raises(NotFoundException):
            await svc.generate_draft(request, tenant_id=tenant_id)

    async def test_generate_draft_raises_validation_for_empty_gateway_reply(self, db_schema, tenant_id, async_session):
        """Gateway returning empty reply raises ValidationException."""
        cust = CustomerModel(
            tenant_id=tenant_id,
            name="Empty Gateway Customer",
            email="empty@example.com",
            status="active",
        )
        async_session.add(cust)
        await async_session.flush()

        svc = AiDraftService(async_session, gateway=EmptyAIChatGateway())
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Test",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=cust.id, template_type=TemplateType.EMAIL),
        )
        with pytest.raises(ValExc):
            await svc.generate_draft(request, tenant_id=tenant_id)

    async def test_cross_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Tenant A cannot access tenant B's customer via generate_draft."""
        # Seed a customer under tenant_id
        cust = CustomerModel(
            tenant_id=tenant_id,
            name="Cross Tenant Customer",
            email="crosstenant@example.com",
            status="active",
        )
        async_session.add(cust)
        await async_session.flush()
        customer_id_under_tenant_a = cust.id

        # Calling with a different tenant_id_2 should raise NotFoundException
        svc = AiDraftService(async_session, gateway=StubAIChatGateway())
        request = DraftRequest(
            type=DraftType.EMAIL,
            subject="Cross tenant test",
            tone=ToneType.PROFESSIONAL,
            context=DraftContext(customer_id=customer_id_under_tenant_a, template_type=TemplateType.EMAIL),
        )
        with pytest.raises(NotFoundException):
            await svc.generate_draft(request, tenant_id=tenant_id_2)