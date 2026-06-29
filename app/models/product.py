from app.extensions import db
from app.models.base import TimestampMixin


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("product_categories.id"), nullable=True)
    unit = db.Column(db.String(32), nullable=True)
    supplier = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    category = db.relationship("ProductCategory", back_populates="products")
    variants = db.relationship(
        "ProductVariant",
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Product {self.name}>"


class ProductVariant(TimestampMixin, db.Model):
    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    sku = db.Column(db.String(64), unique=True, nullable=False, index=True)
    barcode = db.Column(db.String(64), nullable=True)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    cost_cents = db.Column(db.Integer, nullable=False, default=0)
    attributes = db.Column(db.JSON, nullable=False, default=dict)

    product = db.relationship("Product", back_populates="variants")
    inventory_item = db.relationship(
        "InventoryItem",
        back_populates="variant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    order_lines = db.relationship("OrderLine", back_populates="variant", lazy="dynamic")

    @property
    def display_name(self) -> str:
        attrs = self.attributes or {}
        if attrs:
            attr_str = ", ".join(f"{k}: {v}" for k, v in attrs.items())
            return f"{self.product.name} ({attr_str})"
        return self.product.name

    def __repr__(self) -> str:
        return f"<ProductVariant {self.sku}>"
