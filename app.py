import calendar
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    error = None
    if not name or not email or not password or not confirm_password:
        error = "All fields are required"
    elif password != confirm_password:
        error = "Passwords do not match"
    else:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "Email already registered"

    if error:
        flash(error, "error")
        return render_template("register.html", name=name, email=email)

    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are required", "error")
        return render_template("login.html", email=email)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password", "error")
        return render_template("login.html", email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Profile and placeholder routes                                      #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_day(d):
    return f"{d.day} {d.strftime('%b %Y')}"


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # ---- SECTION: date filter ----
    start = _parse_iso_date(request.args.get("from"))
    end = _parse_iso_date(request.args.get("to"))
    range_reversed = bool(start and end and start > end)
    if range_reversed:
        start = end = None
    date_from = start.isoformat() if start else None
    date_to = end.isoformat() if end else None
    filter_active = bool(start or end)

    today = date.today()
    presets = {
        "month_start": today.replace(day=1).isoformat(),
        "month_end": today.replace(
            day=calendar.monthrange(today.year, today.month)[1]
        ).isoformat(),
        "last30_start": (today - timedelta(days=29)).isoformat(),
        "last30_end": today.isoformat(),
    }

    range_label = ""
    if start and end:
        range_label = f"{_format_day(start)} – {_format_day(end)}"
    elif start:
        range_label = f"From {_format_day(start)}"
    elif end:
        range_label = f"Until {_format_day(end)}"
    # ---- END SECTION: date filter ----

    # ---- SECTION: user + summary stats (subagent 2) ----
    user = get_user_by_id(user_id)
    if user is not None:
        words = user["name"].split()
        user["initials"] = (
            (words[0][0] + words[-1][0]).upper() if len(words) > 1
            else words[0][0].upper() if words else "?"
        )
    stats = get_summary_stats(user_id, date_from, date_to)
    # ---- END SECTION: user + summary stats ----

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if range_reversed:
        flash("Start date must be on or before end date", "error")

    # ---- SECTION: transaction history (subagent 1) ----
    transactions = get_recent_transactions(
        user_id,
        limit=None if filter_active else 10,
        date_from=date_from,
        date_to=date_to,
    )
    # ---- END SECTION: transaction history ----

    # ---- SECTION: category breakdown (subagent 3) ----
    categories = get_category_breakdown(user_id, date_from, date_to)
    for c in categories:
        c["bar"] = round(c["pct"] / 5) * 5
    # ---- END SECTION: category breakdown ----

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_from=date_from or "",
        date_to=date_to or "",
        filter_active=filter_active,
        range_label=range_label,
        presets=presets,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True,port=5001)
