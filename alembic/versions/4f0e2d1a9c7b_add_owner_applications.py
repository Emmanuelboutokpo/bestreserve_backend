"""add owner applications and owner email verification

Revision ID: 4f0e2d1a9c7b
Revises: d87e9b70d579
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import context
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4f0e2d1a9c7b"
down_revision: Union[str, Sequence[str], None] = "d87e9b70d579"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    inspector = None if offline else sa.inspect(bind)

    user_columns = (
        set()
        if offline
        else {column["name"] for column in inspector.get_columns("users")}
    )
    if offline or "email_verified" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        op.alter_column(
            "users",
            "email_verified",
            server_default=None,
        )

    owner_status = postgresql.ENUM(
        "EN_ATTENTE",
        "APPROUVE",
        "REJETE",
        name="ownerapplicationstatus",
    )
    owner_status.create(bind, checkfirst=not offline)

    if offline or not inspector.has_table("owner_applications"):
        op.create_table(
            "owner_applications",
            sa.Column("owner_id", sa.Uuid(), nullable=False),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "EN_ATTENTE",
                    "APPROUVE",
                    "REJETE",
                    name="ownerapplicationstatus",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column(
                "registry_file_name",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "registry_file_public_id",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "registry_mime_type",
                sa.String(length=100),
                nullable=False,
            ),
            sa.Column("registry_file_size", sa.Integer(), nullable=False),
            sa.Column(
                "partnership_file_name",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "partnership_file_public_id",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "partnership_mime_type",
                sa.String(length=100),
                nullable=False,
            ),
            sa.Column("partnership_file_size", sa.Integer(), nullable=False),
            sa.Column(
                "submitted_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("reviewed_by", sa.Uuid(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "rejection_reason",
                sa.String(length=2000),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = (
        ("idx_owner_applications_owner", ["owner_id"]),
        ("idx_owner_applications_status", ["status"]),
        ("ix_owner_applications_id", ["id"]),
    )
    existing_indexes = (
        set()
        if offline or not inspector.has_table("owner_applications")
        else {
            index["name"]
            for index in inspector.get_indexes("owner_applications")
        }
    )
    for index_name, columns in indexes:
        if offline or index_name not in existing_indexes:
            op.create_index(
                index_name,
                "owner_applications",
                columns,
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    inspector = None if offline else sa.inspect(bind)

    op.drop_index(
        "idx_owner_applications_status",
        table_name="owner_applications",
    )
    op.drop_index(
        "idx_owner_applications_owner",
        table_name="owner_applications",
    )
    op.drop_table("owner_applications")
    sa.Enum(
        "EN_ATTENTE",
        "APPROUVE",
        "REJETE",
        name="ownerapplicationstatus",
    ).drop(op.get_bind(), checkfirst=True)
    user_columns = (
        set()
        if offline
        else {column["name"] for column in inspector.get_columns("users")}
    )
    if offline or "email_verified" in user_columns:
        op.drop_column("users", "email_verified")
