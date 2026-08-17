from app.extensions import db


class WeekSheetColumn(db.Model):
    """Product columns visible on the weekly order spreadsheet."""

    __tablename__ = "week_sheet_columns"

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=False, unique=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    variant = db.relationship("ProductVariant")

    def __repr__(self) -> str:
        return f"<WeekSheetColumn variant={self.variant_id} pos={self.position}>"
