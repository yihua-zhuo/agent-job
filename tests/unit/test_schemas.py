"""Unit tests for pkg/response/schemas.py — new concrete typed response schemas."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from pkg.response.schemas import (
    SuccessEnvelope,
    ErrorEnvelope,
    APIResponse,
    CustomerData,
    CustomerSearchData,
    CustomerSearchResponse,
    CustomerListData,
    CustomerResponse,
    CustomerListResponse,
    TagData,
    TagResponse,
    IdData,
    StatusChangeResponse,
    OwnerChangeResponse,
    BulkImportData,
    BulkImportResponse,
    PipelineData,
    PipelineListData,
    PipelineStatsData,
    PipelineFunnelData,
    PipelineResponse,
    PipelineListResponse,
    PipelineStatsResponse,
    PipelineFunnelResponse,
    OpportunityData,
    OpportunityListData,
    OpportunityResponse,
    OpportunityListResponse,
    StageChangeData,
    StageChangeResponse,
    OwnerForecastData,
    ForecastData,
    ForecastResponse,
)


# ---------------------------------------------------------------------------
# SuccessEnvelope
# ---------------------------------------------------------------------------

class TestSuccessEnvelope:
    def test_defaults(self):
        env = SuccessEnvelope()
        assert env.success is True
        assert env.message == "OK"

    def test_custom_message(self):
        env = SuccessEnvelope(message="Created")
        assert env.message == "Created"

    def test_success_field_immutable_default(self):
        env = SuccessEnvelope(success=False)
        assert env.success is False


# ---------------------------------------------------------------------------
# ErrorEnvelope
# ---------------------------------------------------------------------------

class TestErrorEnvelope:
    def test_defaults(self):
        env = ErrorEnvelope(message="Something went wrong")
        assert env.success is False
        assert env.message == "Something went wrong"

    def test_message_required(self):
        with pytest.raises(ValidationError):
            ErrorEnvelope()

    def test_success_is_always_false_by_default(self):
        env = ErrorEnvelope(message="err")
        assert env.success is False


# ---------------------------------------------------------------------------
# APIResponse (generic base)
# ---------------------------------------------------------------------------

class TestAPIResponse:
    def test_ok_classmethod(self):
        resp = APIResponse.ok(data={"id": 1}, message="Success")
        assert resp.success is True
        assert resp.message == "Success"
        assert resp.data == {"id": 1}

    def test_ok_default_message(self):
        resp = APIResponse.ok(data=42)
        assert resp.message == "OK"

    def test_error_classmethod(self):
        resp = APIResponse.error("Not found")
        assert resp.success is False
        assert resp.message == "Not found"
        assert resp.data is None

    def test_defaults(self):
        resp = APIResponse()
        assert resp.success is True
        assert resp.message == "OK"
        assert resp.data is None


# ---------------------------------------------------------------------------
# CustomerData
# ---------------------------------------------------------------------------

VALID_CUSTOMER = {
    "id": 1,
    "tenant_id": 10,
    "name": "Alice",
    "email": "alice@example.com",
    "phone": "555-1234",
    "company": "ACME",
    "status": "lead",
    "owner_id": 5,
    "tags": ["vip"],
    "created_at": None,
    "updated_at": None,
}


class TestCustomerData:
    def test_valid_customer(self):
        c = CustomerData(**VALID_CUSTOMER)
        assert c.id == 1
        assert c.name == "Alice"
        assert c.status == "lead"

    def test_all_valid_statuses(self):
        valid_statuses = ["lead", "customer", "partner", "prospect", "active", "inactive", "blocked"]
        for s in valid_statuses:
            data = {**VALID_CUSTOMER, "status": s}
            c = CustomerData(**data)
            assert c.status == s

    def test_invalid_status_raises(self):
        data = {**VALID_CUSTOMER, "status": "unknown"}
        with pytest.raises(ValidationError):
            CustomerData(**data)

    def test_name_min_length(self):
        data = {**VALID_CUSTOMER, "name": ""}
        with pytest.raises(ValidationError):
            CustomerData(**data)

    def test_name_max_length(self):
        data = {**VALID_CUSTOMER, "name": "x" * 201}
        with pytest.raises(ValidationError):
            CustomerData(**data)

    def test_owner_id_cannot_be_negative(self):
        data = {**VALID_CUSTOMER, "owner_id": -1}
        with pytest.raises(ValidationError):
            CustomerData(**data)

    def test_owner_id_zero_allowed(self):
        data = {**VALID_CUSTOMER, "owner_id": 0}
        c = CustomerData(**data)
        assert c.owner_id == 0

    def test_tags_default_empty_list(self):
        data = {**VALID_CUSTOMER}
        data.pop("tags")
        c = CustomerData(**data)
        assert c.tags == []

    def test_optional_fields_can_be_none(self):
        data = {**VALID_CUSTOMER, "email": None, "phone": None, "company": None}
        c = CustomerData(**data)
        assert c.email is None
        assert c.phone is None
        assert c.company is None

    def test_model_validate_from_dict(self):
        c = CustomerData.model_validate(VALID_CUSTOMER)
        assert c.tenant_id == 10

    def test_email_max_length(self):
        data = {**VALID_CUSTOMER, "email": "a" * 256 + "@x.com"}
        with pytest.raises(ValidationError):
            CustomerData(**data)

    def test_created_at_datetime_accepted(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        data = {**VALID_CUSTOMER, "created_at": now}
        c = CustomerData(**data)
        assert c.created_at == now


# ---------------------------------------------------------------------------
# CustomerSearchData / CustomerSearchResponse
# ---------------------------------------------------------------------------

class TestCustomerSearchData:
    def test_basic(self):
        customer = CustomerData(**VALID_CUSTOMER)
        data = CustomerSearchData(keyword="alice", items=[customer])
        assert data.keyword == "alice"
        assert len(data.items) == 1

    def test_empty_items(self):
        data = CustomerSearchData(keyword="x", items=[])
        assert data.items == []


class TestCustomerSearchResponse:
    def test_inherits_success_envelope(self):
        customer = CustomerData(**VALID_CUSTOMER)
        resp = CustomerSearchResponse(
            data=CustomerSearchData(keyword="k", items=[customer])
        )
        assert resp.success is True
        assert resp.message == "OK"

    def test_custom_message(self):
        resp = CustomerSearchResponse(
            message="found",
            data=CustomerSearchData(keyword="k", items=[]),
        )
        assert resp.message == "found"


# ---------------------------------------------------------------------------
# CustomerListData / CustomerListResponse
# ---------------------------------------------------------------------------

class TestCustomerListData:
    def test_valid(self):
        customer = CustomerData(**VALID_CUSTOMER)
        d = CustomerListData(
            items=[customer], total=1, page=1, page_size=20,
            total_pages=1, has_next=False, has_prev=False,
        )
        assert d.total == 1
        assert d.has_next is False
        assert d.has_prev is False

    def test_total_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            CustomerListData(
                items=[], total=-1, page=1, page_size=20,
                total_pages=0, has_next=False, has_prev=False,
            )

    def test_page_must_be_at_least_1(self):
        with pytest.raises(ValidationError):
            CustomerListData(
                items=[], total=0, page=0, page_size=20,
                total_pages=0, has_next=False, has_prev=False,
            )

    def test_page_size_must_be_at_least_1(self):
        with pytest.raises(ValidationError):
            CustomerListData(
                items=[], total=0, page=1, page_size=0,
                total_pages=0, has_next=False, has_prev=False,
            )


class TestCustomerResponse:
    def test_data_is_optional(self):
        resp = CustomerResponse(message="Deleted")
        assert resp.data is None
        assert resp.success is True

    def test_with_customer_data(self):
        customer = CustomerData(**VALID_CUSTOMER)
        resp = CustomerResponse(message="OK", data=customer)
        assert resp.data.id == 1


class TestCustomerListResponse:
    def test_basic(self):
        customer = CustomerData(**VALID_CUSTOMER)
        list_data = CustomerListData(
            items=[customer], total=1, page=1, page_size=20,
            total_pages=1, has_next=False, has_prev=False,
        )
        resp = CustomerListResponse(data=list_data)
        assert resp.success is True
        assert resp.data.total == 1


# ---------------------------------------------------------------------------
# TagData / TagResponse
# ---------------------------------------------------------------------------

class TestTagData:
    def test_valid(self):
        t = TagData(id=1, tag="vip")
        assert t.id == 1
        assert t.tag == "vip"


class TestTagResponse:
    def test_data_optional(self):
        resp = TagResponse(message="Tag added")
        assert resp.data is None

    def test_with_tag_data(self):
        resp = TagResponse(message="OK", data=TagData(id=1, tag="premium"))
        assert resp.data.tag == "premium"


# ---------------------------------------------------------------------------
# IdData / StatusChangeResponse / OwnerChangeResponse
# ---------------------------------------------------------------------------

class TestIdData:
    def test_all_fields(self):
        d = IdData(id=5, status="active", owner_id=3)
        assert d.id == 5
        assert d.status == "active"
        assert d.owner_id == 3

    def test_optional_fields_none(self):
        d = IdData(id=5)
        assert d.status is None
        assert d.owner_id is None


class TestStatusChangeResponse:
    def test_data_optional(self):
        resp = StatusChangeResponse(message="Status changed")
        assert resp.data is None
        assert resp.success is True

    def test_with_id_data(self):
        resp = StatusChangeResponse(
            message="OK", data=IdData(id=1, status="active")
        )
        assert resp.data.status == "active"


class TestOwnerChangeResponse:
    def test_data_optional(self):
        resp = OwnerChangeResponse(message="Owner changed")
        assert resp.data is None

    def test_with_id_data(self):
        resp = OwnerChangeResponse(
            message="OK", data=IdData(id=1, owner_id=42)
        )
        assert resp.data.owner_id == 42


# ---------------------------------------------------------------------------
# BulkImportData / BulkImportResponse
# ---------------------------------------------------------------------------

class TestBulkImportData:
    def test_valid(self):
        d = BulkImportData(imported=5, errors=[])
        assert d.imported == 5
        assert d.errors == []

    def test_imported_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            BulkImportData(imported=-1, errors=[])

    def test_errors_default_empty(self):
        d = BulkImportData(imported=0)
        assert d.errors == []

    def test_with_errors(self):
        d = BulkImportData(imported=2, errors=[{"index": 0, "error": "bad"}])
        assert len(d.errors) == 1


class TestBulkImportResponse:
    def test_basic(self):
        resp = BulkImportResponse(
            message="Imported",
            data=BulkImportData(imported=3, errors=[]),
        )
        assert resp.success is True
        assert resp.data.imported == 3


# ---------------------------------------------------------------------------
# PipelineData / PipelineListData
# ---------------------------------------------------------------------------

VALID_PIPELINE = {
    "id": 1,
    "tenant_id": 5,
    "name": "Sales",
    "stages": ["lead", "qualified", "closed"],
    "is_default": True,
    "created_at": None,
    "updated_at": None,
}


class TestPipelineData:
    def test_valid(self):
        p = PipelineData(**VALID_PIPELINE)
        assert p.name == "Sales"
        assert p.is_default is True
        assert len(p.stages) == 3

    def test_name_min_length(self):
        data = {**VALID_PIPELINE, "name": ""}
        with pytest.raises(ValidationError):
            PipelineData(**data)

    def test_name_max_length(self):
        data = {**VALID_PIPELINE, "name": "x" * 201}
        with pytest.raises(ValidationError):
            PipelineData(**data)

    def test_model_validate(self):
        p = PipelineData.model_validate(VALID_PIPELINE)
        assert p.tenant_id == 5


class TestPipelineListData:
    def test_valid(self):
        p = PipelineData(**VALID_PIPELINE)
        d = PipelineListData(items=[p], total=1)
        assert d.total == 1

    def test_total_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            PipelineListData(items=[], total=-1)


class TestPipelineStatsData:
    def test_valid(self):
        s = PipelineStatsData(pipeline_id=1, total=10, won=3, lost=2)
        assert s.total == 10
        assert s.won == 3

    def test_negative_total_fails(self):
        with pytest.raises(ValidationError):
            PipelineStatsData(pipeline_id=1, total=-1, won=0, lost=0)

    def test_negative_won_fails(self):
        with pytest.raises(ValidationError):
            PipelineStatsData(pipeline_id=1, total=5, won=-1, lost=0)


class TestPipelineFunnelData:
    def test_valid(self):
        f = PipelineFunnelData(pipeline_id=1, stages=[{"name": "lead", "count": 5}])
        assert f.pipeline_id == 1
        assert len(f.stages) == 1


class TestPipelineResponse:
    def test_data_optional(self):
        resp = PipelineResponse(message="Not found")
        assert resp.data is None

    def test_with_pipeline_data(self):
        p = PipelineData(**VALID_PIPELINE)
        resp = PipelineResponse(message="OK", data=p)
        assert resp.data.name == "Sales"


class TestPipelineListResponse:
    def test_basic(self):
        p = PipelineData(**VALID_PIPELINE)
        resp = PipelineListResponse(
            data=PipelineListData(items=[p], total=1)
        )
        assert resp.success is True
        assert resp.data.total == 1


class TestPipelineStatsResponse:
    def test_basic(self):
        resp = PipelineStatsResponse(
            message="OK",
            data=PipelineStatsData(pipeline_id=1, total=5, won=2, lost=1),
        )
        assert resp.data.pipeline_id == 1


class TestPipelineFunnelResponse:
    def test_basic(self):
        resp = PipelineFunnelResponse(
            message="OK",
            data=PipelineFunnelData(pipeline_id=1, stages=[]),
        )
        assert resp.data.pipeline_id == 1


# ---------------------------------------------------------------------------
# OpportunityData / OpportunityListData
# ---------------------------------------------------------------------------

VALID_OPP = {
    "id": 1,
    "tenant_id": 2,
    "name": "Big Deal",
    "customer_id": 10,
    "pipeline_id": 3,
    "stage": "qualified",
    "amount": "5000.00",
    "probability": 75,
    "expected_close_date": "2025-12-31",
    "owner_id": 7,
    "created_at": None,
    "updated_at": None,
}


class TestOpportunityData:
    def test_valid(self):
        o = OpportunityData(**VALID_OPP)
        assert o.name == "Big Deal"
        assert o.probability == 75

    def test_probability_min(self):
        data = {**VALID_OPP, "probability": 0}
        o = OpportunityData(**data)
        assert o.probability == 0

    def test_probability_max(self):
        data = {**VALID_OPP, "probability": 100}
        o = OpportunityData(**data)
        assert o.probability == 100

    def test_probability_below_min_fails(self):
        data = {**VALID_OPP, "probability": -1}
        with pytest.raises(ValidationError):
            OpportunityData(**data)

    def test_probability_above_max_fails(self):
        data = {**VALID_OPP, "probability": 101}
        with pytest.raises(ValidationError):
            OpportunityData(**data)

    def test_optional_expected_close_date(self):
        data = {**VALID_OPP, "expected_close_date": None}
        o = OpportunityData(**data)
        assert o.expected_close_date is None

    def test_model_validate(self):
        o = OpportunityData.model_validate(VALID_OPP)
        assert o.customer_id == 10


class TestOpportunityListData:
    def test_valid(self):
        o = OpportunityData(**VALID_OPP)
        d = OpportunityListData(
            items=[o], total=1, page=1, page_size=20,
            total_pages=1, has_next=False, has_prev=False,
        )
        assert d.total == 1

    def test_page_must_be_at_least_1(self):
        with pytest.raises(ValidationError):
            OpportunityListData(
                items=[], total=0, page=0, page_size=20,
                total_pages=0, has_next=False, has_prev=False,
            )


class TestOpportunityResponse:
    def test_data_optional(self):
        resp = OpportunityResponse(message="Not found")
        assert resp.data is None

    def test_with_opportunity_data(self):
        o = OpportunityData(**VALID_OPP)
        resp = OpportunityResponse(message="OK", data=o)
        assert resp.data.name == "Big Deal"


class TestOpportunityListResponse:
    def test_basic(self):
        o = OpportunityData(**VALID_OPP)
        list_data = OpportunityListData(
            items=[o], total=1, page=1, page_size=20,
            total_pages=1, has_next=False, has_prev=False,
        )
        resp = OpportunityListResponse(data=list_data)
        assert resp.success is True


# ---------------------------------------------------------------------------
# StageChangeData / StageChangeResponse
# ---------------------------------------------------------------------------

class TestStageChangeData:
    def test_valid(self):
        s = StageChangeData(id=5, stage="qualified")
        assert s.id == 5
        assert s.stage == "qualified"


class TestStageChangeResponse:
    def test_basic(self):
        resp = StageChangeResponse(
            message="Stage changed",
            data=StageChangeData(id=1, stage="closed"),
        )
        assert resp.data.stage == "closed"
        assert resp.success is True


# ---------------------------------------------------------------------------
# Forecast schemas
# ---------------------------------------------------------------------------

class TestOwnerForecastData:
    def test_valid(self):
        d = OwnerForecastData(owner_id=1, forecast={"q1": 1000})
        assert d.owner_id == 1
        assert d.forecast["q1"] == 1000


class TestForecastData:
    def test_owner_id_optional(self):
        d = ForecastData(forecast={"total": 5000})
        assert d.owner_id is None

    def test_with_owner_id(self):
        d = ForecastData(owner_id=3, forecast={"q2": 2000})
        assert d.owner_id == 3


class TestForecastResponse:
    def test_basic(self):
        resp = ForecastResponse(
            message="OK",
            data=ForecastData(forecast={"total": 9000}),
        )
        assert resp.success is True
        assert resp.data.forecast["total"] == 9000

    def test_inherits_success_envelope(self):
        resp = ForecastResponse(
            data=ForecastData(forecast={})
        )
        assert resp.success is True
        assert resp.message == "OK"
