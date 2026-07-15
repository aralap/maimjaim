from app.extensions import db
from app.models import Client
from app.services.audit_service import AuditService
from app.services.exceptions import InventoryError


def _client_details(client: Client) -> dict:
    return {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "phone": client.phone,
        "address": client.address,
        "city": client.city,
        "tax_id": client.tax_id,
        "preferred_payment_method": client.preferred_payment_method,
        "is_active": client.is_active,
        "notes": client.notes,
    }


class ClientService:
    @staticmethod
    def list_clients(active_only: bool = True) -> list[Client]:
        query = Client.query
        if active_only:
            query = query.filter_by(is_active=True)
        clients = query.all()
        return sorted(clients, key=lambda c: (c.name or "").lower())

    @staticmethod
    def get_client(client_id: int) -> Client | None:
        return db.session.get(Client, client_id)

    @staticmethod
    def create_client(
        *,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        city: str | None = None,
        tax_id: str | None = None,
        notes: str | None = None,
        preferred_payment_method: str | None = None,
        is_active: bool = True,
        user_id: int | None = None,
        commit: bool = True,
    ) -> Client:
        name = name.strip()
        if not name:
            raise InventoryError("El nombre del cliente es obligatorio")

        client = Client(
            name=name,
            email=email or None,
            phone=phone or None,
            address=address or None,
            city=city or None,
            tax_id=tax_id or None,
            notes=notes or None,
            preferred_payment_method=preferred_payment_method or None,
            is_active=is_active,
        )
        db.session.add(client)
        db.session.flush()
        AuditService.log(
            "client.create",
            "client",
            f"Cliente creado: {client.name}",
            entity_id=client.id,
            user_id=user_id,
            details=_client_details(client),
        )
        if commit:
            db.session.commit()
        return client

    @staticmethod
    def update_client(
        client_id: int,
        *,
        user_id: int | None = None,
        commit: bool = True,
        **fields,
    ) -> Client:
        client = db.session.get(Client, client_id)
        if not client:
            raise InventoryError(f"Cliente {client_id} no encontrado")

        before = _client_details(client)
        for key, value in fields.items():
            if not hasattr(client, key):
                continue
            if key == "is_active":
                client.is_active = bool(value)
            elif isinstance(value, str):
                setattr(client, key, value.strip() or None)
            else:
                setattr(client, key, value)

        if not client.name or not client.name.strip():
            raise InventoryError("El nombre del cliente es obligatorio")

        AuditService.log(
            "client.update",
            "client",
            f"Cliente actualizado: {client.name}",
            entity_id=client.id,
            user_id=user_id,
            details={"before": before, "after": _client_details(client)},
        )
        if commit:
            db.session.commit()
        return client

    @staticmethod
    def index_by_phone(active_only: bool = False) -> dict[str, Client]:
        """Map phone digit-key → client (phones are encrypted at rest)."""
        from app.services.client_import_service import phone_match_key

        clients = ClientService.list_clients(active_only=active_only)
        index: dict[str, Client] = {}
        for client in clients:
            key = phone_match_key(client.phone)
            if key and key not in index:
                index[key] = client
        return index
