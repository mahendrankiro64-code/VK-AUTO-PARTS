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


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("VKAP_SECRET_KEY", "vk-auto-parts-dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap

    # init_db() runs CREATE TABLE IF NOT EXISTS, so it's safe on every boot.
    init_db(app)

    if is_fresh_database():
        seed_defaults()

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

    app.jinja_env.filters["money"] = fmt_money

    @app.context_processor
    def inject_globals():
        return {"current_user": getattr(g, "user", None), "today": today_str(), "biz_name": "VK Auto Parts"}

    return app


def seed_defaults():
    """Create the first admin user and default categories. Only runs once,
    the moment the database is empty (see is_fresh_database())."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s)",
        ("admin", generate_password_hash("admin123"), "Shop Owner", "admin"),
    )
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
