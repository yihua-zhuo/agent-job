"""Singleton agent registry with decorator-based registration.

Re-exports from agents.base so that the public API can be imported from
either `agents.base` or `agents.registry`.
"""

from __future__ import annotations

from agents.base import AgentRegistry, register

__all__ = ["AgentRegistry", "register"]
