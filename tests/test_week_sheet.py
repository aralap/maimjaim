from datetime import date, timedelta

from app.models import WeekSheetColumn
from app.services import ClientService, OrderService, ProductService, WeekSheetService
from app.week import monday_of, paired_sku, product_short_code, sheet_column_label, variant_column_kind, week_end


def test_product_short_code():
    assert product_short_code("Lechuga francesa") == "FR"
    assert product_short_code("Espinaca") == "ES"
    assert product_short_code("Albahaca")[0] == "A"
    assert sheet_column_label("Lechuga francesa Revisada") == "Lechuga francesa"
    assert variant_column_kind("PROC-001") == "proc"
    assert variant_column_kind("VEG-001") == "veg"
    assert paired_sku("PROC-001") == "VEG-001"
    assert paired_sku("VEG-013") == "PROC-013"


def test_week_sheet_starts_empty_and_adds_client_column_qty(app, variant, user):
    monday = monday_of(date(2026, 8, 17))
    board = WeekSheetService.board(monday)
    assert board["rows"] == []
    assert board["week_number"] == monday.isocalendar().week

    client = ClientService.create_client(name="Romi Poly", phone="+5491100000001")
    order = WeekSheetService.add_client_row(client.id, monday, user_id=user.id)
    assert order.status == "draft"
    assert order.lines == []
    assert order.delivery_date == monday
    assert order.price_type == "retail"

    WeekSheetService.add_column(variant.id)
    columns = WeekSheetService.list_columns()
    assert len(columns) == 1
    assert columns[0].variant_id == variant.id

    order = OrderService.set_line_quantity_by_variant(order.id, variant.id, 2, user_id=user.id)
    assert order.lines[0].quantity == 2
    order = OrderService.set_line_quantity_by_variant(order.id, variant.id, 0, user_id=user.id)
    assert order.lines == []

    board = WeekSheetService.board(monday)
    assert len(board["rows"]) == 1
    assert board["rows"][0]["client"].id == client.id


def test_week_sheet_defaults_proc_columns(app):
    proc = ProductService.create_product(
        name="Lechuga francesa Revisada",
        sku="PROC-001",
        price_cents=500,
    )
    ProductService.create_product(
        name="Lechuga francesa",
        sku="VEG-001",
        price_cents=400,
    )
    columns = WeekSheetService.list_columns()
    assert [column.variant.sku for column in columns] == ["PROC-001"]
    assert columns[0].variant_id == proc.variants[0].id


def test_week_sheet_circle_proc_qty_switches_to_veg(app, user):
    proc = ProductService.create_product(
        name="Lechuga francesa Revisada",
        sku="PROC-001",
        price_cents=500,
    )
    veg = ProductService.create_product(
        name="Lechuga francesa",
        sku="VEG-001",
        price_cents=400,
    )
    monday = monday_of(date(2026, 8, 17))
    client = ClientService.create_client(name="Nicole", phone="+5491100000003")
    order = WeekSheetService.add_client_row(client.id, monday, user_id=user.id)
    proc_id = proc.variants[0].id
    veg_id = veg.variants[0].id
    OrderService.set_line_quantity_by_variant(order.id, proc_id, 3, user_id=user.id)
    order = WeekSheetService.toggle_produce_kind(order.id, proc_id, user_id=user.id)
    assert [line.variant.sku for line in order.lines] == ["VEG-001"]
    assert order.lines[0].quantity == 3
    assert order.lines[0].unit_price_cents == 400
    board = WeekSheetService.board(monday)
    cell = board["rows"][0]["cells"][proc_id]
    assert cell["qty"] == 3
    assert cell["as_veg"] is True
    assert cell["active_variant_id"] == veg_id
    order = WeekSheetService.toggle_produce_kind(order.id, proc_id, user_id=user.id)
    assert [line.variant.sku for line in order.lines] == ["PROC-001"]
    assert order.lines[0].unit_price_cents == 500


def test_week_sheet_proc_uses_paired_veg_prices(app, user):
    proc = ProductService.create_product(
        name="Lechuga francesa Revisada",
        sku="PROC-001",
        price_cents=0,
    )
    veg = ProductService.create_product(
        name="Lechuga francesa",
        sku="VEG-001",
        price_cents=400,
    )
    ProductService.update_variant(veg.variants[0].id, wholesale_price_cents=300, update_wholesale=True)
    monday = monday_of(date(2026, 8, 17))
    client = ClientService.create_client(name="M Cosava", phone="+5491100000004")
    order = WeekSheetService.add_client_row(client.id, monday, user_id=user.id)
    proc_id = proc.variants[0].id
    OrderService.set_line_quantity_by_variant(order.id, proc_id, 2, user_id=user.id)
    order = OrderService.get_order(order.id)
    assert order.total_cents == 800
    order = OrderService.set_order_price_type(order.id, "wholesale", user_id=user.id)
    assert order.lines[0].unit_price_cents == 300
    assert order.total_cents == 600
    order = WeekSheetService.toggle_produce_kind(order.id, proc_id, user_id=user.id)
    assert order.lines[0].variant.sku == "VEG-001"
    assert order.lines[0].unit_price_cents == 300
    assert order.total_cents == 600


def test_week_sheet_mayorista_uses_wholesale_price(app, variant, user):
    ProductService.update_variant(variant.id, wholesale_price_cents=700, update_wholesale=True)
    monday = monday_of(date(2026, 8, 17))
    client = ClientService.create_client(name="Sara Alfie", phone="+5491100000002")
    order = WeekSheetService.add_client_row(client.id, monday, user_id=user.id)
    OrderService.set_line_quantity_by_variant(order.id, variant.id, 2, user_id=user.id)
    order = OrderService.set_order_price_type(order.id, "wholesale", user_id=user.id)
    assert order.price_type == "wholesale"
    assert order.lines[0].price_type == "wholesale"
    assert order.lines[0].unit_price_cents == 700
    assert order.total_cents == 1400
    assert client.price_type == "wholesale"


def test_week_end_is_sunday():
    monday = monday_of(date(2026, 8, 17))
    assert monday.weekday() == 0
    assert week_end(monday) == monday + timedelta(days=6)
    assert WeekSheetColumn.__tablename__ == "week_sheet_columns"
