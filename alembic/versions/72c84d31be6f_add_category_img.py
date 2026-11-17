"""add image URL to categories

Revision ID: 72c84d31be6f
Revises: f13c8a9b2d41
Create Date: 2026-11-15 21:19:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "72c84d31be6f"
down_revision: Union[str, Sequence[str], None] = "f13c8a9b2d41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("img", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("categories", "img")
