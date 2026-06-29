from authlib.integrations.base_client.errors import MismatchingStateError

from app.config import Settings
from app.extensions import oauth


def oauth_app_origin(settings: Settings) -> str | None:
    """Base URL (scheme + host) derived from OAUTH_REDIRECT_URI."""
    if not settings.oauth_redirect_uri:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(settings.oauth_redirect_uri)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def oauth_app_host(settings: Settings) -> str | None:
    if not settings.oauth_redirect_uri:
        return None
    from urllib.parse import urlparse

    return urlparse(settings.oauth_redirect_uri).netloc


def google_oauth_configured(settings: Settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def register_google_oauth(settings: Settings) -> bool:
    """Register the Google OAuth client if credentials are present."""
    if not google_oauth_configured(settings):
        return False

    try:
        oauth.google
        return True
    except AttributeError:
        pass

    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return True


def exchange_google_token(client, redirect_uri: str, code: str):
    """
    Exchange authorization code for tokens.
    Falls back to direct code exchange when OAuth session state is lost (common with ngrok).
    """
    try:
        # redirect_uri is read from session state — do not pass it again here
        return client.authorize_access_token()
    except MismatchingStateError:
        pass
    except Exception as exc:
        if "state" not in str(exc).lower():
            raise

    token = client.fetch_access_token(code=code, redirect_uri=redirect_uri)
    if "userinfo" not in token:
        token["userinfo"] = client.userinfo(token=token)
    return token
