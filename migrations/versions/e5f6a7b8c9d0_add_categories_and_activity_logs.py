"""Add product categories, product fields, and activity logs

Revision ID: e5f6a7b8c9d0
Revises: d4e8f1a2b3c4
Create Date: 2026-06-29 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e8f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activity_logs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_activity_logs_action"), ["action"], unique=False)
        batch_op.create_index(batch_op.f("ix_activity_logs_entity_id"), ["entity_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_activity_logs_entity_type"), ["entity_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_activity_logs_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("unit", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("supplier", sa.String(length=255), nullable=True))
        batch_op.create_foreign_key(
            "fk_products_category_id", "product_categories", ["category_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint("fk_products_category_id", type_="foreignkey")
        batch_op.drop_column("supplier")
        batch_op.drop_column("unit")
        batch_op.drop_column("category_id")

    op.drop_table("activity_logs")
    op.drop_table("product_categories")
