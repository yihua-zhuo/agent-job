"""Unified LLM service — multi-provider chat and embed with cost tracking."""

import asyncio
import logging
import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import ValidationException

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "gpt-4o"
MAX_RETRIES = 3

OPENAI_COST_PER_M_TOKEN = 0.002
ANTHROPIC_COST_PER_M_TOKEN = 0.003
EMBEDDING_COST_PER_M_TOKEN = 0.00002


class LLMService:
    """Unified multi-provider LLM access — chat, embed, and per-tenant cost tracking."""

    def __init__(
        self,
        session: AsyncSession,
        client: httpx.AsyncClient | None = None,
        owns_client: bool = True,
    ):
        self.session = session
        if client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = owns_client
        self._cost_by_tenant: dict[int, float] = {}
        self._cost_lock = asyncio.Lock()

    async def __aenter__(self) -> "LLMService":
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _add_cost(self, tenant_id: int, amount: float) -> None:
        async with self._cost_lock:
            self._cost_by_tenant[tenant_id] = self._cost_by_tenant.get(tenant_id, 0.0) + amount

    async def chat(
        self,
        messages: list[dict[str, str]],
        tenant_id: int,
        model: str | None = None,
    ) -> str:
        """Return the assistant's text reply. Raise ValidationException on provider error."""
        resolved_model = model or DEFAULT_MODEL
        payload = {"model": resolved_model, "messages": messages}

        if resolved_model.startswith("gpt-") or resolved_model.startswith("o1"):
            data = await self._call_openai(payload, tenant_id)
            return data["choices"][0]["message"]["content"]
        if resolved_model.startswith("claude-"):
            data = await self._call_anthropic(payload, tenant_id)
            return data["content"][0]["text"]
        raise ValidationException(f"Unknown model: {resolved_model}")

    async def embed(
        self,
        text: str,
        tenant_id: int,
        model: str = "text-embedding-3-small",
    ) -> list[float]:
        """Return embedding vector for the given text. Raise ValidationException on provider error."""
        payload = {"model": model, "input": text}
        url = f"{OPENAI_API_URL.rsplit('/', 1)[0]}/embeddings"
        headers = {
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
            "Content-Type": "application/json",
        }

        for attempt in range(MAX_RETRIES):
            resp = await self._client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                await self._add_cost(
                    tenant_id,
                    (tokens / 1_000_000) * EMBEDDING_COST_PER_M_TOKEN,
                )
                return data["data"][0]["embedding"]
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
        logger.error(
            "llm_provider_error",
            extra={
                "provider": "openai",
                "endpoint": "embeddings",
                "tenant_id": tenant_id,
                "status_code": resp.status_code,
            },
        )
        raise ValidationException(
            f"LLM provider error: OpenAI embeddings returned {resp.status_code} after {MAX_RETRIES} retries"
        )

    async def get_cost(self, tenant_id: int) -> float:
        """Return accumulated LLM cost for this tenant in USD."""
        return self._cost_by_tenant.get(tenant_id, 0.0)

    async def _call_openai(self, payload: dict, tenant_id: int) -> dict:
        headers = {
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
            "Content-Type": "application/json",
        }
        for attempt in range(MAX_RETRIES):
            resp = await self._client.post(OPENAI_API_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                await self._add_cost(
                    tenant_id,
                    (tokens / 1_000_000) * OPENAI_COST_PER_M_TOKEN,
                )
                return data
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
        logger.error(
            "llm_provider_error",
            extra={"provider": "openai", "endpoint": "chat", "tenant_id": tenant_id, "status_code": resp.status_code},
        )
        raise ValidationException(f"LLM provider error: OpenAI returned {resp.status_code} after {MAX_RETRIES} retries")

    async def _call_anthropic(self, payload: dict, tenant_id: int) -> dict:
        headers = {
            "x-api-key": f"{os.environ.get('ANTHROPIC_API_KEY', '')}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        for attempt in range(MAX_RETRIES):
            resp = await self._client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                await self._add_cost(
                    tenant_id,
                    (tokens / 1_000_000) * ANTHROPIC_COST_PER_M_TOKEN,
                )
                return data
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
        logger.error(
            "llm_provider_error",
            extra={
                "provider": "anthropic",
                "endpoint": "messages",
                "tenant_id": tenant_id,
                "status_code": resp.status_code,
            },
        )
        raise ValidationException(
            f"LLM provider error: Anthropic returned {resp.status_code} after {MAX_RETRIES} retries"
        )
