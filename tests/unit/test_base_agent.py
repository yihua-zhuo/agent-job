"""Unit tests for BaseAgent abstract interface."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass used only for testing."""

    def run(self, task: str):
        return super().run(task)


class TestBaseAgentAbstract:
    def test_cannot_instantiate_base_directly(self):
        """BaseAgent is abstract — TypeError is raised on direct instantiation."""
        with pytest.raises(TypeError):
            BaseAgent(llm=MagicMock(), session=MagicMock())

    def test_concrete_subclass_instantiation(self):
        """A concrete subclass can be instantiated with the expected dependencies."""
        mock_llm = MagicMock()
        mock_session = MagicMock()
        agent = ConcreteAgent(llm=mock_llm, session=mock_session)
        assert agent.llm is mock_llm
        assert agent.session is mock_session

    def test_run_raises_not_implemented_error(self):
        """run() on a concrete subclass raises NotImplementedError."""
        mock_llm = MagicMock()
        mock_session = MagicMock()
        agent = ConcreteAgent(llm=mock_llm, session=mock_session)
        with pytest.raises(NotImplementedError):
            agent.run("test task")

    def test_run_returns_dict(self):
        """A subclass that overrides run returns a dict as expected."""
        class ReturningAgent(BaseAgent):
            def run(self, task: str):
                return {"success": True, "data": task}

        mock_llm = MagicMock()
        mock_session = MagicMock()
        agent = ReturningAgent(llm=mock_llm, session=mock_session)
        result = agent.run("say hello")
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["data"] == "say hello"

    def test_constructor_accepts_llm_and_session(self):
        """The constructor accepts and stores llm and session kwargs."""
        mock_llm = MagicMock()
        mock_session = MagicMock()
        agent = ConcreteAgent(llm=mock_llm, session=mock_session)
        assert hasattr(agent, "llm")
        assert hasattr(agent, "session")
        assert agent.llm is mock_llm
        assert agent.session is mock_session