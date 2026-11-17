"""add location access payments

Revision ID: f13c8a9b2d41
Revises: ba84526ffc24
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f13c8a9b2d41"
down_revision: Union[str, Sequence[str], None] = "4f0e2d1a9c7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_access_payments",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_ref", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "provider_transaction_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "payment_method",
            postgresql.ENUM(
                "CARTE_BANCAIRE",
                "MOBILE_MONEY",
                "VIREMENT",
                "SUR_PLACE",
                name="paymentmethod",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "EN_ATTENTE",
                "PAYE",
                "REMBOURSE",
                "ECHOUE",
                name="paymentstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount = 500",
            name="ck_location_access_payments_amount",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_location_access_payments_idempotency_key",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_location_access_payments_provider_reference",
        ),
        sa.UniqueConstraint(
            "transaction_ref",
            name="uq_location_access_payments_reference",
        ),
    )
    op.create_index(
        "idx_location_access_payments_user",
        "location_access_payments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_location_access_payments_id"),
        "location_access_payments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "uq_location_access_payments_user_pending",
        "location_access_payments",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'EN_ATTENTE'"),
        sqlite_where=sa.text("status = 'EN_ATTENTE'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_location_access_payments_user_pending",
        table_name="location_access_payments",
    )
    op.drop_index(
        op.f("ix_location_access_payments_id"),
        table_name="location_access_payments",
    )
    op.drop_index(
        "idx_location_access_payments_user",
        table_name="location_access_payments",
    )
    op.drop_table("location_access_payments")
