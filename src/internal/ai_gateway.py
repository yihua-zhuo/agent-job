"""AI Chat Gateway — async adapter for the AI backend (stub / MiniMax-M2.7)."""

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class AIResponse:
    """Structured response from the AI gateway."""

    reply: str
    suggestions: list[str] | None = None
    actions: list[dict] | None = None


class AIChatGateway:
    """Async adapter for AI chat calls.

    The ``_call_gateway`` method is the only place that needs to change when
    swapping the stub for a real MiniMax-M2.7 integration — no call sites need
    updating.
    """

    async def chat(self, messages: list[dict[str, str]], context: dict[str, Any] | None = None) -> AIResponse:
        """Send a chat request to the AI gateway.

        Args:
            messages: List of ``{"role": "user"|"assistant", "content": "..."}`` entries.
            context: Optional CRM context dict injected into the prompt.

        Returns:
            AIResponse with reply, optional suggestions, and optional actions.
        """
        return await self._call_gateway(messages, context or {})

    async def _call_gateway(
        self, messages: list[dict[str, str]], context: dict[str, Any]
    ) -> AIResponse:
        """Inner call — replace this method to wire in a real MiniMax-M2.7 endpoint.

        The stub below is deterministic so unit tests are stable.  It uses a
        hash of the last user message so identical questions always produce the
        same answer.
        """
        last_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        # Deterministic seed from message content
        seed = int(hashlib.sha256(last_message.encode()).hexdigest()[:8], 16)

        replies = [
            f"Based on your CRM data, you have {(seed % 10) + 1} active customers and {(seed % 5) + 1} open opportunities. "
            "Would you like me to generate a summary report?",
            f"I've analyzed your pipeline. There are {(seed % 3) + 1} deals in the qualification stage "
            f"totaling approximately ${(seed % 50) + 10}K in potential revenue.",
            f"Your team has {(seed % 8) + 1} open tickets, of which {(seed % 3) + 1} are high priority. "
            f"The average resolution time this week is {(seed % 12) + 2} hours.",
        ]
        reply = replies[seed % len(replies)]

        suggestions = ["Show customers", "Show pipeline", "Summarize tickets"]
        actions = [
            {"type": "navigate", "label": "View Customers", "path": "/customers"},
            {"type": "navigate", "label": "View Pipeline", "path": "/sales"},
        ]

        return AIResponse(reply=reply, suggestions=suggestions, actions=actions)
