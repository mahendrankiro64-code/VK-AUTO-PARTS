from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db
from auth import permission_required
from helpers import today_str

bp = Blueprint("accounts", __name__, url_prefix="/accounts")


def _date_range():
    date_from = request.args.get("from") or today_str()
    date_to = request.args.get("to") or today_str()
    return date_from, date_to


@bp.route("/")
@permission_required("perm_accounts")
def dashboard():
    db = get_db()
    date_from, date_to = _date_range()

    revenue_row = db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS revenue FROM invoices
           WHERE status='completed' AND business_date BETWEEN ? AND ?""",
        (date_from, date_to),
    ).fetchone()
    revenue = revenue_row["revenue"]

    cogs_row = db.execute(
        """SELECT COALESCE(SUM(ii.qty * ii.cost_price_at_sale), 0) AS cogs
           FROM invoice_items ii
           JOIN invoices inv ON inv.id = ii.invoice_id
           WHERE inv.status='completed' AND inv.business_date BETWEEN ? AND ?""",
        (date_from, date_to),
    ).fetchone()
    cogs = cogs_row["cogs"]

    expenses_row = db.execute(
        """SELECT COALESCE(SUM(amount), 0) AS total FROM expenses
           WHERE expense_date BETWEEN ? AND ?""",
        (date_from, date_to),
    ).fetchone()
    total_expenses = expenses_row["total"]

    gross_profit = revenue - cogs
    net_profit = gross_profit - total_expenses

    expense_breakdown = db.execute(
        """SELECT COALESCE(ec.name, 'Uncategorized') AS category, SUM(e.amount) AS total
           FROM expenses e LEFT JOIN expense_categories ec ON ec.id = e.category_id
           WHERE e.expense_date BETWEEN ? AND ?
           GROUP BY ec.name ORDER BY total DESC""",
        (date_from, date_to),
    ).fetchall()

    return render_template(
        "accounts/dashboard.html", date_from=date_from, date_to=date_to,
        revenue=revenue, cogs=cogs, gross_profit=gross_profit,
        total_expenses=total_expenses, net_profit=net_profit,
        expense_breakdown=expense_breakdown,
    )


@bp.route("/expenses", methods=("GET", "POST"))
@permission_required("perm_accounts")
def expenses():
    db = get_db()
    if request.method == "POST":
        expense_date = request.form.get("expense_date") or today_str()
        category_id = request.form.get("category_id") or None
        description = request.form.get("description", "").strip()
        amount = float(request.form.get("amount") or 0)
        payment_mode = request.form.get("payment_mode", "cash")

        if amount <= 0:
            flash("Enter a valid expense amount.", "danger")
        else:
            db.execute(
                """INSERT INTO expenses (expense_date, category_id, description, amount,
                   payment_mode, created_by) VALUES (?,?,?,?,?,?)""",
                (expense_date, category_id, description, amount, payment_mode,
                 g.user["id"] if g.user else None),
            )
            db.commit()
            flash("Expense recorded.", "success")
        return redirect(url_for("accounts.expenses"))

    date_from, date_to = _date_range()
    categories = db.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()
    rows = db.execute(
        """SELECT e.*, COALESCE(ec.name, 'Uncategorized') AS category_name FROM expenses e
           LEFT JOIN expense_categories ec ON ec.id = e.category_id
           WHERE e.expense_date BETWEEN ? AND ? ORDER BY e.expense_date DESC, e.id DESC""",
        (date_from, date_to),
    ).fetchall()
    total = sum(r["amount"] for r in rows)
    return render_template(
        "accounts/expenses.html", categories=categories, rows=rows, total=total,
        date_from=date_from, date_to=date_to,
    )


@bp.route("/expense-categories", methods=("GET", "POST"))
@permission_required("perm_accounts")
def expense_categories():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            try:
                db.execute("INSERT INTO expense_categories (name) VALUES (?)", (name,))
                db.commit()
                flash("Category added.", "success")
            except Exception:
                flash("That category already exists.", "danger")
        return redirect(url_for("accounts.expense_categories"))
    cats = db.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()
    return render_template("accounts/expense_categories.html", categories=cats)
