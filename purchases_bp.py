from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from db import get_db, next_sequence_code
from auth import login_required
from helpers import today_str

bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@bp.route("/")
@login_required
def list_purchases():
    db = get_db()
    purchases = db.execute(
        """SELECT p.*, s.name AS supplier_name FROM purchases p
           LEFT JOIN suppliers s ON s.id = p.supplier_id
           ORDER BY p.id DESC"""
    ).fetchall()
    return render_template("purchases/list.html", purchases=purchases)


@bp.route("/add", methods=("GET", "POST"))
@login_required
def add_purchase():
    db = get_db()
    suppliers = db.execute("SELECT * FROM suppliers WHERE active=1 ORDER BY name").fetchall()
    items = db.execute("SELECT * FROM items WHERE active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id") or None
        purchase_date = request.form.get("purchase_date") or today_str()
        notes = request.form.get("notes", "").strip()
        payment_status = request.form.get("payment_status", "unpaid")
        amount_paid = float(request.form.get("amount_paid") or 0)

        item_ids = request.form.getlist("item_id[]")
        qtys = request.form.getlist("qty[]")
        costs = request.form.getlist("cost_price[]")

        line_items = []
        total_amount = 0.0
        for iid, qty, cost in zip(item_ids, qtys, costs):
            if not iid or not qty:
                continue
            qty_f = float(qty)
            cost_f = float(cost or 0)
            total = qty_f * cost_f
            total_amount += total
            line_items.append((int(iid), qty_f, cost_f, total))

        if not line_items:
            flash("Add at least one item line to the purchase.", "danger")
            return render_template("purchases/add.html", suppliers=suppliers, items=items)

        purchase_no = next_sequence_code(db, "purchase_seq", "PUR", pad=5)
        cur = db.execute(
            """INSERT INTO purchases (purchase_no, supplier_id, purchase_date, total_amount,
               payment_status, amount_paid, notes, created_by)
               VALUES (?,?,?,?,?,?,?,?)""",
            (purchase_no, supplier_id, purchase_date, total_amount, payment_status,
             amount_paid, notes, g.user["id"] if g.user else None),
        )
        purchase_id = cur.lastrowid

        for item_id, qty_f, cost_f, total in line_items:
            db.execute(
                """INSERT INTO purchase_items (purchase_id, item_id, qty, cost_price, total)
                   VALUES (?,?,?,?,?)""",
                (purchase_id, item_id, qty_f, cost_f, total),
            )
            # increase stock and update cost price to the latest purchase cost
            db.execute(
                "UPDATE items SET stock_qty = stock_qty + ?, cost_price = ? WHERE id=?",
                (qty_f, cost_f, item_id),
            )

        if supplier_id:
            outstanding = total_amount - amount_paid
            if outstanding > 0:
                db.execute(
                    "UPDATE suppliers SET balance_due = balance_due + ? WHERE id=?",
                    (outstanding, supplier_id),
                )

        db.commit()
        flash(f"Purchase {purchase_no} recorded and stock updated.", "success")
        return redirect(url_for("purchases.list_purchases"))

    return render_template("purchases/add.html", suppliers=suppliers, items=items)


@bp.route("/<int:purchase_id>")
@login_required
def view_purchase(purchase_id):
    db = get_db()
    purchase = db.execute(
        """SELECT p.*, s.name AS supplier_name FROM purchases p
           LEFT JOIN suppliers s ON s.id = p.supplier_id WHERE p.id=?""",
        (purchase_id,),
    ).fetchone()
    if not purchase:
        flash("Purchase not found.", "danger")
        return redirect(url_for("purchases.list_purchases"))
    line_items = db.execute(
        """SELECT pi.*, i.item_code, i.name AS item_name FROM purchase_items pi
           JOIN items i ON i.id = pi.item_id WHERE pi.purchase_id=?""",
        (purchase_id,),
    ).fetchall()
    return render_template("purchases/view.html", purchase=purchase, line_items=line_items)
