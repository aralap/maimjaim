"""Cifrado de datos sensibles en reposo (Fernet / AES)."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

ENC_PREFIX = "enc:v1:"


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    raw = settings.data_encryption_key.strip()
    if raw:
        key = raw.encode() if isinstance(raw, str) else raw
    else:
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def make_lookup(value: str) -> str:
    """Hash irreversible para búsquedas (email, google sub)."""
    normalized = value.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def is_encrypted(value: str | None) -> bool:
    return bool(value and value.startswith(ENC_PREFIX))


def encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    if is_encrypted(value):
        return value
    token = _fernet().encrypt(value.encode()).decode()
    return f"{ENC_PREFIX}{token}"


def decrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not is_encrypted(value):
        return value
    token = value[len(ENC_PREFIX) :].encode()
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken:
        return value


def encrypt_int(value: int | None) -> str | None:
    if value is None:
        return None
    return encrypt_text(str(value))


def decrypt_int(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if not is_encrypted(value):
        return int(value)
    plain = decrypt_text(value)
    return int(plain) if plain is not None else 0


def encrypt_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return encrypt_text(payload) or ""


def decrypt_json(value: str | dict | list | None) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if not is_encrypted(value):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
    plain = decrypt_text(value)
    if not plain:
        return {}
    return json.loads(plain)
