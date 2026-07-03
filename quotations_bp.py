from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db, next_sequence_code
from auth import permission_required, login_required
from helpers import today_str, now_str

bp = Blueprint("quotations", __name__, url_prefix="/quotations")


@bp.route("/")
@login_required
def list_quotations():
    db = get_db()
    quotations = db.execute(
        """SELECT q.*, COALESCE(c.name, 'Walk-in') AS customer_name FROM quotations q
           LEFT JOIN customers c ON c.id = q.customer_id
           ORDER BY q.id DESC"""
    ).fetchall()
    return render_template("quotations/list.html", quotations=quotations)


@bp.route("/new", methods=("GET", "POST"))
@permission_required("perm_quotations")
def new_quotation():
    db = get_db()
    customers = db.execute("SELECT * FROM customers WHERE active=1 ORDER BY name").fetchall()
    items = db.execute("SELECT * FROM items WHERE active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        customer_id = request.form.get("customer_id") or None
        discount = float(request.form.get("discount") or 0)
        tax = float(request.form.get("tax") or 0)
        valid_until = request.form.get("valid_until") or None
        notes = request.form.get("notes", "").strip()

        item_ids = request.form.getlist("item_id[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("unit_price[]")

        line_items = []
        subtotal = 0.0
        for iid, qty, price in zip(item_ids, qtys, prices):
            if not iid or not qty:
                continue
            item_row = db.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
            if not item_row:
                continue
            qty_f = float(qty)
            price_f = float(price or item_row["selling_price"])
            line_total = qty_f * price_f
            subtotal += line_total
            line_items.append((item_row, qty_f, price_f, line_total))

        if not line_items:
            flash("Add at least one item to the quotation.", "danger")
            return render_template("quotations/new.html", customers=customers, items=items)

        total_amount = subtotal - discount + tax
        quotation_no = next_sequence_code(db, "quotation_seq", "QUO", pad=5)

        cur = db.execute(
            """INSERT INTO quotations (quotation_no, customer_id, quotation_date, valid_until,
               subtotal, discount, tax, total_amount, notes, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (quotation_no, customer_id, now_str(), valid_until, subtotal, discount, tax,
             total_amount, notes, g.user["id"] if g.user else None),
        )
        quotation_id = cur.fetchone()["id"]

        for item_row, qty_f, price_f, line_total in line_items:
            db.execute(
                """INSERT INTO quotation_items (quotation_id, item_id, item_name, qty,
                   unit_price, total) VALUES (?,?,?,?,?,?)""",
                (quotation_id, item_row["id"], item_row["name"], qty_f, price_f, line_total),
            )

        db.commit()
        flash(f"Quotation {quotation_no} created.", "success")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation_id))

    return render_template("quotations/new.html", customers=customers, items=items)


@bp.route("/<int:quotation_id>")
@login_required
def view_quotation(quotation_id):
    db = get_db()
    quotation = db.execute(
        """SELECT q.*, c.name AS customer_name, c.phone AS customer_phone
           FROM quotations q LEFT JOIN customers c ON c.id = q.customer_id
           WHERE q.id=?""",
        (quotation_id,),
    ).fetchone()
    if not quotation:
        flash("Quotation not found.", "danger")
        return redirect(url_for("quotations.list_quotations"))
    line_items = db.execute(
        "SELECT * FROM quotation_items WHERE quotation_id=?", (quotation_id,)
    ).fetchall()
    return render_template("quotations/view.html", quotation=quotation, line_items=line_items)


@bp.route("/<int:quotation_id>/convert", methods=("POST",))
@permission_required("perm_sales")
def convert_to_invoice(quotation_id):
    """Turn an existing (even old) quotation directly into a real invoice --
    one click, no re-typing the items. Stock is only deducted at this point
    (quotations never reserve or deduct stock)."""
    db = get_db()
    quotation = db.execute("SELECT * FROM quotations WHERE id=?", (quotation_id,)).fetchone()
    if not quotation:
        flash("Quotation not found.", "danger")
        return redirect(url_for("quotations.list_quotations"))
    if quotation["status"] != "open":
        flash(f"This quotation is already {quotation['status']} and can't be converted again.", "danger")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation_id))

    q_items = db.execute(
        "SELECT * FROM quotation_items WHERE quotation_id=?", (quotation_id,)
    ).fetchall()

    stock_errors = []
    resolved = []
    for qi in q_items:
        item_row = db.execute("SELECT * FROM items WHERE id=?", (qi["item_id"],)).fetchone()
        if not item_row or not item_row["active"]:
            stock_errors.append(f"{qi['item_name']} is no longer available in inventory")
            continue
        if qi["qty"] > item_row["stock_qty"]:
            stock_errors.append(f"{qi['item_name']} (only {item_row['stock_qty']} in stock, quotation needs {qi['qty']})")
        resolved.append((item_row, qi))

    if stock_errors:
        flash("Can't convert — not enough stock for: " + "; ".join(stock_errors), "danger")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation_id))

    payment_mode = request.form.get("payment_mode", "cash")
    amount_paid_input = request.form.get("amount_paid")
    total_amount = quotation["total_amount"]
    amount_paid = float(amount_paid_input) if (payment_mode == "credit" and amount_paid_input) else (
        total_amount if payment_mode != "credit" else 0.0
    )
    balance = total_amount - amount_paid

    invoice_no = next_sequence_code(db, "invoice_seq", "INV", pad=6)
    biz_date = today_str()
    cur = db.execute(
        """INSERT INTO invoices (invoice_no, customer_id, invoice_date, business_date,
           subtotal, discount, tax, total_amount, payment_mode, amount_paid, balance,
           created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
        (invoice_no, quotation["customer_id"], now_str(), biz_date, quotation["subtotal"],
         quotation["discount"], quotation["tax"], total_amount, payment_mode, amount_paid,
         balance, g.user["id"] if g.user else None),
    )
    invoice_id = cur.fetchone()["id"]

    for item_row, qi in resolved:
        db.execute(
            """INSERT INTO invoice_items (invoice_id, item_id, item_name, qty, unit_price,
               total, cost_price_at_sale) VALUES (?,?,?,?,?,?,?)""",
            (invoice_id, item_row["id"], qi["item_name"], qi["qty"], qi["unit_price"],
             qi["total"], item_row["cost_price"]),
        )
        db.execute("UPDATE items SET stock_qty = stock_qty - ? WHERE id=?", (qi["qty"], item_row["id"]))

    if quotation["customer_id"] and balance > 0:
        db.execute(
            "UPDATE customers SET balance_due = balance_due + ? WHERE id=?",
            (balance, quotation["customer_id"]),
        )

    db.execute(
        "UPDATE quotations SET status='converted', converted_invoice_id=? WHERE id=?",
        (invoice_id, quotation_id),
    )
    db.commit()
    flash(f"Quotation {quotation['quotation_no']} converted to invoice {invoice_no}.", "success")
    return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))


@bp.route("/<int:quotation_id>/cancel", methods=("POST",))
@permission_required("perm_quotations")
def cancel_quotation(quotation_id):
    db = get_db()
    quotation = db.execute("SELECT * FROM quotations WHERE id=?", (quotation_id,)).fetchone()
    if not quotation or quotation["status"] != "open":
        flash("Quotation not found or can't be cancelled.", "danger")
        return redirect(url_for("quotations.list_quotations"))
    db.execute("UPDATE quotations SET status='cancelled' WHERE id=?", (quotation_id,))
    db.commit()
    flash(f"Quotation {quotation['quotation_no']} cancelled.", "success")
    return redirect(url_for("quotations.list_quotations"))
