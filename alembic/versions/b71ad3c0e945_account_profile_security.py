"""Add client account consent and avatar metadata.

Revision ID: b71ad3c0e945
Revises: a32f336efea4
Create Date: 2026-10-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b71ad3c0e945"
down_revision: Union[str, Sequence[str], None] = "a32f336efea4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "profiles",
        sa.Column("avatar_public_id", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "user_consents",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "purpose",
            name="uq_user_consent_purpose",
        ),
    )
    op.create_index(
        "idx_user_consents_user",
        "user_consents",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_user_consents_user", table_name="user_consents")
    op.drop_table("user_consents")
    op.drop_column("profiles", "avatar_public_id")
    op.drop_column("users", "token_version")
