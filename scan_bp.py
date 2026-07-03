from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db, next_sequence_code
from auth import permission_required
from helpers import today_str, now_str

bp = Blueprint("scan", __name__, url_prefix="/scan")

# Manual/handwritten paper bills get turned into text entirely in the
# customer's browser (via Tesseract.js, see templates/scan/new.html) and
# only that confirmed text is ever posted here -- the photo itself is
# never uploaded, saved to disk, or stored in the database. This route
# just takes the confirmed text + a total + a payment method and records
# it as a normal invoice (source='manual_scan') so it counts correctly in
# reports, day-end, and customer balances, exactly like a POS sale would.
#
# One real limitation, by design: because the text comes from OCR of a
# free-form paper bill, we have no reliable way to match it to specific
# inventory items or quantities. So a scanned bill does NOT deduct stock
# automatically -- it's recorded for money/accounting purposes only. If a
# shop keeper needs stock deducted too, they should use New Sale (POS)
# instead, or adjust stock manually afterward.


@bp.route("/new", methods=("GET", "POST"))
@permission_required("perm_sales")
def new_scan():
    db = get_db()
    customers = db.execute("SELECT * FROM customers WHERE active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        scanned_text = request.form.get("scanned_text", "").strip()
        customer_id = request.form.get("customer_id") or None
        payment_mode = request.form.get("payment_mode", "cash")
        total_amount = float(request.form.get("total_amount") or 0)
        amount_paid_input = request.form.get("amount_paid")

        if not scanned_text:
            flash("Scan the bill (or type its text) before saving.", "danger")
            return render_template("scan/new.html", customers=customers)
        if total_amount <= 0:
            flash("Enter the bill's total amount.", "danger")
            return render_template("scan/new.html", customers=customers)

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
                        f"This would push {cust['name']}'s credit balance to "
                        f"Rs. {projected:,.2f}, over their limit of Rs. {cust['credit_limit']:,.2f}. "
                        "Adjust the amount paid or raise their credit limit.",
                        "danger",
                    )
                    return render_template("scan/new.html", customers=customers)

        invoice_no = next_sequence_code(db, "invoice_seq", "INV", pad=6)
        biz_date = today_str()
        cur = db.execute(
            """INSERT INTO invoices (invoice_no, customer_id, invoice_date, business_date,
               subtotal, discount, tax, total_amount, payment_mode, amount_paid, balance,
               status, source, notes, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (invoice_no, customer_id, now_str(), biz_date, total_amount, 0, 0, total_amount,
             payment_mode, amount_paid, balance, "completed", "manual_scan", scanned_text,
             g.user["id"] if g.user else None),
        )
        invoice_id = cur.fetchone()["id"]

        db.execute(
            """INSERT INTO invoice_items (invoice_id, item_id, item_name, qty, unit_price,
               total, cost_price_at_sale) VALUES (?,?,?,?,?,?,?)""",
            (invoice_id, None, "Manual / Scanned Bill", 1, total_amount, total_amount, 0),
        )

        if customer_id and balance > 0:
            db.execute(
                "UPDATE customers SET balance_due = balance_due + ? WHERE id=?",
                (balance, customer_id),
            )

        db.commit()
        flash(
            f"Scanned bill saved as invoice {invoice_no}. Only the text was kept -- "
            "the photo itself was not uploaded or stored anywhere.",
            "success",
        )
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    return render_template("scan/new.html", customers=customers)
