"""Tests for Step 6: date-range filter on GET /profile.

Run with:  python -m pytest tests/test_06-date-filter-profile-page.py
"""
import inspect
from datetime import date

import pytest

import app as app_module
from database import db, queries

EMAIL = "filter@example.com"
PASSWORD = "pw12345"

# (date, category, amount, description) -- descriptions are unique tokens.
BASE_EXPENSES = [
    ("2026-01-05", "Food", 100.0, "Alpha-item"),
    ("2026-01-15", "Transport", 200.0, "Bravo-item"),
    ("2026-02-01", "Food", 300.0, "Charlie-item"),
    ("2026-02-20", "Bills", 400.0, "Delta-item"),
]

FLASH_MSG = "Start date must be on or before end date"
EMPTY_MSG = "No transactions in this period."


def _insert(user_id, rows):
    conn = db.get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, amt, cat, d, desc) for d, cat, amt, desc in rows],
        )
        conn.commit()
    finally:
        conn.close()


def _dump_expenses():
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses ORDER BY id"
        ).fetchall()
        return [tuple(r) for r in rows]
    finally:
        conn.close()


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    app_module.app.config["TESTING"] = True


@pytest.fixture
def client(isolated_db):
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def user_id(client):
    return db.create_user("Filter User", EMAIL, PASSWORD)


@pytest.fixture
def logged_in(client, user_id):
    _insert(user_id, BASE_EXPENSES)
    resp = client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code in (302, 200)
    return client


def get_profile(client, query=""):
    return client.get("/profile" + query, follow_redirects=True).get_data(as_text=True)


# ---------------------------------------------------------------- helpers

class TestHelperSignatures:
    @pytest.mark.parametrize(
        "func",
        [
            queries.get_summary_stats,
            queries.get_recent_transactions,
            queries.get_category_breakdown,
        ],
    )
    def test_helper_has_optional_date_params_defaulting_to_none(self, func):
        params = inspect.signature(func).parameters
        for name in ("date_from", "date_to"):
            assert name in params, f"{func.__name__} missing {name}"
            assert params[name].default is None, f"{name} must default to None"


class TestHelperFiltering:
    def test_summary_stats_no_dates_is_unfiltered(self, logged_in, user_id):
        stats = queries.get_summary_stats(user_id)
        assert stats["total_spent"] == pytest.approx(1000.0)
        assert stats["transaction_count"] == 4

    def test_summary_stats_inclusive_both_ends(self, logged_in, user_id):
        stats = queries.get_summary_stats(
            user_id, date_from="2026-01-15", date_to="2026-02-01"
        )
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(500.0)
        assert stats["top_category"] == "Food"

    def test_summary_stats_only_from(self, logged_in, user_id):
        stats = queries.get_summary_stats(user_id, date_from="2026-02-01")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(700.0)

    def test_summary_stats_only_to(self, logged_in, user_id):
        stats = queries.get_summary_stats(user_id, date_to="2026-01-15")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(300.0)

    def test_summary_stats_empty_range(self, logged_in, user_id):
        stats = queries.get_summary_stats(
            user_id, date_from="2030-01-01", date_to="2030-12-31"
        )
        assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    def test_recent_transactions_filtered_newest_first(self, logged_in, user_id):
        txs = queries.get_recent_transactions(
            user_id, date_from="2026-01-15", date_to="2026-02-20"
        )
        assert [t["description"] for t in txs] == [
            "Delta-item",
            "Charlie-item",
            "Bravo-item",
        ]

    def test_recent_transactions_empty_range(self, logged_in, user_id):
        assert (
            queries.get_recent_transactions(
                user_id, date_from="2030-01-01", date_to="2030-12-31"
            )
            == []
        )

    def test_recent_transactions_default_limit_is_ten(self, logged_in, user_id):
        _insert(
            user_id,
            [("2026-03-%02d" % (i + 1), "Misc", 1.0, f"Bulk-{i:02d}") for i in range(12)],
        )
        assert len(queries.get_recent_transactions(user_id)) == 10

    def test_recent_transactions_limit_none_returns_all(self, logged_in, user_id):
        _insert(
            user_id,
            [("2026-03-%02d" % (i + 1), "Misc", 1.0, f"Bulk-{i:02d}") for i in range(12)],
        )
        txs = queries.get_recent_transactions(
            user_id, date_from="2026-03-01", date_to="2026-03-31", limit=None
        )
        assert len(txs) == 12

    def test_category_breakdown_filtered(self, logged_in, user_id):
        cats = queries.get_category_breakdown(
            user_id, date_from="2026-01-15", date_to="2026-02-01"
        )
        assert {c["name"] for c in cats} == {"Food", "Transport"}
        amounts = {c["name"]: c["amount"] for c in cats}
        assert amounts["Food"] == pytest.approx(300.0)
        assert amounts["Transport"] == pytest.approx(200.0)
        assert sum(c["pct"] for c in cats) == 100

    def test_category_breakdown_pct_sums_to_100_with_rounding(self, logged_in, user_id):
        # Three equal categories (33.33% each) must still sum to exactly 100.
        _insert(
            user_id,
            [
                ("2026-03-01", "CatA", 100.0, "ra"),
                ("2026-03-02", "CatB", 100.0, "rb"),
                ("2026-03-03", "CatC", 100.0, "rc"),
            ],
        )
        cats = queries.get_category_breakdown(
            user_id, date_from="2026-03-01", date_to="2026-03-31"
        )
        assert len(cats) == 3
        assert sum(c["pct"] for c in cats) == 100

    def test_category_breakdown_empty_range(self, logged_in, user_id):
        assert (
            queries.get_category_breakdown(
                user_id, date_from="2030-01-01", date_to="2030-12-31"
            )
            == []
        )

    def test_filter_only_affects_requesting_user(self, logged_in, user_id):
        other = db.create_user("Other", "other@example.com", "pw12345")
        _insert(other, [("2026-01-10", "Food", 9999.0, "Intruder-item")])
        stats = queries.get_summary_stats(
            user_id, date_from="2026-01-01", date_to="2026-01-31"
        )
        assert stats["total_spent"] == pytest.approx(300.0)
        assert stats["transaction_count"] == 2


# ----------------------------------------------------------------- routes

class TestAuthGuard:
    @pytest.mark.parametrize(
        "query",
        ["?from=2026-01-01", "?to=2026-01-31", "?from=2026-01-01&to=2026-01-31", "?from=abc"],
    )
    def test_unauthenticated_filtered_profile_redirects_to_login(self, client, query):
        resp = client.get("/profile" + query)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, logged_in):
        html = get_profile(logged_in)
        for desc in ("Alpha-item", "Bravo-item", "Charlie-item", "Delta-item"):
            assert desc in html, f"{desc} missing from unfiltered view"
        assert "₹1,000.00" in html
        assert '<p class="stat-value">4</p>' in html
        assert "Recent transactions" in html

    def test_empty_params_equal_unfiltered(self, logged_in):
        html = get_profile(logged_in, "?from=&to=")
        for desc in ("Alpha-item", "Bravo-item", "Charlie-item", "Delta-item"):
            assert desc in html
        assert "₹1,000.00" in html
        assert FLASH_MSG not in html
        assert "Recent transactions" in html

    def test_seed_user_no_params_shows_all_8(self, isolated_db):
        db.seed_db()
        with app_module.app.test_client() as c:
            c.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
            html = get_profile(c)
        assert "₹6,249.25" in html
        assert '<p class="stat-value">8</p>' in html


class TestFilteredRange:
    def test_both_bounds_inclusive(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-15&to=2026-02-01")
        assert "Bravo-item" in html, "from date must be inclusive"
        assert "Charlie-item" in html, "to date must be inclusive"
        assert "Alpha-item" not in html
        assert "Delta-item" not in html
        assert "₹500.00" in html
        assert '<p class="stat-value">2</p>' in html
        assert '<p class="stat-value">Food</p>' in html

    def test_single_day_range(self, logged_in):
        html = get_profile(logged_in, "?from=2026-02-01&to=2026-02-01")
        assert "Charlie-item" in html
        assert "Bravo-item" not in html and "Delta-item" not in html
        assert "₹300.00" in html

    def test_only_from_is_open_ended(self, logged_in):
        html = get_profile(logged_in, "?from=2026-02-01")
        assert "Charlie-item" in html and "Delta-item" in html
        assert "Alpha-item" not in html and "Bravo-item" not in html
        assert "₹700.00" in html

    def test_only_to_is_open_ended(self, logged_in):
        html = get_profile(logged_in, "?to=2026-01-15")
        assert "Alpha-item" in html and "Bravo-item" in html
        assert "Charlie-item" not in html and "Delta-item" not in html
        assert "₹300.00" in html

    def test_category_breakdown_reflects_filter(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-15&to=2026-02-01")
        assert html.count("cat-row-head") == 2
        assert "Bills" not in html

    def test_filtered_view_not_capped_at_ten(self, logged_in, user_id):
        _insert(
            user_id,
            [("2026-03-%02d" % (i + 1), "Misc", 1.0, f"Bulk-{i:02d}") for i in range(12)],
        )
        html = get_profile(logged_in, "?from=2026-03-01&to=2026-03-31")
        for i in range(12):
            assert f"Bulk-{i:02d}" in html, f"Bulk-{i:02d} missing; list was capped"

    def test_other_users_expenses_never_shown(self, logged_in):
        other = db.create_user("Other", "other@example.com", "pw12345")
        _insert(other, [("2026-01-10", "Food", 9999.0, "Intruder-item")])
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-01-31")
        assert "Intruder-item" not in html
        assert "9,999" not in html

    def test_currency_symbol_is_rupee(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-12-31")
        assert "₹" in html
        assert "$" not in html


class TestEmptyRange:
    URL = "?from=2030-01-01&to=2030-12-31"

    def test_empty_range_shows_zero_state(self, logged_in):
        resp = logged_in.get("/profile" + self.URL)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "₹0.00" in html
        assert '<p class="stat-value">0</p>' in html
        assert '<p class="stat-value">—</p>' in html
        assert EMPTY_MSG in html
        assert html.count("cat-row-head") == 0
        for desc in ("Alpha-item", "Bravo-item", "Charlie-item", "Delta-item"):
            assert desc not in html


class TestInvalidRange:
    def test_from_after_to_flashes_error(self, logged_in):
        html = get_profile(logged_in, "?from=2026-02-01&to=2026-01-01")
        assert FLASH_MSG in html

    def test_from_after_to_falls_back_to_unfiltered(self, logged_in):
        resp = logged_in.get("/profile?from=2026-02-01&to=2026-01-01", follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        for desc in ("Alpha-item", "Bravo-item", "Charlie-item", "Delta-item"):
            assert desc in html, f"{desc} missing; should fall back to all-time"
        assert "₹1,000.00" in html

    def test_valid_range_has_no_error_flash(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-01-31")
        assert FLASH_MSG not in html

    @pytest.mark.parametrize(
        "query",
        [
            "?from=abc",
            "?to=abc",
            "?from=abc&to=xyz",
            "?from=2026-13-45",
            "?to=2026-02-30",
            "?from=01/02/2026",
            "?from=%20",
            "?from=' OR 1=1 --",
            "?from=2026-01-01'; DROP TABLE expenses; --",
            "?from=" + "9" * 5000,
        ],
    )
    def test_garbage_dates_do_not_500(self, logged_in, query):
        resp = logged_in.get("/profile" + query)
        assert resp.status_code == 200, f"{query[:40]!r} caused {resp.status_code}"

    def test_garbage_from_treated_as_missing(self, logged_in):
        html = get_profile(logged_in, "?from=abc")
        for desc in ("Alpha-item", "Bravo-item", "Charlie-item", "Delta-item"):
            assert desc in html
        assert "₹1,000.00" in html

    def test_garbage_from_valid_to_acts_as_only_to(self, logged_in):
        html = get_profile(logged_in, "?from=abc&to=2026-01-15")
        assert "Alpha-item" in html and "Bravo-item" in html
        assert "Charlie-item" not in html and "Delta-item" not in html

    def test_sql_injection_attempt_leaves_data_intact(self, logged_in):
        before = _dump_expenses()
        logged_in.get("/profile?from=2026-01-01'; DROP TABLE expenses; --")
        logged_in.get("/profile?to=' OR '1'='1")
        assert _dump_expenses() == before


class TestNoSideEffects:
    @pytest.mark.parametrize(
        "query",
        [
            "",
            "?from=2026-01-15&to=2026-02-01",
            "?from=2030-01-01&to=2030-12-31",
            "?from=2026-02-01&to=2026-01-01",
            "?from=abc",
        ],
    )
    def test_filtering_does_not_modify_database(self, logged_in, query):
        before = _dump_expenses()
        logged_in.get("/profile" + query, follow_redirects=True)
        assert _dump_expenses() == before


class TestTemplateElements:
    def test_filter_form_is_get_with_date_inputs(self, logged_in):
        html = get_profile(logged_in)
        assert 'method="get"' in html.lower()
        assert 'type="date"' in html
        assert 'name="from"' in html
        assert 'name="to"' in html
        assert "Apply" in html

    def test_filter_bar_above_stats(self, logged_in):
        html = get_profile(logged_in)
        assert html.index('name="from"') < html.index("stat-value")

    def test_clear_link_points_to_plain_profile(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-01-31")
        assert "Clear" in html
        assert 'href="/profile"' in html

    def test_inputs_prefilled_with_active_values(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-05&to=2026-02-01")
        assert 'value="2026-01-05"' in html
        assert 'value="2026-02-01"' in html

    def test_inputs_not_prefilled_when_unfiltered(self, logged_in):
        html = get_profile(logged_in)
        assert 'value="2026-' not in html

    def test_preset_links_present(self, logged_in):
        html = get_profile(logged_in)
        for label in ("This month", "Last 30 days", "All time"):
            assert label in html, f"preset {label!r} missing"

    def test_this_month_preset_starts_on_first_of_current_month(self, logged_in):
        today = date.today()
        first = today.replace(day=1).isoformat()
        html = get_profile(logged_in)
        assert f"from={first}" in html

    def test_panel_title_is_transactions_when_filtered(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-12-31")
        assert "Recent transactions" not in html
        assert "Transactions" in html

    def test_panel_title_is_recent_when_unfiltered(self, logged_in):
        assert "Recent transactions" in get_profile(logged_in)

    def test_active_range_label_shown_when_filtered(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-05&to=2026-02-01")
        assert 'class="filter-range"' in html
        label = html.split('class="filter-range"', 1)[1].split("</p>", 1)[0]
        assert "5 Jan 2026" in label
        assert "1 Feb 2026" in label

    def test_active_range_label_absent_when_unfiltered(self, logged_in):
        html = get_profile(logged_in)
        assert 'class="filter-range"' not in html

    def test_empty_state_message_not_shown_when_results_exist(self, logged_in):
        html = get_profile(logged_in, "?from=2026-01-01&to=2026-12-31")
        assert EMPTY_MSG not in html
