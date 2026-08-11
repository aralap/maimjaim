"""Add mayorista prices and per-line order price type.

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-08-11 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "h2i3j4k5l6m7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("product_variants", schema=None) as batch_op:
        batch_op.add_column(sa.Column("wholesale_price_cents", sa.Integer(), nullable=True))

    with op.batch_alter_table("order_lines", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("price_type", sa.String(length=32), nullable=False, server_default="retail")
        )


def downgrade():
    with op.batch_alter_table("order_lines", schema=None) as batch_op:
        batch_op.drop_column("price_type")

    with op.batch_alter_table("product_variants", schema=None) as batch_op:
        batch_op.drop_column("wholesale_price_cents")
