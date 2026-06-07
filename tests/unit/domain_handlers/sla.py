"""SLA domain SQL mock handlers — extracted from tests/unit/conftest.py per project conventions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # MockResult imported lazily at runtime inside execute()


class SlaMockSession:
    """Minimal mock AsyncSession that routes session.scalar() and session.execute() to SQL handlers.

    SLAService.get_sla_summary calls session.scalar(select(func.count(...))) directly.
    SlaMockSession also implements execute() so any future call to session.execute()
    is routed to the same handlers instead of silently passing a bare MagicMock.
    """

    def __init__(self, handlers):
        self._handlers = handlers

    async def scalar(self, sql, params=None):
        params = dict(params) if params else {}

        try:
            compiled = sql.compile(dialect=self._get_dialect())
            sql_text = str(compiled).lower()
            for k, v in compiled.params.items():
                if k not in params:
                    params[k] = v
        except Exception as exc:
            import warnings

            warnings.warn(f"SlaMockSession: SQL compilation failed ({exc}), falling back to raw string", UserWarning)
            sql_text = str(sql).lower().strip()

        for h in self._handlers:
            result = h(sql_text, params)
            if result is not None:
                return result
        return None

    async def execute(self, sql, params=None):
        """Route session.execute() to the same handlers as scalar()."""
        from tests.unit.conftest import MockResult

        params = dict(params) if params else {}

        try:
            compiled = sql.compile(dialect=self._get_dialect())
            sql_text = str(compiled).lower()
            for k, v in compiled.params.items():
                if k not in params:
                    params[k] = v
        except Exception as exc:
            import warnings

            warnings.warn(
                f"SlaMockSession.execute: SQL compilation failed ({exc}), falling back to raw string", UserWarning
            )
            sql_text = str(sql).lower().strip()

        for h in self._handlers:
            result = h(sql_text, params)
            if result is not None:
                return MockResult([result])
        return MockResult([[None]])

    @staticmethod
    def _get_dialect():
        if not hasattr(SlaMockSession, "_dialect"):
            from sqlalchemy.dialects.postgresql import dialect as pg_dialect

            SlaMockSession._dialect = pg_dialect()
        return SlaMockSession._dialect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def sla_mock_session(handlers=None):
    """Create a mock AsyncSession wired to the given SQL handlers for SLA tests."""
    return SlaMockSession(handlers or [])


def make_sla_summary_handler(
    breached: int,
    at_risk: int,
    total: int,
    *,
    validate_tenant_id: bool = True,
    expected_tenant_id: int | None = None,
):
    """Return a handler that responds to select count(...) from tickets queries.

    Detects which bucket a query targets by inspecting the SQL clause structure:

      - total    : no "response_deadline" column at all
      - at_risk  : "response_deadline" column AND ">=" (the now-to-threshold window)
      - breached : "response_deadline" column present but no ">=" (past-deadline only)

    When ``validate_tenant_id`` is True the handler asserts ``params["tenant_id"]``
    equals ``expected_tenant_id`` (if given), raising ``AssertionError`` if the
    bind is absent or mismatched.
    """

    def handler(sql_text: str, params: dict):
        if not ("select" in sql_text and "count" in sql_text and "from tickets" in sql_text):
            return None

        if validate_tenant_id:
            tenant_keys = [k for k in params if k.lower().startswith("tenant_id")]
            assert tenant_keys, f"Query is missing tenant_id bind param. sql={sql_text[:100]!r}, params={params!r}"
            if expected_tenant_id is not None:
                actual = next(
                    (params[k] for k in sorted(tenant_keys) if params.get(k) is not None),
                    None,
                )
                assert actual == expected_tenant_id, f"Expected tenant_id={expected_tenant_id}, got {actual}"

        if "response_deadline" not in sql_text:
            return total

        if ">=" in sql_text:
            return at_risk

        return breached

    return handler


__all__ = ["SlaMockSession", "sla_mock_session", "make_sla_summary_handler"]
