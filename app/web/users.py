from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.services import UserService
from app.services.exceptions import InventoryError
from app.web.decorators import admin_required

bp = Blueprint("web_users", __name__, url_prefix="/users")


@bp.route("/")
@admin_required
def list_users():
    users = UserService.list_users()
    pending_count = UserService.count_pending()
    return render_template(
        "users/list.html",
        users=users,
        pending_count=pending_count,
    )


@bp.route("/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve(user_id):
    try:
        user = UserService.approve_user(user_id, actor_id=current_user.id)
        flash(f"Usuario {user.name} habilitado.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_users.list_users"))


@bp.route("/<int:user_id>/revoke", methods=["POST"])
@admin_required
def revoke(user_id):
    try:
        user = UserService.revoke_user(user_id, actor_id=current_user.id)
        flash(f"Usuario {user.name} deshabilitado.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_users.list_users"))


@bp.route("/<int:user_id>/role", methods=["POST"])
@admin_required
def set_role(user_id):
    role = request.form.get("role", "").strip()
    try:
        user = UserService.set_role(user_id, role, actor_id=current_user.id)
        flash(f"Rol de {user.name} actualizado.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_users.list_users"))
