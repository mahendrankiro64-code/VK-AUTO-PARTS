# VK Auto Parts — Inventory & Invoicing System

A complete inventory and invoicing web app built for VK Auto Parts: item management with
auto-generated item codes, purchase entry, cash/credit/online sales invoicing, day-end cash
reconciliation, customer credit ledgers, reports, and Excel/Google Sheets import & export.

Built with Flask + PostgreSQL — no paid software required, and it can be hosted for free using
Supabase (free Postgres database) plus Render (free web hosting). This combination was chosen
specifically so the app isn't tied to one host's local disk: Netlify and Firebase Hosting were
considered too, but neither can run a persistent Python server with a database attached (Netlify
only serves static pages + short-lived functions; Firebase's Cloud Run option requires a Google
Cloud billing account and doesn't keep local files between requests). Postgres + Render sidesteps
both problems for free.

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

## Step 1 — Create your free database (Supabase)

1. Go to https://supabase.com and sign up for a free account (no credit card required).
2. Click **New Project**. Pick any name/region, and set a database password — write this down,
   you'll need it in the connection string.
3. Once the project is ready, click the **Connect** button near the top of the project page.
4. You'll see several connection string options. Copy the one labeled **Session pooler** (not
   "Direct connection") — it looks like:
   ```
   postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-xx-xxxx-1.pooler.supabase.com:5432/postgres
   ```
   The session pooler is the one to use here because free hosts like Render only give your app an
   IPv4 address, and Supabase's direct connection requires IPv6 (or a paid IPv4 add-on) — the
   pooler works over IPv4 with no extra cost.
5. Replace `[YOUR-PASSWORD]` in that string with the database password you set in step 2. This
   full string is your `DATABASE_URL` — you'll paste it into Render in Step 2 below.

One thing worth knowing: **a free Supabase project pauses itself after 7 days with no database
activity** (a dashboard button un-pauses it in seconds, no data is lost). For a shop that's used
most days this is a non-issue. If you close for a longer stretch, just open the Supabase dashboard
before you reopen — or set up a free uptime monitor (e.g. UptimeRobot) to ping your site every so
often, which keeps both Render and Supabase awake.

## Step 2 — Put the code on GitHub

Render deploys from a Git repository, so the code needs to live on GitHub (also free):

1. Create a new repository at https://github.com/new (can be private).
2. Upload this project's files to it — either drag-and-drop the extracted folder contents on the
   GitHub web page ("uploading an existing file"), or if you're comfortable with git:
   ```bash
   cd vk_auto_parts
   git init
   git add .
   git commit -m "VK Auto Parts inventory & invoicing system"
   git remote add origin https://github.com/YOURUSERNAME/vk-auto-parts.git
   git push -u origin main
   ```

## Step 3 — Deploy for free on Render

1. Go to https://render.com and sign up for free (no credit card required for the free tier).
2. Connect your GitHub account, then click **New +** → **Web Service**, and pick the repo you
   just created.
3. Fill in:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Free
4. Under **Environment Variables**, add:
   - `DATABASE_URL` — the Supabase connection string from Step 1
   - `VKAP_SECRET_KEY` — any long random string (e.g. generate one with
     `python3 -c "import secrets; print(secrets.token_hex(32))"`)
5. Click **Create Web Service**. Render will install everything and start the app — the first
   deploy takes a few minutes. Once it's live, your shop system is reachable at the
   `https://your-app-name.onrender.com` URL Render shows you.
6. Log in with `admin` / `admin123` and change that password immediately (Users page).

Render's free web services go to sleep after 15 minutes with no visitors and take 30-60 seconds
to wake back up on the next visit — completely normal for a free tier, and once it's open in a
browser tab during the day it stays responsive.

To update the app later: push new commits to GitHub (`git push`) and Render redeploys automatically.

### Trying it locally before you deploy

You can run the exact same app on your own computer first, pointed at the same free Supabase
database (or a separate one for testing):

```bash
cd vk_auto_parts
pip install -r requirements.txt
export DATABASE_URL="postgresql://...your Supabase connection string..."
export VKAP_SECRET_KEY="any-random-string-for-local-testing"
python app.py
```

Open http://localhost:5000. First run automatically creates all the tables and the default
`admin` / `admin123` login.

### Alternative host: Fly.io

Fly.io's free allowance also works well and follows the same idea — connect it to the same
Supabase `DATABASE_URL` and `VKAP_SECRET_KEY` environment variables, and it will run this app
with no code changes. Render was used above simply because it needs no command-line tool and no
credit card to get started.

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
- **Database**: everything lives in the Postgres database pointed to by `DATABASE_URL`. To move
  to a different Postgres provider later (Render's own Postgres, Neon, Fly Postgres, etc.), just
  change that one environment variable — no code changes needed.

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
├── db.py                  # Postgres (psycopg2) connection helper + auto-sequence codes
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
├── schema.sql                 # Database schema (PostgreSQL dialect)
├── templates/                  # HTML templates (Bootstrap 5)
├── static/                      # CSS
├── Procfile                      # web: gunicorn app:app (used by Render/Fly/Heroku-style hosts)
└── requirements.txt
```

## A note on how this was tested

This sandbox environment's network is locked down to a small allowlist and can't reach PyPI,
apt's package mirrors, or Supabase directly, so I couldn't install the real `psycopg2` driver or
spin up a live Postgres server to test against here. Instead I built a drop-in stand-in for
psycopg2 (backed by SQLite, translating the same SQL calls) and ran the full test suite — login,
add items, purchase entry, a credit sale, invoice view/cancel, day-end open/close, Excel
import/export — against that. Every one of those passed. This gives strong confidence in the
Python-side logic (query wiring, the new `RETURNING id` handling, placeholder translation), but
it isn't a substitute for hitting your real Supabase database once. After you deploy, please run
through: log in, add one item, make one test sale, and check the dashboard updates — if anything
looks off, send me the error and I'll fix it fast.
