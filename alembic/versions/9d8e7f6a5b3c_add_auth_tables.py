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

from alembic import op
import sqlalchemy as sa

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
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # user_credentials
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=255), nullable=False, unique=True),
        # Text() — FIDO2 attestation objects (X.509 cert chains) routinely exceed 1024 chars
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("authenticator_type", sa.String(length=20), nullable=False, server_default=sa.text("'fido2'")),
        sa.Column("transports", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_credentials_user_id", "user_credentials", ["user_id"])
    op.create_index("ix_user_credentials_credential_id", "user_credentials", ["credential_id"])

    # device_trust
    op.create_table(
        "device_trust",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
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
    )
    op.create_index("ix_device_trust_user_id", "device_trust", ["user_id"])
    op.create_index("ix_device_trust_fingerprint", "device_trust", ["device_fingerprint"])

    # webauthn_challenges — single-use challenges with TTL
    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("challenge", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False, server_default=sa.text("'registration'")),
        sa.Column("credential_id", sa.String(length=255), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_webauthn_challenges_user_id", "webauthn_challenges", ["user_id"])
    op.create_index("ix_webauthn_challenges_challenge", "webauthn_challenges", ["challenge"])
    op.create_index("ix_webauthn_challenges_expires", "webauthn_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("webauthn_challenges")
    op.drop_table("device_trust")
    op.drop_table("user_credentials")
    op.drop_table("refresh_tokens")