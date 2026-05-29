"""Enrichment service — third-party company data enrichment via Clearbit."""

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import settings
from db.models.customer_enrichment import CustomerEnrichmentModel
from pkg.errors.app_exceptions import ValidationException


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
        api_key = settings.clearbit_api_key
        if not api_key:
            raise ValidationException("Clearbit API key is not configured")

        params: dict[str, str] = {}
        if domain:
            params["domain"] = domain
        else:
            params["name"] = company_name  # type: ignore[assignment]

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                "https://company.clearbit.com/v2/companies/find",
                params=params,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        if response.status_code == 404:
            return {}
        if not response.is_success:
            raise ValidationException("Clearbit API error")

        raw_data: dict[str, Any] = response.json()
        normalised = self._normalise_clearbit(raw_data)

        # Persist raw payload
        now = datetime.now(UTC)
        enrichment = CustomerEnrichmentModel(
            customer_id=customer_id,
            provider="clearbit",
            raw_data_json=raw_data,
            enriched_at=now,
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
