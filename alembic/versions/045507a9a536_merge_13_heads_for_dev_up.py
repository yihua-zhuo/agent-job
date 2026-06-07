"""merge 13 heads for dev-up

Revision ID: 045507a9a536
Revises: 0596add_notification_analytics_tracking, 127938d15761, 195a79d95b41, 3c19d099a7a9, 6042653c9d73, 663_notif_prefs, a0000012, a0000013, a2a592eec292, a785fd51c79e, a1b2c3d4e5f6, merge_heads_63274_addcp001, merge_heads_four
Create Date: 2026-06-08 01:06:37.695910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '045507a9a536'
down_revision: Union[str, None] = ('0596add_notification_analytics_tracking', '127938d15761', '195a79d95b41', '3c19d099a7a9', '6042653c9d73', '663_notif_prefs', 'a0000012', 'a0000013', 'a2a592eec292', 'a785fd51c79e', 'a1b2c3d4e5f6', 'merge_heads_63274_addcp001', 'merge_heads_four')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass