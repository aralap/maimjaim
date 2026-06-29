from functools import wraps

from flask import g, jsonify, request

from app.models import ApiClient


def get_api_key_from_request() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.headers.get("X-API-Key")


def api_key_required(scope: str | None = None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            raw_key = get_api_key_from_request()
            if not raw_key:
                return jsonify({"error": "Missing API key"}), 401

            clients = ApiClient.query.filter_by(is_active=True).all()
            client = next((c for c in clients if c.verify_key(raw_key)), None)
            if not client:
                return jsonify({"error": "Invalid API key"}), 401

            if scope and not client.has_scope(scope):
                return jsonify({"error": f"Missing scope: {scope}"}), 403

            g.api_client = client
            return view(*args, **kwargs)

        return wrapped

    return decorator
