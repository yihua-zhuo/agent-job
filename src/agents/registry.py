"""Singleton agent registry with decorator-based registration.

Re-exports from agents.base so that the public API can be imported from
either `agents.base` or `agents.registry`.
"""

from __future__ import annotations

from agents.base import register

__all__ = ["AgentRegistry", "BaseAgent", "get", "list_agents", "register"]

# Forward reference for type annotations — actual class is defined below.
# Importing BaseAgent at the top level would create a circular import because
# base.py imports AgentRegistry from here while BaseAgent is still loading.
BaseAgent: type = None  # type: ignore[assignment]


def _sync_base_registry() -> None:
    """Sync the singleton reference into base._registry after first creation."""
    import agents.base as base_module

    base_module._registry = _registry  # type: ignore[assignment]


# Singleton sentinel — shared with agents.base.
_registry: AgentRegistry | None = None  # type: ignore[valid-type]


class AgentRegistry:
    """Singleton registry mapping agent names to BaseAgent subclasses."""

    __slots__ = ("_agents",)

    def __new__(cls) -> AgentRegistry:
        global _registry
        if _registry is None:
            _registry = super().__new__(cls)
            _registry._agents = {}
            _sync_base_registry()
        return _registry

    def _ensure_base(self) -> None:
        """Lazily register 'base' if it was reset or never registered."""
        if "base" not in self._agents:
            from agents.base import BaseAgent as BA

            global BaseAgent
            BaseAgent = BA
            self._agents["base"] = BA

    def get(self, name: str) -> type[BaseAgent]:  # type: ignore[valid-type]
        """Return the registered agent class for *name*."""
        self._ensure_base()
        if name not in self._agents:
            raise LookupError(f"Agent not registered: {name!r}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """Return a sorted list of all registered agent names."""
        self._ensure_base()
        return sorted(self._agents.keys())


def get(name: str) -> type[BaseAgent]:  # type: ignore[valid-type]
    """Return the registered agent class for *name* (module-level API)."""
    return AgentRegistry().get(name)


def list_agents() -> list[str]:
    """Return a sorted list of all registered agent names (module-level API)."""
    return AgentRegistry().list_agents()
