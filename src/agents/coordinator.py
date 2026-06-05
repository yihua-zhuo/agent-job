"""CoordinatorAgent — decomposes tasks and dispatches to registered sub-agents.

This agent is async — it must be awaited when called via ``BaseAgent.run`` and
relies on the registered sub-agents also being async. Sub-agents share the
coordinator's session/llm; they must NOT flush or commit transactions — that
lives at the router layer.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, register
from agents.registry import AgentRegistry
from internal.ai_gateway import AIChatGateway

logger = logging.getLogger(__name__)


class SubTask(BaseModel):
    id: str
    agent_name: str
    description: str
    status: str = "pending"
    result: dict[str, Any] | None = None


class TaskDecomposition(BaseModel):
    task_id: str
    original_description: str
    subtasks: list[SubTask]


class WorkflowResult(BaseModel):
    task_id: str
    completed: list[SubTask] = Field(default_factory=list)
    failed: list[SubTask] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.failed


_KEYWORD_GROUPS: list[tuple[tuple[str, ...], str]] = [
    (("test",), "test_agent"),
    (("review", "code"), "code_review_agent"),
    (("qc", "quality"), "qc_agent"),
    (("implement",), "implement_agent"),
]


@register("coordinator")
class CoordinatorAgent(BaseAgent):
    """Top-level agent that decomposes a task and dispatches subtasks to registered agents.

    Sub-agents are instantiated with this coordinator's ``llm`` and ``session``.
    Sub-agents MUST NOT flush or commit the session — the transaction boundary
    lives at the router layer (rule 121). Treat the shared session/llm as
    read-only inputs into each sub-agent's ``run`` method.
    """

    def __init__(
        self,
        llm: AIChatGateway,
        session: AsyncSession,
        tenant_id: int | None = None,
    ) -> None:
        super().__init__(llm, session, tenant_id=tenant_id)
        # AgentRegistry is a process-wide singleton — always use the global
        # instance, do not allow callers to inject an alternative registry.
        self._registry = AgentRegistry()

    @property
    def name(self) -> str:
        return "coordinator"

    def decompose(self, task_description: str) -> TaskDecomposition:
        task_id = uuid.uuid4().hex[:8]
        lowered = task_description.lower()
        matched: list[str] = []
        seen: set[str] = set()
        for keywords, agent_name in _KEYWORD_GROUPS:
            if agent_name in seen:
                continue
            if any(kw in lowered for kw in keywords):
                seen.add(agent_name)
                matched.append(agent_name)
        if not matched:
            matched.append("implement_agent")
        subtasks = [
            SubTask(id=f"{task_id}-{i}", agent_name=agent_name, description=task_description)
            for i, agent_name in enumerate(matched)
        ]
        return TaskDecomposition(task_id=task_id, original_description=task_description, subtasks=subtasks)

    async def run(self, task: str) -> WorkflowResult:
        """Decompose *task* and dispatch subtasks. Return the WorkflowResult object.

        The router/service layer is responsible for serialising this domain
        object (``.model_dump()``) and wrapping it in the standard response
        envelope.
        """
        decomposition = self.decompose(task)
        return await self._dispatch(decomposition)

    async def _dispatch(self, decomposition: TaskDecomposition) -> WorkflowResult:
        completed: list[SubTask] = []
        failed: list[SubTask] = []
        for subtask in decomposition.subtasks:
            try:
                agent_cls = self._registry.get(subtask.agent_name)
                agent = agent_cls(self.llm, self.session, tenant_id=self.tenant_id)
                completed.append(
                    subtask.model_copy(update={"status": "completed", "result": await agent.run(subtask.description)})
                )
            except LookupError:
                logger.warning(
                    "coordinator.lookup_error",
                    extra={"agent_name": subtask.agent_name, "subtask_id": subtask.id},
                )
                failed.append(
                    subtask.model_copy(
                        update={"status": "failed", "result": {"error": f"Unknown agent: {subtask.agent_name}"}}
                    )
                )
            except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
                failed.append(subtask.model_copy(update={"status": "failed", "result": {"error": str(exc)}}))
        return WorkflowResult(task_id=decomposition.task_id, completed=completed, failed=failed)
