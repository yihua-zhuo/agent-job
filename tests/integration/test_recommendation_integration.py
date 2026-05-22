"""
Integration tests for RecommendationModel and RiskSignalModel.

Run against a real PostgreSQL database:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/integration/test_recommendation_integration.py -v

Requires DATABASE_URL (or TEST_DATABASE_URL) pointing at a live Postgres instance.
Each test gets a fresh schema via TRUNCATE CASCADE (see conftest.py).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from db.models.recommendation import NextAction, RecommendationModel, RiskLevel, RiskSignalModel
from services.pipeline_service import PipelineService
from services.sales_service import SalesService
from services.user_service import UserService


async def _seed_user(async_session, tenant_id: int = 1) -> int:
    """Create a user and return their id."""
    user_svc = UserService(async_session)
    suffix = uuid.uuid4().hex[:8]
    reg = await user_svc.create_user(
        username=f"recuser_{suffix}",
        email=f"rec_{suffix}@example.com",
        password="Test@Pass1234",
        tenant_id=tenant_id,
    )
    return reg.id


async def _seed_customer(async_session, tenant_id: int = 1, **overrides):
    """Create a customer and return the CustomerModel."""
    from services.customer_service import CustomerService

    cust_svc = CustomerService(async_session)
    suffix = uuid.uuid4().hex[:8]
    data = {"name": f"Rec Cust {suffix}", "email": f"rec_{suffix}@example.com", **overrides}
    return await cust_svc.create_customer(data=data, tenant_id=tenant_id)


async def _seed_opportunity(async_session, tenant_id: int, customer_id: int) -> int:
    """Create an opportunity via SalesService and return the opportunity id."""
    sales_svc = SalesService(async_session)
    pipe_svc = PipelineService(async_session)
    pipe = await pipe_svc.create_pipeline(tenant_id=tenant_id, data={"name": f"Rec Pipe {uuid.uuid4().hex[:8]}"})
    uid = await _seed_user(async_session, tenant_id)
    result = await sales_svc.create_opportunity(
        tenant_id=tenant_id,
        data={
            "name": f"Rec Opp {uuid.uuid4().hex[:8]}",
            "customer_id": customer_id,
            "pipeline_id": pipe.id,
            "amount": "10000",
            "stage": "qualified",
            "owner_id": uid,
        },
    )
    return result["id"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestRecommendationCreateAndGet:
    """Test create/retrieve for RecommendationModel and RiskSignalModel plus tenant isolation."""

    async def test_create_and_get_recommendation(self, db_schema, tenant_id, async_session):
        """Insert a RecommendationModel row directly and fetch it back via the session."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        rec = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.CALL.value,
            confidence=0.85,
            reasons={"reason": "Strong fit for enterprise tier", "urgency": "high"},
            similar_deals=[{"name": "Acme Corp", "amount": 50000, "won": True}],
        )
        async_session.add(rec)
        await async_session.flush()
        await async_session.refresh(rec)

        result = await async_session.execute(
            select(RecommendationModel).where(RecommendationModel.id == rec.id)
        )
        fetched = result.scalar_one()

        assert fetched.id == rec.id
        assert fetched.tenant_id == tenant_id
        assert fetched.opportunity_id == opp_id
        assert fetched.next_action == NextAction.CALL.value
        assert fetched.confidence == 0.85
        assert fetched.reasons == {"reason": "Strong fit for enterprise tier", "urgency": "high"}
        assert fetched.similar_deals == [{"name": "Acme Corp", "amount": 50000, "won": True}]
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    async def test_create_and_get_risk_signal(self, db_schema, tenant_id, async_session):
        """Insert a RiskSignalModel row directly and fetch it back via the session."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        signal = RiskSignalModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            risk_level=RiskLevel.HIGH.value,
            risk_factors={"budget_concern": True, "competitor": "VendorX", "timeline_risk": 0.8},
        )
        async_session.add(signal)
        await async_session.flush()
        await async_session.refresh(signal)

        result = await async_session.execute(
            select(RiskSignalModel).where(RiskSignalModel.id == signal.id)
        )
        fetched = result.scalar_one()

        assert fetched.id == signal.id
        assert fetched.tenant_id == tenant_id
        assert fetched.opportunity_id == opp_id
        assert fetched.risk_level == RiskLevel.HIGH.value
        assert fetched.risk_factors == {
            "budget_concern": True,
            "competitor": "VendorX",
            "timeline_risk": 0.8,
        }
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    async def test_recommendation_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Each tenant sees only their own recommendations — even when referencing the same opportunity_id."""
        cust1 = await _seed_customer(async_session, tenant_id)
        cust2 = await _seed_customer(async_session, tenant_id_2)
        opp_id_1 = await _seed_opportunity(async_session, tenant_id, cust1.id)
        opp_id_2 = await _seed_opportunity(async_session, tenant_id_2, cust2.id)

        rec1 = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id_1,
            next_action=NextAction.EMAIL.value,
            confidence=0.9,
            reasons={"signal": "warm_lead"},
            similar_deals=[],
        )
        rec2 = RecommendationModel(
            tenant_id=tenant_id_2,
            opportunity_id=opp_id_2,
            next_action=NextAction.DEMO.value,
            confidence=0.5,
            reasons={"signal": "cold_lead"},
            similar_deals=[],
        )
        async_session.add(rec1)
        async_session.add(rec2)
        await async_session.flush()

        # Tenant 1 should see only rec1
        result_t1 = await async_session.execute(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id,
                RecommendationModel.opportunity_id == opp_id_1,
            )
        )
        t1_rows = result_t1.scalars().all()
        assert len(t1_rows) == 1
        assert t1_rows[0].next_action == NextAction.EMAIL.value
        assert t1_rows[0].confidence == 0.9

        # Tenant 2 should see only rec2
        result_t2 = await async_session.execute(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id_2,
                RecommendationModel.opportunity_id == opp_id_2,
            )
        )
        t2_rows = result_t2.scalars().all()
        assert len(t2_rows) == 1
        assert t2_rows[0].next_action == NextAction.DEMO.value
        assert t2_rows[0].confidence == 0.5

        # Negative isolation: tenant 1 must NOT see tenant 2's rows
        cross_t1 = await async_session.execute(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id,
                RecommendationModel.opportunity_id == opp_id_2,
            )
        )
        assert len(cross_t1.scalars().all()) == 0

        # Negative isolation: tenant 2 must NOT see tenant 1's rows
        cross_t2 = await async_session.execute(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id_2,
                RecommendationModel.opportunity_id == opp_id_1,
            )
        )
        assert len(cross_t2.scalars().all()) == 0

    async def test_risk_signal_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Each tenant sees only their own risk signals — cross-tenant queries return zero rows."""
        cust1 = await _seed_customer(async_session, tenant_id)
        cust2 = await _seed_customer(async_session, tenant_id_2)
        opp_id_1 = await _seed_opportunity(async_session, tenant_id, cust1.id)
        opp_id_2 = await _seed_opportunity(async_session, tenant_id_2, cust2.id)

        signal1 = RiskSignalModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id_1,
            risk_level=RiskLevel.HIGH.value,
            risk_factors={"budget_concern": True},
        )
        signal2 = RiskSignalModel(
            tenant_id=tenant_id_2,
            opportunity_id=opp_id_2,
            risk_level=RiskLevel.LOW.value,
            risk_factors={"timeline_risk": 0.2},
        )
        async_session.add(signal1)
        async_session.add(signal2)
        await async_session.flush()

        # Tenant 1 should see only signal1
        result_t1 = await async_session.execute(
            select(RiskSignalModel).where(
                RiskSignalModel.tenant_id == tenant_id,
                RiskSignalModel.opportunity_id == opp_id_1,
            )
        )
        t1_rows = result_t1.scalars().all()
        assert len(t1_rows) == 1
        assert t1_rows[0].risk_level == RiskLevel.HIGH.value

        # Tenant 2 should see only signal2
        result_t2 = await async_session.execute(
            select(RiskSignalModel).where(
                RiskSignalModel.tenant_id == tenant_id_2,
                RiskSignalModel.opportunity_id == opp_id_2,
            )
        )
        t2_rows = result_t2.scalars().all()
        assert len(t2_rows) == 1
        assert t2_rows[0].risk_level == RiskLevel.LOW.value

        # Negative isolation: tenant 1 must NOT see tenant 2's rows
        cross_t1 = await async_session.execute(
            select(RiskSignalModel).where(
                RiskSignalModel.tenant_id == tenant_id,
                RiskSignalModel.opportunity_id == opp_id_2,
            )
        )
        assert len(cross_t1.scalars().all()) == 0

        # Negative isolation: tenant 2 must NOT see tenant 1's rows
        cross_t2 = await async_session.execute(
            select(RiskSignalModel).where(
                RiskSignalModel.tenant_id == tenant_id_2,
                RiskSignalModel.opportunity_id == opp_id_1,
            )
        )
        assert len(cross_t2.scalars().all()) == 0

    async def test_to_dict_json_serializable(self, db_schema, tenant_id, async_session):
        """to_dict() on both models returns JSON-serializable output including JSON columns."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        rec = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.PROPOSAL.value,
            confidence=0.75,
            reasons={"stage": "negotiation"},
            similar_deals=[{"id": 1, "name": "Deal A"}],
        )
        async_session.add(rec)
        await async_session.flush()

        d = rec.to_dict()
        assert d["next_action"] == "proposal"
        assert d["confidence"] == 0.75
        assert d["reasons"] == {"stage": "negotiation"}
        assert d["similar_deals"] == [{"id": 1, "name": "Deal A"}]

        signal = RiskSignalModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            risk_level=RiskLevel.MEDIUM.value,
            risk_factors={"churn_risk": 0.3},
        )
        async_session.add(signal)
        await async_session.flush()

        d_sig = signal.to_dict()
        assert d_sig["risk_level"] == "medium"
        assert d_sig["risk_factors"] == {"churn_risk": 0.3}

    async def test_recommendation_unique_constraint(self, db_schema, tenant_id, async_session):
        """Duplicate opportunity_id for the same tenant raises an appropriate error."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        rec1 = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.CALL.value,
            confidence=0.8,
            reasons={},
            similar_deals=[],
        )
        async_session.add(rec1)
        await async_session.flush()

        rec2 = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.EMAIL.value,
            confidence=0.6,
            reasons={},
            similar_deals=[],
        )
        async_session.add(rec2)
        with pytest.raises(Exception):  # integrity error from duplicate key
            await async_session.flush()

    async def test_null_json_columns(self, db_schema, tenant_id, async_session):
        """recommendations with null reasons/similar_deals insert and round-trip correctly."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        rec = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.MEETING.value,
            confidence=0.7,
            reasons=None,
            similar_deals=None,
        )
        async_session.add(rec)
        await async_session.flush()
        await async_session.refresh(rec)

        assert rec.reasons is None
        assert rec.similar_deals is None

        d = rec.to_dict()
        assert d["reasons"] is None
        assert d["similar_deals"] is None

    async def test_invalid_risk_level_string(self, db_schema, tenant_id, async_session):
        """Invalid risk_level string raises ValueError in to_dict() to catch DB corruption early."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        signal = RiskSignalModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            risk_level="invalid_level",
            risk_factors={"test": True},
        )
        async_session.add(signal)
        await async_session.flush()
        await async_session.refresh(signal)

        with pytest.raises(ValueError):
            signal.to_dict()

    async def test_to_dict_excludes_tenant_id(self, db_schema, tenant_id, async_session):
        """to_dict() must not expose internal tenant_id in external responses."""
        cust = await _seed_customer(async_session, tenant_id)
        opp_id = await _seed_opportunity(async_session, tenant_id, cust.id)

        rec = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            next_action=NextAction.DEMO.value,
            confidence=0.6,
            reasons={"x": 1},
            similar_deals=[],
        )
        async_session.add(rec)
        await async_session.flush()

        d = rec.to_dict()
        assert "tenant_id" not in d

        signal = RiskSignalModel(
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            risk_level=RiskLevel.LOW.value,
            risk_factors={"y": 2},
        )
        async_session.add(signal)
        await async_session.flush()

        d_sig = signal.to_dict()
        assert "tenant_id" not in d_sig
