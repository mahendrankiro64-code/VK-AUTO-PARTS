from datetime import date, timedelta

from flask import Blueprint, render_template, g, request
from db import get_db
from auth import login_required
from helpers import today_str, get_or_create_open_dayend, recompute_dayend_totals

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    db = get_db()
    biz_date = today_str()

    trend_days = request.args.get("days", "14")
    trend_days = int(trend_days) if trend_days in ("7", "14", "30") else 14
    start_date = date.today() - timedelta(days=trend_days - 1)
    trend_rows = db.execute(
        """SELECT business_date, COALESCE(SUM(total_amount), 0) AS total
           FROM invoices WHERE status='completed' AND business_date >= ?
           GROUP BY business_date""",
        (start_date.isoformat(),),
    ).fetchall()
    trend_map = {r["business_date"]: r["total"] for r in trend_rows}
    trend_labels = []
    trend_values = []
    for i in range(trend_days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        trend_labels.append(d.strftime("%b %d"))
        trend_values.append(trend_map.get(d.isoformat(), 0))

    de = get_or_create_open_dayend(db, opened_by=g.user["id"] if g.user else None)
    de = recompute_dayend_totals(db, de["business_date"]) or de

    invoice_count_today = db.execute(
        "SELECT COUNT(*) c FROM invoices WHERE business_date=? AND status='completed'",
        (biz_date,),
    ).fetchone()["c"]

    low_stock = db.execute(
        "SELECT * FROM items WHERE active=1 AND stock_qty <= reorder_level ORDER BY stock_qty ASC LIMIT 10"
    ).fetchall()
    low_stock_count = db.execute(
        "SELECT COUNT(*) c FROM items WHERE active=1 AND stock_qty <= reorder_level"
    ).fetchone()["c"]

    total_credit_due = db.execute(
        "SELECT COALESCE(SUM(balance_due),0) t FROM customers WHERE active=1"
    ).fetchone()["t"]

    recent_invoices = db.execute(
        """SELECT inv.*, COALESCE(c.name,'Walk-in') AS customer_name FROM invoices inv
           LEFT JOIN customers c ON c.id = inv.customer_id
           WHERE inv.status='completed' ORDER BY inv.id DESC LIMIT 8"""
    ).fetchall()

    item_count = db.execute("SELECT COUNT(*) c FROM items WHERE active=1").fetchone()["c"]
    customer_count = db.execute("SELECT COUNT(*) c FROM customers WHERE active=1").fetchone()["c"]

    return render_template(
        "dashboard.html",
        de=de,
        invoice_count_today=invoice_count_today,
        low_stock=low_stock,
        low_stock_count=low_stock_count,
        total_credit_due=total_credit_due,
        recent_invoices=recent_invoices,
        item_count=item_count,
        customer_count=customer_count,
        trend_labels=trend_labels,
        trend_values=trend_values,
        trend_days=trend_days,
    )
