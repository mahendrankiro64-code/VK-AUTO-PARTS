import io
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, send_file
from db import get_db, next_sequence_code
from auth import permission_required
from helpers import today_str, now_str

bp = Blueprint("scan", __name__, url_prefix="/scan")

# Manual/handwritten paper bills (and Excel bills) get turned into real
# invoices here. The photo is OCR'd to text entirely in the browser
# (Tesseract.js) and the browser also tries to spot item codes + quantities
# in that text; matched lines become real invoice line items (deducting
# stock, just like a normal POS sale) exactly like a spreadsheet upload
# would. Anything the OCR couldn't confidently match, the shop keeper adds
# by hand using the same item search box. Either way, only the confirmed
# line items + the original text are ever sent to the server -- the photo
# itself and the uploaded spreadsheet file are never stored anywhere.


@bp.route("/new", methods=("GET", "POST"))
@permission_required("perm_sales")
def new_scan():
    db = get_db()
    customers = db.execute("SELECT * FROM customers WHERE active=1 ORDER BY name").fetchall()
    items = db.execute("SELECT * FROM items WHERE active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        scanned_text = request.form.get("scanned_text", "").strip()
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
            flash("No matched items to save -- match at least one item code from the bill, or add items manually below.", "danger")
            return render_template("scan/new.html", customers=customers, items=items)

        if stock_errors:
            flash("Not enough stock for: " + ", ".join(stock_errors), "danger")
            return render_template("scan/new.html", customers=customers, items=items)

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
                        f"This would push {cust['name']}'s credit balance to "
                        f"Rs. {projected:,.2f}, over their limit of Rs. {cust['credit_limit']:,.2f}. "
                        "Adjust the amount paid or raise their credit limit.",
                        "danger",
                    )
                    return render_template("scan/new.html", customers=customers, items=items)

        invoice_no = next_sequence_code(db, "invoice_seq", "INV", pad=6)
        biz_date = today_str()
        cur = db.execute(
            """INSERT INTO invoices (invoice_no, customer_id, invoice_date, business_date,
               subtotal, discount, tax, total_amount, payment_mode, amount_paid, balance,
               status, source, notes, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (invoice_no, customer_id, now_str(), biz_date, subtotal, discount, tax,
             total_amount, payment_mode, amount_paid, balance, "completed", "manual_scan",
             scanned_text, g.user["id"] if g.user else None),
        )
        invoice_id = cur.fetchone()["id"]

        for item_row, qty_f, price_f, line_total in line_items:
            db.execute(
                """INSERT INTO invoice_items (invoice_id, item_id, item_name, qty, unit_price,
                   total, cost_price_at_sale) VALUES (?,?,?,?,?,?,?)""",
                (invoice_id, item_row["id"], item_row["name"], qty_f, price_f, line_total,
                 item_row["cost_price"]),
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
        flash(
            f"Bill saved as invoice {invoice_no} and stock was updated. "
            "Only the text/matched items were kept -- nothing else was uploaded or stored.",
            "success",
        )
        return redirect(url_for("sales.view_invoice", invoice_id=invoice_id))

    return render_template("scan/new.html", customers=customers, items=items)


@bp.route("/match", methods=("GET",))
@permission_required("perm_sales")
def match_code():
    """Same idea as items.lookup_by_code, exposed under /scan so the scan
    page's code+qty matcher can look up each candidate code it finds in the
    OCR'd text (or in an uploaded spreadsheet) against real inventory."""
    code = request.args.get("code", "").strip()
    db = get_db()
    item = db.execute(
        "SELECT * FROM items WHERE item_code = ? AND active = 1", (code,)
    ).fetchone()
    if not item:
        return jsonify({"found": False, "code": code})
    return jsonify({
        "found": True,
        "id": item["id"],
        "item_code": item["item_code"],
        "name": item["name"],
        "selling_price": item["selling_price"],
        "stock_qty": item["stock_qty"],
        "unit": item["unit"],
    })


@bp.route("/excel-preview", methods=("POST",))
@permission_required("perm_sales")
def excel_preview():
    """Parse an uploaded spreadsheet bill (columns: item_code, qty, and
    optionally unit_price) and return matched/unmatched lines as JSON so the
    page can populate the same review cart used for scanned photos. The
    uploaded file itself is read in memory only -- it is never saved to
    disk or to the database."""
    db = get_db()
    file = request.files.get("excel_file")
    if not file or not file.filename:
        return jsonify({"error": "Choose a spreadsheet file first."}), 400
    try:
        filename = file.filename.lower()
        data = file.read()
        buf = io.BytesIO(data)
        df = pd.read_csv(buf) if filename.endswith(".csv") else pd.read_excel(buf)
    except Exception as e:
        return jsonify({"error": f"Could not read that file: {e}"}), 400

    df.columns = [str(c).strip().lower() for c in df.columns]
    if "item_code" not in df.columns or "qty" not in df.columns:
        return jsonify({"error": "The file needs at least 'item_code' and 'qty' columns (see the template)."}), 400

    matched, unmatched = [], []
    for _, row in df.iterrows():
        code = str(row.get("item_code", "")).strip()
        if not code or code.lower() == "nan":
            continue
        try:
            qty = float(row.get("qty", 1) or 1)
        except (TypeError, ValueError):
            qty = 1.0

        item_row = db.execute(
            "SELECT * FROM items WHERE item_code = ? AND active = 1", (code,)
        ).fetchone()
        if not item_row:
            unmatched.append(code)
            continue

        price = item_row["selling_price"]
        raw_price = row.get("unit_price")
        if raw_price is not None and str(raw_price).strip().lower() not in ("", "nan"):
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                pass

        matched.append({
            "id": item_row["id"], "code": item_row["item_code"], "name": item_row["name"],
            "price": price, "stock": item_row["stock_qty"], "unit": item_row["unit"], "qty": qty,
        })

    return jsonify({"matched": matched, "unmatched": unmatched})


@bp.route("/excel-template")
@permission_required("perm_sales")
def excel_template():
    """A starter spreadsheet with the exact columns /scan/excel-preview
    expects: item_code, qty, and an optional unit_price override."""
    df = pd.DataFrame([{"item_code": "VKAP-0001", "qty": 2, "unit_price": ""}])
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="bill")
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name="vkap_bill_upload_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
