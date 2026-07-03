# MaimJaim

Stock, inventory, and order management system built with Flask, Google OAuth, and PostgreSQL.

## Features

- **Google OAuth** for staff/admin authentication
- **Product catalog** with SKU-level variants
- **Inventory management** with on-hand, reserved, and available quantities
- **Order lifecycle**: draft → confirmed → fulfilled → cancelled
- **Audit trail** via inventory movement ledger
- **REST API** (`/api/v1`) with API key auth for future WhatsApp and external integrations
- **Server-rendered UI** with Jinja2, Tailwind CSS, and HTMX

## Prerequisites

- Python 3.11+
- PostgreSQL 16+

## Setup

1. **Create database**

```bash
createdb maimjaim
# Or with psql:
# CREATE USER maimjaim WITH PASSWORD 'maimjaim';
# CREATE DATABASE maimjaim OWNER maimjaim;
```

2. **Virtual environment and dependencies**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Environment variables**

```bash
cp .env.example .env
# Edit .env with your SECRET_KEY, DATABASE_URL, and Google OAuth credentials
```

4. **Google OAuth**

- Create a project in [Google Cloud Console](https://console.cloud.google.com/)
- Configure OAuth consent screen
- Create OAuth 2.0 Web Client credentials
- Set authorized redirect URI: `http://localhost:5000/auth/callback`
- Copy Client ID and Secret to `.env`

5. **Database migrations**

```bash
export FLASK_APP=wsgi.py
flask db init          # first time only
flask db migrate -m "Initial schema"
flask db upgrade
flask seed-db
```

6. **Run the app**

```bash
flask --app wsgi run --debug
```

Visit http://localhost:5000 and sign in with Google.

## Testing with ngrok

To expose the app publicly (e.g. for Google OAuth or WhatsApp webhooks):

**Terminal 1 — Flask (port must match ngrok target):**

```bash
flask --app wsgi run --debug --port 5000
```

**Terminal 2 — ngrok (tunnel to the same port Flask uses):**

```bash
# macOS: use 127.0.0.1, not localhost — port 5000 is often taken by AirPlay Receiver
ngrok http --url=steady-beetle-alert.ngrok-free.app 127.0.0.1:5000
```

> **403 Forbidden via ngrok?** On macOS, `localhost:5000` may hit AirPlay instead of Flask.
> Use `127.0.0.1:5000` in ngrok, or run Flask on another port (e.g. `5001`) and tunnel that.
> You can also disable **AirPlay Receiver** in System Settings → General → AirDrop & Handoff.

**`.env` for ngrok:**

```env
OAUTH_REDIRECT_URI=https://steady-beetle-alert.ngrok-free.app/auth/callback
TRUST_PROXY=true
```

**Google Cloud Console:** add this authorized redirect URI:

`https://steady-beetle-alert.ngrok-free.app/auth/callback`

Then open https://steady-beetle-alert.ngrok-free.app in the browser.

> If you use `ngrok http ... 80`, run Flask on port 80 instead (`flask --app wsgi run --port 80`, may require `sudo` on macOS). The ngrok port and Flask port must match.

## API Usage

After running `flask seed-db`, an API key is printed once. Use it for machine-to-machine calls:

```bash
curl -H "Authorization: Bearer mj_..." http://localhost:5000/api/v1/inventory

curl -X POST http://localhost:5000/api/v1/orders \
  -H "Authorization: Bearer mj_..." \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "whatsapp-msg-001",
    "source": "whatsapp",
    "customer": {"name": "John", "phone": "+1234567890"},
    "lines": [{"sku": "SHIRT-M-BLUE", "quantity": 1}],
    "auto_confirm": true
  }'
```

## Testing

```bash
pytest
```

## Project Structure

```
app/
├── models/       # SQLAlchemy models
├── services/     # Domain logic (inventory, orders, products)
├── web/          # Server-rendered routes
├── api/v1/       # REST API endpoints
└── templates/    # Jinja2 templates
```

## Roles

- **admin**: manage products, adjust inventory, create/fulfill orders
- **staff**: create and fulfill orders

Set admin emails via `ADMIN_EMAILS` in `.env` (comma-separated).

## Production

- Run with Gunicorn: `gunicorn -w 4 wsgi:app`
- Set `FLASK_ENV=production` and use HTTPS
- Update Google OAuth redirect URI for your domain
