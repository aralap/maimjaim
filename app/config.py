import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-key"
    database_url: str = "postgresql+psycopg://maimjaim:maimjaim@localhost:5432/maimjaim"
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:5000/auth/callback"
    allowed_email_domain: str = ""
    admin_emails: str = ""
    flask_env: str = "development"
    # Clave Fernet (base64, 32 bytes). Generar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: str = ""
    # Set to true when running behind ngrok/reverse proxy (reads X-Forwarded-* headers)
    trust_proxy: bool = False

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_development() -> bool:
    return get_settings().flask_env == "development" or os.getenv("FLASK_DEBUG") == "1"
