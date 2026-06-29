"""Add order delivery_date

Revision ID: d4e8f1a2b3c4
Revises: c0ad2a1f47e3
Create Date: 2026-06-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e8f1a2b3c4"
down_revision = "c0ad2a1f47e3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("delivery_date", sa.Date(), nullable=True))
        batch_op.create_index(batch_op.f("ix_orders_delivery_date"), ["delivery_date"], unique=False)


def downgrade():
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_orders_delivery_date"))
        batch_op.drop_column("delivery_date")
