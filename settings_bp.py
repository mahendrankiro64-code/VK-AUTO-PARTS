from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db, get_setting, set_setting
from auth import admin_required

bp = Blueprint("settings", __name__, url_prefix="/settings")

FIELDS = ["shop_name", "shop_address", "shop_phone", "invoice_footer_note", "logo_filename"]


@bp.route("/", methods=("GET", "POST"))
@admin_required
def index():
    db = get_db()
    if request.method == "POST":
        for key in FIELDS:
            set_setting(db, key, request.form.get(key, "").strip())
        flash("Invoice / shop settings saved.", "success")
        return redirect(url_for("settings.index"))

    values = {key: get_setting(db, key, "") for key in FIELDS}
    return render_template("settings/index.html", values=values)
