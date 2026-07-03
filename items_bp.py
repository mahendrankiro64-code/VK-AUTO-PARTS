from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db, next_sequence_code
from auth import login_required

bp = Blueprint("items", __name__, url_prefix="/items")


@bp.route("/")
@login_required
def list_items():
    db = get_db()
    q = request.args.get("q", "").strip()
    low_stock_only = request.args.get("low_stock") == "1"
    sql = """SELECT i.*, c.name AS category_name FROM items i
              LEFT JOIN categories c ON c.id = i.category_id WHERE i.active=1"""
    params = []
    if q:
        sql += " AND (i.name LIKE ? OR i.item_code LIKE ? OR i.brand LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if low_stock_only:
        sql += " AND i.stock_qty <= i.reorder_level"
    sql += " ORDER BY i.id DESC"
    items = db.execute(sql, params).fetchall()
    return render_template("items/list.html", items=items, q=q, low_stock_only=low_stock_only)


@bp.route("/add", methods=("GET", "POST"))
@login_required
def add_item():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    if request.method == "POST":
        name = request.form["name"].strip()
        category_id = request.form.get("category_id") or None
        brand = request.form.get("brand", "").strip()
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        cost_price = float(request.form.get("cost_price") or 0)
        selling_price = float(request.form.get("selling_price") or 0)
        stock_qty = float(request.form.get("stock_qty") or 0)
        reorder_level = float(request.form.get("reorder_level") or 5)

        if not name:
            flash("Item name is required.", "danger")
        else:
            item_code = next_sequence_code(db, "item_seq", "VKAP", pad=4)
            db.execute(
                """INSERT INTO items (item_code, name, category_id, brand, unit,
                   cost_price, selling_price, stock_qty, reorder_level)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (item_code, name, category_id, brand, unit, cost_price,
                 selling_price, stock_qty, reorder_level),
            )
            db.commit()
            flash(f"Item added with code {item_code}.", "success")
            return redirect(url_for("items.list_items"))

    return render_template("items/add.html", categories=categories, item=None)


@bp.route("/<int:item_id>/edit", methods=("GET", "POST"))
@login_required
def edit_item(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for("items.list_items"))
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        category_id = request.form.get("category_id") or None
        brand = request.form.get("brand", "").strip()
        unit = request.form.get("unit", "pcs").strip() or "pcs"
        cost_price = float(request.form.get("cost_price") or 0)
        selling_price = float(request.form.get("selling_price") or 0)
        stock_qty = float(request.form.get("stock_qty") or 0)
        reorder_level = float(request.form.get("reorder_level") or 5)

        db.execute(
            """UPDATE items SET name=?, category_id=?, brand=?, unit=?, cost_price=?,
               selling_price=?, stock_qty=?, reorder_level=? WHERE id=?""",
            (name, category_id, brand, unit, cost_price, selling_price,
             stock_qty, reorder_level, item_id),
        )
        db.commit()
        flash("Item updated.", "success")
        return redirect(url_for("items.list_items"))

    return render_template("items/add.html", categories=categories, item=item)


@bp.route("/<int:item_id>/delete", methods=("POST",))
@login_required
def delete_item(item_id):
    db = get_db()
    db.execute("UPDATE items SET active=0 WHERE id=?", (item_id,))
    db.commit()
    flash("Item removed.", "success")
    return redirect(url_for("items.list_items"))


@bp.route("/categories", methods=("GET", "POST"))
@login_required
def categories():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        prefix = request.form.get("prefix", "").strip().upper()
        if name:
            try:
                db.execute("INSERT INTO categories (name, prefix) VALUES (?,?)", (name, prefix))
                db.commit()
                flash("Category added.", "success")
            except Exception:
                flash("That category already exists.", "danger")
        return redirect(url_for("items.categories"))
    cats = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template("items/categories.html", categories=cats)
