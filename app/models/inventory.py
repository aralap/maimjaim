from datetime import datetime, timezone

from app.extensions import db
from app.models.base import TimestampMixin


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(
        db.Integer,
        db.ForeignKey("product_variants.id"),
        unique=True,
        nullable=False,
    )
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    quantity_reserved = db.Column(db.Integer, nullable=False, default=0)
    reorder_point = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    variant = db.relationship("ProductVariant", back_populates="inventory_item")

    @property
    def quantity_available(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_available <= self.reorder_point

    def __repr__(self) -> str:
        return f"<InventoryItem variant={self.variant_id} on_hand={self.quantity_on_hand}>"


class InventoryMovement(TimestampMixin, db.Model):
    __tablename__ = "inventory_movements"

    REASON_RECEIVE = "receive"
    REASON_ADJUSTMENT = "adjustment"
    REASON_SALE = "sale"
    REASON_RETURN = "return"
    REASON_RESERVATION = "reservation"
    REASON_RELEASE = "release"

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False)
    delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(32), nullable=False)
    reference_type = db.Column(db.String(64), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    variant = db.relationship("ProductVariant", backref="movements")
    created_by = db.relationship("User")

    def __repr__(self) -> str:
        return f"<InventoryMovement variant={self.variant_id} delta={self.delta}>"
