"""AgentService — dispatches tasks to agents via the AgentRegistry singleton.

The session is typed AsyncSession with no default so services cannot be
constructed without an active session.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import AgentRegistry, BaseAgent  # type: ignore[attr-defined]
from internal.ai_gateway import AIChatGateway
from pkg.errors.app_exceptions import NotFoundException


class AgentService:
    """Dispatch tasks to registered agents and report agent-registry health."""

    def __init__(
        self,
        session: AsyncSession,
        llm: AIChatGateway,
        registry: AgentRegistry,
    ):
        self.session = session
        self._llm = llm
        self._registry = registry

    def dispatch(self, agent_type: str, task: str, tenant_id: int) -> dict:
        """Look up the agent in the registry and run it with *task* for *tenant_id*.

        ``run`` is a synchronous method on ``BaseAgent`` — no awaiting is needed.
        Raises NotFoundException if the agent type is not registered.
        """
        try:
            agent_cls = self._registry.get(agent_type)
        except LookupError as exc:
            raise NotFoundException(f"Agent type '{agent_type}' not registered") from exc

        agent_instance: BaseAgent = agent_cls(self._llm, self.session, tenant_id=tenant_id)
        return agent_instance.run(task)

    async def get_status(self, tenant_id: int) -> dict:
        """Return registered agent names, tenant scope, and UTC timestamp."""
        return {
            "llm": "ok",
            "agents": self._registry.list_agents(),
            "tenant_id": tenant_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
