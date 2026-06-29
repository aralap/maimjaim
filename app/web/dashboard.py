from flask import Blueprint, render_template

from app.models import Order
from app.services import InventoryService, OrderService
from app.web.decorators import approved_required

bp = Blueprint("web_dashboard", __name__)


@bp.route("/")
@bp.route("/dashboard")
@approved_required
def index():
    open_orders = OrderService.list_orders(status=Order.STATUS_CONFIRMED)
    draft_orders = OrderService.list_orders(status=Order.STATUS_DRAFT)
    low_stock = InventoryService.list_low_stock()
    recent_movements = InventoryService.list_movements(limit=10)
    return render_template(
        "dashboard/index.html",
        open_orders=open_orders,
        draft_orders=draft_orders,
        low_stock=low_stock,
        recent_movements=recent_movements,
    )


@bp.route("/health")
def health():
    return {"status": "ok"}
