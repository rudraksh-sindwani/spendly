from datetime import datetime

from datetime import datetime

from database.db import get_db


# ---- SECTION: user + summary stats (subagent 2) ---------------------
def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = ""
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


def get_summary_stats(user_id):
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": float(totals["total"]),
        "transaction_count": int(totals["cnt"]),
        "top_category": top["category"] if top else "—",
    }


# ---- SECTION: transaction history (subagent 1) ----------------------
def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    transactions = []
    for row in rows:
        d = datetime.strptime(row["date"], "%Y-%m-%d")
        transactions.append({
            "date": f"{d.day} {d.strftime('%b %Y')}",
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        })
    return transactions


# ---- SECTION: category breakdown (subagent 3) -----------------------
def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    grand = sum(r["total"] for r in rows)
    if not rows or grand <= 0:
        return []
    result = [
        {"name": r["category"], "amount": float(r["total"]),
         "pct": int(round(r["total"] * 100 / grand))}
        for r in rows
    ]
    result[0]["pct"] += 100 - sum(c["pct"] for c in result)
    return result
