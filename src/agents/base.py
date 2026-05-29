"""Abstract base agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from internal.ai_gateway import AIChatGateway

if TYPE_CHECKING:
    from agents.registry import AgentRegistry


def register(name: str) -> Callable[[type], type]:
    """Decorator that registers an agent class under *name*."""

    def decorator(cls: type) -> type:
        from agents.registry import AgentRegistry

        global _registry
        if not isinstance(cls, type):
            raise TypeError(f"Registered object must be a class: {cls!r}")
        try:
            if not issubclass(cls, BaseAgent):
                raise TypeError(
                    f"Registered object must be a BaseAgent subclass: {cls!r}"
                )
        except NameError:
            pass
        if _registry is None:
            _registry = AgentRegistry()
            # Sync with registry._registry so both modules reference the same
            # singleton after AgentRegistry.__new__ stores it there.
            import agents.registry

            agents.registry._registry = _registry
        if name in _registry._agents:
            raise ValueError(f"Agent name already registered: {name!r}")
        _registry._agents[name] = cls
        return cls

    return decorator


# Module-level sentinel used by register().
# AgentRegistry is imported lazily (inside functions) to avoid a circular
# import: base.py defines BaseAgent and register; registry.py imports
# BaseAgent and defines AgentRegistry; BaseAgent is decorated with @register
# at import time, which triggers the lazy import of AgentRegistry.
# The sentinel is synced with registry._registry after AgentRegistry() is first
# called so that both modules reference the same singleton instance.
_registry: AgentRegistry | None = None


@register("base")
class BaseAgent(ABC):
    """Abstract base class for all CRM agents.

    Concrete agents inject LLM (AIChatGateway) and database (AsyncSession)
    dependencies through the constructor and implement ``run``.
    """

    def __init__(self, llm: AIChatGateway, session: AsyncSession) -> None:
        self.llm = llm
        self.session = session

    @abstractmethod
    def run(self, task: str) -> dict[str, Any]:
        """Execute a task and return a result dictionary.

        Args:
            task: Natural-language task description.

        Returns:
            Dictionary with at minimum ``"success"`` and ``"data"`` keys.
        """
