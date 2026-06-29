from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.models import InventoryMovement
from app.services import InventoryService
from app.services.exceptions import InsufficientStockError, InventoryError
from app.web.decorators import admin_required, approved_required

bp = Blueprint("web_inventory", __name__, url_prefix="/inventory")


@bp.route("/")
@approved_required
def list_inventory():
    items = InventoryService.list_inventory()
    return render_template("inventory/list.html", items=items)


@bp.route("/movements")
@approved_required
def movements():
    limit = request.args.get("limit", 100, type=int)
    movements_list = InventoryService.list_movements(limit=limit)
    return render_template("inventory/movements.html", movements=movements_list)


@bp.route("/<int:variant_id>/receive", methods=["POST"])
@admin_required
def receive(variant_id):
    try:
        qty = int(request.form["quantity"])
        note = request.form.get("note")
        InventoryService.receive_stock(variant_id, qty, note=note, user_id=current_user.id)
        flash("Stock ingresado.", "success")
    except (InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_inventory.list_inventory"))


@bp.route("/<int:variant_id>/adjust", methods=["POST"])
@admin_required
def adjust(variant_id):
    try:
        qty = int(request.form["quantity"])
        note = request.form.get("note")
        InventoryService.adjust_stock(
            variant_id,
            qty,
            reason=InventoryMovement.REASON_ADJUSTMENT,
            note=note,
            user_id=current_user.id,
        )
        if request.headers.get("HX-Request"):
            from app.services import ProductService

            variant = ProductService.get_variant(variant_id)
            return render_template(
                "inventory/_row.html",
                item=variant.inventory_item,
            )
        flash("Stock ajustado.", "success")
    except (InsufficientStockError, InventoryError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_inventory.list_inventory"))
