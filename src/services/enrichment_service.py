"""Enrichment service — third-party company data enrichment via Clearbit."""

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import settings
from db.models.customer import CustomerModel
from db.models.customer_enrichment import CustomerEnrichmentModel
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class EnrichmentService:
    """Third-party company data enrichment."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def lookup(
        self,
        domain: str | None = None,
        company_name: str | None = None,
        *,
        tenant_id: int | None = None,
        customer_id: int | None = None,
    ) -> dict[str, Any]:
        """Look up company enrichment data from a third-party provider.

        Requires exactly one of *domain* or *company_name*.
        Persists the raw provider payload to ``customer_enrichments`` and returns
        a normalised dict of enriched fields.
        """
        # Normalise: treat blank strings as absent
        if domain is not None:
            domain = domain.strip()
            domain = domain if domain else None
        if company_name is not None:
            company_name = company_name.strip()
            company_name = company_name if company_name else None

        has_domain = domain is not None
        has_name = company_name is not None

        if has_domain == has_name:
            raise ValidationException("Provide exactly one of domain or company_name")

        if customer_id is None:
            raise ValidationException("customer_id is required for enrichment lookup")

        return await self._lookup_clearbit(
            domain=domain,
            company_name=company_name,
            tenant_id=tenant_id,
            customer_id=customer_id,
        )

    async def _lookup_clearbit(
        self, domain: str | None, company_name: str | None, tenant_id: int | None, customer_id: int
    ) -> dict[str, Any]:
        # Verify customer belongs to the requesting tenant
        if customer_id is not None:
            result = await self.session.execute(
                select(CustomerModel).where(
                    and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id)
                )
            )
            customer = result.scalar_one_or_none()
            if customer is None:
                raise NotFoundException("Customer")

        api_key = settings.clearbit_api_key
        if not api_key:
            raise ValidationException("Clearbit API key is not configured")

        params: dict[str, str] = {}
        if domain:
            params["domain"] = domain.strip()
        else:
            params["name"] = company_name.strip()  # type: ignore[arg-type]

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.clearbit_read_timeout, connect=settings.clearbit_connect_timeout)
        ) as client:
            response = await client.get(
                "https://company.clearbit.com/v2/companies/find",
                params=params,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        if response.status_code == 404:
            raise ValidationException("No company found for the given domain or name")
        if not response.is_success:
            raise ValidationException(f"Clearbit API error: {response.status_code}")

        raw_data: dict[str, Any] = response.json()
        normalised = self._normalise_clearbit(raw_data)

        # Persist raw payload
        enrichment = CustomerEnrichmentModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            provider="clearbit",
            raw_data_json=raw_data,
            enriched_at=datetime.now(UTC),
        )
        self.session.add(enrichment)
        await self.session.flush()

        return normalised

    def _normalise_clearbit(self, data: dict[str, Any]) -> dict[str, Any]:
        """Flatten a Clearbit company payload into a portable dict.

        Only includes keys that are present and non-null.
        """
        out: dict[str, Any] = {}

        for key in ("name", "domain", "legalName", "category", "logo", "linkedin"):
            if key in data and data[key] is not None:
                # remap legalName -> legal_name
                normalised_key = key.replace("legalName", "legal_name")
                out[normalised_key] = data[key]

        geo = data.get("geo")
        if isinstance(geo, dict):
            for sub in ("city", "state", "country", "countryCode"):
                if sub in geo and geo[sub] is not None:
                    out[f"geo_{sub}"] = geo[sub]

        metrics = data.get("metrics")
        if isinstance(metrics, dict):
            for sub in ("employees", "employeesRange", "annualRevenue", "raised"):
                if sub in metrics and metrics[sub] is not None:
                    out[f"metrics_{sub}"] = metrics[sub]

        return out
