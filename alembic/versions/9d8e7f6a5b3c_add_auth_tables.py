"""Add auth tables: refresh_tokens, user_credentials, device_trust.

Revision ID: 9d8e7f6a5b3c
Revises:
Create Date: 2026-05-13

This migration creates the tables required for issue #163:
- refresh_tokens: HttpOnly cookie token storage with revocation support
- user_credentials: WebAuthn public key storage
- device_trust: Trusted device tracking for suspicious activity detection
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9d8e7f6a5b3c"
down_revision = "3ea69d66514e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("token_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # user_credentials
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("credential_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("public_key", sa.String(length=1024), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("authenticator_type", sa.String(length=20), nullable=False, server_default="fido2"),
        sa.Column("transports", sa.String(length=100), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
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
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("trusted_ip", sa.String(length=45), nullable=True),
        sa.Column("last_ip", sa.String(length=45), nullable=True),
        sa.Column("last_location", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trusted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("trusted", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_device_trust_user_id", "device_trust", ["user_id"])
    op.create_index("ix_device_trust_fingerprint", "device_trust", ["device_fingerprint"])


def downgrade() -> None:
    op.drop_table("device_trust")
    op.drop_table("user_credentials")
    op.drop_table("refresh_tokens")