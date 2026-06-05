"""AgentService — dispatches tasks to agents via the AgentRegistry singleton.

Wraps an LLMService for health reporting. The session is typed AsyncSession
with no default so services cannot be constructed without an active session.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import AgentRegistry, BaseAgent  # type: ignore[attr-defined]
from pkg.errors.app_exceptions import NotFoundException
from services.llm_service import LLMService


class AgentService:
    """Dispatch tasks to registered agents and report LLM/agent-registry health."""

    def __init__(
        self,
        session: AsyncSession,
        llm_service: LLMService,
        registry: AgentRegistry,
    ):
        self.session = session
        self._llm_service = llm_service
        self._registry = registry

    async def dispatch(self, agent_type: str, task: str, tenant_id: int) -> dict:
        """Look up the agent in the registry and run it with *task* for *tenant_id*.

        Raises NotFoundException if the agent type is not registered.
        """
        try:
            agent_cls = self._registry.get(agent_type)
        except LookupError as exc:
            raise NotFoundException(f"Agent type '{agent_type}' not registered") from exc

        agent_instance: BaseAgent = agent_cls(self._llm_service, self.session)
        result = agent_instance.run(task)
        return result

    async def get_status(self) -> dict:
        """Return a status dict with LLM availability, registered agent names, and UTC timestamp."""
        try:
            llm_status = "ok" if self._llm_service is not None else "error"
        except Exception:
            llm_status = "error"

        return {
            "llm": llm_status,
            "agents": self._registry.list_agents(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
