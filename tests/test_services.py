import pytest

from app.extensions import db
from app.services import InventoryService, OrderService
from app.services.exceptions import InsufficientStockError
from app.services.order_service import OrderLineInput


class TestInventoryService:
    def test_receive_stock(self, app, variant, user):
        item = InventoryService.receive_stock(variant.id, 5, user_id=user.id)
        assert item.quantity_on_hand == 15

    def test_adjust_stock_negative_insufficient(self, app, variant):
        with pytest.raises(InsufficientStockError):
            InventoryService.adjust_stock(variant.id, -20)

    def test_reserve_and_release(self, app, variant, user):
        InventoryService.reserve_stock(variant.id, 3, user_id=user.id)
        item = variant.inventory_item
        db.session.refresh(item)
        assert item.quantity_reserved == 3
        assert item.quantity_available == 7

        InventoryService.release_reservation(variant.id, 3, user_id=user.id)
        db.session.refresh(item)
        assert item.quantity_reserved == 0

    def test_commit_sale(self, app, variant, user):
        InventoryService.reserve_stock(variant.id, 2, user_id=user.id)
        InventoryService.commit_sale(variant.id, 2, user_id=user.id)
        db.session.refresh(variant.inventory_item)
        assert variant.inventory_item.quantity_on_hand == 8
        assert variant.inventory_item.quantity_reserved == 0


class TestOrderService:
    def test_create_and_confirm_order(self, app, variant, user):
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=2)],
            user_id=user.id,
        )
        assert order.status == "draft"

        order = OrderService.confirm_order(order.id, user_id=user.id)
        assert order.status == "confirmed"
        db.session.refresh(variant.inventory_item)
        assert variant.inventory_item.quantity_reserved == 2

    def test_fulfill_order(self, app, variant, user):
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=1)],
            user_id=user.id,
        )
        OrderService.confirm_order(order.id, user_id=user.id)
        order = OrderService.fulfill_order(order.id, user_id=user.id)
        assert order.status == "fulfilled"
        db.session.refresh(variant.inventory_item)
        assert variant.inventory_item.quantity_on_hand == 9

    def test_cancel_confirmed_order(self, app, variant, user):
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=3)],
            user_id=user.id,
        )
        OrderService.confirm_order(order.id, user_id=user.id)
        order = OrderService.cancel_order(order.id, user_id=user.id)
        assert order.status == "cancelled"
        db.session.refresh(variant.inventory_item)
        assert variant.inventory_item.quantity_reserved == 0

    def test_insufficient_stock_on_confirm(self, app, variant, user):
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=100)],
            user_id=user.id,
        )
        with pytest.raises(InsufficientStockError):
            OrderService.confirm_order(order.id, user_id=user.id)

    def test_order_defaults_to_retail_price(self, app, variant, user):
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=1)],
            user_id=user.id,
        )
        assert order.lines[0].price_type == "retail"
        assert order.lines[0].unit_price_cents == variant.price_cents

    def test_order_wholesale_price(self, app, variant, user):
        from app.services import ProductService

        ProductService.update_variant(variant.id, wholesale_price_cents=700, update_wholesale=True)
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=2, price_type="wholesale")],
            user_id=user.id,
        )
        assert order.lines[0].price_type == "wholesale"
        assert order.lines[0].unit_price_cents == 700
        assert order.total_cents == 1400

    def test_order_custom_price_and_update(self, app, variant, user):
        order = OrderService.create_order(
            lines=[
                OrderLineInput(
                    variant_id=variant.id,
                    quantity=1,
                    price_type="custom",
                    unit_price_cents=1234,
                )
            ],
            user_id=user.id,
        )
        assert order.lines[0].price_type == "custom"
        assert order.lines[0].unit_price_cents == 1234

        order = OrderService.update_line_price(
            order.id,
            order.lines[0].id,
            price_type="retail",
            user_id=user.id,
        )
        assert order.lines[0].price_type == "retail"
        assert order.lines[0].unit_price_cents == variant.price_cents

    def test_wholesale_requires_catalog_price(self, app, variant, user):
        from app.services.exceptions import InventoryError

        with pytest.raises(InventoryError):
            OrderService.create_order(
                lines=[OrderLineInput(variant_id=variant.id, quantity=1, price_type="wholesale")],
                user_id=user.id,
            )

    def test_draft_add_and_remove_lines(self, app, variant, user):
        from app.services import ProductService
        from app.services.exceptions import InventoryError, InvalidOrderStateError

        other = ProductService.create_product(
            name="Other",
            sku="OTHER-SKU",
            price_cents=2500,
            initial_stock=5,
        ).variants[0]
        order = OrderService.create_order(
            lines=[OrderLineInput(variant_id=variant.id, quantity=1)],
            user_id=user.id,
        )
        order = OrderService.add_line(
            order.id,
            OrderLineInput(variant_id=other.id, quantity=2),
            user_id=user.id,
        )
        assert len(order.lines) == 2
        assert order.total_cents == variant.price_cents + (2500 * 2)

        order = OrderService.add_line(
            order.id,
            OrderLineInput(variant_id=variant.id, quantity=3),
            user_id=user.id,
        )
        merged = next(line for line in order.lines if line.variant_id == variant.id)
        assert merged.quantity == 4

        extra_id = next(line.id for line in order.lines if line.variant_id == other.id)
        order = OrderService.update_line_quantity(order.id, extra_id, 5, user_id=user.id)
        extra = next(line for line in order.lines if line.id == extra_id)
        assert extra.quantity == 5

        order = OrderService.update_line_quantity(order.id, extra_id, 0, user_id=user.id)
        assert len(order.lines) == 1

        with pytest.raises(InventoryError):
            OrderService.remove_line(order.id, order.lines[0].id, user_id=user.id)

        OrderService.confirm_order(order.id, user_id=user.id)
        with pytest.raises(InvalidOrderStateError):
            OrderService.add_line(
                order.id,
                OrderLineInput(variant_id=other.id, quantity=1),
                user_id=user.id,
            )


class TestAPI:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json["status"] == "ok"

    def test_api_requires_key(self, client):
        response = client.get("/api/v1/products")
        assert response.status_code == 401

    def test_api_list_products(self, client, variant, api_client):
        response = client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {api_client.raw_key}"},
        )
        assert response.status_code == 200
        assert len(response.json["data"]) >= 1

    def test_api_create_order_idempotent(self, client, variant, api_client):
        payload = {
            "external_id": "wa-msg-123",
            "source": "whatsapp",
            "customer": {"name": "Jane", "phone": "+1234"},
            "lines": [{"sku": "TEST-SKU", "quantity": 1}],
        }
        headers = {"Authorization": f"Bearer {api_client.raw_key}"}
        r1 = client.post("/api/v1/orders", json=payload, headers=headers)
        r2 = client.post("/api/v1/orders", json=payload, headers=headers)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json["id"] == r2.json["id"]
