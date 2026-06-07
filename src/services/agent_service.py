"""AgentService — dispatches tasks to agents via the AgentRegistry singleton.

The session is typed AsyncSession with no default so services cannot be
constructed without an active session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry import AgentRegistry, BaseAgent  # type: ignore[attr-defined]
from internal.ai_gateway import AIChatGateway
from pkg.errors.app_exceptions import NotFoundException


@dataclass
class AgentStatus:
    """Snapshot of agent-registry health for a tenant."""

    llm_status: str
    agents: list[str]
    tenant_id: int
    checked_at: datetime

    def to_dict(self) -> dict:
        return {
            "llm": self.llm_status,
            "agents": list(self.agents),
            "tenant_id": self.tenant_id,
            "timestamp": self.checked_at.isoformat(),
        }


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

    async def dispatch(self, agent_type: str, task: str, tenant_id: int) -> dict:
        """Look up the agent in the registry and run it with *task* for *tenant_id*.

        ``BaseAgent.run`` is async and must be awaited. Raises NotFoundException
        if the agent type is not registered.
        """
        try:
            agent_cls = self._registry.get(agent_type)
        except LookupError as exc:
            raise NotFoundException(f"Agent type '{agent_type}' not registered") from exc

        agent_instance: BaseAgent = agent_cls(self._llm, self.session, tenant_id=tenant_id)
        return await agent_instance.run(task)

    async def get_status(self, tenant_id: int) -> AgentStatus:
        """Return an AgentStatus snapshot for the given tenant.

        llm_status is a static snapshot: the AIChatGateway stub is stateless
        and process-local, so a live connectivity probe is not possible here.
        A real LLM client should replace this with an actual health probe
        (e.g. a lightweight ``ping`` or list-models call).
        Registry is tenant-agnostic; tenant_id is echoed in the response for
        caller context.
        """
        return AgentStatus(
            llm_status="ok",
            agents=self._registry.list_agents(),
            tenant_id=tenant_id,
            checked_at=datetime.now(UTC),
        )
