"""Administrative resets that never delete catalog or client records."""

from sqlalchemy import select, text

from app.extensions import db
from app.models import InventoryItem, InventoryMovement, Order, OrderLine
from app.services.audit_service import AuditService
from app.services.exceptions import InventoryError
from app.services.inventory_service import InventoryService


class MaintenanceService:
    SCOPES = {"stock", "sales", "all"}

    @staticmethod
    def _lock_tables():
        # Serialize maintenance against normal writes, including new orders.
        # Both databases supported by the application are covered here.
        connection = db.session.connection()
        if connection.dialect.name == "postgresql":
            db.session.execute(text(
                "LOCK TABLE orders, order_lines, inventory_items, inventory_movements "
                "IN EXCLUSIVE MODE"
            ))
        elif connection.dialect.name == "sqlite":
            if not connection.connection.driver_connection.in_transaction:
                db.session.execute(text("BEGIN IMMEDIATE"))

    @staticmethod
    def _inventory():
        return db.session.execute(
            select(InventoryItem).order_by(InventoryItem.variant_id).with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()

    @staticmethod
    def _require_admin(user_id):
        from app.models import User

        user = db.session.get(User, user_id) if user_id else None
        if not user or not user.is_active or not user.is_admin():
            raise InventoryError("Esta acción requiere un administrador habilitado.")

    @staticmethod
    def _validate(confirmation, expected, reason):
        if (confirmation or "").strip() != expected:
            raise InventoryError(f"Escribí {expected} para confirmar la operación.")
        reason = (reason or "").strip()
        if not reason or len(reason) > 500:
            raise InventoryError("Indicá un motivo de entre 1 y 500 caracteres.")
        return reason

    @staticmethod
    def reset(scope, *, confirmation, reason, user_id):
        if scope not in MaintenanceService.SCOPES:
            raise InventoryError("Seleccioná una opción de restablecimiento válida.")
        reason = MaintenanceService._validate(confirmation, "RESTABLECER", reason)
        try:
            MaintenanceService._require_admin(user_id)
            MaintenanceService._lock_tables()
            items = MaintenanceService._inventory()
            if scope == "stock" and (
                any(item.quantity_reserved for item in items)
                or Order.query.filter_by(status=Order.STATUS_CONFIRMED).count()
            ):
                raise InventoryError(
                    "Hay pedidos confirmados o stock reservado. Cancelá o entregá esos "
                    "pedidos, o elegí restablecer stock y ventas juntos."
                )

            deleted_orders = 0
            released_units = 0
            stock_units = 0
            changed_items = 0
            if scope in {"sales", "all"}:
                # Keep the ledger readable without leaving links to deleted orders.
                InventoryMovement.query.filter_by(reference_type="order").update(
                    {"reference_type": "deleted_order"}, synchronize_session="fetch"
                )
                OrderLine.query.delete(synchronize_session="fetch")
                deleted_orders = Order.query.delete(synchronize_session="fetch")

            for item in items:
                on_hand, reserved = item.quantity_on_hand, item.quantity_reserved
                if scope in {"sales", "all"} and reserved:
                    item.quantity_reserved = 0
                    released_units += reserved
                    InventoryService._record_movement(
                        item.variant_id, reserved, InventoryMovement.REASON_RELEASE,
                        reference_type="maintenance", note=reason, user_id=user_id,
                    )
                if scope in {"stock", "all"}:
                    item.quantity_on_hand = 0
                    stock_units += on_hand
                    if on_hand:
                        InventoryService._record_movement(
                            item.variant_id, -on_hand, InventoryMovement.REASON_ADJUSTMENT,
                            reference_type="maintenance", note=f"Stock a cero: {reason}",
                            user_id=user_id,
                        )
                if (on_hand, reserved) != (item.quantity_on_hand, item.quantity_reserved):
                    changed_items += 1

            details = {
                "scope": scope, "reason": reason, "deleted_orders": deleted_orders,
                "released_units": released_units, "stock_units_removed": stock_units,
                "changed_items": changed_items,
            }
            AuditService.log(
                f"maintenance.reset.{scope}", "maintenance",
                "Restablecimiento administrativo: " + {"stock": "stock", "sales": "pedidos y ventas", "all": "stock, pedidos y ventas"}[scope],
                user_id=user_id, details=details,
            )
            db.session.commit()
            # Bulk deletes must not leave loaded Client.orders / Order.lines stale.
            db.session.expire_all()
            return details
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def delete_order(order_id, *, confirmation, reason, user_id):
        """Remove a sale record, releasing reservations; physical stock stays put."""
        try:
            MaintenanceService._require_admin(user_id)
            MaintenanceService._lock_tables()
            order = db.session.get(Order, order_id, populate_existing=True)
            if not order:
                raise InventoryError("Pedido no encontrado.")
            reason = MaintenanceService._validate(confirmation, order.order_number, reason)
            # Use the same inventory lock order as bulk maintenance.
            items = {item.variant_id: item for item in MaintenanceService._inventory()}
            if order.status == Order.STATUS_CONFIRMED:
                for line in order.lines:
                    item = items.get(line.variant_id)
                    if not item or item.quantity_reserved < line.quantity:
                        raise InventoryError("Las reservas del pedido no coinciden con el inventario.")
                    item.quantity_reserved -= line.quantity
                    InventoryService._record_movement(
                        line.variant_id, line.quantity, InventoryMovement.REASON_RELEASE,
                        reference_type="deleted_order", reference_id=order.id,
                        note=f"Pedido eliminado: {reason}", user_id=user_id,
                    )
            InventoryMovement.query.filter_by(reference_type="order", reference_id=order.id).update(
                {"reference_type": "deleted_order"}, synchronize_session="fetch"
            )
            AuditService.log(
                "order.delete", "order", f"Pedido eliminado: {order.order_number}",
                entity_id=order.id, user_id=user_id,
                details={"order_number": order.order_number, "status": order.status,
                         "total_cents": order.total_cents, "reason": reason},
            )
            db.session.delete(order)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
