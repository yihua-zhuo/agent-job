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
        customer_count = int(context.get("customer_count") or 0)
        open_ticket_count = int(context.get("open_ticket_count") or 0)
        opportunity_count = int(context.get("opportunity_count") or 0)
        recent_customers = context.get("recent_customers") or []
        open_ticket_subjects = context.get("open_ticket_subjects") or []

        context_seed = repr(
            {
                "customer_count": customer_count,
                "open_ticket_count": open_ticket_count,
                "opportunity_count": opportunity_count,
                "recent_customers": recent_customers[:3],
                "open_ticket_subjects": open_ticket_subjects[:3],
            }
        )
        seed = int(hashlib.sha256(f"{last_message}|{context_seed}".encode()).hexdigest()[:8], 16)

        replies = [
            f"Based on your CRM data, you have {customer_count} customers and {opportunity_count} open opportunities. "
            "Would you like me to generate a summary report?",
            f"I've analyzed your pipeline. There are {(seed % 3) + 1} deals in the qualification stage "
            f"totaling approximately ${(seed % 50) + 10}K in potential revenue.",
            f"Your team has {open_ticket_count} open tickets. "
            f"The average resolution time this week is {(seed % 12) + 2} hours.",
        ]
        reply = replies[seed % len(replies)]

        suggestions = ["Show pipeline"]
        actions = [{"type": "navigate", "label": "View Pipeline", "path": "/sales"}]
        if customer_count:
            label = f"Review {recent_customers[0]}" if recent_customers else "View Customers"
            suggestions.insert(0, "Show customers")
            actions.insert(0, {"type": "navigate", "label": label, "path": "/customers"})
        else:
            suggestions.insert(0, "Create first customer")
            actions.insert(0, {"type": "navigate", "label": "Add Customer", "path": "/customers/new"})
        if open_ticket_count:
            suggestions.append("Summarize tickets")
            actions.append({"type": "navigate", "label": "View Tickets", "path": "/tickets"})

        return AIResponse(reply=reply, suggestions=suggestions, actions=actions)
