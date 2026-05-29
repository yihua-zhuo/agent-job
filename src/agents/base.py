"""Abstract base agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from internal.ai_gateway import AIChatGateway

_F = TypeVar("_F", bound=type)

_registry: AgentRegistry | None = None


def register(name: str) -> Callable[[_F], _F]:
    """Decorator that registers an agent class under *name*."""
    from agents.registry import AgentRegistry

    def decorator(cls: _F) -> _F:
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
        if name in _registry._agents:
            raise ValueError(f"Agent name already registered: {name!r}")
        _registry._agents[name] = cls
        return cls

    return decorator


class AgentRegistry:
    """Singleton registry mapping agent names to BaseAgent subclasses."""

    __slots__ = ("_agents",)

    def __new__(cls) -> AgentRegistry:
        global _registry
        if _registry is None:
            _registry = super().__new__(cls)
            _registry._agents = {}
        return _registry

    def _ensure_base(self) -> None:
        """Lazily register 'base' if it was reset or never registered."""
        if "base" not in self._agents:
            self._agents["base"] = BaseAgent

    def get(self, name: str) -> type[BaseAgent]:
        """Return the registered agent class for *name*."""
        self._ensure_base()
        if name not in self._agents:
            raise LookupError(f"Agent not registered: {name!r}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """Return a sorted list of all registered agent names."""
        self._ensure_base()
        return sorted(self._agents.keys())


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
