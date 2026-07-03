-- VK Auto Parts - Inventory & Invoicing System
-- PostgreSQL schema (works with Supabase, Render Postgres, Fly Postgres, etc.)

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'cashier',   -- 'admin' or 'cashier'
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

-- Per-feature staff permissions (admins always have every permission,
-- regardless of these flags -- see auth.py permission_required()).
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_sales INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_purchases INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_items INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_customers INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_suppliers INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_reports INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_accounts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_dayend INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_quotations INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS perm_cancel INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    prefix TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS racks (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    item_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER,
    brand TEXT,
    unit TEXT DEFAULT 'pcs',
    cost_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    selling_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    stock_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
    reorder_level DOUBLE PRECISION NOT NULL DEFAULT 5,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Rack + row shop location, so staff can physically find a part fast.
-- The barcode printed/scanned for every item is simply its item_code
-- (already unique and auto-generated), rendered as a Code128 barcode --
-- no separate barcode column needed.
ALTER TABLE items ADD COLUMN IF NOT EXISTS rack_id INTEGER REFERENCES racks(id);
ALTER TABLE items ADD COLUMN IF NOT EXISTS row_location TEXT;

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_code TEXT UNIQUE,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    customer_type TEXT NOT NULL DEFAULT 'walkin',  -- 'walkin' or 'credit'
    credit_limit DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance_due DOUBLE PRECISION NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    supplier_code TEXT UNIQUE,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    balance_due DOUBLE PRECISION NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    purchase_no TEXT UNIQUE NOT NULL,
    supplier_id INTEGER,
    purchase_date TEXT NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    payment_status TEXT NOT NULL DEFAULT 'unpaid', -- 'paid','unpaid','partial'
    amount_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id SERIAL PRIMARY KEY,
    purchase_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    cost_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER,
    invoice_date TEXT NOT NULL,       -- full timestamp
    business_date TEXT NOT NULL,      -- date only, for day-end grouping
    subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
    discount DOUBLE PRECISION NOT NULL DEFAULT 0,
    tax DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    payment_mode TEXT NOT NULL DEFAULT 'cash',  -- 'cash','credit','online'
    amount_paid DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed',   -- 'completed','cancelled'
    created_by INTEGER,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Snapshot of the item's cost price at the moment of sale, so profit
-- calculations stay accurate even after cost_price later changes.
ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS cost_price_at_sale DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS quotations (
    id SERIAL PRIMARY KEY,
    quotation_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER,
    quotation_date TEXT NOT NULL,
    valid_until TEXT,
    subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
    discount DOUBLE PRECISION NOT NULL DEFAULT 0,
    tax DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',   -- 'open', 'converted', 'cancelled'
    converted_invoice_id INTEGER,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (converted_invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quotation_items (
    id SERIAL PRIMARY KEY,
    quotation_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    invoice_id INTEGER,
    amount DOUBLE PRECISION NOT NULL,
    payment_date TEXT NOT NULL,
    payment_mode TEXT NOT NULL DEFAULT 'cash',
    notes TEXT,
    created_by INTEGER,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);

CREATE TABLE IF NOT EXISTS day_end (
    id SERIAL PRIMARY KEY,
    business_date TEXT UNIQUE NOT NULL,
    opening_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
    cash_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
    credit_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
    online_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
    credit_collections DOUBLE PRECISION NOT NULL DEFAULT 0,   -- cash received against old credit dues
    expenses DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_sales DOUBLE PRECISION NOT NULL DEFAULT 0,
    closing_balance_expected DOUBLE PRECISION NOT NULL DEFAULT 0,
    closing_balance_actual DOUBLE PRECISION,
    difference DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'open',   -- 'open' or 'closed'
    notes TEXT,
    opened_by INTEGER,
    closed_by INTEGER,
    opened_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    closed_at TEXT,
    FOREIGN KEY (opened_by) REFERENCES users(id),
    FOREIGN KEY (closed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    expense_date TEXT NOT NULL,
    category_id INTEGER,
    description TEXT,
    amount DOUBLE PRECISION NOT NULL,
    payment_mode TEXT NOT NULL DEFAULT 'cash',
    created_by INTEGER,
    created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
    FOREIGN KEY (category_id) REFERENCES expense_categories(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_invoices_business_date ON invoices(business_date);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_quotations_status ON quotations(status);
