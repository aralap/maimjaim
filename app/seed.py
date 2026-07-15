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


@click.command("import-clients")
@click.option(
    "--csv",
    "csv_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Ruta al CSV privado (no lo subas al repo ni a static/).",
)
@click.option("--dry-run", is_flag=True, help="Simula sin escribir en la base.")
@click.option(
    "--update-existing",
    is_flag=True,
    help="Actualiza clientes existentes (match por teléfono): completa campos vacíos.",
)
@click.option(
    "--min-confidence",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default=None,
    help="Omitir filas con confidence menor (si el CSV tiene esa columna).",
)
@click.option("--batch-size", default=50, show_default=True, type=int)
@with_appcontext
def import_clients(csv_path, dry_run, update_existing, min_confidence, batch_size):
    """Importa clientes desde CSV. Los campos se cifran al guardar (DATA_ENCRYPTION_KEY)."""
    from app.config import get_settings
    from app.services.client_import_service import ClientImportService

    settings = get_settings()
    if not settings.data_encryption_key.strip():
        click.echo(
            "AVISO: DATA_ENCRYPTION_KEY vacío — se usa un derivado de SECRET_KEY. "
            "En producción conviene definir DATA_ENCRYPTION_KEY explícitamente.",
            err=True,
        )

    click.echo(f"CSV: {csv_path}")
    if dry_run:
        click.echo("Modo dry-run (sin cambios).")
    stats = ClientImportService.import_csv(
        csv_path,
        dry_run=dry_run,
        update_existing=update_existing,
        min_confidence=min_confidence,
        batch_size=batch_size,
    )
    click.echo(
        f"Listo — creados={stats.created} actualizados={stats.updated} "
        f"omitidos={stats.skipped} errores={stats.errors}"
    )
    for line in stats.details[:30]:
        click.echo(f"  {line}")
    if len(stats.details) > 30:
        click.echo(f"  … y {len(stats.details) - 30} más")


def init_app(app):
    app.cli.add_command(seed_db)
    app.cli.add_command(encrypt_sensitive_data)
    app.cli.add_command(import_clients)
