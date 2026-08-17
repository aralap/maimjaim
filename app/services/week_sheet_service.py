from datetime import date, timedelta

from app.extensions import db
from app.models import Order, Product, ProductVariant, WeekSheetColumn
from app.services.client_service import ClientService
from app.services.exceptions import InventoryError
from app.services.order_service import OrderService
from app.week import (
    monday_of,
    paired_sku,
    product_short_code,
    sheet_column_label,
    variant_column_kind,
    week_end,
    weekday_dates,
)


class WeekSheetService:
    @staticmethod
    def list_columns() -> list[WeekSheetColumn]:
        WeekSheetService.ensure_default_proc_columns()
        return WeekSheetColumn.query.order_by(WeekSheetColumn.position, WeekSheetColumn.id).all()

    @staticmethod
    def ensure_default_proc_columns() -> None:
        if WeekSheetColumn.query.first() is not None:
            return
        variants = (
            ProductVariant.query.join(Product)
            .filter(Product.is_active.is_(True), ProductVariant.sku.ilike("PROC-%"))
            .order_by(ProductVariant.sku)
            .all()
        )
        for index, variant in enumerate(variants):
            db.session.add(WeekSheetColumn(variant_id=variant.id, position=index))
        if variants:
            db.session.commit()

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
    def paired_variant(variant: ProductVariant) -> ProductVariant | None:
        sku = paired_sku(variant.sku)
        if sku:
            found = ProductVariant.query.filter(ProductVariant.sku.ilike(sku)).first()
            if found:
                return found
        label = sheet_column_label(variant.display_name).casefold()
        want_kind = "veg" if variant_column_kind(variant.sku) == "proc" else "proc"
        query = ProductVariant.query.join(Product).filter(Product.is_active.is_(True))
        for other in query.all():
            if other.id == variant.id:
                continue
            if variant_column_kind(other.sku) != want_kind:
                continue
            if sheet_column_label(other.display_name).casefold() == label:
                return other
        return None

    @staticmethod
    def _cell_state(order: Order, column_variant: ProductVariant, pair: ProductVariant | None) -> dict:
        qty_by_variant = {line.variant_id: line.quantity for line in order.lines}
        column_qty = qty_by_variant.get(column_variant.id, 0)
        pair_qty = qty_by_variant.get(pair.id, 0) if pair else 0
        kind = variant_column_kind(column_variant.sku)
        if kind == "proc" and not column_qty and pair_qty:
            return {
                "qty": pair_qty,
                "as_veg": True,
                "active_variant_id": pair.id,
            }
        return {
            "qty": column_qty,
            "as_veg": False,
            "active_variant_id": column_variant.id,
        }

    @staticmethod
    def toggle_produce_kind(order_id: int, variant_id: int, user_id: int | None = None) -> Order:
        variant = db.session.get(ProductVariant, variant_id)
        if not variant:
            raise InventoryError("Producto no encontrado")
        if variant_column_kind(variant.sku) != "proc":
            raise InventoryError("Solo se puede marcar crudo en columnas PROC")
        pair = WeekSheetService.paired_variant(variant)
        if not pair:
            raise InventoryError("No hay versión sin revisar (VEG) de este producto")
        order = OrderService.get_order(order_id)
        if not order:
            raise InventoryError("Pedido no encontrado")
        proc_qty = next((line.quantity for line in order.lines if line.variant_id == variant.id), 0)
        veg_qty = next((line.quantity for line in order.lines if line.variant_id == pair.id), 0)
        if proc_qty:
            OrderService.set_line_quantity_by_variant(order_id, variant.id, 0, user_id=user_id)
            return OrderService.set_line_quantity_by_variant(
                order_id, pair.id, proc_qty + veg_qty, user_id=user_id
            )
        if veg_qty:
            OrderService.set_line_quantity_by_variant(order_id, pair.id, 0, user_id=user_id)
            return OrderService.set_line_quantity_by_variant(
                order_id, variant.id, veg_qty, user_id=user_id
            )
        raise InventoryError("Agregá una cantidad primero")

    @staticmethod
    def board(week_start: date | None = None) -> dict:
        monday = monday_of(week_start or date.today())
        sunday = week_end(monday)
        columns = WeekSheetService.list_columns()
        pair_by_column = {
            column.variant_id: WeekSheetService.paired_variant(column.variant)
            for column in columns
        }
        orders = OrderService.list_week_orders(monday, sunday)
        rows = []
        used_clients: set[int] = set()
        for order in orders:
            if order.client_id:
                used_clients.add(order.client_id)
            qty_by_variant = {line.variant_id: line.quantity for line in order.lines}
            cells = {
                column.variant_id: WeekSheetService._cell_state(
                    order, column.variant, pair_by_column.get(column.variant_id)
                )
                for column in columns
            }
            rows.append(
                {
                    "order": order,
                    "client": order.client,
                    "editable": order.status == Order.STATUS_DRAFT,
                    "quantities": qty_by_variant,
                    "cells": cells,
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
            "column_labels": {
                column.variant_id: sheet_column_label(column.variant.display_name)
                for column in columns
            },
            "column_kinds": {
                column.variant_id: variant_column_kind(column.variant.sku)
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
            price_type=client.price_type or Order.PRICE_RETAIL,
        )

    @staticmethod
    def drop_client_row(order_id: int, user_id: int | None = None) -> None:
        order = OrderService.get_order(order_id)
        if not order:
            raise InventoryError("Pedido no encontrado")
        if order.status != Order.STATUS_DRAFT:
            raise InventoryError("Solo se pueden quitar filas en borrador")
        OrderService.cancel_order(order_id, user_id=user_id)
