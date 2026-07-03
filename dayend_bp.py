from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import get_db
from auth import login_required
from helpers import today_str, now_str, get_or_create_open_dayend, recompute_dayend_totals

bp = Blueprint("dayend", __name__, url_prefix="/dayend")


@bp.route("/", methods=("GET", "POST"))
@login_required
def today():
    db = get_db()
    de = get_or_create_open_dayend(db, opened_by=g.user["id"] if g.user else None)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "set_opening":
            opening = float(request.form.get("opening_balance") or 0)
            db.execute(
                "UPDATE day_end SET opening_balance=? WHERE business_date=?",
                (opening, de["business_date"]),
            )
            db.commit()
            flash("Opening balance updated.", "success")
        elif action == "set_expenses":
            expenses = float(request.form.get("expenses") or 0)
            db.execute(
                "UPDATE day_end SET expenses=? WHERE business_date=?",
                (expenses, de["business_date"]),
            )
            db.commit()
            flash("Cash expenses updated.", "success")
        elif action == "close_day":
            actual = float(request.form.get("closing_balance_actual") or 0)
            notes = request.form.get("notes", "").strip()
            recompute_dayend_totals(db, de["business_date"])
            de2 = db.execute(
                "SELECT * FROM day_end WHERE business_date=?", (de["business_date"],)
            ).fetchone()
            diff = actual - de2["closing_balance_expected"]
            db.execute(
                """UPDATE day_end SET closing_balance_actual=?, difference=?, notes=?,
                   status='closed', closed_by=?, closed_at=?
                   WHERE business_date=?""",
                (actual, diff, notes, g.user["id"] if g.user else None, now_str(),
                 de["business_date"]),
            )
            db.commit()
            flash("Day closed successfully.", "success")
        return redirect(url_for("dayend.today"))

    de = recompute_dayend_totals(db, de["business_date"]) or de
    return render_template("dayend/index.html", de=de)


@bp.route("/history")
@login_required
def history():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM day_end ORDER BY business_date DESC LIMIT 90"
    ).fetchall()
    return render_template("dayend/history.html", rows=rows)
