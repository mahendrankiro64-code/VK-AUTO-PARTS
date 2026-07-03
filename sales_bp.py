from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db, next_sequence_code
from auth import login_required
from helpers import today_str, now_str

bp = Blueprint("sales", __name__, url_prefix="/sales")


@bp.route("/")
@login_required
def list_invoices():
    db = get_db()
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")
    sql = """SELECT inv.*, c.name AS customer_name FROM invoices inv
              LEFT JOIN customers c ON c.id = inv.customer_id WHERE inv.status='completed'"""
    params = []
    if date_from:
        sql += " AND inv.business_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND inv.business_date <= ?"
        params.append(date_to)
    sql += " ORDER BY inv.id DESC"
    invoices = db.execute(sql, params).fetchall()
    return render_template("sales/list.html", invoices=invoices, date_from=date_from, date_to=date_to)


@bp.route("/new", methods=("GET", "POST"))
@login_required
def new_invoice():
    db = get_db()
    customers = db.execute("SELECT * FROM customers WHERE active=1 ORDER BY name").fetchall()
    items = db.execute("SELECT * FROM items WHERE active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        customer_id = request.form.get("customer_id") or None
        payment_mode = request.form.get("payment_mode", "cash")
        discount = float(request.form.get("discount") or 0)
        tax = float(request.form.get("tax") or 0)
        amount_paid_input = request.form.get("amount_paid")

        item_ids = request.form.getlist("item_id[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("unit_price[]")

        line_items = []
        subtotal = 0.0
        stock_errors = []
        for iid, qty, price in zip(item_ids, qtys, prices):
            if not iid or not qty:
                continue
            item_row = db.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
            if not item_row:
                continue
            qty_f = float(qty)
            price_f = float(price or item_row["selling_price"])
            if qty_f > item_row["stock_qty"]:
                stock_errors.append(f"{item_row['name']} (only {item_row['stock_qty']} in stock)")
            line_total = qty_f * price_f
            subtotal += line_total
            line_items.append((item_row, qty_f, price_f, line_total))

        if not line_items:
            flash("Add at least one item to the invoice.", "danger")
            return render_template("sales/new.html", customers=customers, items=items)

        if stock_errors:
            flash("Not enough stock for: " + ", ".join(stock_errors), "danger")
            return render_template("sales/new.html", customers=customers, items=items)

        total_amount = subtotal - discount + tax
        if payment_mode == "credit":
            amount_paid = float(amount_paid_input) if amount_paid_input else 0.0
        else:
            amount_paid = total_amount
        balance = total_amount - amount_paid

        if payment_mode == "credit" and customer_id:
            cust = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if cust and cust["credit_limit"] > 0:
                projected = cust["balance_due"] + balance
                if projected > cust["credit_limit"]:
                    flash(
                        f"This sale would push {cust['name']}'s credit balance to "
                        f"Rs. {projected:,.2f}, over their limit of Rs. {cust['credit_limit']:,.2f}. "
                        "Adjust the amount paid or raise their credit limit.",
                        "danger",
                    )
                    return render_template("sales/new.html", customers=customers, items=items)

        invoice_no = next_sequence_code(db, "invoice_seq", "INV", pad=6)
        biz_date = today_str()
        cur = db.execute(
            """INSERT INTO invoices (invoice_no, customer_id, invoice_date, business_date,
               subtotal, discount, tax, total_amount, payment_mode, amount_paid, balance,
               created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (invoice_no, customer_id, now_str(), biz_date, subtotal, discount, tax,
             total_amount, payment_mode, amount_paid, balance,
             g.user["id"] if g.user else None),
        )
        invoice_id = cur.fetchone()["id"]

        for item_row, qty_f, price_f, line_total in line_items:
            db.execute(
                """INSERT INTO invoice_items (invoice_id, item_id, item_name, qty,
                   unit_price, total) VALUES (?,?,?,?,?,?)""",
                (invoice_id, item_row["id"], item_row["name"], qty_f, price_f, line_total),
            )
            db.execute(
                "UPDATE items SET stock_qty = stock_qty - ? WHERE id=?",
                (qty_f, item_row["id"]),
            )

        if customer_id and balance > 0:
            db.execute(
                "UPDATE customers SET balance_due = balance_due + ? WHERE id=?",
                (balance, customer_id),
            )

        db.commit()
        flash(f"Invoice {invoice_no} created.", "success")
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    return render_template("sales/new.html", customers=customers, items=items)


@bp.route("/<int:invoice_id>")
@login_required
def view_invoice(invoice_id):
    db = get_db()
    invoice = db.execute(
        """SELECT inv.*, c.name AS customer_name, c.phone AS customer_phone,
                  c.address AS customer_address
           FROM invoices inv LEFT JOIN customers c ON c.id = inv.customer_id
           WHERE inv.id=?""",
        (invoice_id,),
    ).fetchone()
    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for("sales.list_invoices"))
    line_items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)
    ).fetchall()
    return render_template("sales/invoice.html", invoice=invoice, line_items=line_items)


@bp.route("/<int:invoice_id>/cancel", methods=("POST",))
@login_required
def cancel_invoice(invoice_id):
    db = get_db()
    invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not invoice or invoice["status"] == "cancelled":
        flash("Invoice not found or already cancelled.", "danger")
        return redirect(url_for("sales.list_invoices"))

    line_items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)
    ).fetchall()
    for li in line_items:
        db.execute(
            "UPDATE items SET stock_qty = stock_qty + ? WHERE id=?", (li["qty"], li["item_id"])
        )
    if invoice["customer_id"] and invoice["balance"] > 0:
        db.execute(
            "UPDATE customers SET balance_due = balance_due - ? WHERE id=?",
            (invoice["balance"], invoice["customer_id"]),
        )
    db.execute("UPDATE invoices SET status='cancelled' WHERE id=?", (invoice_id,))
    db.commit()
    flash(f"Invoice {invoice['invoice_no']} cancelled and stock restored.", "success")
    return redirect(url_for("sales.list_invoices"))
