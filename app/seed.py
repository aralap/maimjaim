"""Seed the database with sample data."""

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import ApiClient
from app.services import ProductService


@click.command("seed-db")
@with_appcontext
def seed_db():
    """Carga el catálogo predeterminado y un cliente API."""
    created = ProductService.seed_default_catalog()
    click.echo(f"Catálogo: {created} productos nuevos.")

    if not ApiClient.query.filter_by(name="default-integration").first():
        client, raw_key = ApiClient.create(name="default-integration")
        db.session.add(client)
        db.session.commit()
        click.echo(f"API key (guardala — se muestra una sola vez): {raw_key}")
    else:
        click.echo("Cliente API ya existe.")

    click.echo("Seed completo.")


@click.command("encrypt-sensitive-data")
@with_appcontext
def encrypt_sensitive_data():
    """Cifra datos sensibles existentes (usuarios, pagos, clientes, logs)."""
    from app.data_encryption import migrate_all_sensitive_data

    counts = migrate_all_sensitive_data()
    click.echo(f"Datos cifrados: {counts}")


def init_app(app):
    app.cli.add_command(seed_db)
    app.cli.add_command(encrypt_sensitive_data)
