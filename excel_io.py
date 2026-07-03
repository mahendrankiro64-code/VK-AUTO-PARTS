"""Excel (and Google Sheets, via exported .xlsx/.csv) import & export.

Google Sheets note: this app does not connect live to the Google Sheets API
(that requires setting up a Google Cloud OAuth app, which is a lot of
overhead for a small shop). Instead: in Google Sheets use File > Download >
Microsoft Excel (.xlsx) and upload that file here, and for exports, open the
downloaded .xlsx file with File > Import in Google Sheets. The column layout
is identical either way.
"""
import io
from datetime import datetime
import pandas as pd
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, send_file, g
)
from db import get_db, next_sequence_code
from auth import login_required, admin_required
from helpers import today_str

bp = Blueprint("excel", __name__, url_prefix="/excel")


def _read_upload(file_storage):
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    buf = io.BytesIO(data)
    if filename.endswith(".csv"):
        return pd.read_csv(buf)
    return pd.read_excel(buf)


@bp.route("/")
@login_required
def index():
    return render_template("excel/index.html")


# ---------------------------------------------------------------- TEMPLATES
@bp.route("/template/<kind>")
@login_required
def download_template(kind):
    templates = {
        "items": pd.DataFrame(columns=[
            "name", "category", "brand", "unit", "cost_price",
            "selling_price", "stock_qty", "reorder_level",
        ]),
        "customers": pd.DataFrame(columns=[
            "name", "phone", "address", "customer_type", "credit_limit",
        ]),
        "purchases": pd.DataFrame(columns=[
            "supplier_name", "purchase_date", "item_code_or_name", "qty", "cost_price",
        ]),
    }
    if kind not in templates:
        flash("Unknown template.", "danger")
        return redirect(url_for("excel.index"))
    buf = io.BytesIO()
    templates[kind].to_excel(buf, index=False, sheet_name=kind)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=f"vkap_{kind}_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ------------------------------------------------------------------ IMPORT
@bp.route("/import/items", methods=("POST",))
@login_required
def import_items():
    db = get_db()
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Choose a file to upload.", "danger")
        return redirect(url_for("excel.index"))
    try:
        df = _read_upload(file)
    except Exception as e:
        flash(f"Could not read file: {e}", "danger")
        return redirect(url_for("excel.index"))

    created, skipped = 0, 0
    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        if not name or name.lower() == "nan":
            skipped += 1
            continue
        category_name = str(row.get("category", "")).strip()
        category_id = None
        if category_name and category_name.lower() != "nan":
            cat = db.execute("SELECT id FROM categories WHERE name=?", (category_name,)).fetchone()
            if cat:
                category_id = cat["id"]
            else:
                cur = db.execute("INSERT INTO categories (name) VALUES (?) RETURNING id", (category_name,))
                category_id = cur.fetchone()["id"]

        item_code = next_sequence_code(db, "item_seq", "VKAP", pad=4)
        db.execute(
            """INSERT INTO items (item_code, name, category_id, brand, unit, cost_price,
               selling_price, stock_qty, reorder_level) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                item_code, name, category_id,
                str(row.get("brand", "") or ""),
                str(row.get("unit", "pcs") or "pcs"),
                float(row.get("cost_price", 0) or 0),
                float(row.get("selling_price", 0) or 0),
                float(row.get("stock_qty", 0) or 0),
                float(row.get("reorder_level", 5) or 5),
            ),
        )
        created += 1
    db.commit()
    flash(f"Imported {created} item(s), skipped {skipped} row(s) without a name.", "success")
    return redirect(url_for("items.list_items"))


@bp.route("/import/customers", methods=("POST",))
@login_required
def import_customers():
    db = get_db()
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Choose a file to upload.", "danger")
        return redirect(url_for("excel.index"))
    try:
        df = _read_upload(file)
    except Exception as e:
        flash(f"Could not read file: {e}", "danger")
        return redirect(url_for("excel.index"))

    created, skipped = 0, 0
    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        if not name or name.lower() == "nan":
            skipped += 1
            continue
        code = next_sequence_code(db, "customer_seq", "CUS", pad=4)
        db.execute(
            """INSERT INTO customers (customer_code, name, phone, address,
               customer_type, credit_limit) VALUES (?,?,?,?,?,?)""",
            (
                code, name,
                str(row.get("phone", "") or ""),
                str(row.get("address", "") or ""),
                str(row.get("customer_type", "walkin") or "walkin"),
                float(row.get("credit_limit", 0) or 0),
            ),
        )
        created += 1
    db.commit()
    flash(f"Imported {created} customer(s), skipped {skipped} row(s) without a name.", "success")
    return redirect(url_for("customers.list_customers"))


@bp.route("/import/purchases", methods=("POST",))
@login_required
def import_purchases():
    db = get_db()
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Choose a file to upload.", "danger")
        return redirect(url_for("excel.index"))
    try:
        df = _read_upload(file)
    except Exception as e:
        flash(f"Could not read file: {e}", "danger")
        return redirect(url_for("excel.index"))

    df["supplier_name"] = df.get("supplier_name", "").astype(str).fillna("")
    df["purchase_date"] = df.get("purchase_date", today_str())

    groups_created = 0
    lines_created, lines_skipped = 0, 0
    for (supplier_name, purchase_date), group in df.groupby(["supplier_name", "purchase_date"]):
        supplier_id = None
        supplier_name_clean = supplier_name.strip()
        if supplier_name_clean and supplier_name_clean.lower() != "nan":
            sup = db.execute("SELECT id FROM suppliers WHERE name=?", (supplier_name_clean,)).fetchone()
            if sup:
                supplier_id = sup["id"]
            else:
                scode = next_sequence_code(db, "supplier_seq", "SUP", pad=4)
                cur = db.execute(
                    "INSERT INTO suppliers (supplier_code, name) VALUES (?,?) RETURNING id",
                    (scode, supplier_name_clean),
                )
                supplier_id = cur.fetchone()["id"]

        try:
            pdate = pd.to_datetime(purchase_date).strftime("%Y-%m-%d")
        except Exception:
            pdate = today_str()

        line_items = []
        total_amount = 0.0
        for _, row in group.iterrows():
            key = str(row.get("item_code_or_name", "")).strip()
            qty = float(row.get("qty", 0) or 0)
            cost = float(row.get("cost_price", 0) or 0)
            if not key or qty <= 0:
                lines_skipped += 1
                continue
            item_row = db.execute(
                "SELECT * FROM items WHERE item_code=? OR name=?", (key, key)
            ).fetchone()
            if not item_row:
                lines_skipped += 1
                continue
            total = qty * cost
            total_amount += total
            line_items.append((item_row["id"], qty, cost, total))

        if not line_items:
            continue

        purchase_no = next_sequence_code(db, "purchase_seq", "PUR", pad=5)
        cur = db.execute(
            """INSERT INTO purchases (purchase_no, supplier_id, purchase_date, total_amount,
               payment_status, created_by, notes) VALUES (?,?,?,?,?,?,?) RETURNING id""",
            (purchase_no, supplier_id, pdate, total_amount, "unpaid",
             g.user["id"] if g.user else None, "Imported from spreadsheet"),
        )
        purchase_id = cur.fetchone()["id"]
        for item_id, qty, cost, total in line_items:
            db.execute(
                """INSERT INTO purchase_items (purchase_id, item_id, qty, cost_price, total)
                   VALUES (?,?,?,?,?)""",
                (purchase_id, item_id, qty, cost, total),
            )
            db.execute(
                "UPDATE items SET stock_qty = stock_qty + ?, cost_price=? WHERE id=?",
                (qty, cost, item_id),
            )
        if supplier_id:
            db.execute(
                "UPDATE suppliers SET balance_due = balance_due + ? WHERE id=?",
                (total_amount, supplier_id),
            )
        groups_created += 1
        lines_created += len(line_items)

    db.commit()
    flash(
        f"Imported {groups_created} purchase(s) with {lines_created} line item(s). "
        f"Skipped {lines_skipped} row(s) (unknown item or missing qty).",
        "success",
    )
    return redirect(url_for("purchases.list_purchases"))
