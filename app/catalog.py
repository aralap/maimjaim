"""Catálogo predeterminado de productos Maim Jaim."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogItem:
    sku: str
    name: str
    category: str
    unit: str
    reorder_point: int
    supplier: str
    notes: str = ""
    price_cents: int = 0
    cost_cents: int = 0
    initial_stock: int = 0
    is_active: bool = True


DEFAULT_CATEGORIES = [
    "Lechugas",
    "Hojas verdes",
    "Hierbas aromáticas",
    "Proceso / Servicio",
]

DEFAULT_CATALOG: list[CatalogItem] = [
    CatalogItem("VEG-001", "Lechuga francesa", "Lechugas", "unidad", 10, "Maim Jaim", "Lavada y revisada"),
    CatalogItem("VEG-002", "Lechuga morada", "Lechugas", "unidad", 10, "Maim Jaim", "Lavada y revisada"),
    CatalogItem("VEG-003", "Rúcula", "Hojas verdes", "atado", 10, "Maim Jaim", "Cultivo hidropónico"),
    CatalogItem("VEG-004", "Albahaca", "Hierbas aromáticas", "atado", 8, "Maim Jaim", "Aromática"),
    CatalogItem("VEG-005", "Kale", "Hojas verdes", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-006", "Mantecosa", "Lechugas", "unidad", 10, "Maim Jaim", "Lechuga mantecosa"),
    CatalogItem("VEG-007", "Espinaca", "Hojas verdes", "atado", 10, "Maim Jaim"),
    CatalogItem("VEG-008", "Acelga", "Hojas verdes", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-009", "Perejil", "Hierbas aromáticas", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-010", "Cebollita de verdeo", "Hierbas aromáticas", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-011", "Ciboulette", "Hierbas aromáticas", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-012", "Berro", "Hojas verdes", "atado", 8, "Maim Jaim"),
    CatalogItem("VEG-013", "Menta", "Hierbas aromáticas", "atado", 8, "Maim Jaim", "Aromática"),
    CatalogItem(
        "PROC-001", "Lechuga francesa Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-002", "Lechuga morada Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-003", "Rúcula Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-004", "Albahaca Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-005", "Kale Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-006", "Mantecosa Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-007", "Espinaca Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-008", "Acelga Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-009", "Perejil Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-010", "Cebollita de verdeo Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-011", "Ciboulette Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-012", "Berro Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
    CatalogItem(
        "PROC-013", "Menta Revisada", "Proceso / Servicio", "servicio", 0, "Maim Jaim",
        "Producto/servicio para registrar el lavado y revisión",
    ),
]
