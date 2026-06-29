"""User approval: existing users stay active

Revision ID: g1h2i3j4k5l6
Revises: f7a8b9c0d1e2
Create Date: 2026-06-29 20:00:00.000000

"""
from alembic import op


revision = "g1h2i3j4k5l6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET is_active = 1")


def downgrade():
    pass
