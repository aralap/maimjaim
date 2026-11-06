import pytest
from app.config import get_settings
from app.extensions import db
from app.models import ActivityLog, Client, InventoryMovement, Order, OrderLine, Product, ProductCategory, ProductVariant, User, WeekSheetColumn
from app.services import ClientService, OrderService
from app.services.audit_service import AuditService
from app.services.exceptions import InventoryError
from app.services.maintenance_service import MaintenanceService
from app.services.order_service import OrderLineInput, PaymentInput


@pytest.fixture(autouse=True)
def local_oauth_host(monkeypatch):
    monkeypatch.setenv('OAUTH_REDIRECT_URI', 'http://localhost/auth/callback')
    monkeypatch.setattr(get_settings(), 'oauth_redirect_uri', 'http://localhost/auth/callback')


@pytest.fixture
def operation(app, variant, user):
    # Enforce real FK rules in SQLite, including bulk deletion order.
    db.session.execute(db.text('PRAGMA foreign_keys=ON'))
    customer = ClientService.create_client(name='Ana', phone='+541100000000', address='Test 123')
    category = ProductCategory(name='Verduras')
    variant.product.category = category
    variant.wholesale_price_cents = 800
    column = WeekSheetColumn(variant_id=variant.id, position=3)
    db.session.add(column)
    db.session.commit()
    def create(status='draft', qty=2):
        order = OrderService.create_order(
            [OrderLineInput(variant_id=variant.id, quantity=qty)],
            client_id=customer.id, user_id=user.id,
            payment=PaymentInput(amount_paid_cents=500),
        )
        if status in {'confirmed', 'fulfilled'}:
            order = OrderService.confirm_order(order.id, user_id=user.id)
        if status == 'fulfilled':
            order = OrderService.fulfill_order(order.id, user_id=user.id)
        if status == 'cancelled':
            order = OrderService.cancel_order(order.id, user_id=user.id)
        return order
    return customer, create


def reset(user, scope, **overrides):
    return MaintenanceService.reset(scope, **{
        'confirmation': 'RESTABLECER', 'reason': 'Fin de pruebas', 'user_id': user.id,
        **overrides,
    })


def assert_base_preserved(customer, variant, user):
    assert Product.query.count() == ProductVariant.query.count() == 1
    assert Client.query.count() == 1
    assert db.session.get(Client, customer.id).address == 'Test 123'
    assert db.session.get(ProductVariant, variant.id).wholesale_price_cents == 800
    assert variant.inventory_item.reorder_point == 2
    assert ProductCategory.query.one().name == 'Verduras'
    assert WeekSheetColumn.query.one().position == 3
    assert db.session.get(User, user.id).is_admin()


def test_stock_reset_preserves_sales_and_catalog(app, variant, user, operation):
    customer, create = operation
    create('fulfilled')
    create('draft')
    before = InventoryMovement.query.count()
    result = reset(user, 'stock')
    assert result['stock_units_removed'] == 8
    assert variant.inventory_item.quantity_on_hand == 0
    assert Order.query.count() == 2
    assert OrderLine.query.count() == 2
    assert InventoryMovement.query.count() == before + 1
    assert_base_preserved(customer, variant, user)


def test_stock_reset_rejects_reservations_without_changes(app, variant, user, operation):
    customer, create = operation
    create('confirmed')
    count = ActivityLog.query.count()
    with pytest.raises(InventoryError, match='reservado'):
        reset(user, 'stock')
    assert variant.inventory_item.quantity_on_hand == 10
    assert variant.inventory_item.quantity_reserved == 2
    assert Order.query.count() == 1
    assert ActivityLog.query.count() == count


@pytest.mark.parametrize('scope', ['sales', 'all'])
def test_bulk_reset_removes_every_order_state_keeps_base(app, variant, user, operation, scope):
    customer, create = operation
    for status in ['draft', 'confirmed', 'fulfilled', 'cancelled']:
        create(status)
    before = InventoryMovement.query.count()
    result = reset(user, scope)
    assert result['deleted_orders'] == 4
    assert result['released_units'] == 2
    assert Order.query.count() == OrderLine.query.count() == customer.orders.count() == 0
    assert variant.inventory_item.quantity_reserved == 0
    assert variant.inventory_item.quantity_on_hand == (8 if scope == 'sales' else 0)
    assert InventoryMovement.query.count() > before
    assert not InventoryMovement.query.filter_by(reference_type='order').count()
    audit = ActivityLog.query.filter_by(action=f'maintenance.reset.{scope}').one()
    assert audit.user_id == user.id
    assert audit.details['reason'] == 'Fin de pruebas'
    assert_base_preserved(customer, variant, user)
    # Catalog/clients remain usable and reservations work after a reset.
    if scope == 'sales':
        create('confirmed')
        assert variant.inventory_item.quantity_reserved == 2


def test_reset_rolls_back_if_audit_fails(app, variant, user, operation, monkeypatch):
    _, create = operation
    create('confirmed')
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(AuditService, 'log', fail)
    with pytest.raises(RuntimeError):
        reset(user, 'all')
    assert Order.query.count() == 1
    assert OrderLine.query.count() == 1
    assert variant.inventory_item.quantity_on_hand == 10
    assert variant.inventory_item.quantity_reserved == 2
    assert InventoryMovement.query.filter_by(reference_type='order').count() == 1


@pytest.mark.parametrize('kwargs', [
    {'confirmation': ''}, {'confirmation': 'restablecer'}, {'reason': ''},
    {'reason': 'x' * 501}, {'scope': 'everything'},
])
def test_invalid_confirmation_cannot_change_data(app, variant, user, kwargs):
    scope = kwargs.pop('scope', 'all')
    with pytest.raises(InventoryError):
        reset(user, scope, **kwargs)
    assert variant.inventory_item.quantity_on_hand == 10


@pytest.mark.parametrize('status,expected_stock', [('draft', 10), ('confirmed', 10), ('fulfilled', 8), ('cancelled', 10)])
def test_delete_individual_sale(app, variant, user, operation, status, expected_stock):
    customer, create = operation
    order = create(status)
    order_id = order.id
    # Another order's reservations must survive deleting this order.
    other = create('confirmed', qty=1)
    MaintenanceService.delete_order(order.id, confirmation=order.order_number, reason='Duplicado', user_id=user.id)
    assert db.session.get(Order, order_id) is None
    assert Order.query.count() == 1
    assert variant.inventory_item.quantity_on_hand == expected_stock
    assert variant.inventory_item.quantity_reserved == 1
    assert_base_preserved(customer, variant, user)


def login(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def test_admin_routes_and_post_only_reset(app, client, variant, user, operation):
    _, create = operation
    order = create('draft')
    login(client, user)
    assert client.get('/admin/maintenance/').status_code == 200
    assert client.get('/admin/maintenance/reset').status_code == 405
    assert client.get(f'/admin/maintenance/orders/{order.id}/delete').status_code == 200
    assert Order.query.count() == 1
    response = client.post('/admin/maintenance/reset', data={'scope':'all','confirmation':'wrong','reason':'test'})
    assert response.status_code == 400
    assert Order.query.count() == 1
    response = client.post('/admin/maintenance/reset', data={'scope':'all','confirmation':'RESTABLECER','reason':'test'})
    assert response.status_code == 302
    assert Order.query.count() == 0


@pytest.mark.parametrize('role,active', [('staff', True), ('admin', False)])
def test_unauthorized_users_cannot_reset(app, client, variant, user, role, active):
    user.role, user.is_active = role, active
    db.session.commit()
    login(client, user)
    for url in ['/admin/maintenance/', '/admin/maintenance/reset', '/admin/maintenance/orders/1/delete']:
        response = client.post(url, data={'scope':'all','confirmation':'RESTABLECER','reason':'test'}) if url.endswith('reset') else client.get(url)
        assert response.status_code in {302, 403}
    with pytest.raises(InventoryError):
        reset(user, 'all')
    assert variant.inventory_item.quantity_on_hand == 10


def test_csrf_and_anonymous_access(app, client, variant, user):
    assert client.get('/admin/maintenance/').status_code == 302
    login(client, user)
    app.config['WTF_CSRF_ENABLED'] = True
    assert client.post('/admin/maintenance/reset', data={'scope':'all','confirmation':'RESTABLECER','reason':'test'}).status_code == 400
    assert variant.inventory_item.quantity_on_hand == 10


@pytest.mark.parametrize('path', ['/', '/products/', '/clients/', '/orders/', '/inventory/', '/orders/planilla'])
def test_updated_pages_render(app, client, variant, user, path):
    login(client, user)
    response = client.get(path)
    assert response.status_code == 200
    assert b'app.css' in response.data


def test_single_delete_requires_confirmation_and_rolls_back(app, client, variant, user, operation, monkeypatch):
    _, create = operation
    order = create('confirmed')
    login(client, user)
    url = f'/admin/maintenance/orders/{order.id}/delete'
    response = client.post(url, data={'confirmation':'wrong', 'reason':'test'})
    assert response.status_code == 400
    assert Order.query.count() == 1
    assert variant.inventory_item.quantity_reserved == 2
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(AuditService, 'log', fail)
    with pytest.raises(RuntimeError):
        MaintenanceService.delete_order(order.id, confirmation=order.order_number, reason='test', user_id=user.id)
    assert Order.query.count() == 1
    assert variant.inventory_item.quantity_reserved == 2


def test_staff_cannot_delete_or_view_controls(app, client, variant, user, operation):
    _, create = operation
    order = create('draft')
    user.role = 'staff'
    db.session.commit()
    login(client, user)
    assert client.get('/admin/maintenance/').status_code == 403
    assert client.post(f'/admin/maintenance/orders/{order.id}/delete', data={'confirmation':order.order_number,'reason':'test'}).status_code == 403
    assert b'Eliminar este pedido' not in client.get(f'/orders/{order.id}').data
    assert b'Restablecer datos' not in client.get('/inventory/').data
    assert Order.query.count() == 1
