"""Shared helper functions used across blueprints."""
from datetime import datetime, date


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_money(value):
    try:
        return f"Rs. {float(value):,.2f}"
    except (TypeError, ValueError):
        return "Rs. 0.00"


def get_or_create_open_dayend(db, opened_by=None):
    """Return today's day_end row, creating an 'open' one if missing.

    Opening balance defaults to yesterday's closing balance (actual if set,
    otherwise expected), or 0 if there is no prior day-end record at all.
    """
    biz_date = today_str()
    row = db.execute(
        "SELECT * FROM day_end WHERE business_date = ?", (biz_date,)
    ).fetchone()
    if row:
        return row

    prev = db.execute(
        "SELECT * FROM day_end WHERE business_date < ? ORDER BY business_date DESC LIMIT 1",
        (biz_date,),
    ).fetchone()
    opening = 0.0
    if prev:
        opening = prev["closing_balance_actual"] if prev["closing_balance_actual"] is not None else prev["closing_balance_expected"]

    db.execute(
        "INSERT INTO day_end (business_date, opening_balance, opened_by) VALUES (?,?,?)",
        (biz_date, opening, opened_by),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM day_end WHERE business_date = ?", (biz_date,)
    ).fetchone()


def recompute_dayend_totals(db, business_date):
    """Recalculate cash/credit/online sales + credit collections for a date
    from the underlying invoices/payments tables and update day_end row."""
    sales = db.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN payment_mode='cash' THEN total_amount ELSE 0 END),0) AS cash_sales,
            COALESCE(SUM(CASE WHEN payment_mode='credit' THEN total_amount ELSE 0 END),0) AS credit_sales,
            COALESCE(SUM(CASE WHEN payment_mode='online' THEN total_amount ELSE 0 END),0) AS online_sales
           FROM invoices WHERE business_date = ? AND status = 'completed'""",
        (business_date,),
    ).fetchone()

    collections = db.execute(
        """SELECT COALESCE(SUM(amount),0) AS total FROM payments
           WHERE payment_date = ? AND payment_mode = 'cash'""",
        (business_date,),
    ).fetchone()

    de = db.execute(
        "SELECT * FROM day_end WHERE business_date = ?", (business_date,)
    ).fetchone()
    if not de:
        return None

    total_sales = sales["cash_sales"] + sales["credit_sales"] + sales["online_sales"]
    expected_cash = (de["opening_balance"] or 0) + sales["cash_sales"] + collections["total"] - (de["expenses"] or 0)

    db.execute(
        """UPDATE day_end SET cash_sales=?, credit_sales=?, online_sales=?,
           credit_collections=?, total_sales=?, closing_balance_expected=?
           WHERE business_date=?""",
        (
            sales["cash_sales"], sales["credit_sales"], sales["online_sales"],
            collections["total"], total_sales, expected_cash, business_date,
        ),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM day_end WHERE business_date = ?", (business_date,)
    ).fetchone()
