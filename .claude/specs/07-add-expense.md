# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` placeholder with a real form that lets a
logged-in user record a new expense (amount, category, date, optional
description). Until now the only expenses in the app are the seeded demo rows,
so the profile page can never reflect a user's own spending. This step is the
first write path for expenses: it validates the submitted values server-side,
inserts a row scoped to the current user, and redirects back to the profile
page where the new expense shows up in the stats, transaction list, and
category breakdown.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()` with foreign keys on)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4/5: Profile page and backend helpers (where the new expense appears)
- Step 6: Date filter (new expenses must respect the existing date format,
  ISO `YYYY-MM-DD` text)

## Routes
- `GET /expenses/add` — render the add-expense form, date pre-filled with
  today — logged-in only (redirect to `/login` otherwise)
- `POST /expenses/add` — validate and insert the expense, then redirect to
  `/profile` with a success flash — logged-in only

Validation (on POST):
- `amount` — required, must parse as a number and be greater than 0; the value is
  rounded to 2 decimal places before saving
- `category` — required, must be one of the fixed list: Food, Transport,
  Bills, Health, Entertainment, Shopping, Other
- `date` — required, must parse with `datetime.strptime(value, "%Y-%m-%d")`;
  future dates are allowed
- `description` — optional, stripped, max 200 characters
- On any error: flash the message, re-render the form with a 200 status and
  the submitted values preserved. No 500s on garbage input.

## Database changes
No database changes. The existing `expenses` table
(`id, user_id, amount, category, date, description, created_at`) already holds
everything needed. `user_id` always comes from the session, never from the form.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with
  amount (`type="number"`, `step="0.01"`, `min="0.01"`), category `<select>`,
  date (`type="date"`), description (`type="text"`, `maxlength="200"`), a
  submit button, and a Cancel link to `url_for('profile')`. Flash messages
  rendered the same way as `login.html`.
- **Modify:** `templates/profile.html` — add an "Add expense" button/link
  using `url_for('add_expense')` near the transactions panel header.
- **Modify:** `templates/base.html` — add an "Add expense" link in the
  logged-in nav using `url_for('add_expense')` (only if it fits the existing
  nav without crowding; otherwise rely on the profile page link).

## Files to change
- `app.py` — replace the `add_expense` stub with a `GET`/`POST` route; define
  the category list constant and pass it to the template; import the new DB
  helper
- `database/db.py` — add `create_expense(user_id, amount, category, date,
  description)` next to `create_user`
- `templates/profile.html` — "Add expense" link
- `templates/base.html` — optional nav link
- `static/css/profile.css` — style for the "Add expense" button on the profile
  page, if needed

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles (per-page CSS pattern),
  linked via `{% block head %}`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic in route functions — the `INSERT` lives in `database/db.py`
  (`create_expense`); the route only validates and calls it
- `user_id` is taken from `session["user_id"]`, never from the request body
- Replace the raw string return in the stub — always render a template
- Currency must always display as ₹ — never $ or £ (label the amount field
  "Amount (₹)")
- Use `url_for()` for every link and form action; no hardcoded URLs
- Keep the category list in one place in `app.py` and reuse it for both the
  `<select>` options and server-side validation
- Vanilla HTML/CSS only; no JavaScript is required for this feature
- Do not touch the edit/delete placeholder routes or the analytics page
- No new routes beyond `/expenses/add`, and no new packages

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows the form with today's date pre-filled and all 7 categories in the dropdown
- [ ] The profile page has an "Add expense" link that opens the form
- [ ] Submitting a valid expense (e.g. 250.50, Food, today, "Lunch") redirects to `/profile` with a success flash
- [ ] The new expense appears at the top of the profile transaction list with the correct ₹ amount, category, and date
- [ ] Total spent, transaction count, and category breakdown on `/profile` update to include the new expense, and percentages still sum to 100%
- [ ] Submitting with an empty or non-numeric amount shows an error and keeps the other entered values
- [ ] Submitting an amount of 0 or a negative number is rejected with an error
- [ ] Submitting an invalid category (e.g. by editing the HTML) is rejected with an error, not a 500
- [ ] Submitting an invalid or empty date is rejected with an error, not a 500
- [ ] A description over 200 characters is rejected with an error
- [ ] The expense is saved against the logged-in user only; another user's profile does not show it
- [ ] The date filter from step 6 includes the new expense when its date falls in the chosen range
- [ ] The form is usable at mobile width and uses only CSS variables for colors
