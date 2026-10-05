# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Spendly — a personal expense tracker built as a learning project with vanilla Flask, Jinja templates, and plain CSS/JS (no frontend framework, no build step). The backend is being built incrementally in steps; several routes in `app.py` are still placeholders ("coming in Step N") and `database/db.py` is a stub with only a docstring-style comment describing what it should contain (`get_db()`, `init_db()`, `seed_db()`) — it has not been implemented yet.

## Commands

```bash
source venv/bin/activate          # virtualenv already exists at venv/
pip install -r requirements.txt   # flask, werkzeug, pytest, pytest-flask
python app.py                     # runs the dev server on http://127.0.0.1:5001 (debug=True)
pytest                            # no test files exist yet, but pytest/pytest-flask are installed for when they're added
```

There is no lint/format/build tooling configured — no linter config, no `package.json`, no bundler.

## Architecture

- **`app.py`** — single-file Flask app containing all routes. New routes get added directly here as `@app.route` functions; there's no blueprint structure yet.
- **`database/db.py`** — intended to hold all SQLite access (`get_db()` with `row_factory` and foreign keys enabled, `init_db()` using `CREATE TABLE IF NOT EXISTS`, `seed_db()` for dev sample data). Currently unimplemented. The resulting `.db` file is gitignored (`expense_tracker.db`).
- **`templates/`** — Jinja2 templates. `base.html` defines the shared shell (nav, footer, font links, `main.js` include) with `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}`. Every page template extends `base.html`. Footer links (`terms`, `privacy`) use `url_for(...)`, so new routes should follow the same pattern rather than hardcoded hrefs.
- **`static/css/style.css`** — global design system: CSS custom properties under `:root` (colors as `--ink`, `--paper`, `--accent`, etc.; fonts `--font-display` (DM Serif Display) / `--font-body` (DM Sans); spacing/radius tokens). Shared layout (nav, footer, auth forms/cards) lives here.
- **`static/css/landing.css`** — page-specific styles for the landing page only (hero section, etc.). Follow this per-page CSS file pattern for new pages rather than growing `style.css` indefinitely.
- **`static/js/main.js`** — single shared JS file, vanilla JS only (no frameworks/libraries used anywhere in the project — keep it that way, e.g. the "see how it works" modal was built in plain JS).

## Working conventions

- Match the existing visual theme (DM Serif Display / DM Sans fonts, the `--ink`/`--paper`/`--accent` green palette) when adding or editing templates and CSS.
- When asked to change one section of a page (e.g. "only the hero section"), do not touch unrelated sections, routes, or files — past instructions in this repo have been scoped tightly (e.g. "Do not modify anything else on the page").
- Routes that render a new page should also wire up any corresponding `url_for()` link elsewhere (e.g. footer/nav) rather than leaving placeholder `#` hrefs.


## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **`database/db.py` is currently empty** — do not assume helpers exist until the step that implements them
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- The app runs on **port 5001**, not the Flask default 5000 — don't change this
