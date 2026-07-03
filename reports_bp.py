import io
import pandas as pd
from flask import Blueprint, render_template, request, send_file
from db import get_db
from auth import login_required
from helpers import today_str

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _date_range():
    date_from = request.args.get("from") or today_str()
    date_to = request.args.get("to") or today_str()
    return date_from, date_to


@bp.route("/")
@login_required
def index():
    return render_template("reports/index.html", today=today_str())


@bp.route("/sales")
@login_required
def sales_report():
    db = get_db()
    date_from, date_to = _date_range()
    rows = db.execute(
        """SELECT inv.invoice_no, inv.invoice_date, inv.business_date,
                  COALESCE(c.name,'Walk-in') AS customer_name, inv.payment_mode,
                  inv.subtotal, inv.discount, inv.tax, inv.total_amount,
                  inv.amount_paid, inv.balance, inv.status
           FROM invoices inv LEFT JOIN customers c ON c.id = inv.customer_id
           WHERE inv.business_date BETWEEN ? AND ?
           ORDER BY inv.invoice_date""",
        (date_from, date_to),
    ).fetchall()

    if request.args.get("export") == "xlsx":
        df = pd.DataFrame([dict(r) for r in rows])
        return _export_xlsx(df, f"sales_report_{date_from}_to_{date_to}.xlsx")

    totals = {
        "count": len(rows),
        "total_amount": sum(r["total_amount"] for r in rows if r["status"] == "completed"),
        "cash": sum(r["total_amount"] for r in rows if r["payment_mode"] == "cash" and r["status"] == "completed"),
        "credit": sum(r["total_amount"] for r in rows if r["payment_mode"] == "credit" and r["status"] == "completed"),
        "online": sum(r["total_amount"] for r in rows if r["payment_mode"] == "online" and r["status"] == "completed"),
    }
    return render_template(
        "reports/sales.html", rows=rows, date_from=date_from, date_to=date_to, totals=totals
    )


@bp.route("/stock")
@login_required
def stock_report():
    db = get_db()
    low_only = request.args.get("low_stock") == "1"
    sql = """SELECT i.item_code, i.name, c.name AS category_name, i.brand, i.unit,
                     i.cost_price, i.selling_price, i.stock_qty, i.reorder_level,
                     (i.stock_qty * i.cost_price) AS stock_value
              FROM items i LEFT JOIN categories c ON c.id = i.category_id
              WHERE i.active=1"""
    if low_only:
        sql += " AND i.stock_qty <= i.reorder_level"
    sql += " ORDER BY i.name"
    rows = db.execute(sql).fetchall()

    if request.args.get("export") == "xlsx":
        df = pd.DataFrame([dict(r) for r in rows])
        return _export_xlsx(df, "stock_report.xlsx")

    total_stock_value = sum(r["stock_value"] for r in rows)
    return render_template(
        "reports/stock.html", rows=rows, low_only=low_only, total_stock_value=total_stock_value
    )


@bp.route("/purchases")
@login_required
def purchases_report():
    db = get_db()
    date_from, date_to = _date_range()
    rows = db.execute(
        """SELECT p.purchase_no, p.purchase_date, COALESCE(s.name,'-') AS supplier_name,
                  p.total_amount, p.payment_status, p.amount_paid
           FROM purchases p LEFT JOIN suppliers s ON s.id = p.supplier_id
           WHERE p.purchase_date BETWEEN ? AND ?
           ORDER BY p.purchase_date""",
        (date_from, date_to),
    ).fetchall()

    if request.args.get("export") == "xlsx":
        df = pd.DataFrame([dict(r) for r in rows])
        return _export_xlsx(df, f"purchases_report_{date_from}_to_{date_to}.xlsx")

    total = sum(r["total_amount"] for r in rows)
    return render_template(
        "reports/purchases.html", rows=rows, date_from=date_from, date_to=date_to, total=total
    )


@bp.route("/customer-ledger")
@login_required
def customer_ledger():
    db = get_db()
    rows = db.execute(
        """SELECT customer_code, name, phone, customer_type, credit_limit, balance_due
           FROM customers WHERE active=1 ORDER BY balance_due DESC"""
    ).fetchall()

    if request.args.get("export") == "xlsx":
        df = pd.DataFrame([dict(r) for r in rows])
        return _export_xlsx(df, "customer_ledger.xlsx")

    total_due = sum(r["balance_due"] for r in rows)
    return render_template("reports/customer_ledger.html", rows=rows, total_due=total_due)


@bp.route("/dayend-history")
@login_required
def dayend_history_report():
    db = get_db()
    rows = db.execute("SELECT * FROM day_end ORDER BY business_date DESC LIMIT 365").fetchall()
    if request.args.get("export") == "xlsx":
        df = pd.DataFrame([dict(r) for r in rows])
        return _export_xlsx(df, "dayend_history.xlsx")
    return render_template("reports/dayend_history.html", rows=rows)


def _export_xlsx(df, filename):
    buf = io.BytesIO()
    if df.empty:
        df = pd.DataFrame({"note": ["No data for the selected range"]})
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
