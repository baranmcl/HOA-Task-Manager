# Completion Report — Design

**Date:** 2026-05-23
**Status:** Draft for user review

## Goal

A board-facing in-app page that summarizes completed projects across a chosen date window: headline numbers at the top, per-category breakdown below. Built so a "Printable view" mode can be added later without restructuring the page.

## Audience

HOA board members. They look at this in-app during meetings and (later) print/share an export with the wider HOA membership.

## Time window

- Inputs: a `from` date and a `to` date.
- Both default to "this year" — Jan 1 of the current year through today.
- Preset buttons that prefill the dates (no submit-on-click; user can tweak then submit): **This month**, **This quarter**, **This year**, **Last month**, **Last quarter**, **Last year**.
- "Quarter" = standard calendar quarters (Q1=Jan–Mar, Q2=Apr–Jun, etc).
- URL query params: `?from=YYYY-MM-DD&to=YYYY-MM-DD`. Bookmarkable and shareable. Invalid dates fall back to the default window.

## Which projects count

A project is "completed in the window" when:
1. `status == COMPLETED`, AND
2. `actual_completion_date` is set AND falls within `[from, to]` (inclusive).

We filter on `actual_completion_date`, not `projected_completion_date`, because the question is "what did we actually finish in this window" — including projects that slipped from a prior quarter.

Recurring **templates** (`is_recurring_template=True`) are excluded; only instances and one-offs show up.

## Headline numbers (top of page)

Four tiles, same visual idiom as the existing dashboard stats:

1. **Completed** — count of projects in scope.
2. **Total spent** — sum of `actual_cost` (treating NULL as $0, not as missing). Shown as `$X,XXX`.
3. **Over budget** — count of projects where `actual_cost` and `budget_amount` are both set AND `actual_cost > budget_amount`. We do NOT count projects with no budget_amount.
4. **Avg days to complete** — average of `(actual_completion_date - created_at::date)` in days, across the projects in scope. Computed in Python on the small result set, not as a SQL aggregate (sqlite + date math is painful). NULL `actual_completion_date` is already excluded by the window filter, so no further NULL-handling is needed.

If the window has zero projects, the tiles show `0` / `$0` / `0` / `—`.

## Per-category breakdown (below tiles)

A table with one row per `ProjectCategory` that has at least one completed project in the window. Columns:

| Column | Source |
|---|---|
| Category | `ProjectCategory.name` |
| Count | number of completed projects in this category, in window |
| Total spent | sum of `actual_cost` for those projects (NULL = $0) |
| Avg cost | total_spent / count, rounded to the dollar |

Sorted by Count descending (biggest impact first), then by Category name as a tiebreaker. Empty categories (zero completed in window) are omitted entirely — no rows with `0` count.

If no rows, show a single "No completed projects in this window." line, no empty table.

## Print-friendliness (now, free)

We're not building a separate print mode, but the page should be print-decent today:

- Use the same `base.html` layout but the report content is a single column at print widths — done naturally by Tailwind grid columns collapsing on narrow viewports.
- No JavaScript needed for the page to function — preset buttons are anchor tags with `?from=...&to=...` query strings, not JS handlers.
- Headline tiles stay readable when printed (no hover-only contrast).

A dedicated `/projects/report/print/` view with a stripped-down `print.html` template can be added later once you decide it's worth doing.

## UI flow

- New URL: `/projects/report/`, name `projects:report`.
- New sidebar link: "Reports" (placed between "Recurring" and "Import projects").
- Page sections:
  1. **Title row** — "Reports — Completed projects" + the window summary ("Jan 1 – May 23, 2026").
  2. **Date controls** — a `<form method="get">` with two `<input type="date">` boxes and a submit button. Above the inputs, the six preset buttons render as `<a>` tags styled as buttons.
  3. **Tiles** — the four summary numbers.
  4. **Breakdown table** — or the empty message.

## Login gate

`@login_required`, matching the rest of the app. No staff-only flag.

## Testing strategy

Tests live in `apps/projects/tests/test_views_report.py`. Coverage:

- **Anonymous → 302** (login gate).
- **Default window is current year.**
- **Explicit `?from=&to=` honored.**
- **Invalid date strings fall back to default window.**
- **Completed project inside window appears.**
- **Completed project outside window excluded.**
- **Non-completed project (in-progress) excluded even if inside window.**
- **Recurring template excluded.**
- **Headline `Completed` count matches.**
- **Headline `Total spent` sums correctly (with one NULL actual_cost treated as $0).**
- **Headline `Over budget` counts only rows where `actual_cost > budget_amount` AND both are set.**
- **Headline `Avg days to complete` math.**
- **Category breakdown** — two categories, one completed each → two rows with the right counts.
- **Empty category not shown** — a category with zero completed projects in window is omitted.
- **Empty window shows "no completed projects" message.**
- **Sidebar contains a "Reports" link.**

## Out of scope (parked)

- **Vendor breakdown.** Useful but skipped for v1 — the user only picked Summary + Category.
- **Full project list table.** Same.
- **Printable / PDF export view.** Wait for board buy-in before building.
- **Charts.** Numbers and a table are enough for v1.
- **CSV export of the report.** Easy to add later if asked.
- **Year-over-year comparison.** Not requested.
