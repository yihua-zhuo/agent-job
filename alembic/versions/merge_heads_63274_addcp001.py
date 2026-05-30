"""Merge four parallel heads into one.

Revision ID: merge_heads_63274_addcp001
Revises: 185055a0d4f0, db67d696b6ab, 63274a8b98b3c, addcp001
Create Date: 2026-05-30 12:30:00.000000

The four heads are:
- 185055a0d4f0 (workflow_nodes, parented to 82ecf4a34e34)
- db67d696b6ab (identity subsystem + schema drift, parented to 7b1a2c3d4e5f)
- 63274a8b98b3c (webhook tables, parented to 9d8e7f6a5b3c)
- addcp001 (churn_predictions, parented to 9d8e7f6a5b3c)

This is a true merge/reconciliation-only revision.  All structural DDL
(tables, indexes) is owned by the four parent branches and is NOT replayed
here.  This migration only performs cross-branch reconciliation that could
not be handled by any single parent: adding tenant FKs to tables created by
e646948c549a (automation_logs / automation_rules) for DBs that arrived via
a path that skipped that migration, and adding missing tenant_id indexes on
auth tables created by db67d696b6ab for DBs that bypassed that head.

downgrade() reverses only those reconciliation steps.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merge_heads_63274_addcp001"
down_revision: str | Sequence[str] | None = ("185055a0d4f0", "db67d696b6ab", "63274a8b98b3c", "addcp001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # automation FKs to tenants
    # automation_logs / automation_rules are created by e646948c549a (in the
    # 52b19ee00eaf ancestry); this is a catch-up for DBs that arrived here
    # via a path that skips that migration.
    # PostgreSQL does not support IF NOT EXISTS for ADD CONSTRAINT, so we
    # use a DO block to catch and suppress the "already exists" error.
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE automation_logs ADD CONSTRAINT fk_automation_logs_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "END $$"
        )
    )
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "ALTER TABLE automation_rules ADD CONSTRAINT fk_automation_rules_tenant_id "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "END $$"
        )
    )

    # missing tenant_id indexes on auth tables
    # Created by db67d696b6ab; this is a catch-up for paths that bypassed it.
    op.create_index(op.f("ix_device_trust_tenant_id"), "device_trust", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_tenant_id"), "refresh_tokens", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_credentials_tenant_id"), "user_credentials", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_webauthn_challenges_tenant_id"), "webauthn_challenges", ["tenant_id"], unique=False)


def downgrade() -> None:
    # Reverse reconciliation steps only — tables/indexes are dropped by the
    # parent migrations' downgrades.
    op.drop_index(op.f("ix_webauthn_challenges_tenant_id"), table_name="webauthn_challenges")
    op.drop_index(op.f("ix_user_credentials_tenant_id"), table_name="user_credentials")
    op.drop_index(op.f("ix_refresh_tokens_tenant_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_device_trust_tenant_id"), table_name="device_trust")
    op.execute(sa.text("ALTER TABLE automation_rules DROP CONSTRAINT IF EXISTS fk_automation_rules_tenant_id"))
    op.execute(sa.text("ALTER TABLE automation_logs DROP CONSTRAINT IF EXISTS fk_automation_logs_tenant_id"))
