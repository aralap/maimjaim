from app.extensions import db
from app.models.base import TimestampMixin
from app.models.encrypted_types import EncryptedInteger, EncryptedString, EncryptedText


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.UniqueConstraint("api_client_id", "external_id", name="uq_order_api_external"),
    )

    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FULFILLED = "fulfilled"
    STATUS_CANCELLED = "cancelled"

    SOURCE_MANUAL = "manual"
    SOURCE_API = "api"
    SOURCE_WHATSAPP = "whatsapp"

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUNDED = "refunded"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_DRAFT)
    source = db.Column(db.String(32), nullable=False, default=SOURCE_MANUAL)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    customer_name = db.Column(EncryptedString(), nullable=True)
    customer_phone = db.Column(EncryptedString(), nullable=True)
    customer_email = db.Column(EncryptedString(), nullable=True)
    notes = db.Column(EncryptedText(), nullable=True)
    payment_status = db.Column(db.String(32), nullable=False, default=PAYMENT_UNPAID)
    payment_method = db.Column(EncryptedString(), nullable=True)
    amount_paid_cents = db.Column(EncryptedInteger(), nullable=False, default=0)
    payment_reference = db.Column(EncryptedString(), nullable=True)
    payment_notes = db.Column(EncryptedText(), nullable=True)
    delivery_date = db.Column(db.Date, nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    api_client_id = db.Column(db.Integer, db.ForeignKey("api_clients.id"), nullable=True)
    external_id = db.Column(db.String(255), nullable=True)

    client = db.relationship("Client", back_populates="orders")
    created_by_user = db.relationship("User", back_populates="orders")
    api_client = db.relationship("ApiClient", back_populates="orders")
    lines = db.relationship(
        "OrderLine",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def total_cents(self) -> int:
        return sum(line.line_total_cents for line in self.lines)

    @property
    def amount_paid(self) -> int:
        return self.amount_paid_cents or 0

    @property
    def balance_due_cents(self) -> int:
        return max(0, self.total_cents - self.amount_paid)

    def sync_payment_status(self) -> None:
        if self.payment_status == self.PAYMENT_REFUNDED:
            return
        paid = self.amount_paid_cents or 0
        if paid <= 0:
            self.payment_status = self.PAYMENT_UNPAID
        elif paid >= self.total_cents:
            self.payment_status = self.PAYMENT_PAID
        else:
            self.payment_status = self.PAYMENT_PARTIAL

    def __repr__(self) -> str:
        return f"<Order {self.order_number} status={self.status}>"


class OrderLine(db.Model):
    __tablename__ = "order_lines"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="lines")
    variant = db.relationship("ProductVariant", back_populates="order_lines")

    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents

    def __repr__(self) -> str:
        return f"<OrderLine order={self.order_id} variant={self.variant_id} qty={self.quantity}>"
