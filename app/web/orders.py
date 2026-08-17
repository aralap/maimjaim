from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.labels import PAYMENT_METHOD_CHOICES
from app.money import optional_pesos_to_cents
from app.models import Order, OrderLine
from app.services import ClientService, OrderService, ProductService, WeekSheetService
from app.services.exceptions import InvalidOrderStateError, InventoryError
from app.services.order_service import OrderLineInput, PaymentInput
from app.week import parse_week_start
from app.web.decorators import approved_required

bp = Blueprint("web_orders", __name__, url_prefix="/orders")


def _parse_cart_lines(form) -> list[OrderLineInput]:
    variant_ids = form.getlist("variant_id")
    quantities = form.getlist("quantity")
    price_types = form.getlist("price_type")
    custom_prices = form.getlist("custom_price")
    lines = []
    for index, (variant_id, qty) in enumerate(zip(variant_ids, quantities)):
        if not variant_id:
            continue
        quantity = int(qty)
        if quantity <= 0:
            continue
        price_type = price_types[index] if index < len(price_types) else OrderLine.PRICE_RETAIL
        custom_raw = custom_prices[index] if index < len(custom_prices) else None
        custom_cents = optional_pesos_to_cents(custom_raw)
        lines.append(
            OrderLineInput(
                variant_id=int(variant_id),
                quantity=quantity,
                price_type=price_type or OrderLine.PRICE_RETAIL,
                unit_price_cents=custom_cents,
            )
        )
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


def _active_variants():
    variants = []
    for product in ProductService.list_products():
        variants.extend(product.variants)
    return variants


def _variant_prices(variants) -> dict:
    return {
        str(variant.id): {
            "price": f"{variant.price_cents / 100:.2f}",
            "wholesale": (
                f"{variant.wholesale_price_cents / 100:.2f}"
                if variant.wholesale_price_cents is not None
                else None
            ),
        }
        for variant in variants
    }


def _parse_single_line(form) -> OrderLineInput:
    lines = _parse_cart_lines(form)
    if not lines:
        raise InventoryError("Elegí un producto y una cantidad")
    return lines[0]


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


def _week_redirect(week_start):
    return redirect(url_for("web_orders.week_sheet", week=week_start.isoformat()))


@bp.route("/planilla")
@approved_required
def week_sheet():
    monday = parse_week_start(request.args.get("week"))
    board = WeekSheetService.board(monday)
    return render_template("orders/week_sheet.html", **board)


@bp.route("/planilla/clients", methods=["POST"])
@approved_required
def week_sheet_add_client():
    monday = parse_week_start(request.form.get("week"))
    try:
        client_id = int(request.form.get("client_id") or 0)
        if not client_id:
            raise InventoryError("Elegí un cliente")
        WeekSheetService.add_client_row(client_id, monday, user_id=current_user.id)
        flash("Cliente agregado a la planilla.", "success")
    except (InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/remove", methods=["POST"])
@approved_required
def week_sheet_remove_client(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        WeekSheetService.drop_client_row(order_id, user_id=current_user.id)
        flash("Fila quitada.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/confirm", methods=["POST"])
@approved_required
def week_sheet_confirm(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        order = OrderService.confirm_order(order_id, user_id=current_user.id)
        flash(f"Pedido {order.order_number} confirmado.", "success")
    except (InvalidOrderStateError, InventoryError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/paid", methods=["POST"])
@approved_required
def week_sheet_mark_paid(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        order = OrderService.get_order(order_id)
        if not order:
            raise InventoryError("Pedido no encontrado")
        OrderService.update_payment(
            order_id,
            PaymentInput(
                payment_method=order.payment_method or "cash",
                amount_paid_cents=order.total_cents,
            ),
            user_id=current_user.id,
        )
        flash(f"Pedido {order.order_number} marcado como pagado.", "success")
    except (InventoryError, InvalidOrderStateError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/fulfill", methods=["POST"])
@approved_required
def week_sheet_fulfill(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        order = OrderService.fulfill_order(order_id, user_id=current_user.id)
        flash(f"Pedido {order.order_number} entregado.", "success")
    except (InvalidOrderStateError, InventoryError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/columns", methods=["POST"])
@approved_required
def week_sheet_add_column():
    monday = parse_week_start(request.form.get("week"))
    try:
        variant_id = int(request.form.get("variant_id") or 0)
        if not variant_id:
            raise InventoryError("Elegí un producto")
        WeekSheetService.add_column(variant_id)
        flash("Columna agregada.", "success")
    except (InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/columns/<int:column_id>/remove", methods=["POST"])
@approved_required
def week_sheet_remove_column(column_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        WeekSheetService.remove_column(column_id)
        flash("Columna quitada.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/qty", methods=["POST"])
@approved_required
def week_sheet_set_qty(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        variant_id = int(request.form["variant_id"])
        delta = int(request.form.get("delta") or 0)
        order = OrderService.get_order(order_id)
        if not order:
            raise InventoryError("Pedido no encontrado")
        current = next((line.quantity for line in order.lines if line.variant_id == variant_id), 0)
        raw_qty = request.form.get("quantity")
        if raw_qty not in (None, ""):
            quantity = int(raw_qty)
        else:
            quantity = max(0, current + delta)
        OrderService.set_line_quantity_by_variant(
            order_id, variant_id, quantity, user_id=current_user.id
        )
    except (InventoryError, InvalidOrderStateError, ValueError, KeyError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/toggle-raw", methods=["POST"])
@approved_required
def week_sheet_toggle_raw(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        variant_id = int(request.form["variant_id"])
        WeekSheetService.toggle_produce_kind(order_id, variant_id, user_id=current_user.id)
    except (InventoryError, InvalidOrderStateError, ValueError, KeyError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/price-type", methods=["POST"])
@approved_required
def week_sheet_set_price_type(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        OrderService.set_order_price_type(
            order_id,
            request.form.get("price_type") or Order.PRICE_RETAIL,
            user_id=current_user.id,
        )
    except (InventoryError, InvalidOrderStateError, ValueError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/planilla/<int:order_id>/delivery", methods=["POST"])
@approved_required
def week_sheet_set_delivery(order_id):
    monday = parse_week_start(request.form.get("week"))
    try:
        OrderService.update_delivery_date(
            order_id,
            _parse_delivery_date(request.form),
            user_id=current_user.id,
        )
    except (InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return _week_redirect(monday)


@bp.route("/new", methods=["GET", "POST"])
@approved_required
def new_order():
    variants = _active_variants()
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

    variant_prices = _variant_prices(variants)
    return render_template(
        "orders/new.html",
        variants=variants,
        variant_prices=variant_prices,
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
    variants = _active_variants() if order.status == "draft" else []
    return render_template(
        "orders/detail.html",
        order=order,
        payment_methods=PAYMENT_METHOD_CHOICES,
        variants=variants,
        variant_prices=_variant_prices(variants),
    )


@bp.route("/<int:order_id>/lines", methods=["POST"])
@approved_required
def add_line(order_id):
    try:
        OrderService.add_line(order_id, _parse_single_line(request.form), user_id=current_user.id)
        flash("Artículo agregado.", "success")
    except (InventoryError, InvalidOrderStateError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/lines/<int:line_id>/quantity", methods=["POST"])
@approved_required
def update_line_quantity(order_id, line_id):
    try:
        quantity = int(request.form.get("quantity", 0) or 0)
        if quantity <= 0:
            OrderService.remove_line(order_id, line_id, user_id=current_user.id)
            flash("Artículo quitado.", "success")
        else:
            OrderService.update_line_quantity(
                order_id, line_id, quantity, user_id=current_user.id
            )
            flash("Cantidad actualizada.", "success")
    except (InventoryError, InvalidOrderStateError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/lines/<int:line_id>/remove", methods=["POST"])
@approved_required
def remove_line(order_id, line_id):
    try:
        OrderService.remove_line(order_id, line_id, user_id=current_user.id)
        flash("Artículo quitado.", "success")
    except (InventoryError, InvalidOrderStateError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/lines/<int:line_id>/price", methods=["POST"])
@approved_required
def update_line_price(order_id, line_id):
    try:
        price_type = request.form.get("price_type") or OrderLine.PRICE_RETAIL
        custom_cents = optional_pesos_to_cents(request.form.get("custom_price"))
        OrderService.update_line_price(
            order_id,
            line_id,
            price_type=price_type,
            unit_price_cents=custom_cents,
            user_id=current_user.id,
        )
        flash("Precio actualizado.", "success")
    except (InventoryError, InvalidOrderStateError, ValueError) as exc:
        flash(str(exc), "error")
    if request.form.get("week"):
        return _week_redirect(parse_week_start(request.form.get("week")))
    return redirect(url_for("web_orders.detail", order_id=order_id))


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
