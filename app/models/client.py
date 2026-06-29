from app.extensions import db
from app.models.base import TimestampMixin
from app.models.encrypted_types import EncryptedString, EncryptedText


class Client(TimestampMixin, db.Model):
    __tablename__ = "clients"

    PAYMENT_CASH = "cash"
    PAYMENT_TRANSFER = "transfer"
    PAYMENT_CARD = "card"
    PAYMENT_MERCADO_PAGO = "mercado_pago"
    PAYMENT_OTHER = "other"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(EncryptedString(), nullable=False)
    email = db.Column(EncryptedString(), nullable=True)
    phone = db.Column(EncryptedString(), nullable=True)
    address = db.Column(EncryptedString(), nullable=True)
    city = db.Column(EncryptedString(), nullable=True)
    tax_id = db.Column(EncryptedString(), nullable=True)
    notes = db.Column(EncryptedText(), nullable=True)
    preferred_payment_method = db.Column(EncryptedString(), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    orders = db.relationship("Order", back_populates="client", lazy="dynamic")

    @property
    def display_label(self) -> str:
        parts = [self.name]
        if self.phone:
            parts.append(self.phone)
        elif self.email:
            parts.append(self.email)
        return " — ".join(parts)

    def __repr__(self) -> str:
        return f"<Client id={self.id}>"
