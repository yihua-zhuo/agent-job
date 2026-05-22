"""add_automation_and_routing_models

Revision ID: 7770543dc37d
Revises: f0c74d3d54f0
Create Date: 2026-05-22 10:25:19.121445

Migration is intentionally empty — the opportunities table was already
created by the initial schema migration (b2c3dce4b714_create_all_tables.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7770543dc37d'
down_revision: Union[str, None] = 'f0c74d3d54f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass