"""Simple session-based authentication (no external deps)."""
import functools
from flask import Blueprint, session, redirect, url_for, request, flash, g, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

bp = Blueprint("auth", __name__)

# Every togglable permission, in the order they're shown on the Users page.
# (key, label)
PERMISSIONS = [
    ("perm_sales", "Make sales (POS)"),
    ("perm_quotations", "Create quotations"),
    ("perm_purchases", "Purchase entry"),
    ("perm_items", "Manage inventory / items"),
    ("perm_customers", "Manage customers"),
    ("perm_suppliers", "Manage suppliers"),
    ("perm_dayend", "Open/close day-end"),
    ("perm_reports", "View reports"),
    ("perm_accounts", "View accounts / profit / expenses"),
    ("perm_cancel", "Cancel invoices"),
]


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute(
            "SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)
        ).fetchone()


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        if g.user["role"] != "admin":
            flash("Only admins can access that page.", "danger")
            return redirect(url_for("dashboard.index"))
        return view(**kwargs)
    return wrapped_view


def has_permission(user, perm_key):
    """Admins always have every permission. Cashiers depend on their
    individual perm_* flags."""
    if user is None:
        return False
    if user["role"] == "admin":
        return True
    try:
        return bool(user[perm_key])
    except (KeyError, IndexError):
        return False


def permission_required(perm_key):
    """Route decorator: require login AND a specific permission flag
    (admins bypass every check)."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.path))
            if not has_permission(g.user, perm_key):
                flash("You don't have permission to access that page. Ask an admin to grant it from the Users page.", "danger")
                return redirect(url_for("dashboard.index"))
            return view(**kwargs)
        return wrapped_view
    return decorator


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Incorrect username or password."
        elif not user["active"]:
            error = "This user account is disabled."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            nxt = request.args.get("next") or url_for("dashboard.index")
            return redirect(nxt)
        flash(error, "danger")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/users", methods=("GET", "POST"))
@admin_required
def users():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form["username"].strip()
            full_name = request.form["full_name"].strip()
            role = request.form.get("role", "cashier")
            password = request.form["password"]
            existing = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                flash("That username already exists.", "danger")
            else:
                perm_values = [1 if request.form.get(key) else 0 for key, _ in PERMISSIONS]
                cols = ", ".join(key for key, _ in PERMISSIONS)
                placeholders = ", ".join("?" for _ in PERMISSIONS)
                db.execute(
                    f"""INSERT INTO users (username, password_hash, full_name, role, {cols})
                        VALUES (?,?,?,?,{placeholders})""",
                    [username, generate_password_hash(password), full_name, role] + perm_values,
                )
                db.commit()
                flash(f"User '{username}' created.", "success")
        elif action == "toggle":
            uid = request.form["user_id"]
            db.execute("UPDATE users SET active = 1 - active WHERE id = ?", (uid,))
            db.commit()
            flash("User status updated.", "success")
        elif action == "update_permissions":
            uid = request.form["user_id"]
            perm_values = [1 if request.form.get(key) else 0 for key, _ in PERMISSIONS]
            set_clause = ", ".join(f"{key} = ?" for key, _ in PERMISSIONS)
            db.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?",
                perm_values + [uid],
            )
            db.commit()
            flash("Permissions updated.", "success")
        return redirect(url_for("auth.users"))

    all_users = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("users.html", users=all_users, permissions=PERMISSIONS)
