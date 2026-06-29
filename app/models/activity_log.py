from app.extensions import db
from app.models.base import TimestampMixin
from app.models.encrypted_types import EncryptedJSON, EncryptedString


class ActivityLog(TimestampMixin, db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    summary = db.Column(EncryptedString(), nullable=False)
    details = db.Column(EncryptedJSON(), nullable=False, default=dict)
    ip_address = db.Column(db.String(64), nullable=True)

    user = db.relationship("User", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} {self.entity_type}:{self.entity_id}>"
