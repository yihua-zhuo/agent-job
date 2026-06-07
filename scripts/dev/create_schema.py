#!/usr/bin/env python3
"""Create all ORM tables on the dev database.

Used by ``make dev-up`` in place of ``alembic upgrade head``. The migration
chain on this branch has multiple heads with duplicate-DDL merge migrations
that can't be applied to a fresh DB cleanly; ``Base.metadata.create_all`` is
the canonical "current model state" path (it's also what the integration
test harness uses).

After tables are created, alembic is stamped to ``heads`` so subsequent
``alembic`` invocations report a clean state.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("error: DATABASE_URL not set", file=sys.stderr)
        return 2

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    import db.base  # noqa: F401
    import db.models  # noqa: F401 - registers every model with Base.metadata
    from db.base import Base

    engine = create_engine(sync_url)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()

    print(f"created {len(Base.metadata.tables)} tables on {sync_url}")

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.stamp(cfg, "heads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
