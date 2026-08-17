from datetime import date, timedelta

from app.models import WeekSheetColumn
from app.services import ClientService, OrderService, WeekSheetService
from app.week import monday_of, product_short_code, week_end


def test_product_short_code():
    assert product_short_code("Lechuga francesa") == "FR"
    assert product_short_code("Espinaca") == "ES"
    assert product_short_code("Albahaca")[0] == "A"


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


def test_week_end_is_sunday():
    monday = monday_of(date(2026, 8, 17))
    assert monday.weekday() == 0
    assert week_end(monday) == monday + timedelta(days=6)
    assert WeekSheetColumn.__tablename__ == "week_sheet_columns"
