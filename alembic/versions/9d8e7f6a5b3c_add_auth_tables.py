"""Add auth tables: refresh_tokens, user_credentials, device_trust, webauthn_challenges.

Revision ID: 9d8e7f6a5b3c
Revises: 3ea69d66514e
Create Date: 2026-05-13

This migration creates the tables required for issue #163:
- refresh_tokens: HttpOnly cookie token storage with revocation support
- user_credentials: WebAuthn public key storage
- device_trust: Trusted device tracking for suspicious activity detection
- webauthn_challenges: Single-use WebAuthn registration/assertion challenges (TTL-based)
"""

import sqlalchemy as sa

from alembic import op

revision = "9d8e7f6a5b3c"
down_revision = "3ea69d66514e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_user_revoked", "refresh_tokens", ["tenant_id", "user_id", "revoked"])
    op.create_index("ix_refresh_tokens_expires", "refresh_tokens", ["tenant_id", "expires_at"])

    # user_credentials
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=1024), nullable=False, unique=True),
        # Text() — FIDO2 attestation objects (X.509 cert chains) routinely exceed 1024 chars
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("authenticator_type", sa.String(length=50), nullable=False, server_default=sa.text("'fido2'")),
        sa.Column("transports", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_credentials_user_id", "user_credentials", ["user_id"])
    op.create_index("ix_user_credentials_user_enabled", "user_credentials", ["tenant_id", "user_id", "enabled"])

    # device_trust
    op.create_table(
        "device_trust",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("trusted_ip", sa.String(length=45), nullable=True),
        sa.Column("last_ip", sa.String(length=45), nullable=True),
        sa.Column("last_location", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trusted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", "device_fingerprint", name="uq_device_trust_tenant_user_fingerprint"),
    )
    op.create_index("ix_device_trust_user_id", "device_trust", ["user_id"])
    op.create_index("ix_device_trust_lookup", "device_trust", ["tenant_id", "user_id", "trusted"])
    op.create_index("ix_device_trust_suspicious", "device_trust", ["tenant_id", "user_id", "trusted", "last_ip"])

    # webauthn_challenges — single-use challenges with TTL
    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("challenge", sa.String(length=512), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False, server_default=sa.text("'registration'")),
        sa.Column("credential_id", sa.String(length=1024), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_webauthn_challenges_user_id", "webauthn_challenges", ["user_id"])
    op.create_index("ix_webauthn_challenges_challenge", "webauthn_challenges", ["tenant_id", "challenge"])
    op.create_index("ix_webauthn_challenges_expires", "webauthn_challenges", ["tenant_id", "expires_at"])
    op.create_index(
        "ix_webauthn_challenges_consume",
        "webauthn_challenges",
        ["tenant_id", "user_id", "purpose", "consumed", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("webauthn_challenges")
    op.drop_table("device_trust")
    op.drop_table("user_credentials")
    op.drop_table("refresh_tokens")
