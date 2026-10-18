import pytest

import app as app_module
from database import db, queries


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def seed_id(client):
    return db.get_user_by_email("demo@spendly.com")["id"]


@pytest.fixture
def empty_id(client):
    return db.create_user("New Person", "new@example.com", "pw12345")


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


# ---- unit tests ------------------------------------------------------

def test_get_user_by_id_valid(seed_id):
    user = queries.get_user_by_id(seed_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    month, year = user["member_since"].split()
    assert month.isalpha() and len(year) == 4


def test_get_user_by_id_missing(client):
    assert queries.get_user_by_id(9999) is None


def test_get_summary_stats_with_expenses(seed_id):
    stats = queries.get_summary_stats(seed_id)
    assert stats["total_spent"] == pytest.approx(6249.25)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_get_summary_stats_no_expenses(empty_id):
    assert queries.get_summary_stats(empty_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_get_recent_transactions_newest_first(seed_id):
    txs = queries.get_recent_transactions(seed_id)
    assert len(txs) == 8
    assert set(txs[0]) == {"date", "description", "category", "amount"}
    assert txs[0]["description"] == "Miscellaneous"
    assert txs[-1]["description"] == "Electricity bill"


def test_get_recent_transactions_empty(empty_id):
    assert queries.get_recent_transactions(empty_id) == []


def test_get_category_breakdown(seed_id):
    cats = queries.get_category_breakdown(seed_id)
    assert len(cats) == 7
    assert cats[0]["name"] == "Shopping"
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_empty(empty_id):
    assert queries.get_category_breakdown(empty_id) == []


# ---- route tests -----------------------------------------------------

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_seed_user(client):
    login(client)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹6,249.25" in html
    assert "<p class=\"stat-value\">8</p>" in html
    assert "<p class=\"stat-value\">Shopping</p>" in html
    assert html.index("Miscellaneous") < html.index("Electricity bill")
    assert html.count("cat-row-head") == 7


def test_profile_new_user_empty(client, empty_id):
    login(client, "new@example.com", "pw12345")
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "No transactions yet." in html


def test_profile_stale_session_redirects(client):
    with client.session_transaction() as s:
        s["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
