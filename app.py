import os
import psycopg2
from flask import Flask, g
from werkzeug.security import generate_password_hash

from db import init_db, is_fresh_database, DATABASE_URL
from helpers import fmt_money, today_str

import auth
import dashboard_bp
import items_bp
import customers_bp
import suppliers_bp
import purchases_bp
import sales_bp
import dayend_bp
import excel_io
import reports_bp
import racks_bp
import quotations_bp
import accounts_bp
import settings_bp
import scan_bp
import themes
from db import get_setting


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("VKAP_SECRET_KEY", "vk-auto-parts-dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

    # init_db() runs CREATE TABLE/ALTER TABLE ... IF NOT EXISTS, so it's
    # always safe to call on every boot, even against an already-live
    # database with real data in it.
    init_db(app)

    if is_fresh_database():
        seed_defaults()
    seed_reference_data()  # always runs; every insert is ON CONFLICT DO NOTHING

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard_bp.bp)
    app.register_blueprint(items_bp.bp)
    app.register_blueprint(customers_bp.bp)
    app.register_blueprint(suppliers_bp.bp)
    app.register_blueprint(purchases_bp.bp)
    app.register_blueprint(sales_bp.bp)
    app.register_blueprint(dayend_bp.bp)
    app.register_blueprint(excel_io.bp)
    app.register_blueprint(reports_bp.bp)
    app.register_blueprint(racks_bp.bp)
    app.register_blueprint(quotations_bp.bp)
    app.register_blueprint(accounts_bp.bp)
    app.register_blueprint(settings_bp.bp)
    app.register_blueprint(scan_bp.bp)

    app.jinja_env.filters["money"] = fmt_money
    app.jinja_env.globals["has_permission"] = auth.has_permission

    @app.context_processor
    def inject_globals():
        db = None
        try:
            from db import get_db
            db = get_db()
            shop_name = get_setting(db, "shop_name", "VK Auto Parts")
            logo_filename = get_setting(db, "logo_filename", "")
            logo_data = get_setting(db, "logo_data", "")
            shop_address = get_setting(db, "shop_address", "")
            shop_phone = get_setting(db, "shop_phone", "")
            invoice_footer_note = get_setting(db, "invoice_footer_note", "Thank you for your business!")
            theme = themes.get_theme(get_setting(db, "pos_theme", themes.DEFAULT_THEME))
        except Exception:
            shop_name = "VK Auto Parts"
            logo_filename = ""
            logo_data = ""
            shop_address = ""
            shop_phone = ""
            invoice_footer_note = "Thank you for your business!"
            theme = themes.get_theme(themes.DEFAULT_THEME)
        return {
            "current_user": getattr(g, "user", None),
            "today": today_str(),
            "biz_name": shop_name,
            "logo_filename": logo_filename,
            "logo_data": logo_data,
            "shop_address": shop_address,
            "shop_phone": shop_phone,
            "invoice_footer_note": invoice_footer_note,
            "theme": theme,
        }

    return app


def seed_defaults():
    """Create the first admin user. Only runs once, the moment the database
    is empty (see is_fresh_database())."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s)",
        ("admin", generate_password_hash("admin123"), "Shop Owner", "admin"),
    )
    conn.commit()
    cur.close()
    conn.close()


def seed_reference_data():
    """Seed default categories, expense categories, and shop settings.
    Runs on EVERY boot (not just fresh installs) so upgrading an existing
    live deployment picks up new reference data automatically. Every insert
    is ON CONFLICT DO NOTHING, so it never overwrites anything the shop has
    already customized."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    default_categories = [
        ("Engine Parts", "ENG"), ("Brake Parts", "BRK"), ("Electrical", "ELE"),
        ("Body Parts", "BDY"), ("Filters", "FLT"), ("Lubricants", "LUB"),
        ("Suspension", "SUS"), ("Tyres & Wheels", "TYR"), ("Accessories", "ACC"),
    ]
    for name, prefix in default_categories:
        cur.execute(
            "INSERT INTO categories (name, prefix) VALUES (%s,%s) ON CONFLICT (name) DO NOTHING",
            (name, prefix),
        )

    default_expense_categories = [
        "Transport", "Electricity", "Water", "Tea / Meals", "Rent", "Salaries",
        "Repairs & Maintenance", "Telephone / Internet", "Loading / Unloading",
        "Sundry / Misc",
    ]
    for name in default_expense_categories:
        cur.execute(
            "INSERT INTO expense_categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            (name,),
        )

    default_settings = {
        "shop_name": "VK Auto Parts",
        "shop_address": "Gampola Kahatapitiya",
        "shop_phone": "",
        "invoice_footer_note": "Thank you for your business!",
        "logo_filename": "",
    }
    for key, value in default_settings.items():
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING",
            (key, value),
        )

    conn.commit()
    cur.close()
    conn.close()


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Debug mode is OFF by default for safety (it exposes a code-execution
    # debugger in the browser). Set VKAP_DEBUG=1 only on your own machine
    # while developing, never on a public deployment.
    debug = os.environ.get("VKAP_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
