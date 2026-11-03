"""Tests for Step 7: Add Expense (GET/POST /expenses/add).

Run with:  python -m pytest tests/test_07-add-expense.py
"""
import os
import tempfile
from datetime import date, timedelta

import pytest

from database import db

# Point the DB at a throwaway file BEFORE importing app, because app.py runs
# init_db()/seed_db() at import time and must never touch expense_tracker.db.
_IMPORT_TMP = tempfile.mkdtemp(prefix="spendly_import_")
_REAL_DB_PATH = db.DB_PATH
db.DB_PATH = os.path.join(_IMPORT_TMP, "import.db")

import app as app_module  # noqa: E402

db.DB_PATH = _REAL_DB_PATH

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
URL = "/expenses/add"
PROFILE = "/profile"


def _today():
    return date.today().isoformat()


def _valid(**overrides):
    data = {
        "amount": "250.50",
        "category": "Food",
        "date": _today(),
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def _all_expenses():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()]
    finally:
        conn.close()


def _expenses_for(user_id):
    return [e for e in _all_expenses() if e["user_id"] == user_id]


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
def user_id(isolated_db):
    return db.create_user("Adder", "adder@example.com", "pw12345")


@pytest.fixture
def other_user_id(isolated_db):
    return db.create_user("Other", "other@example.com", "pw12345")


def _login_as(client, uid):
    with client.session_transaction() as sess:
        sess["user_id"] = uid


@pytest.fixture
def auth_client(client, user_id):
    _login_as(client, user_id)
    return client


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        r = client.get(URL)
        assert r.status_code == 302, "Logged-out GET should redirect"
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_redirects_to_login(self, client):
        r = client.post(URL, data=_valid())
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_does_not_insert(self, client, user_id):
        client.post(URL, data=_valid())
        assert _all_expenses() == [], "No expense may be saved when logged out"


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestForm:
    def test_get_logged_in_returns_200(self, auth_client):
        assert auth_client.get(URL).status_code == 200

    def test_form_prefills_today(self, auth_client):
        html = auth_client.get(URL).get_data(as_text=True)
        assert _today() in html, "Date should be pre-filled with today"

    @pytest.mark.parametrize("cat", CATEGORIES)
    def test_form_lists_each_category(self, auth_client, cat):
        html = auth_client.get(URL).get_data(as_text=True)
        assert cat in html, f"Category {cat} missing from dropdown"

    def test_form_has_expected_inputs(self, auth_client):
        html = auth_client.get(URL).get_data(as_text=True)
        assert 'type="number"' in html
        assert 'step="0.01"' in html
        assert 'min="0.01"' in html
        assert 'type="date"' in html
        assert 'maxlength="200"' in html
        assert "<select" in html
        assert 'name="amount"' in html
        assert 'name="category"' in html
        assert 'name="date"' in html
        assert 'name="description"' in html

    def test_form_labels_amount_in_rupees(self, auth_client):
        html = auth_client.get(URL).get_data(as_text=True)
        assert "Amount (₹)" in html
        assert "$" not in html.split("<body", 1)[-1] or "Amount ($)" not in html

    def test_form_has_cancel_link_to_profile(self, auth_client):
        html = auth_client.get(URL).get_data(as_text=True)
        assert "Cancel" in html
        assert 'href="/profile"' in html

    def test_profile_has_add_expense_link(self, auth_client):
        html = auth_client.get(PROFILE).get_data(as_text=True)
        assert 'href="/expenses/add"' in html, "Profile should link to the add form"


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestCreateSuccess:
    def test_valid_post_redirects_to_profile(self, auth_client):
        r = auth_client.post(URL, data=_valid())
        assert r.status_code == 302
        assert r.headers["Location"].endswith(PROFILE) or PROFILE + "?" in r.headers["Location"]

    def test_valid_post_flashes_success(self, auth_client):
        r = auth_client.post(URL, data=_valid(), follow_redirects=True)
        assert r.status_code == 200
        with auth_client.session_transaction() as sess:
            # flash consumed by rendered profile page
            assert not sess.get("_flashes")
        html = r.get_data(as_text=True)
        assert "flash" in html.lower() or "added" in html.lower() or "success" in html.lower()

    def test_valid_post_inserts_row_with_values(self, auth_client, user_id):
        auth_client.post(URL, data=_valid())
        rows = _expenses_for(user_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == 250.50
        assert row["category"] == "Food"
        assert row["date"] == _today()
        assert row["description"] == "Lunch"

    def test_new_expense_shown_on_profile(self, auth_client):
        r = auth_client.post(
            URL, data=_valid(amount="123.45", description="UniqueTokenXYZ"), follow_redirects=True
        )
        html = r.get_data(as_text=True)
        assert "UniqueTokenXYZ" in html
        assert "₹" in html
        assert "123.45" in html

    def test_new_expense_is_first_in_transaction_list(self, auth_client):
        auth_client.post(URL, data=_valid(date="2020-01-01", description="OldItemAAA"))
        future = (date.today() + timedelta(days=1)).isoformat()
        auth_client.post(URL, data=_valid(date=future, description="NewestItemBBB"))
        html = auth_client.get(PROFILE).get_data(as_text=True)
        assert html.index("NewestItemBBB") < html.index("OldItemAAA")

    def test_profile_stats_update_with_new_expense(self, auth_client, user_id):
        auth_client.post(URL, data=_valid(amount="100", category="Food", description="a"))
        auth_client.post(URL, data=_valid(amount="300", category="Bills", description="b"))
        html = auth_client.get(PROFILE).get_data(as_text=True)
        assert "400" in html, "Total spent should include both expenses"
        assert "25" in html and "75" in html, "Category percentages 25/75 expected"

    def test_date_filter_includes_new_expense(self, auth_client):
        auth_client.post(URL, data=_valid(date="2031-03-10", description="InRangeItem"))
        auth_client.post(URL, data=_valid(date="2031-05-10", description="OutRangeItem"))
        html = auth_client.get(
            PROFILE, query_string={"from": "2031-03-01", "to": "2031-03-31"}
        ).get_data(as_text=True)
        assert "InRangeItem" in html
        assert "OutRangeItem" not in html

    def test_future_date_allowed(self, auth_client, user_id):
        future = (date.today() + timedelta(days=400)).isoformat()
        r = auth_client.post(URL, data=_valid(date=future))
        assert r.status_code == 302
        assert _expenses_for(user_id)[0]["date"] == future

    @pytest.mark.parametrize("cat", CATEGORIES)
    def test_every_category_accepted(self, auth_client, user_id, cat):
        r = auth_client.post(URL, data=_valid(category=cat))
        assert r.status_code == 302
        assert _expenses_for(user_id)[0]["category"] == cat


# ------------------------------------------------------------------ #
# Amount                                                              #
# ------------------------------------------------------------------ #

class TestAmount:
    @pytest.mark.parametrize(
        "raw,expected",
        [("10.456", 10.46), ("10.454", 10.45), ("99", 99.0), ("0.01", 0.01), ("1e2", 100.0)],
    )
    def test_amount_rounded_to_two_places(self, auth_client, user_id, raw, expected):
        r = auth_client.post(URL, data=_valid(amount=raw))
        assert r.status_code == 302, f"{raw} should be accepted"
        assert _expenses_for(user_id)[0]["amount"] == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize(
        "raw", ["", "   ", "abc", "12abc", "0", "0.0", "-5", "-0.01", "nan", "inf", "-inf"]
    )
    def test_invalid_amount_rejected(self, auth_client, user_id, raw):
        r = auth_client.post(URL, data=_valid(amount=raw, description="KeepMeDesc"))
        assert r.status_code == 200, f"Amount {raw!r} should re-render form, not redirect/500"
        assert _expenses_for(user_id) == [], "Nothing should be saved"
        html = r.get_data(as_text=True)
        assert "KeepMeDesc" in html, "Other submitted values should be preserved"

    def test_missing_amount_field_rejected(self, auth_client, user_id):
        data = _valid()
        del data["amount"]
        r = auth_client.post(URL, data=data)
        assert r.status_code == 200
        assert _expenses_for(user_id) == []

    def test_invalid_amount_shows_error_message(self, auth_client):
        r = auth_client.post(URL, data=_valid(amount="abc"))
        html = r.get_data(as_text=True).lower()
        assert "amount" in html, "An error mentioning the amount is expected"

    def test_rounding_to_zero_is_not_silently_saved_as_zero(self, auth_client, user_id):
        r = auth_client.post(URL, data=_valid(amount="0.001"))
        rows = _expenses_for(user_id)
        # Either rejected, or saved as a positive amount; never saved as 0.
        assert all(row["amount"] > 0 for row in rows)
        assert r.status_code in (200, 302)


# ------------------------------------------------------------------ #
# Category                                                            #
# ------------------------------------------------------------------ #

class TestCategory:
    @pytest.mark.parametrize(
        "raw", ["", "Groceries", "food", "FOOD", "'; DROP TABLE expenses;--", "<script>"]
    )
    def test_invalid_category_rejected(self, auth_client, user_id, raw):
        r = auth_client.post(URL, data=_valid(category=raw))
        assert r.status_code == 200, f"Category {raw!r} must give 200 with error, not 500"
        assert _expenses_for(user_id) == []

    def test_missing_category_field_rejected(self, auth_client, user_id):
        data = _valid()
        del data["category"]
        r = auth_client.post(URL, data=data)
        assert r.status_code == 200
        assert _expenses_for(user_id) == []

    def test_invalid_category_preserves_other_values(self, auth_client):
        r = auth_client.post(URL, data=_valid(category="Nope", amount="77.25", description="PreservedDesc"))
        html = r.get_data(as_text=True)
        assert "77.25" in html
        assert "PreservedDesc" in html


# ------------------------------------------------------------------ #
# Date                                                                #
# ------------------------------------------------------------------ #

class TestDate:
    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "not-a-date", "2026-13-01", "2026-02-30", "01/02/2026", "2026/01/02", "20260102", "2026-1-2x"],
    )
    def test_invalid_date_rejected(self, auth_client, user_id, raw):
        r = auth_client.post(URL, data=_valid(date=raw))
        assert r.status_code == 200, f"Date {raw!r} must give 200 with error, not 500"
        assert _expenses_for(user_id) == []

    def test_missing_date_field_rejected(self, auth_client, user_id):
        data = _valid()
        del data["date"]
        r = auth_client.post(URL, data=data)
        assert r.status_code == 200
        assert _expenses_for(user_id) == []

    def test_invalid_date_preserves_other_values(self, auth_client):
        r = auth_client.post(URL, data=_valid(date="garbage", amount="55.5", description="KeepThis"))
        html = r.get_data(as_text=True)
        assert "55.5" in html
        assert "KeepThis" in html


# ------------------------------------------------------------------ #
# Description                                                         #
# ------------------------------------------------------------------ #

class TestDescription:
    def test_description_over_200_rejected(self, auth_client, user_id):
        r = auth_client.post(URL, data=_valid(description="x" * 201))
        assert r.status_code == 200
        assert _expenses_for(user_id) == []

    def test_description_exactly_200_accepted(self, auth_client, user_id):
        r = auth_client.post(URL, data=_valid(description="x" * 200))
        assert r.status_code == 302
        assert _expenses_for(user_id)[0]["description"] == "x" * 200

    def test_description_stripped(self, auth_client, user_id):
        auth_client.post(URL, data=_valid(description="   padded lunch  \t"))
        assert _expenses_for(user_id)[0]["description"] == "padded lunch"

    def test_description_over_200_only_after_strip_is_accepted(self, auth_client, user_id):
        r = auth_client.post(URL, data=_valid(description="  " + "y" * 200 + "  "))
        assert r.status_code == 302, "Stripping happens before the length check"
        assert _expenses_for(user_id)[0]["description"] == "y" * 200

    @pytest.mark.parametrize("raw", ["", "    "])
    def test_empty_description_accepted(self, auth_client, user_id, raw):
        r = auth_client.post(URL, data=_valid(description=raw))
        assert r.status_code == 302, "Description is optional"
        desc = _expenses_for(user_id)[0]["description"]
        assert desc in (None, ""), f"Blank description should be NULL/empty, got {desc!r}"

    def test_missing_description_field_accepted(self, auth_client, user_id):
        data = _valid()
        del data["description"]
        r = auth_client.post(URL, data=data)
        assert r.status_code == 302
        assert len(_expenses_for(user_id)) == 1

    def test_sql_injection_in_description_stored_literally(self, auth_client, user_id):
        payload = "x'); DROP TABLE expenses;--"
        r = auth_client.post(URL, data=_valid(description=payload))
        assert r.status_code == 302
        rows = _expenses_for(user_id)
        assert rows and rows[0]["description"] == payload

    def test_html_in_description_is_escaped_on_profile(self, auth_client):
        r = auth_client.post(
            URL, data=_valid(description="<script>alert(1)</script>"), follow_redirects=True
        )
        assert b"<script>alert(1)</script>" not in r.data


# ------------------------------------------------------------------ #
# Ownership / user_id                                                 #
# ------------------------------------------------------------------ #

class TestOwnership:
    def test_expense_saved_against_session_user(self, auth_client, user_id, other_user_id):
        auth_client.post(URL, data=_valid())
        assert len(_expenses_for(user_id)) == 1
        assert _expenses_for(other_user_id) == []

    def test_user_id_in_form_is_ignored(self, auth_client, user_id, other_user_id):
        auth_client.post(URL, data=_valid(user_id=str(other_user_id)))
        assert len(_expenses_for(user_id)) == 1, "Row must belong to the session user"
        assert _expenses_for(other_user_id) == [], "Form user_id must never be honoured"

    def test_user_id_nonexistent_in_form_does_not_cause_error(self, auth_client, user_id):
        r = auth_client.post(URL, data=_valid(user_id="99999"))
        assert r.status_code == 302
        assert len(_expenses_for(user_id)) == 1

    def test_other_users_profile_does_not_show_expense(self, client, user_id, other_user_id):
        _login_as(client, user_id)
        client.post(URL, data=_valid(description="PrivateSecretItem"))
        client.get("/logout")
        _login_as(client, other_user_id)
        html = client.get(PROFILE).get_data(as_text=True)
        assert "PrivateSecretItem" not in html

    def test_failed_validation_does_not_create_row_for_anyone(self, auth_client):
        auth_client.post(URL, data=_valid(amount="-1"))
        assert _all_expenses() == []


# ------------------------------------------------------------------ #
# Misc robustness                                                     #
# ------------------------------------------------------------------ #

class TestRobustness:
    def test_empty_post_returns_200_no_500(self, auth_client):
        r = auth_client.post(URL, data={})
        assert r.status_code == 200
        assert _all_expenses() == []

    def test_error_rerender_still_lists_all_categories(self, auth_client):
        html = auth_client.post(URL, data=_valid(amount="")).get_data(as_text=True)
        for cat in CATEGORIES:
            assert cat in html

    def test_error_rerender_preserves_selected_category(self, auth_client):
        html = auth_client.post(URL, data=_valid(amount="", category="Health")).get_data(as_text=True)
        assert "selected" in html

    def test_very_long_garbage_input_no_500(self, auth_client):
        r = auth_client.post(
            URL, data=_valid(amount="9" * 5000, category="C" * 5000, date="D" * 5000)
        )
        assert r.status_code in (200, 302)
        assert r.status_code != 500

    def test_multiple_submissions_create_multiple_rows(self, auth_client, user_id):
        auth_client.post(URL, data=_valid())
        auth_client.post(URL, data=_valid())
        assert len(_expenses_for(user_id)) == 2

    def test_real_database_file_untouched_path(self, isolated_db):
        assert db.DB_PATH != _REAL_DB_PATH, "Tests must use a temp database"
