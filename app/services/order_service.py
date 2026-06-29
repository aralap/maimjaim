import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from collections import defaultdict

from app.extensions import db
from app.models import Client, Order, OrderLine, ProductVariant
from app.services.audit_service import AuditService
from app.services.client_service import ClientService
from app.services.exceptions import InvalidOrderStateError, InventoryError
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService


@dataclass
class OrderLineInput:
    variant_id: int | None = None
    sku: str | None = None
    quantity: int = 1


@dataclass
class CustomerInput:
    name: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass
class PaymentInput:
    payment_method: str | None = None
    amount_paid_cents: int = 0
    payment_reference: str | None = None
    payment_notes: str | None = None


class OrderService:
    @staticmethod
    def _order_details(order: Order) -> dict:
        return {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "source": order.source,
            "client_id": order.client_id,
            "customer_name": order.customer_name,
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "amount_paid_cents": order.amount_paid_cents,
            "total_cents": order.total_cents,
            "lines": [
                {"sku": line.variant.sku, "quantity": line.quantity, "unit_price_cents": line.unit_price_cents}
                for line in order.lines
            ],
        }

    @staticmethod
    def _audit_order(order: Order, action: str, summary: str, user_id: int | None = None, extra: dict | None = None):
        details = OrderService._order_details(order)
        if extra:
            details.update(extra)
        AuditService.log(action, "order", summary, entity_id=order.id, user_id=user_id, details=details)

    @staticmethod
    def _generate_order_number() -> str:
        return f"ORD-{secrets.token_hex(4).upper()}"

    @staticmethod
    def _resolve_variant(line: OrderLineInput) -> ProductVariant:
        if line.variant_id:
            variant = ProductService.get_variant(line.variant_id)
        elif line.sku:
            variant = ProductService.get_variant_by_sku(line.sku)
        else:
            raise InventoryError("Cada línea del pedido requiere variant_id o sku")

        if not variant:
            raise InventoryError("Variante no encontrada")
        if line.quantity <= 0:
            raise InventoryError("La cantidad debe ser mayor a cero")
        return variant

    @staticmethod
    def _apply_client_to_order(order: Order, client_id: int | None) -> None:
        if not client_id:
            return
        client = ClientService.get_client(client_id)
        if not client:
            raise InventoryError(f"Cliente {client_id} no encontrado")
        order.client_id = client.id
        order.customer_name = client.name
        order.customer_phone = client.phone
        order.customer_email = client.email
        if not order.payment_method and client.preferred_payment_method:
            order.payment_method = client.preferred_payment_method

    @staticmethod
    def _apply_payment(order: Order, payment: PaymentInput | None) -> None:
        if not payment:
            return
        if payment.payment_method:
            order.payment_method = payment.payment_method
        if payment.amount_paid_cents:
            order.amount_paid_cents = payment.amount_paid_cents
        if payment.payment_reference:
            order.payment_reference = payment.payment_reference
        if payment.payment_notes:
            order.payment_notes = payment.payment_notes
        order.sync_payment_status()

    @staticmethod
    def create_order(
        lines: list[OrderLineInput],
        customer: CustomerInput | None = None,
        source: str = Order.SOURCE_MANUAL,
        *,
        client_id: int | None = None,
        payment: PaymentInput | None = None,
        external_id: str | None = None,
        api_client_id: int | None = None,
        notes: str | None = None,
        delivery_date: date | None = None,
        user_id: int | None = None,
        auto_confirm: bool = False,
    ) -> Order:
        if not lines:
            raise InventoryError("El pedido debe tener al menos un artículo")

        if external_id and api_client_id:
            existing = Order.query.filter_by(
                api_client_id=api_client_id,
                external_id=external_id,
            ).first()
            if existing:
                return existing

        customer = customer or CustomerInput()
        order = Order(
            order_number=OrderService._generate_order_number(),
            status=Order.STATUS_DRAFT,
            source=source,
            customer_name=customer.name,
            customer_phone=customer.phone,
            customer_email=customer.email,
            notes=notes,
            delivery_date=delivery_date,
            payment_status=Order.PAYMENT_UNPAID,
            amount_paid_cents=0,
            created_by_id=user_id,
            api_client_id=api_client_id,
            external_id=external_id,
        )

        OrderService._apply_client_to_order(order, client_id)
        if not client_id:
            if customer.name:
                order.customer_name = customer.name
            if customer.phone:
                order.customer_phone = customer.phone
            if customer.email:
                order.customer_email = customer.email

        for line_input in lines:
            variant = OrderService._resolve_variant(line_input)
            order.lines.append(
                OrderLine(
                    variant=variant,
                    quantity=line_input.quantity,
                    unit_price_cents=variant.price_cents,
                )
            )

        OrderService._apply_payment(order, payment)
        order.sync_payment_status()

        db.session.add(order)
        db.session.flush()
        OrderService._audit_order(
            order,
            "order.create",
            f"Pedido creado: {order.order_number}",
            user_id=user_id,
        )
        db.session.commit()

        if auto_confirm:
            return OrderService.confirm_order(order.id, user_id=user_id)
        return order

    @staticmethod
    def update_payment(order_id: int, payment: PaymentInput, user_id: int | None = None) -> Order:
        order = db.session.get(Order, order_id)
        if not order:
            raise InventoryError(f"Pedido {order_id} no encontrado")
        before = order.payment_status
        OrderService._apply_payment(order, payment)
        order.sync_payment_status()
        OrderService._audit_order(
            order,
            "order.payment.update",
            f"Pago actualizado en {order.order_number}",
            user_id=user_id,
            extra={"payment_status_before": before},
        )
        db.session.commit()
        return order

    @staticmethod
    def get_order(order_id: int) -> Order | None:
        return db.session.get(Order, order_id)

    @staticmethod
    def update_delivery_date(order_id: int, delivery_date: date | None, user_id: int | None = None) -> Order:
        order = db.session.get(Order, order_id)
        if not order:
            raise InventoryError(f"Pedido {order_id} no encontrado")
        before = order.delivery_date.isoformat() if order.delivery_date else None
        order.delivery_date = delivery_date
        OrderService._audit_order(
            order,
            "order.delivery.update",
            f"Fecha de entrega actualizada en {order.order_number}",
            user_id=user_id,
            extra={
                "delivery_date_before": before,
                "delivery_date_after": delivery_date.isoformat() if delivery_date else None,
            },
        )
        db.session.commit()
        return order

    @staticmethod
    def get_procurement_plan(days: int = 7) -> dict:
        """Pedidos con entrega en los próximos N días y stock faltante por SKU."""
        today = date.today()
        end = today + timedelta(days=days)

        orders = (
            Order.query.filter(
                Order.delivery_date.isnot(None),
                Order.delivery_date >= today,
                Order.delivery_date <= end,
                Order.status.in_([Order.STATUS_DRAFT, Order.STATUS_CONFIRMED]),
            )
            .order_by(Order.delivery_date.asc())
            .all()
        )

        needs: dict[int, int] = defaultdict(int)
        for order in orders:
            for line in order.lines:
                needs[line.variant_id] += line.quantity

        items = []
        for variant_id, qty_needed in needs.items():
            variant = db.session.get(ProductVariant, variant_id)
            if not variant:
                continue
            available = InventoryService.get_availability(variant_id)
            items.append(
                {
                    "variant": variant,
                    "qty_needed": qty_needed,
                    "available": available,
                    "to_order": max(0, qty_needed - available),
                }
            )
        items.sort(key=lambda row: (-row["to_order"], row["variant"].sku))

        return {"orders": orders, "product_needs": items, "start": today, "end": end, "days": days}

    @staticmethod
    def list_orders(status: str | None = None) -> list[Order]:
        query = Order.query.order_by(Order.created_at.desc())
        if status:
            query = query.filter_by(status=status)
        return query.all()

    @staticmethod
    def confirm_order(order_id: int, user_id: int | None = None) -> Order:
        order = db.session.get(Order, order_id)
        if not order:
            raise InventoryError(f"Pedido {order_id} no encontrado")
        if order.status != Order.STATUS_DRAFT:
            raise InvalidOrderStateError(order_id, order.status, "confirm")

        try:
            for line in order.lines:
                InventoryService.reserve_stock(
                    line.variant_id,
                    line.quantity,
                    reference_type="order",
                    reference_id=order.id,
                    user_id=user_id,
                )
            order.status = Order.STATUS_CONFIRMED
            OrderService._audit_order(
                order,
                "order.confirm",
                f"Pedido confirmado: {order.order_number}",
                user_id=user_id,
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return order

    @staticmethod
    def fulfill_order(order_id: int, user_id: int | None = None) -> Order:
        order = db.session.get(Order, order_id)
        if not order:
            raise InventoryError(f"Pedido {order_id} no encontrado")
        if order.status != Order.STATUS_CONFIRMED:
            raise InvalidOrderStateError(order_id, order.status, "fulfill")

        try:
            for line in order.lines:
                InventoryService.commit_sale(
                    line.variant_id,
                    line.quantity,
                    reference_type="order",
                    reference_id=order.id,
                    user_id=user_id,
                )
            order.status = Order.STATUS_FULFILLED
            OrderService._audit_order(
                order,
                "order.fulfill",
                f"Pedido entregado: {order.order_number}",
                user_id=user_id,
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return order

    @staticmethod
    def cancel_order(order_id: int, user_id: int | None = None) -> Order:
        order = db.session.get(Order, order_id)
        if not order:
            raise InventoryError(f"Pedido {order_id} no encontrado")
        if order.status == Order.STATUS_FULFILLED:
            raise InvalidOrderStateError(order_id, order.status, "cancel")
        if order.status == Order.STATUS_CANCELLED:
            return order

        try:
            if order.status == Order.STATUS_CONFIRMED:
                for line in order.lines:
                    InventoryService.release_reservation(
                        line.variant_id,
                        line.quantity,
                        reference_type="order",
                        reference_id=order.id,
                        user_id=user_id,
                    )
            order.status = Order.STATUS_CANCELLED
            OrderService._audit_order(
                order,
                "order.cancel",
                f"Pedido cancelado: {order.order_number}",
                user_id=user_id,
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return order
