# Spec: Date Filter For Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so a user can narrow the
summary stats, transaction list, and category breakdown to a chosen period.
Until now `/profile` always aggregates every expense a user has ever logged.
With a `from` / `to` date range passed as query-string parameters, the same
three data sections reflect only the expenses inside that range, plus a few
quick presets (this month, last 30 days, all time) for common cases. The filter
is applied server-side in SQL and is a plain GET form, so it works without
JavaScript and the filtered view is bookmarkable.

## Depends on
- Step 1: Database setup (`expenses.date` stored as ISO `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4: Profile page static UI (`templates/profile.html`, `profile.css`)
- Step 5: Profile backend routes (`database/queries.py` helpers feeding `/profile`)

## Routes
No new routes. The existing `GET /profile` route is modified to accept two
optional query parameters (logged-in only):
- `from` — start date, inclusive, `YYYY-MM-DD`
- `to` — end date, inclusive, `YYYY-MM-DD`

Behaviour:
- Both missing/empty → no filter (all time), identical to today's behaviour.
- Only one supplied → open-ended range on the other side.
- Unparseable value → ignored (treated as missing); no 500.
- `from` later than `to` → flash an error ("Start date must be on or before
  end date"), and fall back to the unfiltered view.

## Database changes
No database changes. `expenses.date` is already ISO text, so range filtering
uses `date >= ? AND date <= ?` with no schema change or index required at this
stage.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats section: a `<form method="get"
    action="{{ url_for('profile') }}">` with two `<input type="date">` fields
    (`from`, `to`, pre-filled with the active values), an "Apply" button, and a
    "Clear" link back to `url_for('profile')`.
  - Add preset links (This month, Last 30 days, All time) built with
    `url_for('profile', **{'from': ..., 'to': ...})`. The route passes the
    preset date strings to the template; the template must not compute dates.
  - Rename the "Recent transactions" panel title to "Transactions" when a
    filter is active (keep "Recent transactions" otherwise).
  - Show the active range as a short label (e.g. "1 Oct 2026 – 25 Oct 2026")
    when a filter is active.
  - Empty-state text when a filter is active and nothing matches: "No
    transactions in this period."

## Files to change
- `app.py` — in `profile()`, read and validate `from` / `to`, pass them to the
  query helpers, and pass the active range and preset dates to the template
- `database/queries.py` — add optional `date_from=None, date_to=None`
  parameters to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`
- `templates/profile.html` — filter bar, presets, active-range label, empty state
- `static/css/profile.css` — styles for the filter bar and preset links

## Files to create
None. (No new templates, CSS, or JS files; the filter is a plain GET form.)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — build the optional `AND date >= ?` / `AND date <= ?`
  clauses from fixed strings and append values to the params tuple; never
  format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic in route functions — range filtering lives in `database/queries.py`;
  the route only parses and validates the query-string values
- Date validation uses `datetime.strptime(value, "%Y-%m-%d")` in the route;
  pass validated ISO strings to the helpers
- New helper parameters default to `None` so existing callers and the
  step 5 tests keep working unchanged
- When a filter is active, `get_recent_transactions` must not apply the
  default `limit=10` cap silently — the route passes `limit=None` (no limit)
  for filtered views and the helper omits the `LIMIT` clause in that case
- `pct` values in the category breakdown must still sum to 100 over the
  filtered set; empty result → empty list, zeros for stats, no exceptions
- Currency must always display as ₹ — never $ or £
- No inline styles; no hardcoded URLs — use `url_for()`
- Vanilla HTML only; no JavaScript is required for this feature
- No new routes and no new packages

## Definition of done
- [ ] Visiting `/profile` with no query params looks and behaves exactly as before (all 8 seed expenses, ₹ totals)
- [ ] A filter bar with From / To date inputs, an Apply button, and a Clear link appears above the summary stats
- [ ] Choosing a range and clicking Apply updates the URL to `/profile?from=...&to=...` and the inputs stay pre-filled
- [ ] Total spent, transaction count, top category, transaction list, and category breakdown all reflect only expenses inside the range (inclusive of both end dates)
- [ ] Category percentages in a filtered view add up to 100 %
- [ ] "This month", "Last 30 days", and "All time" preset links apply the expected range
- [ ] A range containing no expenses shows ₹0.00, 0 transactions, "—" top category, "No transactions in this period.", and an empty category breakdown, with no errors
- [ ] Setting From later than To shows an error flash and falls back to the unfiltered view
- [ ] A garbage value such as `/profile?from=abc` does not cause a 500; it is ignored
- [ ] "Clear" returns to the unfiltered `/profile`
- [ ] Unauthenticated access to `/profile?from=2026-01-01` still redirects to `/login`
- [ ] The filter bar is usable at mobile width and uses only CSS variables for colors
