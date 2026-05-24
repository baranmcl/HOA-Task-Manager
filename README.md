# HOA Task Manager

A small, opinionated project tracker for an HOA board. Built to replace
the usual mix of spreadsheets, email chains, and "didn't we discuss that
in April?"

- **Live staging:** <https://cica.pythonanywhere.com>
- **Walkthrough for board members:** [`docs/board-presentation.md`](docs/board-presentation.md)
- **Source:** <https://github.com/baranmcl/HOA-Task-Manager>

## What it does

- **Projects** with category, status, priority, due dates, budget vs.
  actual, and vendor info.
- **RACI assignments** drawn from a roster of board members and
  volunteers — first-class Responsible / Accountable / Consulted /
  Informed, not just "assignee".
- **Notes** with a pin for the "what is this project" anchor, plus a
  chronological log everyone can read to catch up in 30 seconds.
- **Attachments** stored in Cloudflare R2 — vendor quotes, permits,
  photos.
- **Recurring templates** that auto-generate fresh instances every
  week / month / quarter / year, preserving RACI and category.
- **Activity log** of every status change, budget update, RACI edit,
  and note touch, attributed to a real user.
- **Dashboard** with stats (overdue, upcoming 14 days, in progress,
  done this month) and a recent activity feed.
- **Board** — a Kanban view with drag-and-drop to change status.
- **Calendar** — a month grid of every due date.
- **Reports** — completed-project summary over any date window
  (six presets) with a per-category breakdown.
- **Bulk CSV import** with a preview-then-confirm flow; per-row
  rejection messages for bad data.
- **Bulk delete** from the project list, with a typed-`delete`
  confirmation.
- **Search** across project titles, descriptions, and notes.
- **Daily SQLite backups** to R2, retained 30 days.
- **Timezone-aware activity timestamps** per-user.

What it deliberately doesn't have: dependencies, gantt charts, custom
fields, time tracking, mobile apps, or anything else that isn't pulling
its weight for a five-person volunteer board. See the board
presentation for the rationale.

## Tech stack

- **Backend:** Django 5.0 on Python 3.12, SQLite.
- **Frontend:** Server-rendered Django templates + Tailwind CSS, with
  HTMX for the inline-edit flows and Sortable.js for the board drag.
  No SPA, no build pipeline beyond Tailwind.
- **Storage:** Cloudflare R2 (S3-compatible, via `boto3`) for
  attachments and daily DB backups.
- **Tests:** `pytest-django`, ~360 tests, all hitting a real test DB.
- **Lint:** `ruff` with `E F I B UP DJ` rules.
- **Hosting:** PythonAnywhere free tier (staging).

## Local development

Requires Python 3.12 and the `uv` or `pip` toolchain. PowerShell on
Windows is the primary dev environment; Linux/macOS works too.

```powershell
# Clone
git clone https://github.com/baranmcl/HOA-Task-Manager.git
cd HOA-Task-Manager

# Virtualenv + deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e . --group dev

# DB
python manage.py migrate
python manage.py createsuperuser

# Static / CSS (one-time, also after template edits)
.\bin\tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
python manage.py collectstatic --noinput

# Run
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Log in with the superuser account; you
land on the dashboard.

## Running tests

```powershell
python -m pytest -q           # full suite
python -m pytest apps/projects/tests/test_views_board.py -v   # one file
ruff check .                  # lint
```

The test DB is recreated per session; fixtures (`user`, `auth_client`,
`category`, `person`, `project`) live in
[`apps/projects/tests/conftest.py`](apps/projects/tests/conftest.py).

## Project layout

```
apps/
  accounts/   — user profile, timezone middleware, R2 backup job
  roster/     — RosterPerson model (board members, volunteers)
  projects/
    models/   — Project, Category, RACI, Note, Attachment, Activity, ...
    views/    — dashboard, list, detail, board, calendar, report, csv_import, ...
    services/ — pure-function helpers (csv parsing, report computation)
    forms/
    signals.py — ActivityLog writers
    middleware.py — ActorMiddleware, RecurringGenerationMiddleware
config/       — Django settings + URL conf
templates/    — server-rendered HTML (Tailwind classes inline)
static/       — compiled CSS, vendored JS (htmx)
docs/
  board-presentation.md   — feature walkthrough for non-technical readers
  runbooks/               — deploy, restore, host-switch
  superpowers/            — design specs + implementation plans
```

## Deployment

Staging runs on PythonAnywhere free tier. The end-to-end one-time
setup and the routine "pull / collectstatic / reload" update flow are
in [`docs/runbooks/deploy-pythonanywhere.md`](docs/runbooks/deploy-pythonanywhere.md).

Fly.io setup is retained but dormant — see
[`docs/runbooks/switch-back-to-fly.md`](docs/runbooks/switch-back-to-fly.md)
if PythonAnywhere ever stops working.

## Data model notes

- **Single shared data, no per-user isolation.** Every logged-in user
  sees every project. This is intentional for an HOA board.
- **Recurring projects** are split into a *template* (`is_recurring_template=True`)
  and *instances* — the lazy `RecurringGenerationMiddleware` creates
  the next instance on the first web request of each day.
- **Activity log** writes are gated by a thread-local `set_actor()`
  called from `ActorMiddleware`. Service-layer code (CSV import, bulk
  delete) silences this to write its own consolidated entries.
- **The default `Project.objects` manager includes templates.** Use
  `Project.instances` for "real" projects and `Project.templates` for
  the recurring definitions.

## Backups & restore

Daily SQLite backups land in the R2 `db-backups/` prefix as
`YYYY-MM-DD.sqlite3`. Restore steps:
[`docs/runbooks/restore-database.md`](docs/runbooks/restore-database.md).

## Contributing

This is a single-user project built for one specific HOA's workflow.
Forks welcome; PRs accepted on a case-by-case basis. If you're another
board manager who'd find this useful, open an issue and we can talk.

---

*Built by Baran, 2026. No license file yet — assume "all rights
reserved" until one is added. Get in touch if you want to use this for
your own HOA.*
