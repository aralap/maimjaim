"""Helpers for peso form fields stored as integer cents."""


def pesos_to_cents(value, *, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    cents = int(round(float(value) * 100))
    if cents < 0:
        raise ValueError("El precio no puede ser negativo")
    return cents


def optional_pesos_to_cents(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return pesos_to_cents(value)
