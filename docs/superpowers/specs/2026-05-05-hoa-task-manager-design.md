# HOA Task Manager — Design

**Date:** 2026-05-05
**Author:** Project owner (Baran) + Claude
**Status:** Approved, ready for implementation planning

---

## 1. Purpose

A web-based task and project tracker for HOA board work. Single user (the project owner) at launch, with multi-user readiness baked into the architecture so board members can be invited later without rewrites.

The app is purpose-built for the rhythm of HOA board work:

- **Multi-month capital projects** (sprinkler upgrades, concrete repair, security installs)
- **Recurring operational obligations** (monthly financial reviews, annual audits)
- **Board accountability** (RACI assignments, motion/vote tracking, completed-work logs that feed monthly board reports)

Generic task managers (Asana, Trello) don't model RACI, board approvals, budget vs actual, or generate copy-paste-friendly board reports. This app does.

## 2. Goals & Non-Goals

### Goals

- Track projects with RACI assignments, status (with delay reasons), projected dates, budget vs actual, board approvals, attachments, and update notes.
- Auto-generate monthly board reports the user can copy-paste into a Word doc.
- Support recurring projects with automatic instance generation.
- Run on a free cloud tier (zero monthly cost) with credible production-quality security.
- Architected for multi-user expansion without rework.

### Non-Goals (v1)

- Email notifications / reminders. (Planned fast-follow.)
- Native mobile apps (iOS/Android). The web app will be responsive via Tailwind defaults — usable on a phone, but not a dedicated mobile UX.
- Granular role-based permissions. (Single privilege level for v1.)
- Real-time collaboration / presence indicators.
- Integrations with QuickBooks, Slack, calendar systems.
- Public-facing portal for residents.

## 3. Architecture

### Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Django 5.x (Python) | Batteries-included: auth, admin, ORM, forms, security headers all built in. Saves 5+ admin pages of work. |
| Frontend | Django templates + HTMX + Tailwind CSS | Modern UX without SPA complexity. Inline edits and partial refreshes via HTMX. |
| Database | SQLite | Single file, trivial backups (`cp db.sqlite3 backup.sqlite3`). Handles the expected scale (10s of users, 1000s of projects) without breaking a sweat. |
| File storage | Cloudflare R2 (S3-compatible) | 10 GB free tier, no egress fees. Object storage for project attachments. |
| Auth | Django built-in (email + password) | Standard, well-understood, secure-by-default. |
| Hosting | Fly.io | Free tier with persistent volumes (needed for SQLite + litestream). |
| CI/CD | GitHub Actions → Fly.io | Auto-deploy from `main` on green CI. Separate staging environment. |
| Backups | litestream → Cloudflare R2 | Continuous SQLite replication, point-in-time recovery. |

### Project structure

```
hoa_task_manager/
├── config/                  # Django settings, root URLs, ASGI/WSGI
├── apps/
│   ├── accounts/            # User auth (login/logout/profile/password change)
│   ├── roster/              # RosterPerson model and management
│   ├── projects/            # Core: Project, RACI, BoardApproval, UpdateNote,
│   │                        # Attachment, ActivityLog, Tag, Category
│   └── reports/             # Monthly close view + report generation
├── templates/               # Shared base templates (layout, nav, partials)
├── static/                  # Compiled Tailwind, JS, images
├── tests/                   # Cross-app integration tests
├── manage.py
├── fly.toml                 # Fly.io deployment config
├── Dockerfile               # Container build
├── litestream.yml           # SQLite replication config
└── pyproject.toml           # Dependencies (uv or poetry)
```

Each Django app has a single, clear purpose. The `projects` app holds the core data; `reports` consumes from it; `roster` and `accounts` are independent supporting concerns.

### Background jobs

Daily Fly.io cron at 6am UTC runs `python manage.py generate_recurring_instances`. The command is idempotent — running it twice the same day produces no duplicates.

### Time zones

All timestamps stored in UTC. Date-only fields (e.g., `projected_completion_date`) interpreted as the user's configured timezone. Default `America/New_York`; configurable in account settings (single setting, used for display and date-input parsing).

## 4. Data Model

### User (Django built-in `auth_user`)

- `email` (unique, used as username)
- `password` (PBKDF2-hashed)
- `is_staff` (Django admin access)
- `is_active`

### RosterPerson

| Field | Type | Notes |
|---|---|---|
| `name` | string, required | Display name |
| `email` | string, optional | Used later for notifications |
| `phone` | string, optional | |
| `role_title` | string, optional | e.g., "Treasurer", "Contractor — ABC Concrete" |
| `notes` | text, optional | Free text |
| `archived` | boolean, default false | Soft-delete: preserves history when someone leaves |

### ProjectCategory

Fixed seeded list, editable in admin: **Capital, Operational, Recurring, Security, Maintenance, Financial.**

- `name` (unique)
- `display_order` (integer)

### Tag

- `name` (unique, slugified)
- Created on-the-fly when typed in the project form

### Project (core entity)

| Field | Type | Notes |
|---|---|---|
| `title` | string, required | |
| `description` | text | |
| `category` | FK → ProjectCategory | |
| `status` | enum | `not_started` / `in_progress` / `delayed` / `completed` |
| `delay_reason` | text | Required when status=delayed (form-level) |
| `priority` | enum, default `medium` | `high` / `medium` / `low` |
| `projected_completion_date` | date, optional | |
| `actual_completion_date` | date | Auto-set when status → completed |
| `budget_amount` | decimal(12,2), optional | |
| `actual_cost` | decimal(12,2), optional | |
| `vendor_name` | string, optional | Denormalized for simplicity |
| `vendor_bid_amount` | decimal(12,2), optional | |
| `tags` | M2M → Tag | |
| `is_recurring_template` | boolean, default false | |
| `recurrence_rule` | enum, optional | `weekly` / `monthly` / `quarterly` / `semiannual` / `annual` |
| `next_due_date` | date, optional | Used only when `is_recurring_template=true` |
| `is_active` | boolean, default true | Used to pause recurring templates (no generation while false). On non-template projects, always true. |
| `parent_template` | FK → self, optional | Set on instances generated from a template |
| `created_at` | datetime, auto | |
| `updated_at` | datetime, auto | |
| `created_by` | FK → User | |

### RACIAssignment

| Field | Type |
|---|---|
| `project` | FK → Project |
| `person` | FK → RosterPerson |
| `role` | enum: `responsible` / `accountable` / `consulted` / `informed` |

Unique constraint: `(project, person, role)`. Allows the same person in multiple roles on a project (e.g., R + A) and multiple people sharing a role (e.g., two Consulted), but blocks duplicates.

### BoardApproval

For projects that required a board vote.

| Field | Type | Notes |
|---|---|---|
| `project` | FK → Project | |
| `motion_text` | text, required | The motion as voted |
| `vote_date` | date, required | |
| `votes_for` | int | |
| `votes_against` | int | |
| `votes_abstain` | int | |
| `minutes_reference` | string, optional | e.g., "Apr 2026 minutes, p. 3" |

### UpdateNote

Chronological journal entries on a project.

| Field | Type |
|---|---|
| `project` | FK → Project |
| `body` | text, required (basic markdown supported) |
| `created_at` | datetime, auto |
| `author` | FK → User |

### Attachment

| Field | Type | Notes |
|---|---|---|
| `project` | FK → Project | |
| `file_key` | string | The R2 object key |
| `original_filename` | string | |
| `content_type` | string | |
| `size_bytes` | int | |
| `uploaded_at` | datetime, auto | |
| `uploaded_by` | FK → User | |

Limits: 10 MB per file, 50 MB per project. Allowed content types: PDF, JPG, PNG, DOCX, XLSX.

### ActivityLog

Auto-generated, write-only audit trail.

| Field | Type | Notes |
|---|---|---|
| `project` | FK → Project, nullable | Null for non-project events |
| `actor` | FK → User | |
| `verb` | string | e.g., "changed status", "added attachment", "approved motion" |
| `before_value` | JSON, optional | |
| `after_value` | JSON, optional | |
| `created_at` | datetime, auto | |

Written via Django signals on Project save/delete, RACIAssignment add/remove, status changes, attachment uploads, board approvals.

### MonthlyReportSummary

Per-month override of the auto-generated summary blurb.

| Field | Type | Notes |
|---|---|---|
| `year_month` | string, unique | e.g., "2026-04" |
| `override_text` | text | The user's edited summary |
| `updated_at` | datetime, auto | |
| `updated_by` | FK → User | |

If a row exists for the displayed month, its `override_text` shows in the report. Otherwise the auto-generated summary is shown. The "revert to auto" button deletes the row.

### Notes on the model

- **Recurring templates** are first-class Projects with `is_recurring_template=true`. Generated instances point back via `parent_template`. Reports/lists filter out templates by default.
- **Soft-archive over delete** for RosterPerson (preserves RACI history). Same approach for projects if we ever add deletion.
- **No multi-tenancy** in v1 — single org, single user. Adding tenancy later means a single FK to an Org model on each row.

## 5. Pages & Navigation

### Top-level navigation (sidebar)

1. **Dashboard** — landing page (overdue, upcoming, recent activity)
2. **Projects** — full list with filters
3. **Recurring** — list of recurring templates
4. **Roster** — people who can be assigned RACI
5. **Reports** — monthly close view
6. **Account** — profile, change password, logout

### Drilldown pages

- **Project detail** — heart of the app (see layout below)
- **New / Edit project** form
- **Roster person detail** — their info + every project they're on
- **Login / Logout / Password reset**

### Behind-the-scenes

- **Django admin** at `/admin/` — managing categories, tags, ad-hoc data fixes. `is_staff` users only.

### Dashboard layout

- **Top stats strip:** 4 cards — Overdue, Upcoming (next 14 days), In Progress, Done This Month
- **Two-column lists:** Overdue (left) + Upcoming (right)
- **Recent activity** (bottom): last ~10 entries from ActivityLog

### Project list layout

- **Toolbar:** search input, status filter, category filter, person filter, sort dropdown, "+ New Project" button
- **Table:** priority dot, title (with note/file count subtitle), category pill, status pill, condensed RACI ("R: Mike • A: Jane"), due date (color-coded by overdue/upcoming/normal), budget vs actual
- **Default filter** excludes Completed and archived. Toggle reveals them.

### Project detail layout

Two-column:

- **Left (1.4fr):** Description, key dates & budget, RACI, board approval, attachments
- **Right (1fr):** Notes & activity stream (newest first), with "+ Add note" at the top

A red **delay banner** appears at the top whenever status=Delayed, surfacing the reason prominently.

Inline editing via HTMX — clicking a field swaps it for an editor without a page reload.

### Monthly report layout

- **Controls:** month dropdown, "Copy report text" button
- **Stats strip:** Completed / In Progress / Delayed / Approvals / Spent (capital)
- **Auto-generated summary blurb** — editable, with "revert to auto" button
- **Sections (serif typography for paste-readiness):**
  - Completed This Month (grouped by category, with cost vs budget, vendor, approval ref)
  - In Progress highlights (with delay reasons)
  - Board Approvals This Month
- **Copy button** copies formatted content (with inline styles preserved) to clipboard

## 6. Recurring Tasks

### Lifecycle

1. User creates a recurring template — a Project with `is_recurring_template=true`, a chosen `recurrence_rule`, and an initial `next_due_date`.
2. Daily cron runs `generate_recurring_instances` at 6am UTC.
3. For each active template (`is_active=true`) where `next_due_date <= today`:
   - Create a new Project copying description, category, RACI, priority, tags
   - Generate the instance title from the template title + a cadence-specific suffix:
     - `weekly` → "{title} — Week of {YYYY-MM-DD}"
     - `monthly` → "{title} — {Month YYYY}" (e.g., "Financial review — April 2026")
     - `quarterly` → "{title} — Q{1-4} {YYYY}"
     - `semiannual` → "{title} — H{1-2} {YYYY}"
     - `annual` → "{title} — {YYYY}"
   - Set `parent_template = template`, `is_recurring_template = false`, `is_active = true`, `status = not_started`
   - Set `projected_completion_date = next_due_date + cadence`
   - Advance template's `next_due_date` by one cadence
4. The generated instance is a normal Project — fully editable, completable, separately trackable.

### Cadences supported

`weekly`, `monthly`, `quarterly`, `semiannual`, `annual`. No "every N units" or specific-day-of-month support in v1.

### Catching up after downtime

If the cron misses days (Fly.io outage, deployment downtime), the next run advances `next_due_date` once per missed cycle, generating one instance per cycle. Idempotent: `next_due_date > today` after generation.

### Editing templates

Templates have a dedicated `/recurring/` page — list, create, edit, pause (set `is_active=false` on the template), delete. Editing a template only affects future instances; past instances are independent. A paused template stays in the list but is skipped by the generator until reactivated.

## 7. Authentication & Security

- Django built-in auth, email as username field
- Passwords hashed with PBKDF2 (Django default)
- **Login throttling** via `django-axes`: 5 failed attempts → 15-min lockout
- HTTPS everywhere (Fly.io provides SSL)
- Sessions: 14-day "remember me", cookies marked `Secure` + `HttpOnly` + `SameSite=Strict`
- CSRF protection on all state-changing requests (Django default)
- Single role for v1 — anyone authenticated has full access. Multi-role expansion (admin / member / view-only) deferred until board members are invited.
- **No password recovery via email in v1** (notifications come later). Manual reset via `manage.py changepassword` if the sole user locks themselves out.
- **Backups:** litestream replicates SQLite continuously to Cloudflare R2 (point-in-time recoverable, free tier covers it).

## 8. Error Handling & Edge Cases

- **Form validation:** Django forms for all input. Decimal fields validate currency. Date fields validate real dates. Required fields enforced server-side, hinted client-side.
- **File upload limits:** 10 MB / file, 50 MB / project. Content-type allowlist (PDF, JPG, PNG, DOCX, XLSX). Friendly inline error messages.
- **Concurrent edits:** last-write-wins for v1 (single user, low risk). Optimistic locking (a `version` integer that increments on save) added when board members are introduced.
- **Status transitions:**
  - `not_started → in_progress` — straightforward
  - `→ delayed` — requires `delay_reason` (form validation)
  - `→ completed` — auto-sets `actual_completion_date = today`
  - All transitions logged to ActivityLog
- **Recurring template edge cases:**
  - Cron missed → next run catches up, one instance per missed cycle
  - Template deleted → existing instances remain (independent rows)
  - Template paused → no generation while paused; resuming continues from current `next_due_date`
- **Archived roster person:**
  - Cannot be assigned to new RACI roles
  - Existing assignments display with "(archived)" suffix
  - Cross-project view of their assignments still works
- **R2 outage:** uploads fail with a retry button. Existing attachments still readable (signed URLs regenerable on demand).
- **Empty states:** every list page has friendly empty-state copy with a primary action ("No projects yet — create your first one →").

## 9. Testing

- **Framework:** Django's test framework + `pytest-django`
- **Coverage targets:**
  - Models: 100% — every constraint, signal, custom method
  - Views: critical paths (CRUD on projects, status transitions, recurring generation, monthly report rendering, login/logout)
  - Forms: every validation rule
- **Integration tests** for `generate_recurring_instances` — feed it various template configs and dates, verify correct instances created (and idempotency on re-run).
- **No mocking the database** — SQLite in tests too. Catches real ORM/migration issues.
- **Manual UI smoke test** before each deploy: log in, create project, change status, add note, upload file, view monthly report, log out.
- **CI:** GitHub Actions on every PR and push to `main`. Fly.io deploys only on green main.

## 10. Deployment

### Environments

- **Local development** — SQLite file, `python manage.py runserver`, Tailwind in watch mode
- **Staging** — Fly.io app at `hoa-task-manager-staging.fly.dev`, separate SQLite + R2 bucket
- **Production** — Fly.io app at `hoa-task-manager.fly.dev` (custom domain optional later)

### Pipeline

1. Push to feature branch → CI runs (lint, type check, tests)
2. Merge to `main` → CI runs again → deploys to staging on green
3. Manual promotion: tag a release → deploys to production
4. Cron jobs configured via `fly.toml`

### Free-tier sizing

- Fly.io free tier: 3 small VMs (256 MB RAM each) + 3 GB persistent volume — sufficient for staging + production
- Cloudflare R2: 10 GB storage + 1M Class A operations/month free — way more than needed
- Total runtime cost: $0/month at expected usage

### Domain

Default to `*.fly.dev` URLs. Custom domain (~$12/yr at Cloudflare Registrar or similar) can be added later — not blocking for v1.

## 11. Future Work (out of scope for v1)

- **Email notifications** — overdue alerts, weekly digests, password reset (requires Resend/SendGrid integration)
- **Multi-user roles** — admin / member / view-only with row-level permissions
- **PDF export** of monthly reports
- **Mobile responsive polish** beyond what Tailwind gives us by default
- **Search** improvements — full-text across notes, attachments
- **Vendor management** — first-class Vendor model (currently denormalized string field)
- **Comments on update notes** — threaded discussion when board members are added
- **Budget rollups** — annual capital spend dashboards
- **Import** from existing project lists (CSV)
