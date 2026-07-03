import base64

from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_db, get_setting, set_setting
from auth import admin_required
from themes import THEMES, DEFAULT_THEME

bp = Blueprint("settings", __name__, url_prefix="/settings")

FIELDS = ["shop_name", "shop_address", "shop_phone", "invoice_footer_note"]

# Logos are stored directly in the database as a base64 data: URL (under the
# "logo_data" setting key) instead of as a file on disk. This is deliberate:
# Render's free tier wipes any file the app itself writes to disk on every
# restart/redeploy, so a normal file upload would just vanish. Storing the
# image as text in Postgres survives restarts and needs zero GitHub/file
# steps from the shop owner -- upload once here and it's done.
ALLOWED_LOGO_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for a logo and keeps page loads fast


@bp.route("/", methods=("GET", "POST"))
@admin_required
def index():
    db = get_db()
    if request.method == "POST":
        for key in FIELDS:
            set_setting(db, key, request.form.get(key, "").strip())

        theme_key = request.form.get("pos_theme", DEFAULT_THEME)
        if theme_key not in THEMES:
            theme_key = DEFAULT_THEME
        set_setting(db, "pos_theme", theme_key)

        if request.form.get("remove_logo") == "1":
            set_setting(db, "logo_data", "")
        else:
            logo_file = request.files.get("logo_file")
            if logo_file and logo_file.filename:
                mime = (logo_file.mimetype or "").lower()
                if mime not in ALLOWED_LOGO_TYPES:
                    flash("Logo must be a PNG, JPG, or WEBP image.", "danger")
                else:
                    data = logo_file.read()
                    if len(data) > MAX_LOGO_BYTES:
                        flash("That logo image is too large (max 2 MB). Please use a smaller image.", "danger")
                    else:
                        b64 = base64.b64encode(data).decode("ascii")
                        set_setting(db, "logo_data", f"data:{mime};base64,{b64}")
                        flash("Logo uploaded.", "success")

        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))

    values = {key: get_setting(db, key, "") for key in FIELDS}
    values["logo_data"] = get_setting(db, "logo_data", "")
    values["pos_theme"] = get_setting(db, "pos_theme", DEFAULT_THEME)
    return render_template("settings/index.html", values=values, themes=THEMES)
