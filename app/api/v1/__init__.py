from datetime import date

from flask import Blueprint, g, jsonify, request

from app.api.v1.auth import api_key_required
from app.models import Order
from app.services import InventoryService, OrderService, ProductService
from app.services.exceptions import InvalidOrderStateError, InventoryError
from app.services.order_service import CustomerInput, OrderLineInput, PaymentInput

bp = Blueprint("api_v1", __name__)


def _variant_to_dict(variant):
    inv = variant.inventory_item
    return {
        "id": variant.id,
        "sku": variant.sku,
        "product_name": variant.product.name,
        "attributes": variant.attributes,
        "price_cents": variant.price_cents,
        "available": inv.quantity_available if inv else 0,
    }


def _order_to_dict(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "source": order.source,
        "client_id": order.client_id,
        "customer": {
            "name": order.customer_name,
            "phone": order.customer_phone,
            "email": order.customer_email,
        },
        "payment": {
            "status": order.payment_status,
            "method": order.payment_method,
            "amount_paid_cents": order.amount_paid_cents,
            "balance_due_cents": order.balance_due_cents,
            "reference": order.payment_reference,
        },
        "lines": [
            {
                "sku": line.variant.sku,
                "quantity": line.quantity,
                "unit_price_cents": line.unit_price_cents,
            }
            for line in order.lines
        ],
        "total_cents": order.total_cents,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "external_id": order.external_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@bp.route("/products")
@api_key_required("read")
def list_products():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)
    products = ProductService.list_products()
    variants = []
    for product in products:
        for variant in product.variants:
            variants.append(_variant_to_dict(variant))

    start = (page - 1) * per_page
    end = start + per_page
    return jsonify(
        {
            "data": variants[start:end],
            "page": page,
            "per_page": per_page,
            "total": len(variants),
        }
    )


@bp.route("/inventory")
@api_key_required("read")
def list_inventory():
    items = InventoryService.list_inventory()
    return jsonify(
        {
            "data": [
                {
                    "sku": item.variant.sku,
                    "product_name": item.variant.product.name,
                    "quantity_on_hand": item.quantity_on_hand,
                    "quantity_reserved": item.quantity_reserved,
                    "quantity_available": item.quantity_available,
                    "reorder_point": item.reorder_point,
                }
                for item in items
            ]
        }
    )


@bp.route("/inventory/<sku>")
@api_key_required("read")
def get_inventory_by_sku(sku):
    item = InventoryService.get_inventory_by_sku(sku.upper())
    if not item:
        return jsonify({"error": "SKU not found"}), 404
    return jsonify(
        {
            "sku": item.variant.sku,
            "quantity_on_hand": item.quantity_on_hand,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available,
        }
    )


@bp.route("/orders", methods=["POST"])
@api_key_required("write")
def create_order():
    data = request.get_json(silent=True) or {}
    lines_data = data.get("lines", [])
    if not lines_data:
        return jsonify({"error": "lines required"}), 400

    try:
        lines = [
            OrderLineInput(
                sku=line.get("sku", "").upper() if line.get("sku") else None,
                variant_id=line.get("variant_id"),
                quantity=int(line.get("quantity", 1)),
            )
            for line in lines_data
        ]
        customer_data = data.get("customer", {})
        payment_data = data.get("payment", {})
        delivery_raw = data.get("delivery_date")
        delivery_date = date.fromisoformat(delivery_raw) if delivery_raw else None
        order = OrderService.create_order(
            lines=lines,
            customer=CustomerInput(
                name=customer_data.get("name"),
                phone=customer_data.get("phone"),
                email=customer_data.get("email"),
            ),
            client_id=data.get("client_id"),
            payment=PaymentInput(
                payment_method=payment_data.get("method"),
                amount_paid_cents=int(payment_data.get("amount_paid_cents", 0)),
                payment_reference=payment_data.get("reference"),
                payment_notes=payment_data.get("notes"),
            ),
            source=data.get("source", Order.SOURCE_API),
            external_id=data.get("external_id"),
            api_client_id=g.api_client.id,
            notes=data.get("notes"),
            delivery_date=delivery_date,
            auto_confirm=data.get("auto_confirm", False),
        )
        return jsonify(_order_to_dict(order)), 201
    except (InventoryError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/orders/<int:order_id>")
@api_key_required("read")
def get_order(order_id):
    order = OrderService.get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(_order_to_dict(order))


@bp.route("/orders/<int:order_id>/confirm", methods=["PATCH"])
@api_key_required("write")
def confirm_order(order_id):
    try:
        order = OrderService.confirm_order(order_id)
        return jsonify(_order_to_dict(order))
    except (InvalidOrderStateError, InventoryError) as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/orders/<int:order_id>/fulfill", methods=["PATCH"])
@api_key_required("write")
def fulfill_order(order_id):
    try:
        order = OrderService.fulfill_order(order_id)
        return jsonify(_order_to_dict(order))
    except (InvalidOrderStateError, InventoryError) as exc:
        return jsonify({"error": str(exc)}), 400
