"""Cifra datos existentes en texto plano tras activar columnas cifradas."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.crypto import decrypt_text, is_encrypted, make_lookup
from app.extensions import db
from app.models import ActivityLog, Client, Order, User


def _encrypt_row_value(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if is_encrypted(value):
        return value
    return encrypt_text(value)


def migrate_users() -> int:
    updated = 0
    for user in User.query.all():
        changed = False
        if user.email:
            plain_email = decrypt_text(str(user.email)) or str(user.email)
            user.email_lookup = make_lookup(plain_email)
            if not is_encrypted(str(user.email)):
                user.email = plain_email
                changed = True
        if user.google_sub:
            plain_sub = decrypt_text(str(user.google_sub)) or str(user.google_sub)
            user.google_sub_lookup = make_lookup(plain_sub)
            if not is_encrypted(str(user.google_sub)):
                user.google_sub = plain_sub
                changed = True
        if user.name and not is_encrypted(str(user.name)):
            user.name = decrypt_text(str(user.name)) or str(user.name)
            changed = True
        if changed or not user.email_lookup or not user.google_sub_lookup:
            updated += 1
    return updated


def migrate_clients() -> int:
    updated = 0
    for client in Client.query.all():
        changed = False
        for field in (
            "name",
            "email",
            "phone",
            "address",
            "city",
            "tax_id",
            "notes",
            "preferred_payment_method",
        ):
            value = getattr(client, field)
            if value and not is_encrypted(str(value)):
                setattr(client, field, str(value))
                changed = True
        if changed:
            updated += 1
    return updated


def migrate_orders() -> int:
    updated = 0
    for order in Order.query.all():
        changed = False
        for field in (
            "customer_name",
            "customer_phone",
            "customer_email",
            "notes",
            "payment_method",
            "payment_reference",
            "payment_notes",
        ):
            value = getattr(order, field)
            if value and not is_encrypted(str(value)):
                setattr(order, field, str(value))
                changed = True

        raw_amount = db.session.execute(
            text("SELECT amount_paid_cents FROM orders WHERE id = :id"),
            {"id": order.id},
        ).scalar()
        if raw_amount is not None and not is_encrypted(str(raw_amount)):
            order.amount_paid_cents = int(raw_amount)
            changed = True

        if changed:
            updated += 1
    return updated


def migrate_activity_logs() -> int:
    updated = 0
    for log in ActivityLog.query.all():
        changed = False
        raw = db.session.execute(
            text("SELECT summary, details FROM activity_logs WHERE id = :id"),
            {"id": log.id},
        ).one()
        summary_raw, details_raw = raw

        if summary_raw and not is_encrypted(str(summary_raw)):
            log.summary = str(summary_raw)
            changed = True

        if details_raw is not None:
            if isinstance(details_raw, str):
                if not is_encrypted(details_raw):
                    try:
                        log.details = json.loads(details_raw)
                    except json.JSONDecodeError:
                        log.details = {}
                    changed = True
            elif not is_encrypted(str(details_raw)):
                log.details = details_raw
                changed = True

        if changed:
            updated += 1
    return updated


def migrate_all_sensitive_data() -> dict[str, int]:
    with db.session.no_autoflush:
        counts = {
            "users": migrate_users(),
            "clients": migrate_clients(),
            "orders": migrate_orders(),
            "activity_logs": migrate_activity_logs(),
        }
    db.session.commit()
    return counts
