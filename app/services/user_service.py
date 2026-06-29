from app.extensions import db
from app.models import User
from app.services.audit_service import AuditService
from app.services.exceptions import InventoryError


class UserService:
    @staticmethod
    def list_users() -> list[User]:
        return User.query.order_by(User.created_at.desc()).all()

    @staticmethod
    def get_user(user_id: int) -> User | None:
        return db.session.get(User, user_id)

    @staticmethod
    def approve_user(user_id: int, *, actor_id: int | None = None) -> User:
        user = db.session.get(User, user_id)
        if not user:
            raise InventoryError(f"Usuario {user_id} no encontrado")
        user.is_active = True
        AuditService.log(
            "user.approve",
            "user",
            f"Usuario habilitado: {user.name}",
            entity_id=user.id,
            user_id=actor_id,
            details={"email": user.email, "role": user.role},
        )
        db.session.commit()
        return user

    @staticmethod
    def revoke_user(user_id: int, *, actor_id: int | None = None) -> User:
        user = db.session.get(User, user_id)
        if not user:
            raise InventoryError(f"Usuario {user_id} no encontrado")
        if actor_id and user.id == actor_id:
            raise InventoryError("No podés deshabilitar tu propia cuenta")
        user.is_active = False
        AuditService.log(
            "user.revoke",
            "user",
            f"Usuario deshabilitado: {user.name}",
            entity_id=user.id,
            user_id=actor_id,
            details={"email": user.email, "role": user.role},
        )
        db.session.commit()
        return user

    @staticmethod
    def set_role(user_id: int, role: str, *, actor_id: int | None = None) -> User:
        if role not in ("admin", "staff"):
            raise InventoryError("Rol inválido")
        user = db.session.get(User, user_id)
        if not user:
            raise InventoryError(f"Usuario {user_id} no encontrado")
        if actor_id and user.id == actor_id and role != "admin":
            raise InventoryError("No podés quitarte el rol de administrador")
        before = user.role
        user.role = role
        AuditService.log(
            "user.role.update",
            "user",
            f"Rol actualizado: {user.name} → {role}",
            entity_id=user.id,
            user_id=actor_id,
            details={"email": user.email, "role_before": before, "role_after": role},
        )
        db.session.commit()
        return user

    @staticmethod
    def count_pending() -> int:
        return User.query.filter_by(is_active=False).count()
