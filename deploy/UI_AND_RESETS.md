# UI refresh and administrative resets

This update adds a responsive sidebar, a dashboard with delivery and stock summaries,
search on product/client/order/inventory lists, and administrative maintenance controls.
The application UI remains in Spanish. Tailwind and HTMX are served locally; the UI does
not depend on a CDN request or a runtime CSS compiler.

## What administrators can do

Go to **Administración → Restablecer datos** (also available from Inventario and Pedidos).
The screen shows current counts and requires a reason and the exact confirmation word
`RESTABLECER` before accepting a POST request.

| Option | Stock on hand | Reserved stock | Orders and their payment data |
| --- | --- | --- | --- |
| Solo stock | Set to zero | Must already be zero; confirmed orders also block this action | Preserved |
| Solo pedidos y ventas | Preserved | Released | All deleted, including drafts, confirmed, delivered and cancelled orders |
| Stock, pedidos y ventas | Set to zero | Set to zero | All deleted |

**All options preserve** product cards, categories, SKUs, prices/costs, reorder points,
client cards/contact details/preferences, users, API clients and weekly spreadsheet columns.
The weekly sheet's order rows disappear when their underlying orders are deleted;
its product column configuration stays available.

Administrators can also open a single order and choose **Eliminar este pedido…**.
That requires its order number and a reason. Confirmed orders release only their own
reservations. Physical stock stays unchanged, including when deleting a delivered sale.
For an actual returned delivery, use the existing delivery reversal workflow before
removing the order, or record a stock adjustment separately.

Resetting sales does **not** mean putting delivered goods back on the shelf. This avoids
inventing stock when clearing historical/test transactions.

## History and recovery

Inventory movements and activity logs are retained. Every reset/deletion records the acting
administrator and reason. Order movement references are marked `deleted_order` so they
cannot be mistaken for a new order if SQLite reuses an ID. These operations run in one
transaction and roll back if any part fails, including the audit entry.

There is no undo button. Retained activity history is not a database backup. Take a backup
before a real reset and choose a time when staff are not entering orders. Existing API
external IDs are deleted with orders; integrations must not replay previously processed
requests after a sales reset.

No reset is run by installing this code, and no production data is bundled in it.

## Update on PythonAnywhere

1. Review and merge the pull request into `main`.
2. In a PythonAnywhere Bash console, activate the application's existing virtual environment
   and update the checkout. The paths below match `deploy/pythonanywhere_wsgi.py`; adjust
   them if your deployed paths differ:

   ```bash
   cd /home/aralap/maimjaim/maimjaim
   source .venv/bin/activate
   git pull --ff-only origin main
   ```

3. Keep the current `.env`, database and `DATA_ENCRYPTION_KEY`. This update has **no schema
   migration or new Python dependency**. If earlier migrations have not been applied, run
   the application's normal `flask --app wsgi db upgrade` before reloading.
4. Ensure PythonAnywhere's **Web → Static files** has URL `/static/` mapped to
   `/home/aralap/maimjaim/maimjaim/app/static/` (or the corresponding real checkout path).
   Flask also serves these files when no platform mapping overrides `/static/`.
5. Click **Reload** on the Web tab and hard-refresh the browser.
6. Sign in with an approved admin. Check the dashboard, weekly planilla and the new
   maintenance page. Staff should not see maintenance controls and must receive a
   forbidden response if they attempt to access them directly.

Installing the update does not clear any data. Use the confirmation screen only when
intending to reset real operational records.

## Rebuilding browser assets (development only)

Generated files in `app/static/vendor/` are committed. No npm commands are needed on
PythonAnywhere. After adding or changing Tailwind utility classes in templates, run:

```bash
npm ci
npm run build
```

Commit the generated CSS and HTMX assets together with any template changes. Versions
are pinned in `package-lock.json`; licenses are included with the browser assets.

## Verification

Run `python -m pytest -q`. Coverage includes all order states, preserved client/catalog
fields, reservation release, transaction rollback, invalid confirmation, admin/staff/
pending access, CSRF and rendering of the updated pages. The automated database tests
use SQLite with foreign keys enabled for maintenance scenarios. PostgreSQL uses a
transactional table lock for resets, but was not exercised against a live PostgreSQL
server in this change.

Browser verification also exercised desktop (1440 px), mobile (390 px), and narrow
mobile (320 px) layouts; menu open/close, accent-insensitive search, weekly-sheet print
visibility, real CSRF-protected deletion/reset submissions, preserved product/client
counts and denial of maintenance access for staff. There were no browser JavaScript
errors. Reset submissions used only a disposable local sample database.
