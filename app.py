import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

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
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Rudraksh Sindwani",
        "email": "rudraksh@example.com",
        "initials": "RS",
        "member_since": "January 2026",
    }

    transactions = [
        {"date": "12 Oct 2026", "description": "Swiggy dinner", "category": "Food", "amount": 640},
        {"date": "10 Oct 2026", "description": "Metro card recharge", "category": "Transport", "amount": 500},
        {"date": "08 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 1850},
        {"date": "05 Oct 2026", "description": "Running shoes", "category": "Shopping", "amount": 2600},
        {"date": "03 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 420},
        {"date": "01 Oct 2026", "description": "Grocery run", "category": "Food", "amount": 1380},
    ]

    category_totals = [
        ("Food", 4200),
        ("Bills", 3500),
        ("Shopping", 2600),
        ("Transport", 1800),
        ("Health", 900),
    ]
    grand_total = sum(total for _, total in category_totals)
    categories = [
        {
            "name": name,
            "total": total,
            "percent": round(total / grand_total * 100),
            # bar widths are bucketed to 5% steps so CSS classes can size them
            "bar": round(total / grand_total * 20) * 5,
        }
        for name, total in category_totals
    ]

    stats = {
        "total_spent": grand_total,
        "transaction_count": 24,
        "top_category": category_totals[0][0],
    }

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
