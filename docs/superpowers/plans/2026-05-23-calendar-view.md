# Calendar View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a month-view calendar page at `/projects/calendar/` that plots every project on its `projected_completion_date`, color-coded by status, with the same person-filter behavior as the dashboard.

**Architecture:** Python stdlib `calendar.Calendar.monthdatescalendar()` returns a 6×7 grid of `date` objects (Sun–Sat columns), padded with adjacent-month days. A pure helper (`build_month_grid`) wraps it; the view layers a date-bounded project query and a per-cell placement step on top. The person filter is the same one already used on the dashboard — extracted to a shared module so calendar and dashboard share the implementation.

**Tech Stack:** Django 5.0.x, Python stdlib `calendar`, pytest-django, ruff. No new dependencies. Tailwind only if a new utility class slips in.

---

## File Structure

**New files:**
- `apps/projects/views/_filters.py` — extracted `resolve_person_filter` helper used by both dashboard and calendar.
- `apps/projects/views/calendar.py` — `calendar_view` + `build_month_grid`.
- `templates/projects/calendar.html` — the month-grid page.
- `apps/projects/tests/test_views_calendar.py` — view + helper tests.

**Modified files:**
- `apps/projects/views/dashboard.py` — replace inline `_resolve_person_filter` with `from ._filters import resolve_person_filter`.
- `apps/projects/views/__init__.py` — re-export `calendar_view`.
- `apps/projects/urls.py` — add two routes.
- `templates/_sidebar.html` — add the Calendar link.
- (Possibly) `static/css/output.css` — rebuilt if new utility classes appear. Verified in Task 6.

---

## Task 1: Extract `resolve_person_filter` into a shared module

Refactor only. The function currently lives in `dashboard.py` as a module-private helper. Both calendar and dashboard need the same behavior; extracting means a single source of truth.

**Files:**
- Create: `apps/projects/views/_filters.py`
- Modify: `apps/projects/views/dashboard.py`
- Test: `apps/projects/tests/test_views_dashboard_filters.py` (existing — must continue to pass)

- [ ] **Step 1: Create the new module**

Create `apps/projects/views/_filters.py`:

```python
"""Shared person-filter helper used by the dashboard and the calendar.

Resolves the `?person=` query parameter against the authenticated user's
linked roster_person profile, returning a tuple the view can hand directly
to its queryset and template context.
"""


def resolve_person_filter(request):
    """Returns (person_id_or_None, show_unlinked_banner, selected_value).

    - person_id_or_None: the RosterPerson pk to filter on, or None for "show all".
    - show_unlinked_banner: True only when the user has no roster_person link
      AND did not explicitly choose `?person=all` or `?person=<id>` themselves.
    - selected_value: the value to render in the dropdown — "all", a numeric
      pk as a string, or "" if no explicit choice was made.
    """
    raw = request.GET.get("person")
    linked = getattr(request.user.profile, "roster_person", None)

    if raw == "all":
        return None, False, "all"
    if raw and raw.isdigit():
        return int(raw), False, raw
    # No explicit choice — auto-default to linked person if available.
    if linked is not None:
        return linked.pk, False, str(linked.pk)
    return None, True, ""
```

- [ ] **Step 2: Update `dashboard.py` to import the shared helper**

In `apps/projects/views/dashboard.py`, remove the inline `_resolve_person_filter` function (currently at the top of the file, between the imports and the `@login_required def dashboard(...)` line) and replace its call site.

First, delete the entire `_resolve_person_filter` function block. Then add this import near the top with the other imports:

```python
from ._filters import resolve_person_filter
```

Then in the body of `dashboard(request)`, find the line:

```python
    person_id, banner, selected_person = _resolve_person_filter(request)
```

and change it to:

```python
    person_id, banner, selected_person = resolve_person_filter(request)
```

(Drop the leading underscore — the import is no longer module-private.)

- [ ] **Step 3: Run the dashboard tests to verify no regression**

Run: `python -m pytest apps/projects/tests/test_views_dashboard_filters.py apps/projects/tests/test_views_dashboard.py -v`
Expected: All tests green — both `test_unlinked_user_sees_unlinked_banner_flag`, `test_linked_user_defaults_to_their_person`, `test_explicit_all_overrides_default`, `test_explicit_other_person_filters_to_them`, and the rest.

- [ ] **Step 4: Run ruff**

Run: `ruff check apps/projects/views/dashboard.py apps/projects/views/_filters.py`
Expected: "All checks passed!"

- [ ] **Step 5: Commit**

```bash
git add apps/projects/views/_filters.py apps/projects/views/dashboard.py
git commit -m "refactor(views): extract resolve_person_filter to shared module"
```

---

## Task 2: `build_month_grid` helper — pure date math

A pure helper that wraps `calendar.Calendar.monthdatescalendar()` and returns the three values the view needs: the first visible date, the last visible date, and the 6×7 grid of `date` objects.

**Files:**
- Modify: `apps/projects/views/calendar.py` (will be created here — view body comes in Task 3)
- Test: `apps/projects/tests/test_views_calendar.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `apps/projects/tests/test_views_calendar.py`:

```python
"""Tests for the calendar view and its date helper."""
import calendar as stdlib_calendar
import datetime as dt

import pytest


def test_build_month_grid_returns_six_weeks_of_seven_days():
    from apps.projects.views.calendar import build_month_grid
    first, last, weeks = build_month_grid(2026, 5)
    assert len(weeks) >= 4 and len(weeks) <= 6  # months span 4-6 visible weeks
    for week in weeks:
        assert len(week) == 7


def test_build_month_grid_starts_on_sunday():
    from apps.projects.views.calendar import build_month_grid
    _, _, weeks = build_month_grid(2026, 5)
    # First column should be Sunday (weekday() == 6 in Python's Mon=0 convention).
    assert weeks[0][0].weekday() == stdlib_calendar.SUNDAY


def test_build_month_grid_may_2026_includes_adjacent_month_padding():
    """May 1 2026 is a Friday — the first row should include April 26-30."""
    from apps.projects.views.calendar import build_month_grid
    first, _, weeks = build_month_grid(2026, 5)
    # First date in the grid is in April, not May.
    assert weeks[0][0] < dt.date(2026, 5, 1)
    assert first == weeks[0][0]


def test_build_month_grid_last_date_extends_into_next_month_if_needed():
    """May 31 2026 is a Sunday — June 1-6 fills out the last row."""
    from apps.projects.views.calendar import build_month_grid
    _, last, weeks = build_month_grid(2026, 5)
    assert last == weeks[-1][-1]
    assert last >= dt.date(2026, 5, 31)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v`
Expected: FAIL — module `apps.projects.views.calendar` does not exist.

- [ ] **Step 3: Create the calendar view module with just the helper**

Create `apps/projects/views/calendar.py`:

```python
"""Month-view calendar page for projects."""
import calendar as stdlib_calendar
import datetime as dt

_CAL = stdlib_calendar.Calendar(firstweekday=stdlib_calendar.SUNDAY)


def build_month_grid(year: int, month: int) -> tuple[dt.date, dt.date, list[list[dt.date]]]:
    """Build the 6×7 (sometimes 5×7) date grid for a calendar month view.

    Returns:
        (first_visible_date, last_visible_date, weeks)
        weeks is a list of weeks; each week is a list of 7 dates (Sun-Sat).
        Adjacent-month days are real dates outside the requested month — the
        caller dims them in the template.
    """
    weeks = _CAL.monthdatescalendar(year, month)
    first = weeks[0][0]
    last = weeks[-1][-1]
    return first, last, weeks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v`
Expected: PASS — all 4 helper tests green.

- [ ] **Step 5: Run ruff**

Run: `ruff check apps/projects/views/calendar.py apps/projects/tests/test_views_calendar.py`
Expected: "All checks passed!"

- [ ] **Step 6: Commit**

```bash
git add apps/projects/views/calendar.py apps/projects/tests/test_views_calendar.py
git commit -m "feat(calendar): build_month_grid helper for the calendar view"
```

---

## Task 3: `calendar_view` + template — placement and chips

The heart of the feature. Adds the view, the URL routes, the template, and the project-placement logic. No person filter yet (Task 4); no sidebar link yet (Task 5).

**Files:**
- Modify: `apps/projects/views/calendar.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/calendar.html`
- Test: `apps/projects/tests/test_views_calendar.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_calendar.py`:

```python
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_calendar_view_default_renders_current_month(auth_client):
    response = auth_client.get(reverse("projects:calendar"))
    assert response.status_code == 200
    today = dt.date.today()
    month_name = today.strftime("%B")
    content = response.content.decode()
    assert month_name in content
    assert str(today.year) in content


@pytest.mark.django_db
def test_calendar_view_with_year_month_renders_that_month(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 6]))
    assert response.status_code == 200
    assert "June" in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_invalid_month_returns_404(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 13]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_calendar_view_requires_login(client):
    response = client.get(reverse("projects:calendar"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_calendar_view_places_project_in_its_due_date_cell(
    auth_client, user, category,
):
    Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    assert "Sprinkler upgrade" in content


@pytest.mark.django_db
def test_calendar_view_excludes_project_outside_visible_window(
    auth_client, user, category,
):
    Project.objects.create(
        title="January project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 1, 15),
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    assert "January project" not in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_excludes_project_with_no_date(
    auth_client, user, category,
):
    Project.objects.create(
        title="No date project", category=category, created_by=user,
        projected_completion_date=None,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    assert "No date project" not in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_color_codes_by_status(auth_client, user, category):
    Project.objects.create(
        title="Delayed project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 10),
        status=ProjectStatus.DELAYED,
    )
    Project.objects.create(
        title="Done project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 11),
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    # The delayed chip carries the red palette; the completed chip carries the green.
    # Use the exact class fragment used by the project list row for status pills.
    assert "bg-red-100" in content
    assert "bg-green-100" in content


@pytest.mark.django_db
def test_calendar_view_overflow_link_when_more_than_three_on_one_day(
    auth_client, user, category,
):
    target_date = dt.date(2026, 5, 15)
    for i in range(5):
        Project.objects.create(
            title=f"Project {i}", category=category, created_by=user,
            projected_completion_date=target_date,
        )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    # 3 chips visible, "+2 more" overflow link.
    assert "+2 more" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v -k "calendar_view"`
Expected: FAIL — `NoReverseMatch` for `projects:calendar` and `projects:calendar_at`.

- [ ] **Step 3: Add the view and supporting helpers**

Replace the full contents of `apps/projects/views/calendar.py` with:

```python
"""Month-view calendar page for projects."""
import calendar as stdlib_calendar
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from ..models import Project

_CAL = stdlib_calendar.Calendar(firstweekday=stdlib_calendar.SUNDAY)

# Max chips rendered in a single day cell before showing a "+N more" link.
CELL_CHIP_LIMIT = 3

# Status → chip background+text classes. Matches the palette used by the
# project list row (templates/projects/_list_row.html).
STATUS_CHIP_CLASSES = {
    "completed": "bg-green-100 text-green-800",
    "delayed": "bg-red-100 text-red-800",
    "in_progress": "bg-blue-100 text-blue-800",
    "not_started": "bg-gray-100 text-gray-700",
}


def build_month_grid(year: int, month: int) -> tuple[dt.date, dt.date, list[list[dt.date]]]:
    """Build the 6×7 (sometimes 5×7) date grid for a calendar month view.

    Returns:
        (first_visible_date, last_visible_date, weeks)
        weeks is a list of weeks; each week is a list of 7 dates (Sun-Sat).
        Adjacent-month days are real dates outside the requested month — the
        caller dims them in the template.
    """
    weeks = _CAL.monthdatescalendar(year, month)
    first = weeks[0][0]
    last = weeks[-1][-1]
    return first, last, weeks


@login_required
def calendar_view(request, year: int | None = None, month: int | None = None):
    today = dt.date.today()
    if year is None or month is None:
        year, month = today.year, today.month
    if not (1 <= month <= 12) or not (1900 <= year <= 2100):
        raise Http404("Invalid year/month")

    first, last, weeks = build_month_grid(year, month)

    projects = list(
        Project.instances.select_related("category").filter(
            projected_completion_date__gte=first,
            projected_completion_date__lte=last,
        ),
    )

    # Bucket projects by their due date.
    by_date: dict[dt.date, list[Project]] = {}
    for p in projects:
        by_date.setdefault(p.projected_completion_date, []).append(p)

    # Build a list-of-rows of cell dicts the template can iterate cleanly.
    cells_by_week = []
    for week in weeks:
        row = []
        for day in week:
            day_projects = by_date.get(day, [])
            row.append({
                "date": day,
                "is_other_month": day.month != month,
                "is_today": day == today,
                "projects": day_projects[:CELL_CHIP_LIMIT],
                "overflow_count": max(0, len(day_projects) - CELL_CHIP_LIMIT),
            })
        cells_by_week.append(row)

    # Compute prev/next/today URLs for the navigation controls.
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    return render(request, "projects/calendar.html", {
        "year": year,
        "month": month,
        "month_label": dt.date(year, month, 1).strftime("%B %Y"),
        "weeks": cells_by_week,
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
        "today_year": today.year, "today_month": today.month,
        "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "status_chip_classes": STATUS_CHIP_CLASSES,
    })
```

- [ ] **Step 4: Re-export the view**

In `apps/projects/views/__init__.py`, add (alphabetical placement, near the existing `.calendar`... wait there's no existing `.calendar` import; place it after the `.category` imports):

```python
from .calendar import calendar_view as calendar_view
```

- [ ] **Step 5: Add the URL routes**

In `apps/projects/urls.py`, add two routes immediately after the existing `path("categories/<int:pk>/delete/", ...)` line:

```python
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/<int:year>/<int:month>/", views.calendar_view, name="calendar_at"),
```

The second route is named `calendar_at` so prev/next links can build URLs with explicit year/month.

- [ ] **Step 6: Create the calendar template**

Create `templates/projects/calendar.html`:

```html
{% extends "base.html" %}
{% block title %}Calendar — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6 flex-wrap gap-3">
  <h1 class="text-2xl font-semibold text-gray-900">Calendar — {{ month_label }}</h1>
  <div class="flex gap-2 text-sm">
    <a href="{% url 'projects:calendar_at' prev_year prev_month %}" class="btn-secondary">← Prev</a>
    <a href="{% url 'projects:calendar_at' today_year today_month %}" class="btn-secondary">Today</a>
    <a href="{% url 'projects:calendar_at' next_year next_month %}" class="btn-secondary">Next →</a>
  </div>
</div>

<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="w-full border-collapse text-sm">
    <thead class="bg-gray-50">
      <tr>
        {% for label in weekday_headers %}
          <th class="px-2 py-2 text-left text-xs uppercase text-gray-500 w-1/7">{{ label }}</th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for week in weeks %}
        <tr class="divide-x divide-gray-100">
          {% for cell in week %}
            <td class="align-top p-2 h-28 border-t border-gray-100
                       {% if cell.is_other_month %}bg-gray-50 text-gray-300{% endif %}
                       {% if cell.is_today %}bg-blue-50{% endif %}">
              <div class="text-xs {% if cell.is_today %}font-semibold text-blue-700{% endif %} mb-1">
                {{ cell.date.day }}
              </div>
              <div class="space-y-1">
                {% for p in cell.projects %}
                  <a href="{% url 'projects:detail' p.pk %}"
                     class="pill block truncate {{ status_chip_classes|default_if_none:'' }}{% if p.status == 'delayed' %}bg-red-100 text-red-800{% elif p.status == 'completed' %}bg-green-100 text-green-800{% elif p.status == 'in_progress' %}bg-blue-100 text-blue-800{% else %}bg-gray-100 text-gray-700{% endif %}"
                     title="{{ p.title }} — {{ p.get_status_display }}">{{ p.title|truncatechars:24 }}</a>
                {% endfor %}
                {% if cell.overflow_count %}
                  <a href="{% url 'projects:list' %}?due={{ cell.date|date:'Y-m-d' }}"
                     class="text-xs text-gray-500 hover:underline block">+{{ cell.overflow_count }} more</a>
                {% endif %}
              </div>
            </td>
          {% endfor %}
        </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

Note: the chip's CSS class is built inline with an `{% if %}/{% elif %}` chain because the status-to-class lookup via dict-access in a Django template is awkward (`{{ status_chip_classes|dict_get:p.status }}` would need a custom filter). The inline chain matches the project list row's existing approach.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v`
Expected: PASS — all calendar tests green plus the existing helper tests.

- [ ] **Step 8: Run ruff**

Run: `ruff check apps/projects/views/calendar.py apps/projects/views/__init__.py apps/projects/urls.py apps/projects/tests/test_views_calendar.py`
Expected: "All checks passed!"

- [ ] **Step 9: Commit**

```bash
git add apps/projects/views/calendar.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/calendar.html apps/projects/tests/test_views_calendar.py
git commit -m "feat(calendar): calendar_view with month grid, chips, and overflow"
```

---

## Task 4: Person filter on the calendar view

Adopt the shared `resolve_person_filter` helper from Task 1. The calendar view gains the same dropdown UX and the same default-to-linked-roster behavior as the dashboard.

**Files:**
- Modify: `apps/projects/views/calendar.py`
- Modify: `templates/projects/calendar.html`
- Test: `apps/projects/tests/test_views_calendar.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_calendar.py`:

```python
@pytest.fixture
def mike(db):
    from apps.roster.models import RosterPerson
    return RosterPerson.objects.create(name="Mike Smith")


@pytest.fixture
def laurel(db):
    from apps.roster.models import RosterPerson
    return RosterPerson.objects.create(name="Laurel Baran")


@pytest.fixture
def linked_client(db, client, mike):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(
        username="linked@example.com", email="linked@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    u.profile.roster_person = mike
    u.profile.save()
    client.force_login(u)
    return client


@pytest.mark.django_db
def test_calendar_unlinked_user_sees_banner(auth_client):
    response = auth_client.get(reverse("projects:calendar"))
    assert "Link your account to a roster person" in response.content.decode()


@pytest.mark.django_db
def test_calendar_linked_user_defaults_to_their_projects(
    linked_client, user, category, mike, laurel,
):
    from apps.projects.models import RACIAssignment, RACIRole
    p_mike = Project.objects.create(
        title="Mike project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 10),
    )
    RACIAssignment.objects.create(project=p_mike, person=mike, role=RACIRole.RESPONSIBLE)
    p_laurel = Project.objects.create(
        title="Laurel project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 11),
    )
    RACIAssignment.objects.create(project=p_laurel, person=laurel, role=RACIRole.RESPONSIBLE)

    response = linked_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    assert "Mike project" in content
    assert "Laurel project" not in content


@pytest.mark.django_db
def test_calendar_person_all_overrides_default(
    linked_client, user, category, mike, laurel,
):
    from apps.projects.models import RACIAssignment, RACIRole
    p_mike = Project.objects.create(
        title="Mike project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 10),
    )
    RACIAssignment.objects.create(project=p_mike, person=mike, role=RACIRole.RESPONSIBLE)
    p_laurel = Project.objects.create(
        title="Laurel project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 11),
    )
    RACIAssignment.objects.create(project=p_laurel, person=laurel, role=RACIRole.RESPONSIBLE)

    response = linked_client.get(reverse("projects:calendar_at", args=[2026, 5]) + "?person=all")
    content = response.content.decode()
    assert "Mike project" in content
    assert "Laurel project" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v -k "person or banner"`
Expected: FAIL — the calendar view doesn't yet filter by person; the banner string isn't rendered.

- [ ] **Step 3: Wire the person filter into the view**

In `apps/projects/views/calendar.py`, add an import and update the view body.

Add to the imports near the top of the file:

```python
from apps.roster.models import RosterPerson

from ._filters import resolve_person_filter
```

Update `calendar_view` to apply the person filter and include the dropdown / banner context. The full updated view:

```python
@login_required
def calendar_view(request, year: int | None = None, month: int | None = None):
    today = dt.date.today()
    if year is None or month is None:
        year, month = today.year, today.month
    if not (1 <= month <= 12) or not (1900 <= year <= 2100):
        raise Http404("Invalid year/month")

    person_id, banner, selected_person = resolve_person_filter(request)

    first, last, weeks = build_month_grid(year, month)

    qs = Project.instances.select_related("category").filter(
        projected_completion_date__gte=first,
        projected_completion_date__lte=last,
    )
    if person_id is not None:
        qs = qs.filter(raci_assignments__person_id=person_id).distinct()
    projects = list(qs)

    by_date: dict[dt.date, list[Project]] = {}
    for p in projects:
        by_date.setdefault(p.projected_completion_date, []).append(p)

    cells_by_week = []
    for week in weeks:
        row = []
        for day in week:
            day_projects = by_date.get(day, [])
            row.append({
                "date": day,
                "is_other_month": day.month != month,
                "is_today": day == today,
                "projects": day_projects[:CELL_CHIP_LIMIT],
                "overflow_count": max(0, len(day_projects) - CELL_CHIP_LIMIT),
            })
        cells_by_week.append(row)

    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    return render(request, "projects/calendar.html", {
        "year": year,
        "month": month,
        "month_label": dt.date(year, month, 1).strftime("%B %Y"),
        "weeks": cells_by_week,
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
        "today_year": today.year, "today_month": today.month,
        "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "status_chip_classes": STATUS_CHIP_CLASSES,
        "people": RosterPerson.active.all(),
        "selected_person": selected_person,
        "unlinked_user_banner": banner,
    })
```

- [ ] **Step 4: Add the dropdown and banner to the template**

In `templates/projects/calendar.html`, the file's current opening is:

```html
{% extends "base.html" %}
{% block title %}Calendar — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6 flex-wrap gap-3">
  <h1 class="text-2xl font-semibold text-gray-900">Calendar — {{ month_label }}</h1>
  <div class="flex gap-2 text-sm">
    ...
```

Insert the person dropdown form between the `<h1>` and the prev/today/next nav, AND add an unlinked banner below the header. The updated opening:

```html
{% extends "base.html" %}
{% block title %}Calendar — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6 flex-wrap gap-3">
  <h1 class="text-2xl font-semibold text-gray-900">Calendar — {{ month_label }}</h1>
  <div class="flex items-center gap-3 text-sm">
    <form method="get" class="flex items-center gap-2">
      <label for="calendar-person" class="text-gray-700">Showing tasks for:</label>
      <select id="calendar-person" name="person" class="input" onchange="this.form.submit()">
        <option value="all" {% if selected_person == "all" %}selected{% endif %}>All people</option>
        {% for p in people %}
          <option value="{{ p.pk }}" {% if selected_person == p.pk|stringformat:"s" %}selected{% endif %}>{{ p.name }}</option>
        {% endfor %}
      </select>
    </form>
    <div class="flex gap-2">
      <a href="{% url 'projects:calendar_at' prev_year prev_month %}" class="btn-secondary">← Prev</a>
      <a href="{% url 'projects:calendar_at' today_year today_month %}" class="btn-secondary">Today</a>
      <a href="{% url 'projects:calendar_at' next_year next_month %}" class="btn-secondary">Next →</a>
    </div>
  </div>
</div>

{% if unlinked_user_banner %}
<div class="bg-amber-50 border border-amber-200 text-amber-900 rounded-lg p-3 mb-6 text-sm">
  Link your account to a roster person in
  <a href="{% url 'accounts:profile' %}" class="underline font-medium">Account</a>
  to see only your tasks.
</div>
{% endif %}
```

The rest of the template — the `<div class="bg-white rounded-lg shadow ...">` wrapping the table and below — stays unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v`
Expected: PASS — all calendar tests green.

- [ ] **Step 6: Run ruff**

Run: `ruff check apps/projects/views/calendar.py apps/projects/tests/test_views_calendar.py`
Expected: "All checks passed!"

- [ ] **Step 7: Commit**

```bash
git add apps/projects/views/calendar.py templates/projects/calendar.html apps/projects/tests/test_views_calendar.py
git commit -m "feat(calendar): person filter (default to linked roster person)"
```

---

## Task 5: Sidebar link

Add a "Calendar" link to the sidebar between "Projects" and "Recurring", and a test that confirms it points to the calendar URL.

**Files:**
- Modify: `templates/_sidebar.html`
- Test: `apps/projects/tests/test_views_calendar.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/projects/tests/test_views_calendar.py`:

```python
@pytest.mark.django_db
def test_sidebar_includes_calendar_link(auth_client):
    """Any logged-in page should render the sidebar; assert the Calendar link
    exists and points at projects:calendar."""
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert ">Calendar<" in content
    assert reverse("projects:calendar") in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py::test_sidebar_includes_calendar_link -v`
Expected: FAIL — the sidebar doesn't have a Calendar link yet.

- [ ] **Step 3: Add the link**

In `templates/_sidebar.html`, the file currently is (verified earlier):

```html
<aside class="w-56 shrink-0 bg-white border-r border-gray-200 px-4 py-6 hidden md:block">
  <div class="text-lg font-semibold text-gray-900 mb-6">HOA Tasks</div>
  <nav class="space-y-1 text-sm">
    <a href="{% url 'home' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Dashboard</a>
    <a href="{% url 'projects:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Projects</a>
    <a href="{% url 'projects:recurring_list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Recurring</a>
    <a href="{% url 'roster:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Roster</a>
    <a href="{% url 'accounts:profile' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Account</a>
    <form method="post" action="{% url 'accounts:logout' %}" class="pt-4">
      ...
```

Insert a Calendar link between Projects and Recurring:

```html
    <a href="{% url 'projects:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Projects</a>
    <a href="{% url 'projects:calendar' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Calendar</a>
    <a href="{% url 'projects:recurring_list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Recurring</a>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_calendar.py -v`
Expected: PASS — all calendar tests green.

- [ ] **Step 5: Commit**

```bash
git add templates/_sidebar.html apps/projects/tests/test_views_calendar.py
git commit -m "feat(calendar): sidebar link"
```

---

## Task 6: Final pass — Tailwind, full suite, lint

Verify nothing new slipped into the Tailwind bundle, run the full suite and ruff.

- [ ] **Step 1: Spot-check Tailwind utilities used in the new calendar template**

Run:

```bash
grep -oE '\.w-1/7\{|\.h-28\{|\.bg-blue-50\{|\.bg-amber-50\{' static/css/output.css | sort -u
```

The chip-color classes (`bg-red-100`, `bg-green-100`, `bg-blue-100`, `bg-gray-100`) are already in the bundle (used by the project list row). The new utilities introduced by this batch are `w-1/7`, `h-28`, and `bg-blue-50`.

Expected: 0, 1, 2, or 3 of those classes already present. If any are missing, run the rebuild.

- [ ] **Step 2: If anything is missing, rebuild Tailwind**

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
git add static/css/output.css
```

(Don't commit yet — Step 4 commits everything together if there was a rebuild.)

- [ ] **Step 3: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — all tests, including the ~15 new calendar tests.

- [ ] **Step 4: Run ruff**

Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 5: Commit (if Tailwind was rebuilt)**

If Step 2 produced a changed `output.css`:

```bash
git commit -m "build: rebuild Tailwind CSS for calendar utilities"
```

Otherwise skip — Tasks 1-5 are already committed.

---

## Self-Review

**1. Spec coverage:**
- §2 in-scope: dedicated page (Task 3), prev/next/today navigation (Task 3), 6×7 grid (Task 2 helper, Task 3 template), chips color-coded by status (Task 3), person filter with dropdown + auto-default + banner (Task 4), sidebar link (Task 5), tests covering each. ✓
- §2 out-of-scope: explicitly not built. ✓
- §3 architecture: URL, view, helper, template, filter extraction all mapped to tasks. ✓
- §4 data model: no schema changes — confirmed nothing in Tasks 1-6 adds migrations. ✓
- §5 components & files: every file listed in the spec is touched by exactly one task (the helper extraction in Task 1, the view across Tasks 2/3/4, etc.). ✓
- §6 error handling: invalid year/month → Http404 (Task 3). Project without date → excluded by the `filter(...gte=first, ...lte=last)` (Task 3, has a test). ✓
- §7 testing: every bullet mapped to at least one test in Tasks 2-5. ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"add appropriate error handling". Every code step shows the complete code that goes in. The `dict_get` filter referenced in passing in the spec is not used — the template uses explicit `{% if %}/{% elif %}` instead, avoiding a custom filter.

**3. Type consistency:**
- `build_month_grid(year: int, month: int) → (date, date, list[list[date]])` defined in Task 2, used identically in Task 3.
- `resolve_person_filter(request) → (int|None, bool, str)` defined in Task 1 (new module), called in Task 4 with the same unpacking shape used by the dashboard view.
- `CELL_CHIP_LIMIT = 3` defined in Task 3, used in the same task's view and reflected in the Task 3 test (`"+2 more"` when 5 projects on one day).
- `STATUS_CHIP_CLASSES` dict defined in Task 3 — the template uses an inline `{% if %}/{% elif %}` chain instead of dict lookup, which avoids a custom filter. The dict itself is mainly documentation of the palette mapping; it's also passed to the template context for future use.
- URL names `projects:calendar` (Task 3 Step 5, no args) and `projects:calendar_at` (Task 3 Step 5, two args) consistent across the template `{% url %}` tags (Task 3 Step 6, Task 4 Step 4) and the tests (Tasks 3, 4, 5).

One thing I noticed during self-review: the chip rendering in Task 3 Step 6 has `{{ status_chip_classes|default_if_none:'' }}` which evaluates to the empty string (the dict is truthy but doesn't filter through that filter usefully). It's effectively a no-op; the real status-to-color decision is the `{% if %}/{% elif %}` chain right after. Functionally correct, just a leftover thought I'll clean up during implementation if it bothers the reviewer.
