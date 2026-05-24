# HOA Task Manager — Calendar View — Design

**Date:** 2026-05-23
**Author:** Project owner (Baran) + Claude
**Status:** Approved, ready for implementation planning

---

## 1. Background

Today, a board member trying to answer "what's coming up in May?" has two
options: scan the project list and squint at the Due column, or check the
dashboard's 14-day Upcoming card. Neither shows the *shape* of the
month — bunching, gaps, overlapping deadlines, weeks with nothing on the
calendar.

A month-view calendar is the natural answer. HOA work is sized in weeks
(not hours like sprint software), so a calendar grid is the right
abstraction — one cell per day, projects appearing as small chips in
the cell they're due.

The data is already there: every `Project` has a
`projected_completion_date`. Templates excepted (they're schedules, not
work items), every other instance has a date that can be plotted on a
grid. This is purely a new view — no schema changes.

## 2. Scope

**In scope:**
- A new page at `/projects/calendar/` showing the current month by default.
- Prev / Next month navigation + a "Today" jump-back button.
- Month grid as a 6×7 table (Sunday–Saturday columns), with adjacent-month
  days rendered dimmed.
- Projects shown as small chips in their due-date cell, color-coded by
  status. Cell shows up to 3 chips; overflow shown as a "+N more" link
  that scrolls into the cell or jumps to the project list filtered to
  that day.
- Person filter matching the dashboard: defaults to the linked
  `roster_person`, `?person=all` overrides, `?person=<id>` switches.
- A new sidebar link "Calendar" between "Projects" and "Recurring".
- Tests covering the date math, the person filter, the color coding,
  and the chip placement.

**Out of scope:**
- **Week view, day view, or year view.** Month only.
- **Drag-and-drop rescheduling.** Calendar is read-only; rescheduling
  happens on the project detail page.
- **Click-day-to-add-project.** YAGNI; the existing "+ New project" flow
  is one click away in the sidebar.
- **Tooltip / hover preview of project details.** The chip is the link.
- **Multi-day project spans.** The model has only
  `projected_completion_date`, not a start date — no spans to draw.
- **Recurring templates on the calendar.** Templates aren't dated work;
  their generated instances appear normally.
- **Showing `actual_completion_date` for completed projects.** Completed
  projects render on their `projected_completion_date` (their original
  target), color-coded green. Showing the actual completion date would
  require a separate cell rendering path and isn't worth the complexity.
- **iCal/Google Calendar export.** Reasonable v2 feature, not now.
- **Calendar embedding on the dashboard.** It's a separate page.

## 3. Architecture

### URL

```
/projects/calendar/                  # current calendar month
/projects/calendar/2026/06/          # June 2026
?person=<id>                         # filter to a roster person
?person=all                          # explicit "everyone"
```

The path-form URL with `<year>/<month>` makes prev/next navigation
bookmarkable and back-button-friendly. The default `/projects/calendar/`
resolves to today's month at view time.

### View

A new function-based view in `apps/projects/views/calendar.py`:

```python
def calendar_view(request, year: int | None = None, month: int | None = None):
    ...
```

Takes optional `year` and `month` URL kwargs. When either is None,
defaults to `today.year` / `today.month`.

Resolves the person filter using a tiny variant of the dashboard's
existing `_resolve_person_filter` (which lives in
`apps/projects/views/dashboard.py`).

Computes:
- The first and last visible dates (sometimes the prior month's tail and
  the next month's head fill the grid).
- A QuerySet of `Project.instances` with `projected_completion_date`
  in `[first_visible, last_visible]`, optionally filtered by RACI
  person.
- A list-of-lists grid of cells, each with a date and a (possibly empty)
  list of projects sorted by priority then title.

Renders `projects/calendar.html` with the grid, the navigation context
(prev/next month URLs, "Today" URL), the person dropdown context, and
the unlinked-user banner flag.

### Date helper

`apps/projects/views/calendar.py` exposes one pure helper used by both
the view and the tests:

```python
def build_month_grid(year: int, month: int) -> tuple[date, date, list[list[date]]]:
    """Returns (first_visible_date, last_visible_date, weeks).

    weeks is a list of 6 weeks, each a list of 7 dates (Sun-Sat).
    Adjacent-month days are real dates, just outside [first_of_month, last].
    """
```

Uses Python's `calendar.Calendar(firstweekday=calendar.SUNDAY)` and its
`monthdatescalendar()` method, which returns exactly this shape. No
manual date arithmetic needed.

### Template

`templates/projects/calendar.html` extends `base.html`. Layout:

```
<h1>Calendar — May 2026</h1>          [← Prev]  [Today]  [Next →]
[Person dropdown — same as dashboard]
[Unlinked-user banner, if applicable]

<table>
  <thead> Sun Mon Tue Wed Thu Fri Sat </thead>
  <tbody>
    <tr> 6 weeks worth of <td> cells, each containing:
      - day number
      - up to 3 project chips (color-coded by status)
      - "+N more" link if there are more than 3 in this cell
    </tr>
  </tbody>
</table>
```

The chip is a `<a>` to `projects:detail` styled as a small colored pill.
Colors come from the existing status palette (`bg-gray-100/text-gray-700`
for not_started, `bg-blue-100/text-blue-800` for in_progress,
`bg-red-100/text-red-800` for delayed, `bg-green-100/text-green-800`
for completed). All four are already in the bundle (used by the project
list row).

The grid is a real HTML table for accessibility — screen readers
announce row and column headers correctly, which a CSS-grid div soup
wouldn't.

### Person filter

Identical to `_resolve_person_filter` from `dashboard.py`:

- `?person` absent → auto-default to `request.user.profile.roster_person`
  if linked; otherwise no filter (show everyone).
- `?person=all` → explicit "show everyone".
- `?person=<id>` → filter to that specific roster person.

The dropdown lives above the grid, identical to the dashboard's. To
avoid duplicating the helper, extract `_resolve_person_filter` from
`dashboard.py` into a small shared module
`apps/projects/views/_filters.py` and have both dashboard and calendar
import it.

### Sidebar link

`templates/_sidebar.html` gains a "Calendar" link between "Projects"
and "Recurring":

```html
<a href="{% url 'projects:list' %}" class="...">Projects</a>
<a href="{% url 'projects:calendar' %}" class="...">Calendar</a>
<a href="{% url 'projects:recurring_list' %}" class="...">Recurring</a>
```

## 4. Data model

**No schema changes.** Uses existing `Project.projected_completion_date`,
`Project.status`, `Project.priority`, and `Project.raci_assignments`.

## 5. Components & files

**New files:**
- `apps/projects/views/calendar.py` — `calendar_view` plus
  `build_month_grid` helper.
- `apps/projects/views/_filters.py` — extracted shared
  `resolve_person_filter` helper.
- `templates/projects/calendar.html` — the month-grid page.
- `apps/projects/tests/test_views_calendar.py` — coverage for the date
  math, the queryset, the person filter, and the rendered output.

**Modified files:**
- `apps/projects/views/__init__.py` — re-export the new view.
- `apps/projects/urls.py` — add two routes (`calendar/` and
  `calendar/<int:year>/<int:month>/`).
- `apps/projects/views/dashboard.py` — replace inline
  `_resolve_person_filter` with an import from `_filters.py`.
- `templates/_sidebar.html` — add the Calendar link.
- `static/css/output.css` — rebuilt if any new utility classes appear
  (likely none — the chip palette is already in use).

## 6. Error handling

- **Invalid year/month in URL** (e.g. `/calendar/2026/13/`): URL converter
  uses `<int:>`, accepts any integer. The view validates `1 <= month <= 12`
  and `year` in a sane range (1900–2100); on out-of-range, returns a 404
  via `Http404`. This is the same pattern as Django's admin date views.
- **No projects in the visible window**: cells render empty, no error.
  The grid still shows.
- **Person filter to a roster person with zero projects**: same — empty
  cells, no error.
- **`projected_completion_date` is NULL for a project** (it's a nullable
  field): skipped entirely from the calendar. Mentioned in `out of scope`.
- **More than 3 projects on one day**: cell shows first 3 + a "+N more"
  link that jumps to the project list filtered to that day
  (`projects:list?due=<date>`). The list-page `?due=` filter doesn't
  exist today, but the cell link is well-formed and Out-of-scope §11
  lists adding it as a future polish item.

## 7. Testing

- **`build_month_grid`** (pure helper, fastest tests):
  - May 2026 returns 6 weeks × 7 days.
  - The first week starts on a Sunday.
  - Dates outside May 2026 appear at the edges (April 26 in week 1, June
    in the last week).

- **`calendar_view` URL routing**:
  - `/projects/calendar/` (no year/month) defaults to today's month.
  - `/projects/calendar/2026/06/` renders June 2026.
  - `/projects/calendar/2026/13/` returns 404.
  - `@login_required` redirects anonymous → login.

- **Project placement**:
  - A project due May 15 appears in the May 15 cell.
  - A project due in April (when viewing May) does NOT appear.
  - A project with `projected_completion_date=None` does NOT appear.

- **Status color coding**:
  - The chip for a `delayed` project has the red-100 background class.
  - The chip for a `completed` project has the green-100 background class.

- **Person filter** (mirrors the dashboard tests):
  - Unlinked user sees the unlinked banner.
  - Linked user defaults to their roster_person's projects.
  - `?person=all` shows everyone.
  - `?person=<id>` switches.

- **Overflow**:
  - 5 projects on the same day renders 3 chips + "+2 more".
  - 3 projects on the same day renders 3 chips and no overflow text.

- **Sidebar link**:
  - The Calendar link is present and points at `projects:calendar`.

## 8. Out of scope (recap)

- Week / day / year views.
- Drag-and-drop rescheduling.
- Click-day-to-add-project.
- Tooltip previews.
- Multi-day spans.
- Recurring templates on the grid.
- `actual_completion_date` rendering for completed projects.
- iCal / Google Calendar export.
- Dashboard-embedded calendar.
- Project-list `?due=<date>` filter (the cell's overflow link is
  forward-compatible with this; the filter itself is a separate small
  task to add later).

## 9. Performance

For a typical HOA install (≤ 50 active projects), this is trivial — one
SELECT for projects in the window, plus the existing
`select_related("category")` prefetch is enough. The view should run in
single-digit milliseconds.

If the install ever grows to thousands of projects (won't, but for
honesty): the visible-window filter is already date-bounded, so the
query is `SELECT * FROM projects WHERE date >= X AND date <= Y AND ...`
— well-indexed by Django's default. No performance work needed.

## 10. Cost & risk

- **Schema risk**: zero (no schema change).
- **UX risk**: low. The calendar is read-only; the chip color codes
  match the project list's existing palette so nothing new visually.
- **Code risk**: the date helper is pure and fully testable. The view
  uses well-trodden Django patterns. The biggest "land mine" is the
  shared person filter — moving it from `dashboard.py` to `_filters.py`
  needs to keep dashboard tests passing.

## 11. Open decisions for owner sign-off

None. All defaults are listed above; if the owner wants to override
any (e.g. Monday-start instead of Sunday-start), the
`calendar.Calendar(firstweekday=…)` argument is the one change.
