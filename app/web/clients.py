from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.labels import PAYMENT_METHOD_CHOICES
from app.services import ClientService
from app.services.exceptions import InventoryError
from app.web.decorators import approved_required

bp = Blueprint("web_clients", __name__, url_prefix="/clients")


@bp.route("/")
@approved_required
def list_clients():
    clients = ClientService.list_clients(active_only=False)
    return render_template("clients/list.html", clients=clients)


@bp.route("/new", methods=["GET", "POST"])
@approved_required
def new_client():
    if request.method == "POST":
        try:
            client = ClientService.create_client(
                name=request.form["name"],
                email=request.form.get("email") or None,
                phone=request.form.get("phone") or None,
                address=request.form.get("address") or None,
                city=request.form.get("city") or None,
                tax_id=request.form.get("tax_id") or None,
                notes=request.form.get("notes") or None,
                preferred_payment_method=request.form.get("preferred_payment_method") or None,
                user_id=current_user.id,
            )
            flash(f"Cliente {client.name} creado.", "success")
            next_url = request.form.get("next") or url_for("web_clients.detail", client_id=client.id)
            return redirect(next_url)
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template(
        "clients/form.html",
        client=None,
        payment_methods=PAYMENT_METHOD_CHOICES,
        form_action=url_for("web_clients.new_client"),
        title="Nuevo cliente",
    )


@bp.route("/<int:client_id>")
@approved_required
def detail(client_id):
    from app.models import Order

    client = ClientService.get_client(client_id)
    if not client:
        flash("Cliente no encontrado.", "error")
        return redirect(url_for("web_clients.list_clients"))
    orders = (
        Order.query.filter_by(client_id=client.id)
        .order_by(Order.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("clients/detail.html", client=client, orders=orders)


@bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
@approved_required
def edit_client(client_id):
    client = ClientService.get_client(client_id)
    if not client:
        flash("Cliente no encontrado.", "error")
        return redirect(url_for("web_clients.list_clients"))

    if request.method == "POST":
        try:
            ClientService.update_client(
                client_id,
                user_id=current_user.id,
                name=request.form["name"],
                email=request.form.get("email") or None,
                phone=request.form.get("phone") or None,
                address=request.form.get("address") or None,
                city=request.form.get("city") or None,
                tax_id=request.form.get("tax_id") or None,
                notes=request.form.get("notes") or None,
                preferred_payment_method=request.form.get("preferred_payment_method") or None,
                is_active=request.form.get("is_active") == "on",
            )
            flash("Cliente actualizado.", "success")
            return redirect(url_for("web_clients.detail", client_id=client_id))
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template(
        "clients/form.html",
        client=client,
        payment_methods=PAYMENT_METHOD_CHOICES,
        form_action=url_for("web_clients.edit_client", client_id=client_id),
        title="Editar cliente",
    )
