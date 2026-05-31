"""Enrichment service — third-party company data enrichment via Clearbit."""

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
        tenant_id: int,
        customer_id: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Look up company enrichment data from a third-party provider.

        Requires exactly one of *domain* or *company_name*.
        Returns a (normalised, raw) tuple; caller owns persistence.
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

        raw_data = await self._call_clearbit_api(customer_id, tenant_id, domain, company_name)
        normalised = self._normalise_clearbit(raw_data)

        now = datetime.now(UTC)
        stmt = pg_insert(CustomerEnrichmentModel).values(
            tenant_id=tenant_id,
            customer_id=customer_id,
            provider="clearbit",
            raw_data_json=raw_data,
            enriched_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "customer_id"],
            set_={
                "provider": "clearbit",
                "raw_data_json": stmt.excluded.raw_data_json,
                "enriched_at": stmt.excluded.enriched_at,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)

        return normalised, raw_data

    async def _call_clearbit_api(
        self,
        customer_id: int,
        tenant_id: int,
        domain: str | None,
        company_name: str | None,
    ) -> dict[str, Any]:
        """Validate the customer, check API key, and call Clearbit.

        Returns the raw provider payload. Caller owns persistence.
        """
        result = await self.session.execute(
            select(CustomerModel).where(
                and_(CustomerModel.id == customer_id, CustomerModel.tenant_id == tenant_id)
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")

        api_key: str = settings.clearbit_api_key
        if not api_key:
            raise ValidationException("Clearbit API key is not configured")

        params: dict[str, str] = {}
        if domain:
            params["domain"] = domain.strip()
        elif company_name:
            params["name"] = company_name.strip()

        return await self._call_clearbit(params, api_key)

    async def _call_clearbit(
        self,
        params: dict[str, str],
        api_key: str,
    ) -> dict[str, Any]:
        """Make a request to the Clearbit company API and return parsed JSON.

        Raises ValidationException on 404 or non-success status codes.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.clearbit_read_timeout,
                connect=settings.clearbit_connect_timeout or 5.0,
            ),
            transport=httpx.AsyncHTTPTransport(retries=2),
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

        return response.json()

    async def _upsert_enrichment(
        self,
        tenant_id: int,
        customer_id: int,
        raw_data: dict[str, Any],
        now: datetime | None = None,
    ) -> None:
        """Upsert a CustomerEnrichmentModel record (insert or replace)."""
        if now is None:
            now = datetime.now(UTC)
        stmt = pg_insert(CustomerEnrichmentModel).values(
            tenant_id=tenant_id,
            customer_id=customer_id,
            provider="clearbit",
            raw_data_json=raw_data,
            enriched_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "customer_id"],
            set_={
                "provider": "clearbit",
                "raw_data_json": stmt.excluded.raw_data_json,
                "enriched_at": stmt.excluded.enriched_at,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)

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

    async def refresh(
        self,
        customer_id: int,
        tenant_id: int,
        domain: str | None = None,
        company_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Re-call the enrichment provider for an existing customer.

        Validates inputs, calls Clearbit, upserts the enrichment record, and
        returns a (normalised, raw) tuple.
        """
        # Normalise and validate inputs
        if domain:
            domain = domain.strip() or None
        if company_name:
            company_name = company_name.strip() or None
        if not domain and not company_name:
            raise ValidationException("At least one of domain or company_name is required")

        raw_data = await self._call_clearbit_api(customer_id, tenant_id, domain, company_name)
        normalised = self._normalise_clearbit(raw_data)

        now = datetime.now(UTC)
        stmt = pg_insert(CustomerEnrichmentModel).values(
            tenant_id=tenant_id,
            customer_id=customer_id,
            provider="clearbit",
            raw_data_json=raw_data,
            enriched_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "customer_id"],
            set_={
                "provider": "clearbit",
                "raw_data_json": stmt.excluded.raw_data_json,
                "enriched_at": stmt.excluded.enriched_at,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)

        return normalised, raw_data
