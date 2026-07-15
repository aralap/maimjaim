"""Import clients from a private CSV into the encrypted clients table."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.extensions import db
from app.models import Client
from app.services.client_service import ClientService
from app.services.exceptions import InventoryError

PAYMENT_METHODS = {
    Client.PAYMENT_CASH,
    Client.PAYMENT_TRANSFER,
    Client.PAYMENT_CARD,
    Client.PAYMENT_MERCADO_PAGO,
    Client.PAYMENT_OTHER,
}

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

IMPORT_FIELDNAMES = {
    "name",
    "phone",
    "email",
    "address",
    "city",
    "tax_id",
    "notes",
    "preferred_payment_method",
    "is_active",
}


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    raw = phone.strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    if cleaned.startswith("+"):
        return f"+{digits}"
    return f"+{digits}"


def phone_match_key(phone: str | None) -> str | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    return re.sub(r"\D", "", normalized)


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def _normalize_payment(value: str | None) -> str | None:
    method = _blank(value)
    if not method:
        return None
    method = method.lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "efectivo": Client.PAYMENT_CASH,
        "cash": Client.PAYMENT_CASH,
        "transferencia": Client.PAYMENT_TRANSFER,
        "transfer": Client.PAYMENT_TRANSFER,
        "tarjeta": Client.PAYMENT_CARD,
        "card": Client.PAYMENT_CARD,
        "mp": Client.PAYMENT_MERCADO_PAGO,
        "mercadopago": Client.PAYMENT_MERCADO_PAGO,
        "mercado_pago": Client.PAYMENT_MERCADO_PAGO,
        "other": Client.PAYMENT_OTHER,
        "otro": Client.PAYMENT_OTHER,
    }
    method = aliases.get(method, method)
    return method if method in PAYMENT_METHODS else None


def _looks_like_phone_name(name: str | None) -> bool:
    if not name:
        return True
    digits = re.sub(r"\D", "", name)
    letters = re.sub(r"[^A-Za-zÁÉÍÓÚÜáéíóúüñÑ]", "", name)
    return len(digits) >= 8 and len(letters) < 3


def _merge_notes(existing: str | None, incoming: str | None) -> str | None:
    incoming = _blank(incoming)
    existing = _blank(existing)
    if not incoming:
        return existing
    if not existing:
        return incoming
    if incoming in existing:
        return existing
    return f"{existing}\n{incoming}"


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[str] = field(default_factory=list)

    def skip(self, reason: str) -> None:
        self.skipped += 1
        self.details.append(f"skip: {reason}")

    def error(self, reason: str) -> None:
        self.errors += 1
        self.details.append(f"error: {reason}")


class ClientImportService:
    @staticmethod
    def import_csv(
        csv_path: str | Path,
        *,
        dry_run: bool = False,
        update_existing: bool = False,
        min_confidence: str | None = None,
        batch_size: int = 50,
        user_id: int | None = None,
    ) -> ImportStats:
        path = Path(csv_path).expanduser().resolve()
        if not path.is_file():
            raise InventoryError(f"CSV no encontrado: {path}")

        min_rank = None
        if min_confidence:
            key = min_confidence.strip().lower()
            if key not in CONFIDENCE_RANK:
                raise InventoryError("min_confidence debe ser low, medium o high")
            min_rank = CONFIDENCE_RANK[key]

        stats = ImportStats()
        by_phone = ClientService.index_by_phone(active_only=False)
        pending = 0

        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise InventoryError("CSV sin encabezados")
            if "name" not in reader.fieldnames:
                raise InventoryError("CSV debe incluir columna 'name'")

            for row_num, raw in enumerate(reader, start=2):
                try:
                    result = ClientImportService._process_row(
                        raw,
                        row_num=row_num,
                        by_phone=by_phone,
                        dry_run=dry_run,
                        update_existing=update_existing,
                        min_rank=min_rank,
                        user_id=user_id,
                    )
                except Exception as exc:  # noqa: BLE001 — keep import going
                    stats.error(f"fila {row_num}: {exc}")
                    continue

                if result == "created":
                    stats.created += 1
                    pending += 1
                elif result == "updated":
                    stats.updated += 1
                    pending += 1
                elif result and result.startswith("skip:"):
                    stats.skip(result.removeprefix("skip:"))

                if not dry_run and pending >= batch_size:
                    db.session.commit()
                    pending = 0

        if not dry_run and pending:
            db.session.commit()
        elif dry_run:
            db.session.rollback()

        return stats

    @staticmethod
    def _process_row(
        raw: dict,
        *,
        row_num: int,
        by_phone: dict[str, Client],
        dry_run: bool,
        update_existing: bool,
        min_rank: int | None,
        user_id: int | None,
    ) -> str:
        confidence = (_blank(raw.get("confidence")) or "medium").lower()
        if min_rank is not None and CONFIDENCE_RANK.get(confidence, 0) < min_rank:
            return f"skip:fila {row_num} confidence={confidence}"

        name = _blank(raw.get("name"))
        phone = normalize_phone(_blank(raw.get("phone")))
        if not name:
            return f"skip:fila {row_num} sin nombre"
        if not phone:
            return f"skip:fila {row_num} sin teléfono"

        key = phone_match_key(phone)
        assert key is not None

        payload = {
            "name": name,
            "phone": phone,
            "email": _blank(raw.get("email")),
            "address": _blank(raw.get("address")),
            "city": _blank(raw.get("city")),
            "tax_id": _blank(raw.get("tax_id")),
            "notes": _blank(raw.get("notes")),
            "preferred_payment_method": _normalize_payment(raw.get("preferred_payment_method")),
            "is_active": _parse_bool(raw.get("is_active"), default=True),
        }

        existing = by_phone.get(key)
        if existing is None:
            if dry_run:
                return "created"
            client = ClientService.create_client(
                **payload,
                user_id=user_id,
                commit=False,
            )
            by_phone[key] = client
            return "created"

        if not update_existing:
            return f"skip:fila {row_num} teléfono ya existe ({phone})"

        fields = ClientImportService._merge_update_fields(existing, payload)
        if not fields:
            return f"skip:fila {row_num} sin cambios"
        if dry_run:
            return "updated"
        ClientService.update_client(
            existing.id,
            user_id=user_id,
            commit=False,
            **fields,
        )
        return "updated"

    @staticmethod
    def _merge_update_fields(existing: Client, payload: dict) -> dict:
        fields: dict = {}
        if payload["name"] and (
            _looks_like_phone_name(existing.name) and not _looks_like_phone_name(payload["name"])
        ):
            fields["name"] = payload["name"]

        for key in ("email", "address", "city", "tax_id", "preferred_payment_method"):
            if payload.get(key) and not getattr(existing, key):
                fields[key] = payload[key]

        merged_notes = _merge_notes(existing.notes, payload.get("notes"))
        if merged_notes != (existing.notes or None) and merged_notes:
            fields["notes"] = merged_notes

        if existing.is_active != payload["is_active"]:
            fields["is_active"] = payload["is_active"]

        return fields
