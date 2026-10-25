from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    sql = ""
    params = []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    return sql, params


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


def get_summary_stats(user_id, date_from=None, date_to=None):
    clause, extra = _date_clause(date_from, date_to)
    params = (user_id, *extra)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?" + clause,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": float(totals["total"]),
        "transaction_count": int(totals["cnt"]),
        "top_category": top["category"] if top else "—",
    }


# ---- SECTION: transaction history (subagent 1) ----------------------
def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    params = [user_id, *params]
    sql = (
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
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
def get_category_breakdown(user_id, date_from=None, date_to=None):
    clause, extra = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY total DESC",
            (user_id, *extra),
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
