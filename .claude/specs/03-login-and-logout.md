# Spec: Login and Logout

## Overview
Implement session-based authentication so registered users can sign in and out of Spendly. This step upgrades the stub `GET /login` route to also handle `POST` (verify email and password against the `users` table, store the user in Flask's `session`) and replaces the placeholder `/logout` route with one that clears the session. It also makes the shared navbar session-aware. This follows Registration (Step 02) and is the gate for every authenticated feature that comes next (profile, expenses).

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, users with hashed passwords, flash message pattern, `app.secret_key`)

## Routes
- `GET /login` — render login form; if already logged in, redirect to `/profile` — public
- `POST /login` — validate credentials, set `session["user_id"]` and `session["user_name"]`, redirect to `/profile` — public
- `GET /logout` — clear the session, flash a confirmation, redirect to `/` — logged-in (a logged-out visitor is simply redirected to `/login`)

## Database changes
No new tables or columns. The existing `users` table covers all requirements.

A new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — parameterised `SELECT` on `users` by email; returns a `sqlite3.Row` or `None`. Password verification (`check_password_hash`) happens in the route, against the returned `password_hash`.

## Templates
- **Modify:** `templates/login.html`
  - Change form `action` from the hardcoded `/login` to `url_for('login')`
  - Repopulate the email field with the submitted `email` value after a failed attempt (never repopulate the password)
  - Keep the existing flash display and visual design
- **Modify:** `templates/base.html`
  - Navbar: when `session.user_id` is set, show the user's name, a link to `url_for('profile')`, and a "Sign out" link to `url_for('logout')`; otherwise keep the existing "Sign in" / "Get started" links
- **Create:** none

## Files to change
- `app.py` — upgrade `login()` to handle `GET`/`POST`; replace placeholder `logout()`; import `session` and `check_password_hash`
- `database/db.py` — add `get_user_by_email()`
- `templates/login.html` — wire up form action and email repopulation
- `templates/base.html` — session-aware navbar
- `static/css/style.css` — only if needed for the navbar user name / sign-out styling (use existing tokens)

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` and Flask's built-in `session`, `flash`, `redirect`, `url_for`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Passwords hashed with werkzeug — verify with `check_password_hash`, never compare plaintext
- DB logic stays in `database/db.py` — route functions must not run SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect — never hardcode URLs
- Normalise the email (`strip().lower()`) before lookup, matching registration
- Server-side validation: both fields non-empty; on any failure (unknown email or wrong password) show the same generic message "Invalid email or password" so account existence isn't leaked
- On failure, re-render the form with a flashed error (category `error`) — do not redirect
- On success, call `session.clear()` before setting `user_id`/`user_name`, then redirect to `url_for('profile')`
- Logout must clear the whole session (`session.clear()`), flash a success message, and redirect — never render a raw string
- `/profile` is still a placeholder until Step 04; do not implement it here
- Do not touch the registration flow, landing page, or other placeholder routes
- Keep the app on port 5001; no JS frameworks

## Definition of done
- [ ] `GET /login` renders the sign-in form without errors
- [ ] Logging in as the seeded user (`demo@spendly.com` / `demo123`) redirects to `/profile` and the navbar shows the user's name and a "Sign out" link instead of "Sign in" / "Get started"
- [ ] A user created via `/register` can log in with the credentials they registered with
- [ ] Wrong password shows "Invalid email or password" and re-renders the form with the email prefilled
- [ ] Unknown email shows the same "Invalid email or password" message
- [ ] Submitting with an empty field shows a validation error and does not log in
- [ ] Email matching is case-insensitive and ignores surrounding whitespace
- [ ] Visiting `/login` while logged in redirects to `/profile`
- [ ] `GET /logout` clears the session, redirects to `/` with a confirmation message, and the navbar returns to "Sign in" / "Get started"
- [ ] After logout, the session cookie no longer contains `user_id`
- [ ] Visiting `/logout` while logged out redirects to `/login` without error
- [ ] The success message after registration ("Account created! Please sign in.") still displays on the login page
