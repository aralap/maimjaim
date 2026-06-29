"""Add clients and order payment fields

Revision ID: c0ad2a1f47e3
Revises: b13188ddb81f
Create Date: 2026-06-29 00:18:00.880181

"""
from alembic import op
import sqlalchemy as sa


revision = "c0ad2a1f47e3"
down_revision = "b13188ddb81f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("preferred_payment_method", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_clients_name"), ["name"], unique=False)

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("client_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "payment_status",
                sa.String(length=32),
                nullable=False,
                server_default="unpaid",
            )
        )
        batch_op.add_column(sa.Column("payment_method", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column(
                "amount_paid_cents",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("payment_reference", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("payment_notes", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_orders_client_id", "clients", ["client_id"], ["id"]
        )

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.alter_column("payment_status", server_default=None)
        batch_op.alter_column("amount_paid_cents", server_default=None)


def downgrade():
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_constraint("fk_orders_client_id", type_="foreignkey")
        batch_op.drop_column("payment_notes")
        batch_op.drop_column("payment_reference")
        batch_op.drop_column("amount_paid_cents")
        batch_op.drop_column("payment_method")
        batch_op.drop_column("payment_status")
        batch_op.drop_column("client_id")

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clients_name"))

    op.drop_table("clients")
