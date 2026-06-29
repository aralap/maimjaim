from flask import Blueprint, render_template, request

from app.services import AuditService
from app.web.decorators import admin_required

bp = Blueprint("web_logs", __name__, url_prefix="/logs")


@bp.route("/")
@admin_required
def list_logs():
    entity_type = request.args.get("entity_type") or None
    action = request.args.get("action") or None
    limit = request.args.get("limit", 100, type=int)
    logs = AuditService.list_logs(limit=limit, entity_type=entity_type, action=action)
    return render_template(
        "logs/list.html",
        logs=logs,
        current_entity_type=entity_type,
        current_action=action,
    )
