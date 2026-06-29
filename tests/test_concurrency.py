import pytest

from app.extensions import db
from app.services import OrderService, ProductService
from app.services.exceptions import InsufficientStockError
from app.services.order_service import OrderLineInput


@pytest.fixture
def low_stock_variant(app):
    product = ProductService.create_product(
        name="Concurrency Product",
        sku="CONC-SKU",
        price_cents=500,
        initial_stock=1,
        reorder_point=0,
    )
    return product.variants[0]


class TestInventoryConcurrency:
    def test_second_confirm_fails_when_stock_exhausted(self, app, low_stock_variant, user):
        """Sequential test: only one of two competing orders can confirm."""
        variant_id = low_stock_variant.id
        order_a = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant_id, quantity=1)],
            user_id=user.id,
        )
        order_b = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant_id, quantity=1)],
            user_id=user.id,
        )

        OrderService.confirm_order(order_a.id, user_id=user.id)

        with pytest.raises(InsufficientStockError):
            OrderService.confirm_order(order_b.id, user_id=user.id)

        db.session.refresh(low_stock_variant.inventory_item)
        assert low_stock_variant.inventory_item.quantity_reserved == 1
        assert low_stock_variant.inventory_item.quantity_available == 0
