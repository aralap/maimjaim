import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.config import get_settings
from app.extensions import db
from app.models import ApiClient, User
from app.services import ProductService

TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    get_settings.cache_clear()
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    u = User(
        email="test@example.com",
        google_sub="sub123",
        name="Test User",
        role="admin",
        is_active=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def variant(app):
    product = ProductService.create_product(
        name="Test Product",
        sku="TEST-SKU",
        price_cents=1000,
        initial_stock=10,
        reorder_point=2,
    )
    return product.variants[0]


@pytest.fixture
def api_client(app):
    client, raw_key = ApiClient.create(name="test-client")
    db.session.add(client)
    db.session.commit()
    client.raw_key = raw_key
    return client
