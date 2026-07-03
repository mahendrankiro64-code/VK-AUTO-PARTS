from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db
from auth import permission_required

bp = Blueprint("racks", __name__, url_prefix="/racks")


@bp.route("/", methods=("GET", "POST"))
@permission_required("perm_items")
def list_racks():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            try:
                db.execute("INSERT INTO racks (name) VALUES (?)", (name,))
                db.commit()
                flash(f"Rack '{name}' added.", "success")
            except Exception:
                flash("That rack name already exists.", "danger")
        return redirect(url_for("racks.list_racks"))

    racks = db.execute(
        """SELECT r.*, COUNT(i.id) AS item_count FROM racks r
           LEFT JOIN items i ON i.rack_id = r.id AND i.active = 1
           GROUP BY r.id ORDER BY r.name"""
    ).fetchall()
    return render_template("racks/list.html", racks=racks)


@bp.route("/<int:rack_id>/delete", methods=("POST",))
@permission_required("perm_items")
def delete_rack(rack_id):
    db = get_db()
    in_use = db.execute(
        "SELECT COUNT(*) AS c FROM items WHERE rack_id=? AND active=1", (rack_id,)
    ).fetchone()
    if in_use["c"] > 0:
        flash(f"Can't remove that rack — {in_use['c']} item(s) are still assigned to it. Move them to another rack first.", "danger")
    else:
        db.execute("DELETE FROM racks WHERE id=?", (rack_id,))
        db.commit()
        flash("Rack removed.", "success")
    return redirect(url_for("racks.list_racks"))
