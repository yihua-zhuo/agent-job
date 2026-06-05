"""Unit tests for src/services/llm_service.py — LLMService chat/embed/cost tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pkg.errors.app_exceptions import ValidationException
from services.llm_service import (
    ANTHROPIC_COST_PER_M_TOKEN,
    EMBEDDING_COST_PER_M_TOKEN,
    MAX_RETRIES,
    OPENAI_COST_PER_M_TOKEN,
    LLMService,
)


def _make_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    """Build a mock httpx response with given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    return resp


@pytest.fixture
def session():
    return AsyncMock()


# ---------------------------------------------------------------------------
# Happy path: OpenAI chat
# ---------------------------------------------------------------------------


async def test_chat_openai_happy_path(session):
    ok_body = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"total_tokens": 100},
    }
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_response(200, ok_body)
        async with LLMService(session) as svc:
            result = await svc.chat([{"role": "user", "content": "hello"}], tenant_id=1)

    assert result == "hi"
    expected_cost = (100 / 1_000_000) * OPENAI_COST_PER_M_TOKEN
    assert await svc.get_cost(1) == expected_cost


# ---------------------------------------------------------------------------
# Provider routing: Anthropic
# ---------------------------------------------------------------------------


async def test_chat_anthropic_routing(session):
    ok_body = {
        "content": [{"text": "reply"}],
        "usage": {"input_tokens": 50, "output_tokens": 50},
    }
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_response(200, ok_body)
        async with LLMService(session) as svc:
            result = await svc.chat(
                [{"role": "user", "content": "hi"}], tenant_id=1, model="claude-3-5-sonnet"
            )

    assert result == "reply"
    expected_cost = (100 / 1_000_000) * ANTHROPIC_COST_PER_M_TOKEN
    assert await svc.get_cost(1) == expected_cost


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


async def test_embed_returns_vector(session):
    ok_body = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}],
        "usage": {"total_tokens": 10},
    }
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_response(200, ok_body)
        async with LLMService(session) as svc:
            result = await svc.embed("some text", tenant_id=1)

    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)
    assert len(result) == 3
    expected_cost = (10 / 1_000_000) * EMBEDDING_COST_PER_M_TOKEN
    assert await svc.get_cost(1) == expected_cost


# ---------------------------------------------------------------------------
# Retry success
# ---------------------------------------------------------------------------


async def test_chat_retry_on_429(session):
    ok_body = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"total_tokens": 100},
    }
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _make_response(429),
            _make_response(429),
            _make_response(200, ok_body),
        ]
        async with LLMService(session) as svc:
            result = await svc.chat([{"role": "user", "content": "hi"}], tenant_id=1)

    assert result == "hi"
    assert mock_post.call_count == 3


# ---------------------------------------------------------------------------
# Retry exhaustion
# ---------------------------------------------------------------------------


async def test_chat_retry_exhausted(session):
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _make_response(500),
            _make_response(500),
            _make_response(500),
        ]
        async with LLMService(session) as svc:
            with pytest.raises(ValidationException, match="LLM provider error"):
                await svc.chat([{"role": "user", "content": "hi"}], tenant_id=1)

    assert mock_post.call_count == MAX_RETRIES


# ---------------------------------------------------------------------------
# Unknown model
# ---------------------------------------------------------------------------


async def test_unknown_model_raises(session):
    async with LLMService(session) as svc:
        with pytest.raises(ValidationException, match="Unknown model: some-unknown-model"):
            await svc.chat(
                [{"role": "user", "content": "hi"}],
                tenant_id=1,
                model="some-unknown-model",
            )


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


async def test_get_cost_tenant_isolation(session):
    ok_body = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"total_tokens": 100},
    }
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_response(200, ok_body)
        async with LLMService(session) as svc:
            await svc.chat([{"role": "user", "content": "hi"}], tenant_id=10)
            await svc.chat([{"role": "user", "content": "hi"}], tenant_id=20)

    cost_a = await svc.get_cost(10)
    cost_b = await svc.get_cost(20)
    assert cost_a == pytest.approx((100 / 1_000_000) * OPENAI_COST_PER_M_TOKEN)
    assert cost_b == pytest.approx((100 / 1_000_000) * OPENAI_COST_PER_M_TOKEN)
    # And an unseen tenant returns 0.0
    assert await svc.get_cost(999) == 0.0


# ---------------------------------------------------------------------------
# Embed retry exhaustion
# ---------------------------------------------------------------------------


async def test_embed_retry_exhausted(session):
    with patch("services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _make_response(500),
            _make_response(500),
            _make_response(500),
        ]
        async with LLMService(session) as svc:
            with pytest.raises(ValidationException, match="LLM provider error"):
                await svc.embed("text", tenant_id=1)

    assert mock_post.call_count == MAX_RETRIES
