from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db, next_sequence_code
from auth import login_required
from helpers import today_str

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.route("/")
@login_required
def list_customers():
    db = get_db()
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM customers WHERE active=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR phone LIKE ? OR customer_code LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC"
    customers = db.execute(sql, params).fetchall()
    return render_template("customers/list.html", customers=customers, q=q)


@bp.route("/add", methods=("GET", "POST"))
@login_required
def add_customer():
    if request.method == "POST":
        db = get_db()
        name = request.form["name"].strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        customer_type = request.form.get("customer_type", "walkin")
        credit_limit = float(request.form.get("credit_limit") or 0)

        if not name:
            flash("Customer name is required.", "danger")
        else:
            code = next_sequence_code(db, "customer_seq", "CUS", pad=4)
            db.execute(
                """INSERT INTO customers (customer_code, name, phone, address,
                   customer_type, credit_limit) VALUES (?,?,?,?,?,?)""",
                (code, name, phone, address, customer_type, credit_limit),
            )
            db.commit()
            flash(f"Customer added ({code}).", "success")
            return redirect(url_for("customers.list_customers"))
    return render_template("customers/add.html", customer=None)


@bp.route("/<int:customer_id>/edit", methods=("GET", "POST"))
@login_required
def edit_customer(customer_id):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.list_customers"))
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        customer_type = request.form.get("customer_type", "walkin")
        credit_limit = float(request.form.get("credit_limit") or 0)
        db.execute(
            """UPDATE customers SET name=?, phone=?, address=?, customer_type=?,
               credit_limit=? WHERE id=?""",
            (name, phone, address, customer_type, credit_limit, customer_id),
        )
        db.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("customers.list_customers"))
    return render_template("customers/add.html", customer=customer)


@bp.route("/<int:customer_id>")
@login_required
def view_customer(customer_id):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.list_customers"))
    invoices = db.execute(
        """SELECT * FROM invoices WHERE customer_id=? ORDER BY invoice_date DESC""",
        (customer_id,),
    ).fetchall()
    payments = db.execute(
        """SELECT * FROM payments WHERE customer_id=? ORDER BY payment_date DESC""",
        (customer_id,),
    ).fetchall()
    return render_template(
        "customers/view.html", customer=customer, invoices=invoices, payments=payments
    )


@bp.route("/<int:customer_id>/payment", methods=("POST",))
@login_required
def record_payment(customer_id):
    db = get_db()
    amount = float(request.form.get("amount") or 0)
    mode = request.form.get("payment_mode", "cash")
    notes = request.form.get("notes", "").strip()
    invoice_id = request.form.get("invoice_id") or None

    if amount <= 0:
        flash("Enter a valid payment amount.", "danger")
        return redirect(url_for("customers.view_customer", customer_id=customer_id))

    db.execute(
        """INSERT INTO payments (customer_id, invoice_id, amount, payment_date,
           payment_mode, notes, created_by) VALUES (?,?,?,?,?,?,?)""",
        (customer_id, invoice_id, amount, today_str(), mode, notes,
         g.user["id"] if g.user else None),
    )
    db.execute(
        "UPDATE customers SET balance_due = balance_due - ? WHERE id=?",
        (amount, customer_id),
    )
    if invoice_id:
        db.execute(
            "UPDATE invoices SET amount_paid = amount_paid + ?, balance = balance - ? WHERE id=?",
            (amount, amount, invoice_id),
        )
    db.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("customers.view_customer", customer_id=customer_id))
