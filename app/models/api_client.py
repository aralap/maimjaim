import secrets

import bcrypt

from app.extensions import db
from app.models.base import TimestampMixin


class ApiClient(TimestampMixin, db.Model):
    __tablename__ = "api_clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    key_hash = db.Column(db.String(255), nullable=False)
    scopes = db.Column(db.String(512), nullable=False, default="read,write")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    orders = db.relationship("Order", back_populates="api_client", lazy="dynamic")

    @staticmethod
    def generate_key() -> str:
        return f"mj_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_key(self, raw_key: str) -> bool:
        return bcrypt.checkpw(raw_key.encode("utf-8"), self.key_hash.encode("utf-8"))

    def has_scope(self, scope: str) -> bool:
        return scope in {s.strip() for s in self.scopes.split(",") if s.strip()}

    @classmethod
    def create(cls, name: str, scopes: str = "read,write") -> tuple["ApiClient", str]:
        raw_key = cls.generate_key()
        client = cls(name=name, key_hash=cls.hash_key(raw_key), scopes=scopes)
        return client, raw_key

    def __repr__(self) -> str:
        return f"<ApiClient {self.name}>"
