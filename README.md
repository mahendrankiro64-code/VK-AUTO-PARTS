# VK Auto Parts — Inventory & Invoicing System

A complete inventory and invoicing web app built for VK Auto Parts: item management with
auto-generated item codes, purchase entry, cash/credit/online sales invoicing, day-end cash
reconciliation, customer credit ledgers, reports, and Excel/Google Sheets import & export.

Built with Flask + SQLite (Python's built-in database) — no paid services required, and it
can be hosted for free.

## What's included

- **Inventory**: add/edit parts with auto item codes (`VKAP-0001`, `VKAP-0002`, ...), categories,
  brand, cost/selling price, stock levels, low-stock alerts.
- **Purchases**: record stock purchases from suppliers; stock and cost price update automatically.
- **Sales / Invoicing**: create invoices with multiple line items, pick cash, credit, or online
  payment, auto stock deduction, printable invoice.
- **Day-End Closing**: opening balance carries over from yesterday's close automatically; the
  system tallies cash/credit/online sales and credit collections through the day and shows the
  expected cash in the drawer versus what you actually count.
- **Customers**: walk-in or credit customers, credit limits, running balance due, payment history.
- **Suppliers**: supplier list with outstanding balances.
- **Reports**: sales, stock, purchases, customer ledger, and day-end history — every report can
  be exported to Excel.
- **Excel / Google Sheets**: bulk-upload items, customers, and purchase entries from a spreadsheet;
  download ready-made templates from the Excel page in the app.
- **Users**: admin and cashier roles; admins manage staff logins.

## Running it locally (fastest way to try it)

Requirements: Python 3.9+

```bash
cd vk_auto_parts
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

**Default login:** username `admin`, password `admin123` — change this immediately from the
Users page (top menu → More → Users) or create a new admin user and disable this one.

The database is a single file at `instance/vkap.db`. Back it up regularly (just copy that file).

## Deploying for free so you can use it from anywhere (PythonAnywhere)

Render and Railway's free tiers wipe your database file every time the app restarts, which
would erase your sales history — not acceptable for real bookkeeping. **PythonAnywhere's free
tier gives you persistent storage** (your `vkap.db` file survives restarts), so that's what
these instructions use.

1. Create a free account at https://www.pythonanywhere.com (choose the "Beginner" plan — it's free).
2. Open a **Bash console** from the PythonAnywhere dashboard and upload this project, e.g.:
   ```bash
   git clone <your-repo-url> vk_auto_parts   # or upload the zip via the Files tab and unzip it
   cd vk_auto_parts
   pip install --user -r requirements.txt
   ```
3. Go to the **Web** tab → **Add a new web app** → choose **Flask** → pick a recent Python version.
4. When asked for the Flask app's path, point it at `/home/<your-username>/vk_auto_parts/app.py`.
5. Open the generated WSGI configuration file (linked at the top of the Web tab) and make sure it
   imports the app object, e.g.:
   ```python
   import sys
   path = '/home/<your-username>/vk_auto_parts'
   if path not in sys.path:
       sys.path.append(path)
   from app import app as application
   ```
6. Set the **Working directory** to `/home/<your-username>/vk_auto_parts`.
7. Click the green **Reload** button on the Web tab. Your shop system is now live at
   `https://<your-username>.pythonanywhere.com`, reachable from any phone or computer.
8. Log in with `admin` / `admin123` and change the password right away.

To update the app later, just re-upload changed files (or `git pull`) and hit **Reload** again.

### Alternative: Render / Railway (if you don't mind paying a small amount for a persistent disk)

Both support Flask out of the box. On their free tiers the filesystem resets on every deploy or
restart, so you'd lose all your data — only use these if you add a paid "persistent disk" add-on,
or switch `VKAP_DB_PATH` (see below) to an external database instead of SQLite.

## Excel & Google Sheets

This app does not connect live to Google's servers — that requires setting up a Google Cloud
OAuth application, which is a lot of overhead for a small shop. Instead:

- **Importing from Google Sheets**: In Google Sheets, go to File → Download → Microsoft Excel
  (.xlsx), then upload that file on the app's Excel page (top menu → More → Excel Import/Export).
- **Exporting to Google Sheets**: Export any report to Excel from the app, then in Google Sheets
  use File → Import → Upload to bring that file in.
- Ready-made column templates for Items, Customers, and Purchases are available for download on
  the Excel page so you know exactly what headings to use.

## Day-end workflow, explained

1. Each morning, the system automatically opens "today" with an opening balance equal to
   yesterday's actual closing cash count (or 0 on day one).
2. Throughout the day, every cash/credit/online sale updates the day's running totals
   automatically — no manual entry needed.
3. If a credit customer pays off part of their balance in cash, record it from their customer
   page; it's automatically added to the day's credit collections.
4. At close of business, go to **Day End**, enter any cash expenses paid out of the drawer, count
   the actual cash in the drawer, and click **Close Day**. The system shows you the difference
   between what was expected and what you actually counted.
5. Once closed, that day's record is locked and appears in Day-End History (and it becomes
   tomorrow's opening balance automatically).

## Customizing

- **Currency**: edit `fmt_money()` in `helpers.py` (defaults to `Rs.` — change to your currency
  symbol).
- **Item code prefix**: edit the `"VKAP"` prefix in `items_bp.py` / `excel_io.py` if you want a
  different prefix.
- **Categories**: nine automotive categories are seeded on first run (Engine Parts, Brake Parts,
  Electrical, etc.) — add/edit these from Inventory → Categories.
- **Database location**: set the `VKAP_DB_PATH` environment variable to change where the SQLite
  file lives (useful for backups or migrating hosts).

## Security notes before going live

- Change the default `admin` / `admin123` login immediately (Users page).
- Set a real `VKAP_SECRET_KEY` environment variable to a long random string before deploying
  publicly (used to sign login sessions). Example: `export VKAP_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"`.
- Debug mode is off by default. Only set `VKAP_DEBUG=1` while developing on your own machine —
  never on a public deployment, since it exposes a browser-based debugger that can run code.

## Project structure

```
vk_auto_parts/
├── app.py                 # App entrypoint, blueprint registration, seed data
├── db.py                  # SQLite connection helper + auto-sequence codes
├── auth.py                # Login/session auth, user management
├── helpers.py              # Shared helpers (money formatting, day-end math)
├── dashboard_bp.py         # Dashboard
├── items_bp.py             # Inventory
├── customers_bp.py         # Customers + credit ledger
├── suppliers_bp.py         # Suppliers
├── purchases_bp.py         # Purchase entry
├── sales_bp.py              # Invoicing / sales
├── dayend_bp.py             # Day-end closing
├── reports_bp.py            # Reports + Excel export
├── excel_io.py               # Excel/Google Sheets import + templates
├── schema.sql                 # Database schema
├── templates/                  # HTML templates (Bootstrap 5)
├── static/                      # CSS
└── requirements.txt
```
