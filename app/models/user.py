from flask_login import UserMixin
from sqlalchemy.orm import validates

from app.crypto import make_lookup
from app.extensions import db
from app.models.base import TimestampMixin
from app.models.encrypted_types import EncryptedString


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email_lookup = db.Column(db.String(64), unique=True, nullable=False, index=True)
    google_sub_lookup = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(EncryptedString(), nullable=False)
    google_sub = db.Column(EncryptedString(), nullable=False)
    name = db.Column(EncryptedString(), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    orders = db.relationship("Order", back_populates="created_by_user", lazy="dynamic")
    activity_logs = db.relationship("ActivityLog", back_populates="user", lazy="dynamic")

    @validates("email")
    def _validate_email(self, _key, value: str) -> str:
        if value:
            self.email_lookup = make_lookup(value)
        return value

    @validates("google_sub")
    def _validate_google_sub(self, _key, value: str) -> str:
        if value:
            self.google_sub_lookup = make_lookup(value)
        return value

    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.email_lookup[:8]}…>"
