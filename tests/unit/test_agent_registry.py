"""Unit tests for AgentRegistry singleton."""

import pytest

import agents.base as agent_base
from agents.base import register
from agents.registry import AgentRegistry


def _reset_registry() -> None:
    """Reset the singleton so tests are independent."""
    import agents.registry as agent_registry

    agent_base._registry = None
    agent_registry._registry = None


class TestAgentRegistrySingleton:
    def test_singleton_identity(self):
        """AgentRegistry() called twice returns the same object instance."""
        _reset_registry()
        r1 = AgentRegistry()
        r2 = AgentRegistry()
        assert r1 is r2

    def test_singleton_shared_across_calls(self):
        """Multiple calls share the same underlying _agents dict."""
        _reset_registry()
        r1 = AgentRegistry()
        r2 = AgentRegistry()
        assert r1._agents is r2._agents


class TestRegisterDecorator:
    def test_register_adds_entry(self):
        """@register adds the decorated class to the registry under the given name."""
        _reset_registry()

        @register("test_agent")
        class TestAgent(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        registry = AgentRegistry()
        assert "test_agent" in registry._agents
        assert registry._agents["test_agent"] is TestAgent

    def test_get_returns_correct_class(self):
        """get() returns the class registered under the given name."""
        _reset_registry()

        @register("get_test")
        class GetTestAgent(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        registry = AgentRegistry()
        cls = registry.get("get_test")
        assert cls is GetTestAgent

    def test_get_raises_lookup_error_for_unknown_name(self):
        """get() raises LookupError when the name is not registered."""
        _reset_registry()
        registry = AgentRegistry()
        with pytest.raises(LookupError):
            registry.get("nonexistent_agent")

    def test_list_agents_includes_preregistered_base(self):
        """list_agents() includes the "base" entry from BaseAgent's @register."""
        # Do NOT reset — "base" is registered at module import time
        registry = AgentRegistry()
        names = registry.list_agents()
        assert "base" in names

    def test_list_agents_returns_sorted_names(self):
        """list_agents() returns names in sorted order."""
        _reset_registry()

        @register("zeta")
        class ZetaAgent(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        @register("alpha")
        class AlphaAgent(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        registry = AgentRegistry()
        names = registry.list_agents()
        assert names == sorted(names)

    def test_register_same_name_twice_raises_value_error(self):
        """Registering the same name twice raises ValueError."""
        _reset_registry()

        @register("duplicate")
        class DuplicateAgent1(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        with pytest.raises(ValueError) as exc_info:

            @register("duplicate")
            class DuplicateAgent2(agent_base.BaseAgent):
                def run(self, task: str):
                    return {}

        assert "duplicate" in str(exc_info.value)

    def test_register_decorator_returns_class_unchanged(self):
        """The decorator returns the original class without modification."""
        _reset_registry()

        @register("unchanged")
        class UnchangedAgent(agent_base.BaseAgent):
            def run(self, task: str):
                return {}

        assert UnchangedAgent is not None
        assert hasattr(UnchangedAgent, "run")
