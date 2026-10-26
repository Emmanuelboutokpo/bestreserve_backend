"""fix_reviews_approved_at_timezone

Revision ID: d87e9b70d579
Revises: 90733424c276
Create Date: 2026-10-26 16:23:17.485301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd87e9b70d579'
down_revision: Union[str, Sequence[str], None] = '90733424c276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
