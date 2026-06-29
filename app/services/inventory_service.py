from sqlalchemy import select

from app.extensions import db
from app.models import InventoryItem, InventoryMovement, ProductVariant
from app.services.audit_service import AuditService
from app.services.exceptions import InsufficientStockError, InventoryError


class InventoryService:
    @staticmethod
    def _lock_inventory(variant_id: int) -> InventoryItem:
        item = db.session.execute(
            select(InventoryItem)
            .where(InventoryItem.variant_id == variant_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not item:
            raise InventoryError(f"No inventory record for variant {variant_id}")
        return item

    @staticmethod
    def _record_movement(
        variant_id: int,
        delta: int,
        reason: str,
        *,
        reference_type: str | None = None,
        reference_id: int | None = None,
        note: str | None = None,
        user_id: int | None = None,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            variant_id=variant_id,
            delta=delta,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by_id=user_id,
        )
        db.session.add(movement)
        return movement

    @staticmethod
    def get_availability(variant_id: int) -> int:
        item = InventoryItem.query.filter_by(variant_id=variant_id).first()
        if not item:
            return 0
        return item.quantity_available

    @staticmethod
    def receive_stock(
        variant_id: int,
        qty: int,
        note: str | None = None,
        user_id: int | None = None,
    ) -> InventoryItem:
        if qty <= 0:
            raise InventoryError("Receive quantity must be positive")

        item = InventoryService._lock_inventory(variant_id)
        item.quantity_on_hand += qty
        InventoryService._record_movement(
            variant_id,
            delta=qty,
            reason=InventoryMovement.REASON_RECEIVE,
            note=note,
            user_id=user_id,
        )
        variant = db.session.get(ProductVariant, variant_id)
        AuditService.log(
            "inventory.receive",
            "inventory",
            f"Stock ingresado: {variant.sku} (+{qty})",
            entity_id=variant_id,
            user_id=user_id,
            details={
                "sku": variant.sku,
                "quantity": qty,
                "on_hand": item.quantity_on_hand,
                "note": note,
            },
        )
        db.session.commit()
        return item

    @staticmethod
    def adjust_stock(
        variant_id: int,
        qty: int,
        reason: str = InventoryMovement.REASON_ADJUSTMENT,
        note: str | None = None,
        user_id: int | None = None,
    ) -> InventoryItem:
        if qty == 0:
            raise InventoryError("Adjustment quantity cannot be zero")

        item = InventoryService._lock_inventory(variant_id)
        new_on_hand = item.quantity_on_hand + qty
        if new_on_hand - item.quantity_reserved < 0:
            raise InsufficientStockError(
                variant_id, abs(qty), item.quantity_available
            )

        item.quantity_on_hand = new_on_hand
        InventoryService._record_movement(
            variant_id,
            delta=qty,
            reason=reason,
            note=note,
            user_id=user_id,
        )
        variant = db.session.get(ProductVariant, variant_id)
        AuditService.log(
            "inventory.adjust",
            "inventory",
            f"Ajuste de stock: {variant.sku} ({qty:+d})",
            entity_id=variant_id,
            user_id=user_id,
            details={
                "sku": variant.sku,
                "delta": qty,
                "reason": reason,
                "on_hand": item.quantity_on_hand,
                "available": item.quantity_available,
                "note": note,
            },
        )
        db.session.commit()
        return item

    @staticmethod
    def reserve_stock(
        variant_id: int,
        qty: int,
        *,
        reference_type: str | None = None,
        reference_id: int | None = None,
        user_id: int | None = None,
    ) -> InventoryItem:
        if qty <= 0:
            raise InventoryError("Reserve quantity must be positive")

        item = InventoryService._lock_inventory(variant_id)
        if item.quantity_available < qty:
            raise InsufficientStockError(variant_id, qty, item.quantity_available)

        item.quantity_reserved += qty
        InventoryService._record_movement(
            variant_id,
            delta=-qty,
            reason=InventoryMovement.REASON_RESERVATION,
            reference_type=reference_type,
            reference_id=reference_id,
            user_id=user_id,
        )
        db.session.flush()
        return item

    @staticmethod
    def release_reservation(
        variant_id: int,
        qty: int,
        *,
        reference_type: str | None = None,
        reference_id: int | None = None,
        user_id: int | None = None,
    ) -> InventoryItem:
        if qty <= 0:
            raise InventoryError("Release quantity must be positive")

        item = InventoryService._lock_inventory(variant_id)
        if item.quantity_reserved < qty:
            raise InventoryError(
                f"Cannot release {qty} reserved units; only {item.quantity_reserved} reserved"
            )

        item.quantity_reserved -= qty
        InventoryService._record_movement(
            variant_id,
            delta=qty,
            reason=InventoryMovement.REASON_RELEASE,
            reference_type=reference_type,
            reference_id=reference_id,
            user_id=user_id,
        )
        db.session.flush()
        return item

    @staticmethod
    def commit_sale(
        variant_id: int,
        qty: int,
        *,
        reference_type: str | None = None,
        reference_id: int | None = None,
        user_id: int | None = None,
    ) -> InventoryItem:
        if qty <= 0:
            raise InventoryError("Sale quantity must be positive")

        item = InventoryService._lock_inventory(variant_id)
        if item.quantity_reserved < qty:
            raise InventoryError(
                f"Cannot fulfill {qty} units; only {item.quantity_reserved} reserved"
            )
        if item.quantity_on_hand < qty:
            raise InsufficientStockError(variant_id, qty, item.quantity_on_hand)

        item.quantity_on_hand -= qty
        item.quantity_reserved -= qty
        InventoryService._record_movement(
            variant_id,
            delta=-qty,
            reason=InventoryMovement.REASON_SALE,
            reference_type=reference_type,
            reference_id=reference_id,
            user_id=user_id,
        )
        db.session.flush()
        return item

    @staticmethod
    def list_inventory() -> list[InventoryItem]:
        return (
            InventoryItem.query.join(ProductVariant)
            .join(ProductVariant.product)
            .order_by(ProductVariant.sku)
            .all()
        )

    @staticmethod
    def list_low_stock() -> list[InventoryItem]:
        items = InventoryService.list_inventory()
        return [item for item in items if item.is_low_stock]

    @staticmethod
    def list_movements(limit: int = 50) -> list[InventoryMovement]:
        return (
            InventoryMovement.query.order_by(InventoryMovement.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_inventory_by_sku(sku: str) -> InventoryItem | None:
        variant = ProductVariant.query.filter_by(sku=sku).first()
        if not variant or not variant.inventory_item:
            return None
        return variant.inventory_item
