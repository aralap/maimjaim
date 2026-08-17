"""Add minorista/mayorista price type on orders and clients.

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-08-17 19:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j4k5l6m7n8o9"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_type", sa.String(length=32), nullable=False, server_default="retail")
        )
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_type", sa.String(length=32), nullable=False, server_default="retail")
        )


def downgrade():
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_column("price_type")
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("price_type")
