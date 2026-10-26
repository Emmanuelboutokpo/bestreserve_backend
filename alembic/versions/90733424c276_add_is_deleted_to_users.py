"""add is_deleted to users

Revision ID: 90733424c276
Revises: ba84526ffc24
Create Date: 2026-10-23 11:05:16.805046
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90733424c276"
down_revision: Union[str, Sequence[str], None] = "ba84526ffc24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_deleted to users."""

    op.add_column(
        "users",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "users",
        "is_deleted",
        server_default=None,
    )

    op.create_index(
        op.f("ix_users_is_deleted"),
        "users",
        ["is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    """Remove is_deleted from users."""

    op.drop_index(
        op.f("ix_users_is_deleted"),
        table_name="users",
    )

    op.drop_column("users", "is_deleted")
