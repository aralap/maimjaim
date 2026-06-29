from flask import has_request_context, request

from app.extensions import db
from app.models import ActivityLog


class AuditService:
    @staticmethod
    def log(
        action: str,
        entity_type: str,
        summary: str,
        *,
        entity_id: int | None = None,
        user_id: int | None = None,
        details: dict | None = None,
    ) -> ActivityLog:
        ip_address = None
        if has_request_context():
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip_address and "," in ip_address:
                ip_address = ip_address.split(",")[0].strip()

        entry = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            details=details or {},
            ip_address=ip_address,
        )
        db.session.add(entry)
        db.session.flush()
        return entry

    @staticmethod
    def list_logs(
        *,
        limit: int = 100,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> list[ActivityLog]:
        query = ActivityLog.query.order_by(ActivityLog.created_at.desc())
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        if action:
            query = query.filter_by(action=action)
        return query.limit(limit).all()

    @staticmethod
    def user_snapshot(user) -> dict | None:
        if not user:
            return None
        return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
