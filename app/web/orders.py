from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.labels import PAYMENT_METHOD_CHOICES
from app.services import ClientService, OrderService, ProductService
from app.services.exceptions import InvalidOrderStateError, InventoryError
from app.services.order_service import OrderLineInput, PaymentInput
from app.web.decorators import approved_required

bp = Blueprint("web_orders", __name__, url_prefix="/orders")


def _parse_cart_lines(form) -> list[OrderLineInput]:
    variant_ids = form.getlist("variant_id")
    quantities = form.getlist("quantity")
    lines = []
    for variant_id, qty in zip(variant_ids, quantities):
        if not variant_id:
            continue
        quantity = int(qty)
        if quantity <= 0:
            continue
        lines.append(OrderLineInput(variant_id=int(variant_id), quantity=quantity))
    return lines


def _parse_payment(form) -> PaymentInput:
    amount = form.get("amount_paid", "0").strip()
    amount_cents = int(float(amount or 0) * 100)
    return PaymentInput(
        payment_method=form.get("payment_method") or None,
        amount_paid_cents=amount_cents,
        payment_reference=form.get("payment_reference") or None,
        payment_notes=form.get("payment_notes") or None,
    )


def _parse_delivery_date(form) -> date | None:
    raw = form.get("delivery_date", "").strip()
    if not raw:
        return None
    return date.fromisoformat(raw)


@bp.route("/")
@approved_required
def list_orders():
    status = request.args.get("status")
    orders = OrderService.list_orders(status=status)
    return render_template("orders/list.html", orders=orders, current_status=status)


@bp.route("/planificacion")
@approved_required
def procurement_plan():
    days = request.args.get("days", 7, type=int)
    plan = OrderService.get_procurement_plan(days=days)
    return render_template("orders/procurement.html", plan=plan)


@bp.route("/new", methods=["GET", "POST"])
@approved_required
def new_order():
    variants = []
    for product in ProductService.list_products():
        variants.extend(product.variants)
    clients = ClientService.list_clients()

    if request.method == "POST":
        try:
            lines = _parse_cart_lines(request.form)
            if not lines:
                raise InventoryError("Agregá al menos un artículo al pedido")

            client_id = request.form.get("client_id")
            client_id = int(client_id) if client_id else None

            order = OrderService.create_order(
                lines=lines,
                client_id=client_id,
                payment=_parse_payment(request.form),
                notes=request.form.get("notes") or None,
                delivery_date=_parse_delivery_date(request.form),
                user_id=current_user.id,
            )
            flash(f"Pedido {order.order_number} creado.", "success")
            return redirect(url_for("web_orders.detail", order_id=order.id))
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template(
        "orders/new.html",
        variants=variants,
        clients=clients,
        payment_methods=PAYMENT_METHOD_CHOICES,
    )


@bp.route("/<int:order_id>")
@approved_required
def detail(order_id):
    order = OrderService.get_order(order_id)
    if not order:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("web_orders.list_orders"))
    return render_template(
        "orders/detail.html",
        order=order,
        payment_methods=PAYMENT_METHOD_CHOICES,
    )


@bp.route("/<int:order_id>/delivery", methods=["POST"])
@approved_required
def update_delivery(order_id):
    try:
        delivery_date = _parse_delivery_date(request.form)
        order = OrderService.update_delivery_date(order_id, delivery_date, user_id=current_user.id)
        flash("Fecha de entrega actualizada.", "success")
        if request.headers.get("HX-Request"):
            return render_template("orders/_delivery_date.html", order=order)
    except (InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/payment", methods=["POST"])
@approved_required
def update_payment(order_id):
    try:
        order = OrderService.update_payment(order_id, _parse_payment(request.form), user_id=current_user.id)
        flash("Pago actualizado.", "success")
        if request.headers.get("HX-Request"):
            return render_template(
                "orders/_payment_section.html",
                order=order,
                payment_methods=PAYMENT_METHOD_CHOICES,
            )
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/confirm", methods=["POST"])
@approved_required
def confirm(order_id):
    try:
        order = OrderService.confirm_order(order_id, user_id=current_user.id)
        if request.headers.get("HX-Request"):
            return render_template("orders/_status_badge.html", order=order)
        flash(f"Pedido {order.order_number} confirmado.", "success")
    except (InvalidOrderStateError, InventoryError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/fulfill", methods=["POST"])
@approved_required
def fulfill(order_id):
    try:
        order = OrderService.fulfill_order(order_id, user_id=current_user.id)
        if request.headers.get("HX-Request"):
            return render_template("orders/_status_badge.html", order=order)
        flash(f"Pedido {order.order_number} entregado.", "success")
    except (InvalidOrderStateError, InventoryError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@approved_required
def cancel(order_id):
    try:
        order = OrderService.cancel_order(order_id, user_id=current_user.id)
        if request.headers.get("HX-Request"):
            return render_template("orders/_status_badge.html", order=order)
        flash(f"Pedido {order.order_number} cancelado.", "success")
    except (InvalidOrderStateError, InventoryError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))
