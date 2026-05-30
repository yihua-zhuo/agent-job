"""Unit tests for src/services/enrichment_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pkg.errors.app_exceptions import NotFoundException, ValidationException
from services.enrichment_service import EnrichmentService


# ---------------------------------------------------------------------------
# Mock session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    # Configure each mock explicitly to catch attribute typos (e.g. execute vs exceute).
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def service(mock_db_session):
    return EnrichmentService(mock_db_session)


# ---------------------------------------------------------------------------
# lookup — argument validation
# ---------------------------------------------------------------------------

class TestLookupArgumentValidation:
    async def test_neither_domain_nor_name_raises(self, service):
        with pytest.raises(ValidationException) as exc_info:
            await service.lookup(domain=None, company_name=None, customer_id=1)
        assert "exactly one" in exc_info.value.detail

    async def test_both_domain_and_name_raises(self, service):
        with pytest.raises(ValidationException) as exc_info:
            await service.lookup(domain="stripe.com", company_name="Stripe", customer_id=1)
        assert "exactly one" in exc_info.value.detail

    async def test_missing_customer_id_raises(self, service):
        with pytest.raises(ValidationException) as exc_info:
            await service.lookup(domain="stripe.com", customer_id=None)
        assert "customer_id" in exc_info.value.detail

    async def test_blank_domain_treated_as_absent(self, service):
        """domain='' should fall through to company_name check."""
        with pytest.raises(ValidationException) as exc_info:
            await service.lookup(domain="", company_name=None, customer_id=1)
        assert "exactly one" in exc_info.value.detail

    async def test_whitespace_only_domain_treated_as_absent(self, service):
        with pytest.raises(ValidationException) as exc_info:
            await service.lookup(domain="   ", company_name=None, customer_id=1)
        assert "exactly one" in exc_info.value.detail


# ---------------------------------------------------------------------------
# lookup — HTTP client mock factory
# ---------------------------------------------------------------------------

def _make_http_response(is_success: bool, status_code: int, data: dict) -> MagicMock:
    """Return a mock httpx response matching httpx 0.28.x sync Response.json()."""
    mock_resp = MagicMock()
    mock_resp.is_success = is_success
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=data)
    return mock_resp


# ---------------------------------------------------------------------------
# lookup — domain path (success)
# ---------------------------------------------------------------------------

class TestLookupDomainSuccess:
    async def test_returns_normalised_dict(self, service, mock_db_session):
        clearbit_payload = {
            "name": "Stripe",
            "domain": "stripe.com",
            "legalName": "Stripe, Inc.",
            "category": {"sector": "Software", "industryGroup": "IT"},
            "logo": "https://logo.clearbit.com/stripe.com/logo.png",
            "linkedin": {"handle": "company/stripe"},
            "geo": {"city": "San Francisco", "state": "CA", "country": "US", "countryCode": "US"},
            "metrics": {
                "employees": 8000,
                "employeesRange": "5000+",
                "annualRevenue": "1000000000",
                "raised": 2000000,
            },
        }

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json = MagicMock(return_value=clearbit_payload)
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        # Mock session.execute for the customer-tenant check
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 42
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            result = await service.lookup(domain="stripe.com", customer_id=1, tenant_id=42)

        assert result["name"] == "Stripe"
        assert result["domain"] == "stripe.com"
        assert result["legal_name"] == "Stripe, Inc."
        assert result["geo_city"] == "San Francisco"
        assert result["metrics_employees"] == 8000

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["domain"] == "stripe.com"

        mock_db_session.add.assert_called_once()
        added = mock_db_session.add.call_args[0][0]
        assert added.provider == "clearbit"
        assert added.raw_data_json == clearbit_payload
        assert added.tenant_id == 42

    async def test_inserts_enrichment_row(self, service, mock_db_session):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json = MagicMock(return_value={"name": "Acme", "domain": "acme.com"})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            await service.lookup(domain="acme.com", customer_id=1, tenant_id=1)

        mock_db_session.add.assert_called_once()
        added = mock_db_session.add.call_args[0][0]
        assert added.customer_id == 1
        assert added.tenant_id == 1
        assert added.provider == "clearbit"
        assert added.raw_data_json == {"name": "Acme", "domain": "acme.com"}
        mock_db_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# lookup — company_name path (success)
# ---------------------------------------------------------------------------

class TestLookupCompanyNameSuccess:
    async def test_uses_name_param(self, service, mock_db_session):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json = MagicMock(return_value={"name": "Acme Corp", "domain": "acme.com"})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            result = await service.lookup(company_name="Acme Corp", customer_id=1, tenant_id=1)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["name"] == "Acme Corp"
        assert result["name"] == "Acme Corp"


# ---------------------------------------------------------------------------
# lookup — cross-tenant isolation
# ---------------------------------------------------------------------------

class TestLookupCrossTenantIsolation:
    async def test_customer_from_different_tenant_raises_not_found(self, service, mock_db_session):
        """Service raises NotFoundException when customer_id belongs to a different tenant."""
        with patch("services.enrichment_service.settings") as mock_settings:
            mock_settings.clearbit_api_key = "test-key"
            # No customer found for this tenant_id + customer_id combination
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(NotFoundException) as exc_info:
                await service.lookup(domain="stripe.com", customer_id=1, tenant_id=999)
            assert "Customer" in exc_info.value.detail


# ---------------------------------------------------------------------------
# lookup — HTTP error cases
# ---------------------------------------------------------------------------

class TestLookupHttpErrors:
    async def test_http_404_raises_validation_exception(self, service, mock_db_session):
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 404
        mock_resp.json = MagicMock(return_value={})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            with pytest.raises(ValidationException) as exc_info:
                await service.lookup(domain="notfound.example.com", customer_id=1, tenant_id=1)
        assert "No company found" in exc_info.value.detail

    async def test_http_500_raises_validation_exception(self, service, mock_db_session):
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 500
        mock_resp.json = MagicMock(return_value={})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            with pytest.raises(ValidationException) as exc_info:
                await service.lookup(domain="stripe.com", customer_id=1, tenant_id=1)
        assert "Clearbit API error" in exc_info.value.detail

    async def test_http_503_raises_validation_exception(self, service, mock_db_session):
        """Non-500 non-404 errors (e.g. 503) also raise ValidationException."""
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 503
        mock_resp.json = MagicMock(return_value={})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            with pytest.raises(ValidationException) as exc_info:
                await service.lookup(domain="stripe.com", customer_id=1, tenant_id=1)
        assert "Clearbit API error: 503" in exc_info.value.detail

    async def test_missing_api_key_raises(self, service, mock_db_session):
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.tenant_id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_customer)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("services.enrichment_service.settings") as mock_settings:
            mock_settings.clearbit_api_key = None

            with pytest.raises(ValidationException) as exc_info:
                await service.lookup(domain="stripe.com", customer_id=1)
            assert "not configured" in exc_info.value.detail


# ---------------------------------------------------------------------------
# _normalise_clearbit
# ---------------------------------------------------------------------------

class TestNormaliseClearbit:
    def test_includes_present_keys(self, service):
        data = {
            "name": "Stripe",
            "domain": "stripe.com",
            "legalName": "Stripe, Inc.",
            "logo": "https://logo.example.com/logo.png",
            "linkedin": {"handle": "company/stripe"},
        }
        result = service._normalise_clearbit(data)
        assert result["name"] == "Stripe"
        assert result["domain"] == "stripe.com"
        assert result["legal_name"] == "Stripe, Inc."
        assert result["logo"] == "https://logo.example.com/logo.png"

    def test_skips_null_values(self, service):
        data = {"name": "Stripe", "domain": None}
        result = service._normalise_clearbit(data)
        assert "name" in result
        assert "domain" not in result

    def test_flattens_geo(self, service):
        data = {
            "name": "Stripe",
            "geo": {"city": "San Francisco", "country": "US", "countryCode": "US"},
        }
        result = service._normalise_clearbit(data)
        assert result["geo_city"] == "San Francisco"
        assert result["geo_country"] == "US"
        assert result["geo_countryCode"] == "US"

    def test_flattens_metrics(self, service):
        data = {
            "name": "Stripe",
            "metrics": {"employees": 8000, "annualRevenue": "1000000000", "raised": 2000000},
        }
        result = service._normalise_clearbit(data)
        assert result["metrics_employees"] == 8000
        assert result["metrics_annualRevenue"] == "1000000000"

    def test_skips_missing_geo_and_metrics(self, service):
        data = {"name": "Acme"}
        result = service._normalise_clearbit(data)
        assert "name" in result
        assert "geo_city" not in result
        assert "metrics_employees" not in result

    def test_empty_input_returns_empty_dict(self, service):
        """Empty input dict should return empty dict (no keys present)."""
        assert service._normalise_clearbit({}) == {}
