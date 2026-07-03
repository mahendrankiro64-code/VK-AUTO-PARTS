"""Simple session-based authentication (no external deps)."""
import functools
from flask import Blueprint, session, redirect, url_for, request, flash, g, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

bp = Blueprint("auth", __name__)


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
                db.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
                    (username, generate_password_hash(password), full_name, role),
                )
                db.commit()
                flash(f"User '{username}' created.", "success")
        elif action == "toggle":
            uid = request.form["user_id"]
            db.execute("UPDATE users SET active = 1 - active WHERE id = ?", (uid,))
            db.commit()
            flash("User status updated.", "success")
        return redirect(url_for("auth.users"))

    all_users = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("users.html", users=all_users)
