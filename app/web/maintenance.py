from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Client, InventoryItem, Order, Product, ProductVariant
from app.services.exceptions import InventoryError
from app.services.maintenance_service import MaintenanceService
from app.web.decorators import admin_required

bp = Blueprint("web_maintenance", __name__, url_prefix="/admin/maintenance")


def _render_index(status=200):
    items = InventoryItem.query.all()
    return render_template(
        "maintenance/index.html",
        counts={"products": Product.query.count(), "variants": ProductVariant.query.count(),
                "clients": Client.query.count(), "orders": Order.query.count(),
                "stock": sum(item.quantity_on_hand for item in items),
                "reserved": sum(item.quantity_reserved for item in items)},
        selected=request.form.get("scope", "stock"),
    ), status


@bp.get("/")
@admin_required
def index():
    return _render_index()


@bp.post("/reset")
@admin_required
def reset():
    try:
        MaintenanceService.reset(
            request.form.get("scope"), confirmation=request.form.get("confirmation"),
            reason=request.form.get("reason"), user_id=current_user.id,
        )
    except InventoryError as exc:
        flash(str(exc), "error")
        return _render_index(400)
    flash("Restablecimiento completado. Las fichas de productos y los clientes se conservaron.", "success")
    return redirect(url_for("web_maintenance.index"))


@bp.route("/orders/<int:order_id>/delete", methods=["GET", "POST"])
@admin_required
def delete_order(order_id):
    order = db.get_or_404(Order, order_id)
    if request.method == "POST":
        try:
            MaintenanceService.delete_order(
                order.id, confirmation=request.form.get("confirmation"),
                reason=request.form.get("reason"), user_id=current_user.id,
            )
        except InventoryError as exc:
            flash(str(exc), "error")
            return render_template("maintenance/delete_order.html", order=order), 400
        flash("Pedido eliminado. El cliente y los productos se conservaron.", "success")
        return redirect(url_for("web_orders.list_orders"))
    return render_template("maintenance/delete_order.html", order=order)
