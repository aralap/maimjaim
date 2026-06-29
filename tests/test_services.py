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
