"""Unit tests for BaseAgent abstract interface."""

from unittest.mock import MagicMock

import pytest

from agents.base import BaseAgent


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_session():
    return MagicMock()


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass used only for testing."""

    def run(self, task: str):
        return {"result": task}


@pytest.fixture
def concrete_agent(mock_llm, mock_session):
    """ConcreteAgent with mocked dependencies."""
    return ConcreteAgent(llm=mock_llm, session=mock_session)


class TestBaseAgentAbstract:
    def test_cannot_instantiate_base_directly(self):
        """BaseAgent is abstract — TypeError is raised on direct instantiation."""
        with pytest.raises(TypeError):
            BaseAgent(llm=MagicMock(), session=MagicMock())

    def test_concrete_subclass_instantiation(self, concrete_agent):
        """A concrete subclass can be instantiated with the expected dependencies."""
        assert concrete_agent.llm is not None
        assert concrete_agent.session is not None

    def test_run_returns_dict(self, mock_llm, mock_session):
        """A subclass that overrides run returns a dict as expected."""

        class ReturningAgent(BaseAgent):
            def run(self, task: str):
                return {"success": True, "data": task}

        agent = ReturningAgent(llm=mock_llm, session=mock_session)
        result = agent.run("say hello")
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["data"] == "say hello"

    def test_constructor_accepts_llm_and_session(self, concrete_agent, mock_llm, mock_session):
        """The constructor accepts and stores llm and session kwargs."""
        assert hasattr(concrete_agent, "llm")
        assert hasattr(concrete_agent, "session")
        assert concrete_agent.llm is mock_llm
        assert concrete_agent.session is mock_session
