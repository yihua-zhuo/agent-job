"""Unit tests for src/services/enrichment_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pkg.errors.app_exceptions import ValidationException
from services.enrichment_service import EnrichmentService


# ---------------------------------------------------------------------------
# Mock session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
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


# ---------------------------------------------------------------------------
# lookup — HTTP client mock factory
# ---------------------------------------------------------------------------

def _make_http_response(is_success: bool, data: dict) -> MagicMock:
    """Return a mock httpx response matching httpx 0.28.x sync Response.json()."""
    mock_resp = MagicMock()
    mock_resp.is_success = is_success
    mock_resp.status_code = 500 if not is_success else 200
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

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
            mock_settings.clearbit_api_key = "test-key"
            result = await service.lookup(domain="stripe.com", customer_id=1)

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

    async def test_inserts_enrichment_row(self, service, mock_db_session):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json = MagicMock(return_value={"name": "Acme", "domain": "acme.com"})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            await service.lookup(domain="acme.com", customer_id=1)

        mock_db_session.add.assert_called_once()
        added = mock_db_session.add.call_args[0][0]
        assert added.customer_id == 1
        assert added.provider == "clearbit"
        mock_db_session.flush.assert_awaited_once()
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

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            result = await service.lookup(company_name="Acme Corp", customer_id=1)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["name"] == "Acme Corp"
        assert result["name"] == "Acme Corp"


# ---------------------------------------------------------------------------
# lookup — HTTP error cases
# ---------------------------------------------------------------------------

class TestLookupHttpErrors:
    async def test_http_404_returns_empty_dict(self, service):
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 404
        mock_resp.json = MagicMock(return_value={})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            result = await service.lookup(domain="notfound.example.com", customer_id=1)
        assert result == {}

    async def test_http_500_raises_validation_exception(self, service):
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 500
        mock_resp.json = MagicMock(return_value={})
        mock_get = AsyncMock(return_value=mock_resp)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = mock_get

        with patch("services.enrichment_service.settings") as mock_settings, \
             patch("services.enrichment_service.httpx.AsyncClient", return_value=mock_client):
            mock_settings.clearbit_api_key = "test-key"
            with pytest.raises(ValidationException) as exc_info:
                await service.lookup(domain="stripe.com", customer_id=1)
        assert "Clearbit API error" in exc_info.value.detail

    async def test_missing_api_key_raises(self, service):
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