from datetime import date, timedelta

from app.extensions import db
from app.models import Order, ProductVariant, WeekSheetColumn
from app.services.client_service import ClientService
from app.services.exceptions import InventoryError
from app.services.order_service import OrderService
from app.week import monday_of, product_short_code, week_end, weekday_dates


class WeekSheetService:
    @staticmethod
    def list_columns() -> list[WeekSheetColumn]:
        return WeekSheetColumn.query.order_by(WeekSheetColumn.position, WeekSheetColumn.id).all()

    @staticmethod
    def available_variants() -> list[ProductVariant]:
        used = {column.variant_id for column in WeekSheetService.list_columns()}
        query = ProductVariant.query.join(ProductVariant.product).order_by(ProductVariant.sku)
        return [
            variant
            for variant in query.all()
            if variant.product.is_active and variant.id not in used
        ]

    @staticmethod
    def add_column(variant_id: int) -> WeekSheetColumn:
        variant = db.session.get(ProductVariant, variant_id)
        if not variant:
            raise InventoryError("Producto no encontrado")
        existing = WeekSheetColumn.query.filter_by(variant_id=variant_id).first()
        if existing:
            return existing
        last = WeekSheetColumn.query.order_by(WeekSheetColumn.position.desc()).first()
        column = WeekSheetColumn(
            variant_id=variant_id,
            position=(last.position + 1) if last else 0,
        )
        db.session.add(column)
        db.session.commit()
        return column

    @staticmethod
    def remove_column(column_id: int) -> None:
        column = db.session.get(WeekSheetColumn, column_id)
        if not column:
            raise InventoryError("Columna no encontrada")
        db.session.delete(column)
        db.session.commit()

    @staticmethod
    def board(week_start: date | None = None) -> dict:
        monday = monday_of(week_start or date.today())
        sunday = week_end(monday)
        columns = WeekSheetService.list_columns()
        orders = OrderService.list_week_orders(monday, sunday)
        rows = []
        used_clients: set[int] = set()
        for order in orders:
            if order.client_id:
                used_clients.add(order.client_id)
            qty_by_variant = {line.variant_id: line.quantity for line in order.lines}
            rows.append(
                {
                    "order": order,
                    "client": order.client,
                    "editable": order.status == Order.STATUS_DRAFT,
                    "quantities": qty_by_variant,
                    "qty_total": sum(qty_by_variant.values()),
                }
            )
        unused_clients = [
            client
            for client in ClientService.list_clients(active_only=True)
            if client.id not in used_clients
        ]
        return {
            "monday": monday,
            "sunday": sunday,
            "prev_monday": monday - timedelta(days=7),
            "next_monday": monday + timedelta(days=7),
            "week_number": monday.isocalendar().week,
            "year": monday.isocalendar().year,
            "weekdays": weekday_dates(monday),
            "columns": columns,
            "column_codes": {
                column.variant_id: product_short_code(column.variant.display_name)
                for column in columns
            },
            "rows": rows,
            "unused_clients": unused_clients,
            "available_variants": WeekSheetService.available_variants(),
        }

    @staticmethod
    def add_client_row(client_id: int, week_start: date, user_id: int | None = None) -> Order:
        monday = monday_of(week_start)
        sunday = week_end(monday)
        client = ClientService.get_client(client_id)
        if not client:
            raise InventoryError("Cliente no encontrado")
        existing = [
            order
            for order in OrderService.list_week_orders(monday, sunday)
            if order.client_id == client_id
        ]
        if existing:
            return existing[0]
        return OrderService.create_order(
            lines=[],
            client_id=client_id,
            delivery_date=monday,
            user_id=user_id,
            allow_empty=True,
        )

    @staticmethod
    def drop_client_row(order_id: int, user_id: int | None = None) -> None:
        order = OrderService.get_order(order_id)
        if not order:
            raise InventoryError("Pedido no encontrado")
        if order.status != Order.STATUS_DRAFT:
            raise InventoryError("Solo se pueden quitar filas en borrador")
        OrderService.cancel_order(order_id, user_id=user_id)
