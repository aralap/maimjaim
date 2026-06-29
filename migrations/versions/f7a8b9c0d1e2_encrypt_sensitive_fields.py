"""Encrypt sensitive user and payment fields at rest

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-06-29 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email_lookup", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("google_sub_lookup", sa.String(length=64), nullable=True))
        batch_op.drop_index("ix_users_email")
        batch_op.drop_index("ix_users_google_sub")

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_index("ix_clients_name")

    # Widen / change column types for ciphertext (SQLite stores as TEXT)
    for table, columns in [
        ("users", ["email", "google_sub", "name"]),
        (
            "clients",
            ["name", "email", "phone", "address", "city", "tax_id", "notes", "preferred_payment_method"],
        ),
        (
            "orders",
            [
                "customer_name",
                "customer_phone",
                "customer_email",
                "notes",
                "payment_method",
                "amount_paid_cents",
                "payment_reference",
                "payment_notes",
            ],
        ),
        ("activity_logs", ["summary", "details"]),
    ]:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for col in columns:
                batch_op.alter_column(col, type_=sa.Text(), existing_nullable=True)

    from app.data_encryption import migrate_all_sensitive_data

    migrate_all_sensitive_data()

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("email_lookup", nullable=False)
        batch_op.alter_column("google_sub_lookup", nullable=False)
        batch_op.create_index(batch_op.f("ix_users_email_lookup"), ["email_lookup"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_users_google_sub_lookup"), ["google_sub_lookup"], unique=True
        )


def downgrade():
    raise NotImplementedError("No se puede revertir el cifrado de datos sin pérdida.")
