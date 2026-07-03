from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db, next_sequence_code
from auth import login_required

bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@bp.route("/")
@login_required
def list_suppliers():
    db = get_db()
    suppliers = db.execute("SELECT * FROM suppliers WHERE active=1 ORDER BY id DESC").fetchall()
    return render_template("suppliers/list.html", suppliers=suppliers)


@bp.route("/add", methods=("GET", "POST"))
@login_required
def add_supplier():
    if request.method == "POST":
        db = get_db()
        name = request.form["name"].strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        if not name:
            flash("Supplier name is required.", "danger")
        else:
            code = next_sequence_code(db, "supplier_seq", "SUP", pad=4)
            db.execute(
                "INSERT INTO suppliers (supplier_code, name, phone, address) VALUES (?,?,?,?)",
                (code, name, phone, address),
            )
            db.commit()
            flash(f"Supplier added ({code}).", "success")
            return redirect(url_for("suppliers.list_suppliers"))
    return render_template("suppliers/add.html")
