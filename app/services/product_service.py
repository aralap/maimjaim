from app.catalog import DEFAULT_CATALOG, DEFAULT_CATEGORIES
from app.extensions import db
from app.models import InventoryItem, InventoryMovement, Product, ProductCategory, ProductVariant
from app.services.audit_service import AuditService
from app.services.exceptions import InventoryError


def _product_details(product: Product, variant: ProductVariant | None = None) -> dict:
    data = {
        "product_id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category.name if product.category else None,
        "unit": product.unit,
        "supplier": product.supplier,
        "is_active": product.is_active,
    }
    if variant:
        data.update(
            {
                "variant_id": variant.id,
                "sku": variant.sku,
                "price_cents": variant.price_cents,
                "cost_cents": variant.cost_cents,
                "attributes": variant.attributes,
            }
        )
    elif product.variants:
        v = product.variants[0]
        data.update(
            {
                "variant_id": v.id,
                "sku": v.sku,
                "price_cents": v.price_cents,
                "cost_cents": v.cost_cents,
            }
        )
    return data


class ProductService:
    @staticmethod
    def list_categories() -> list[ProductCategory]:
        return ProductCategory.query.order_by(ProductCategory.name).all()

    @staticmethod
    def get_or_create_category(name: str) -> ProductCategory:
        name = name.strip()
        category = ProductCategory.query.filter_by(name=name).first()
        if category:
            return category
        category = ProductCategory(name=name)
        db.session.add(category)
        db.session.flush()
        return category

    @staticmethod
    def list_products(
        active_only: bool = True,
        category_id: int | None = None,
    ) -> list[Product]:
        query = Product.query.order_by(Product.name)
        if active_only:
            query = query.filter_by(is_active=True)
        if category_id:
            query = query.filter_by(category_id=category_id)
        return query.all()

    @staticmethod
    def get_product(product_id: int) -> Product | None:
        return db.session.get(Product, product_id)

    @staticmethod
    def create_product(
        name: str,
        description: str | None = None,
        *,
        sku: str,
        price_cents: int = 0,
        cost_cents: int = 0,
        attributes: dict | None = None,
        initial_stock: int = 0,
        reorder_point: int = 0,
        category_id: int | None = None,
        category_name: str | None = None,
        unit: str | None = None,
        supplier: str | None = None,
        user_id: int | None = None,
        log_action: bool = True,
    ) -> Product:
        existing = ProductVariant.query.filter_by(sku=sku).first()
        if existing:
            raise InventoryError(f"El SKU '{sku}' ya existe")

        category = None
        if category_id:
            category = db.session.get(ProductCategory, category_id)
            if not category:
                raise InventoryError(f"Categoría {category_id} no encontrada")
        elif category_name:
            category = ProductService.get_or_create_category(category_name)

        product = Product(
            name=name,
            description=description,
            category=category,
            unit=unit,
            supplier=supplier,
        )
        variant = ProductVariant(
            product=product,
            sku=sku,
            price_cents=price_cents,
            cost_cents=cost_cents,
            attributes=attributes or {},
        )
        inventory = InventoryItem(
            variant=variant,
            quantity_on_hand=initial_stock,
            reorder_point=reorder_point,
        )
        db.session.add(product)
        db.session.add(variant)
        db.session.add(inventory)
        if initial_stock > 0:
            db.session.add(
                InventoryMovement(
                    variant=variant,
                    delta=initial_stock,
                    reason=InventoryMovement.REASON_RECEIVE,
                    note="Stock inicial",
                    created_by_id=user_id,
                )
            )
        db.session.flush()

        if log_action:
            AuditService.log(
                "product.create",
                "product",
                f"Producto creado: {name} ({sku})",
                entity_id=product.id,
                user_id=user_id,
                details=_product_details(product, variant),
            )
        db.session.commit()
        return product

    @staticmethod
    def update_product(
        product_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        category_id: int | None = None,
        unit: str | None = None,
        supplier: str | None = None,
        is_active: bool | None = None,
        user_id: int | None = None,
    ) -> Product:
        product = db.session.get(Product, product_id)
        if not product:
            raise InventoryError(f"Producto {product_id} no encontrado")

        before = _product_details(product)
        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if category_id is not None:
            if category_id:
                category = db.session.get(ProductCategory, category_id)
                if not category:
                    raise InventoryError(f"Categoría {category_id} no encontrada")
                product.category = category
            else:
                product.category = None
        if unit is not None:
            product.unit = unit or None
        if supplier is not None:
            product.supplier = supplier or None
        if is_active is not None:
            product.is_active = is_active

        after = _product_details(product)
        action = "product.update"
        if is_active is False and before.get("is_active"):
            action = "product.deactivate"
        elif is_active is True and not before.get("is_active"):
            action = "product.activate"

        summary = f"Producto actualizado: {product.name}"
        if action == "product.deactivate":
            summary = f"Producto desactivado: {product.name}"
        elif action == "product.activate":
            summary = f"Producto reactivado: {product.name}"

        AuditService.log(
            action,
            "product",
            summary,
            entity_id=product.id,
            user_id=user_id,
            details={"before": before, "after": after},
        )
        db.session.commit()
        return product

    @staticmethod
    def deactivate_product(product_id: int, user_id: int | None = None) -> Product:
        return ProductService.update_product(product_id, is_active=False, user_id=user_id)

    @staticmethod
    def activate_product(product_id: int, user_id: int | None = None) -> Product:
        return ProductService.update_product(product_id, is_active=True, user_id=user_id)

    @staticmethod
    def add_variant(
        product_id: int,
        *,
        sku: str,
        price_cents: int = 0,
        cost_cents: int = 0,
        attributes: dict | None = None,
        initial_stock: int = 0,
        reorder_point: int = 0,
        user_id: int | None = None,
    ) -> ProductVariant:
        product = db.session.get(Product, product_id)
        if not product:
            raise InventoryError(f"Producto {product_id} no encontrado")

        existing = ProductVariant.query.filter_by(sku=sku).first()
        if existing:
            raise InventoryError(f"El SKU '{sku}' ya existe")

        variant = ProductVariant(
            product=product,
            sku=sku,
            price_cents=price_cents,
            cost_cents=cost_cents,
            attributes=attributes or {},
        )
        inventory = InventoryItem(
            variant=variant,
            quantity_on_hand=initial_stock,
            reorder_point=reorder_point,
        )
        db.session.add(variant)
        db.session.add(inventory)
        if initial_stock > 0:
            db.session.add(
                InventoryMovement(
                    variant=variant,
                    delta=initial_stock,
                    reason=InventoryMovement.REASON_RECEIVE,
                    note="Stock inicial",
                    created_by_id=user_id,
                )
            )
        db.session.flush()
        AuditService.log(
            "product.variant.create",
            "product",
            f"Variante agregada: {sku} a {product.name}",
            entity_id=product.id,
            user_id=user_id,
            details=_product_details(product, variant),
        )
        db.session.commit()
        return variant

    @staticmethod
    def seed_default_catalog(user_id: int | None = None) -> int:
        """Carga el catálogo predeterminado. Omite SKUs existentes."""
        created = 0
        for cat_name in DEFAULT_CATEGORIES:
            ProductService.get_or_create_category(cat_name)

        for item in DEFAULT_CATALOG:
            if ProductVariant.query.filter_by(sku=item.sku).first():
                continue
            ProductService.create_product(
                name=item.name,
                description=item.notes or None,
                sku=item.sku,
                price_cents=item.price_cents,
                cost_cents=item.cost_cents,
                initial_stock=item.initial_stock,
                reorder_point=item.reorder_point,
                category_name=item.category,
                unit=item.unit,
                supplier=item.supplier,
                user_id=user_id,
                log_action=False,
            )
            created += 1

        if created:
            AuditService.log(
                "catalog.seed",
                "catalog",
                f"Catálogo predeterminado cargado ({created} productos)",
                user_id=user_id,
                details={"created": created, "total_in_catalog": len(DEFAULT_CATALOG)},
            )
            db.session.commit()
        return created

    @staticmethod
    def get_variant_by_sku(sku: str) -> ProductVariant | None:
        return ProductVariant.query.filter_by(sku=sku).first()

    @staticmethod
    def get_variant(variant_id: int) -> ProductVariant | None:
        return db.session.get(ProductVariant, variant_id)
