"""Coordinator agent test fixtures.

Domain-owned fixtures for tests that exercise the AgentRegistry singleton.
Importing this module from a test file and requesting ``reset_agent_registry``
explicitly isolates AgentRegistry state between tests.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest


def reset_agent_registry_singleton() -> None:
    """Reset the AgentRegistry singleton to a clean state."""
    from agents.registry import AgentRegistry

    AgentRegistry.reset()


@pytest.fixture
def reset_agent_registry() -> Generator[None, None, None]:
    """Reset the AgentRegistry singleton before and after each test.

    The coordinator module mutates the process-wide registry via
    ``@register("coordinator")`` at import time. Tests that register custom
    sub-agents should request this fixture to prevent registry state from
    leaking between tests.
    """
    reset_agent_registry_singleton()
    yield
    reset_agent_registry_singleton()
