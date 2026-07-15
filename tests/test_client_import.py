import csv

from app.models import Client
from app.services import ClientService
from app.services.client_import_service import (
    ClientImportService,
    normalize_phone,
    phone_match_key,
)


def test_normalize_phone():
    assert normalize_phone("+54 9 11 2515-4222") == "+5491125154222"
    assert normalize_phone("5491125154222") == "+5491125154222"
    assert phone_match_key("+5491125154222") == phone_match_key("5491125154222")


def test_import_clients_creates_encrypted_rows(app, tmp_path):
    csv_path = tmp_path / "clients.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "name",
                "phone",
                "email",
                "address",
                "city",
                "tax_id",
                "notes",
                "preferred_payment_method",
                "is_active",
                "confidence",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "name": "Denise Test",
                "phone": "+5491125154222",
                "email": "denise@example.com",
                "address": "Lavalle 2880",
                "city": "CABA",
                "tax_id": "",
                "notes": "WhatsApp import",
                "preferred_payment_method": "mercado_pago",
                "is_active": "true",
                "confidence": "high",
            }
        )

    stats = ClientImportService.import_csv(csv_path)
    assert stats.created == 1
    assert stats.errors == 0

    clients = ClientService.list_clients()
    assert len(clients) == 1
    client = clients[0]
    assert client.name == "Denise Test"
    assert client.phone == "+5491125154222"
    assert client.preferred_payment_method == "mercado_pago"

    # Stored value in DB must be ciphertext, not plaintext
    raw = Client.query.first()
    # Access via SQLAlchemy column history / table — use connection for raw storage
    from app.extensions import db

    stored = db.session.execute(db.text("SELECT phone FROM clients")).scalar()
    assert stored.startswith("enc:v1:")
    assert "25154222" not in stored


def test_import_clients_skips_duplicate_unless_update(app, tmp_path):
    ClientService.create_client(name="+5491125154222", phone="+5491125154222")
    csv_path = tmp_path / "clients.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "phone", "address", "confidence"])
        writer.writeheader()
        writer.writerow(
            {
                "name": "Denise Mbazbaz",
                "phone": "5491125154222",
                "address": "Lavalle 2880 1b",
                "confidence": "high",
            }
        )

    skipped = ClientImportService.import_csv(csv_path)
    assert skipped.created == 0
    assert skipped.skipped == 1

    updated = ClientImportService.import_csv(csv_path, update_existing=True)
    assert updated.updated == 1
    client = ClientService.list_clients()[0]
    assert client.name == "Denise Mbazbaz"
    assert client.address == "Lavalle 2880 1b"


def test_import_min_confidence(app, tmp_path):
    csv_path = tmp_path / "clients.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "phone", "confidence"])
        writer.writeheader()
        writer.writerow({"name": "Low", "phone": "+5491100000001", "confidence": "low"})
        writer.writerow({"name": "High", "phone": "+5491100000002", "confidence": "high"})

    stats = ClientImportService.import_csv(csv_path, min_confidence="high")
    assert stats.created == 1
    assert stats.skipped == 1
    assert ClientService.list_clients()[0].name == "High"
