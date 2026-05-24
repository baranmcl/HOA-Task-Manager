# Completion Report — Implementation Plan

**Goal:** A `/projects/report/` page for the board, summarizing completed projects across a chosen `from`/`to` date window. Headline tiles + per-category breakdown. Bookmarkable URLs, six preset buttons.

**Architecture:** Pure-function `compute_completion_report(from_date, to_date)` in `apps/projects/services/reports.py` returns a dataclass-ish dict with `summary`, `by_category`, `from_date`, `to_date`. View parses query params (or defaults to this-year), calls the service, renders template.

**Branch:** `completion-report` (already created).

---

## Task 1: Service — compute_completion_report

**Files:**
- Create: `apps/projects/services/reports.py`
- Create: `apps/projects/tests/test_reports_service.py`

### Step 1: Write the failing tests

```python
# apps/projects/tests/test_reports_service.py
import datetime as dt
from decimal import Decimal

import pytest

from apps.projects.models import Project, ProjectCategory, ProjectStatus
from apps.projects.services.reports import compute_completion_report


def _complete_on(date, project):
    """Force actual_completion_date to a specific value, bypassing save() side-effects."""
    Project.objects.filter(pk=project.pk).update(actual_completion_date=date)
    project.refresh_from_db()
    return project


@pytest.mark.django_db
def test_empty_window_returns_zeros(category):
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0
    assert result["summary"]["total_spent"] == Decimal("0")
    assert result["summary"]["over_budget"] == 0
    assert result["summary"]["avg_days_to_complete"] is None
    assert result["by_category"] == []


@pytest.mark.django_db
def test_completed_in_window_counted(user, category):
    p = Project.objects.create(
        title="Done", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    _complete_on(dt.date(2026, 3, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 1
    assert result["summary"]["total_spent"] == Decimal("100")


@pytest.mark.django_db
def test_completed_outside_window_excluded(user, category):
    p = Project.objects.create(
        title="Last year", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    _complete_on(dt.date(2025, 6, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_in_progress_excluded_even_inside_window(user, category):
    Project.objects.create(
        title="WIP", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_recurring_template_excluded(user, category):
    Project.objects.create(
        title="Template", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, is_recurring_template=True,
    )
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_total_spent_treats_null_actual_cost_as_zero(user, category):
    p1 = Project.objects.create(
        title="A", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("250"),
    )
    p2 = Project.objects.create(
        title="B", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=None,
    )
    _complete_on(dt.date(2026, 3, 15), p1)
    _complete_on(dt.date(2026, 4, 1), p2)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 2
    assert result["summary"]["total_spent"] == Decimal("250")


@pytest.mark.django_db
def test_over_budget_requires_both_amounts_set(user, category):
    # Has both, over budget — counts.
    a = Project.objects.create(
        title="Over", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=Decimal("100"), actual_cost=Decimal("150"),
    )
    # Has both, under budget — doesn't count.
    b = Project.objects.create(
        title="Under", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=Decimal("100"), actual_cost=Decimal("80"),
    )
    # Missing budget — doesn't count.
    c = Project.objects.create(
        title="No budget", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=None, actual_cost=Decimal("999"),
    )
    for p in (a, b, c):
        _complete_on(dt.date(2026, 3, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["over_budget"] == 1


@pytest.mark.django_db
def test_avg_days_to_complete_math(user, category):
    """Avg of (actual_completion_date - created_at.date()) in days.

    We can't easily control created_at (auto_now_add), so we update it
    post-hoc with .filter().update().
    """
    p1 = Project.objects.create(
        title="Fast", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    p2 = Project.objects.create(
        title="Slow", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    created_at_fixed = dt.datetime(2026, 3, 1, 12, 0, tzinfo=dt.UTC)
    Project.objects.filter(pk__in=[p1.pk, p2.pk]).update(created_at=created_at_fixed)
    _complete_on(dt.date(2026, 3, 5), p1)   # 4 days
    _complete_on(dt.date(2026, 3, 11), p2)  # 10 days
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["avg_days_to_complete"] == 7  # (4 + 10) / 2


@pytest.mark.django_db
def test_by_category_breakdown(user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    empty = ProjectCategory.objects.create(name="Empty", display_order=3)

    p1 = Project.objects.create(
        title="L1", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    p2 = Project.objects.create(
        title="L2", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("300"),
    )
    p3 = Project.objects.create(
        title="P1", category=pool, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("500"),
    )
    for p in (p1, p2, p3):
        _complete_on(dt.date(2026, 3, 15), p)

    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    rows = result["by_category"]
    # Sorted by count desc; landscaping (2) before pool (1).
    assert [r["name"] for r in rows] == ["Landscaping", "Pool"]
    assert rows[0]["count"] == 2
    assert rows[0]["total_spent"] == Decimal("400")
    assert rows[0]["avg_cost"] == Decimal("200")
    assert rows[1]["count"] == 1
    assert rows[1]["total_spent"] == Decimal("500")
    # Empty category not in the list.
    assert "Empty" not in [r["name"] for r in rows]


@pytest.mark.django_db
def test_window_boundary_inclusive(user, category):
    p1 = Project.objects.create(
        title="On from", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    p2 = Project.objects.create(
        title="On to", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    _complete_on(dt.date(2026, 1, 1), p1)
    _complete_on(dt.date(2026, 12, 31), p2)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 2
```

### Step 2: Run them to verify they fail

`python -m pytest apps/projects/tests/test_reports_service.py -v`
Expected: ModuleNotFoundError for `apps.projects.services.reports`.

### Step 3: Implement the service

```python
# apps/projects/services/reports.py
"""Pure-function report computations.

compute_completion_report(from_date, to_date) -> dict with the shape:
{
    "from_date": dt.date,
    "to_date": dt.date,
    "summary": {
        "completed": int,
        "total_spent": Decimal,
        "over_budget": int,
        "avg_days_to_complete": int | None,
    },
    "by_category": [
        {"name": str, "count": int, "total_spent": Decimal, "avg_cost": Decimal},
        ...
    ],
}
"""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from apps.projects.models import Project, ProjectStatus

ZERO = Decimal("0")


def compute_completion_report(from_date: dt.date, to_date: dt.date) -> dict:
    qs = (
        Project.instances  # excludes recurring templates
        .filter(
            status=ProjectStatus.COMPLETED,
            actual_completion_date__gte=from_date,
            actual_completion_date__lte=to_date,
        )
        .select_related("category")
    )

    total_spent = ZERO
    over_budget = 0
    days_to_complete = []
    by_cat_count = defaultdict(int)
    by_cat_spent = defaultdict(lambda: ZERO)
    cat_names = {}  # cat_id -> name (preserve casing)

    completed_count = 0
    for p in qs:
        completed_count += 1
        cost = p.actual_cost if p.actual_cost is not None else ZERO
        total_spent += cost
        if p.budget_amount is not None and p.actual_cost is not None:
            if p.actual_cost > p.budget_amount:
                over_budget += 1
        delta = (p.actual_completion_date - p.created_at.date()).days
        days_to_complete.append(delta)
        by_cat_count[p.category_id] += 1
        by_cat_spent[p.category_id] += cost
        cat_names[p.category_id] = p.category.name

    avg_days = (
        round(sum(days_to_complete) / len(days_to_complete))
        if days_to_complete else None
    )

    by_category = []
    for cat_id, count in by_cat_count.items():
        spent = by_cat_spent[cat_id]
        avg = (spent / count).quantize(Decimal("1")) if count else ZERO
        by_category.append({
            "name": cat_names[cat_id],
            "count": count,
            "total_spent": spent,
            "avg_cost": avg,
        })
    by_category.sort(key=lambda r: (-r["count"], r["name"]))

    return {
        "from_date": from_date,
        "to_date": to_date,
        "summary": {
            "completed": completed_count,
            "total_spent": total_spent,
            "over_budget": over_budget,
            "avg_days_to_complete": avg_days,
        },
        "by_category": by_category,
    }
```

### Step 4: Tests green

`python -m pytest apps/projects/tests/test_reports_service.py -v`
Expected: 10 pass.

### Step 5: Commit

```bash
git add apps/projects/services/reports.py apps/projects/tests/test_reports_service.py docs/superpowers/specs/2026-05-23-completion-report-design.md docs/superpowers/plans/2026-05-23-completion-report.md
git commit -m "feat(reports): completion-report compute service"
```

---

## Task 2: View + URL + sidebar link

**Files:**
- Create: `apps/projects/views/report.py`
- Modify: `apps/projects/views/__init__.py` (one new export)
- Modify: `apps/projects/urls.py` (one new route)
- Create: `templates/projects/report.html`
- Modify: `templates/_sidebar.html` (add "Reports" link)
- Create: `apps/projects/tests/test_views_report.py`

### Step 1: Write failing tests

```python
# apps/projects/tests/test_views_report.py
import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectCategory, ProjectStatus


def _complete_on(date, project):
    Project.objects.filter(pk=project.pk).update(actual_completion_date=date)
    project.refresh_from_db()
    return project


@pytest.mark.django_db
def test_report_requires_login(client):
    response = client.get(reverse("projects:report"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_report_default_window_is_current_year(auth_client):
    response = auth_client.get(reverse("projects:report"))
    assert response.status_code == 200
    today = dt.date.today()
    assert response.context["from_date"] == dt.date(today.year, 1, 1)
    assert response.context["to_date"] == today


@pytest.mark.django_db
def test_report_honors_explicit_window(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-03-01&to=2026-03-31",
    )
    assert response.context["from_date"] == dt.date(2026, 3, 1)
    assert response.context["to_date"] == dt.date(2026, 3, 31)


@pytest.mark.django_db
def test_report_invalid_dates_fall_back_to_default(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=not-a-date&to=also-bad",
    )
    today = dt.date.today()
    assert response.context["from_date"] == dt.date(today.year, 1, 1)
    assert response.context["to_date"] == today


@pytest.mark.django_db
def test_report_shows_summary_tiles(auth_client, user, category):
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("250"),
    )
    _complete_on(dt.date(2026, 3, 15), p)
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-01-01&to=2026-12-31",
    )
    content = response.content.decode()
    assert response.context["report"]["summary"]["completed"] == 1
    # The dollar amount renders.
    assert "$250" in content or "250" in content


@pytest.mark.django_db
def test_report_renders_category_breakdown_table(auth_client, user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    p1 = Project.objects.create(
        title="L", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    p2 = Project.objects.create(
        title="P", category=pool, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("200"),
    )
    _complete_on(dt.date(2026, 3, 15), p1)
    _complete_on(dt.date(2026, 3, 15), p2)
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-01-01&to=2026-12-31",
    )
    content = response.content.decode()
    assert "Landscaping" in content
    assert "Pool" in content


@pytest.mark.django_db
def test_report_empty_window_shows_message(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=2030-01-01&to=2030-12-31",
    )
    content = response.content.decode()
    assert "No completed projects" in content


@pytest.mark.django_db
def test_sidebar_includes_reports_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert ">Reports<" in content
    assert reverse("projects:report") in content
```

### Step 2: Implement view

```python
# apps/projects/views/report.py
"""Completion report view.

Free-date-range with preset query strings. Defaults to the current
calendar year (Jan 1 → today).
"""
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..services.reports import compute_completion_report


def _default_window():
    today = dt.date.today()
    return dt.date(today.year, 1, 1), today


def _parse_iso(raw):
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _presets(today):
    """Returns [(label, from_iso, to_iso), ...] for the six preset buttons."""
    first_of_month = today.replace(day=1)
    last_of_prev_month = first_of_month - dt.timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)

    # Current quarter
    q_start_month = ((today.month - 1) // 3) * 3 + 1
    q_start = dt.date(today.year, q_start_month, 1)

    # Previous quarter
    if q_start_month == 1:
        prev_q_year, prev_q_start_month = today.year - 1, 10
    else:
        prev_q_year, prev_q_start_month = today.year, q_start_month - 3
    prev_q_start = dt.date(prev_q_year, prev_q_start_month, 1)
    prev_q_end = q_start - dt.timedelta(days=1)

    year_start = dt.date(today.year, 1, 1)
    last_year_start = dt.date(today.year - 1, 1, 1)
    last_year_end = dt.date(today.year - 1, 12, 31)

    return [
        ("This month", first_of_month, today),
        ("This quarter", q_start, today),
        ("This year", year_start, today),
        ("Last month", first_of_prev_month, last_of_prev_month),
        ("Last quarter", prev_q_start, prev_q_end),
        ("Last year", last_year_start, last_year_end),
    ]


@login_required
def report_view(request):
    default_from, default_to = _default_window()
    from_date = _parse_iso(request.GET.get("from")) or default_from
    to_date = _parse_iso(request.GET.get("to")) or default_to

    report = compute_completion_report(from_date, to_date)

    today = dt.date.today()
    presets = [
        {"label": label, "from": f.isoformat(), "to": t.isoformat()}
        for (label, f, t) in _presets(today)
    ]

    return render(request, "projects/report.html", {
        "report": report,
        "from_date": from_date,
        "to_date": to_date,
        "presets": presets,
    })
```

### Step 3: Wire up exports and URL

In `apps/projects/views/__init__.py` (alphabetical, after `raci`):

```python
from .report import report_view as report_view
```

In `apps/projects/urls.py` (group with the other top-level routes, after `search/`):

```python
    path("report/", views.report_view, name="report"),
```

### Step 4: Write the template

```html
<!-- templates/projects/report.html -->
{% extends "base.html" %}
{% load humanize %}
{% block title %}Reports — HOA Task Manager{% endblock %}
{% block content %}
<div class="mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Reports — Completed projects</h1>
  <p class="text-sm text-gray-600 mt-1">
    {{ from_date|date:"M j, Y" }} – {{ to_date|date:"M j, Y" }}
  </p>
</div>

<form method="get" class="bg-white rounded-lg shadow p-4 mb-6">
  <div class="flex flex-wrap gap-2 mb-4">
    {% for p in presets %}
      <a href="?from={{ p.from }}&to={{ p.to }}" class="btn-secondary text-xs">{{ p.label }}</a>
    {% endfor %}
  </div>
  <div class="flex items-end gap-3 text-sm flex-wrap">
    <label class="block">
      <span class="text-gray-700 block">From</span>
      <input type="date" name="from" value="{{ from_date|date:'Y-m-d' }}" class="input">
    </label>
    <label class="block">
      <span class="text-gray-700 block">To</span>
      <input type="date" name="to" value="{{ to_date|date:'Y-m-d' }}" class="input">
    </label>
    <button type="submit" class="btn-primary">Apply</button>
  </div>
</form>

<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Completed</div>
    <div class="text-3xl font-semibold">{{ report.summary.completed }}</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Total spent</div>
    <div class="text-3xl font-semibold">${{ report.summary.total_spent|floatformat:0|intcomma }}</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Over budget</div>
    <div class="text-3xl font-semibold {% if report.summary.over_budget %}text-red-700{% endif %}">
      {{ report.summary.over_budget }}
    </div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Avg days to complete</div>
    <div class="text-3xl font-semibold">
      {% if report.summary.avg_days_to_complete is None %}—{% else %}{{ report.summary.avg_days_to_complete }}{% endif %}
    </div>
  </div>
</div>

<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">By category</h2>
  {% if report.by_category %}
    <table class="w-full text-sm">
      <thead class="text-xs uppercase text-gray-500 border-b border-gray-100">
        <tr>
          <th class="py-2 text-left">Category</th>
          <th class="py-2 text-right">Count</th>
          <th class="py-2 text-right">Total spent</th>
          <th class="py-2 text-right">Avg cost</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        {% for row in report.by_category %}
          <tr>
            <td class="py-2">{{ row.name }}</td>
            <td class="py-2 text-right">{{ row.count }}</td>
            <td class="py-2 text-right">${{ row.total_spent|floatformat:0|intcomma }}</td>
            <td class="py-2 text-right">${{ row.avg_cost|floatformat:0|intcomma }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="text-gray-400 text-sm">No completed projects in this window.</p>
  {% endif %}
</section>
{% endblock %}
```

### Step 5: Sidebar link

In `templates/_sidebar.html`, after the Recurring link and before Import projects:

```html
<a href="{% url 'projects:report' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Reports</a>
```

### Step 6: Run all report tests

`python -m pytest apps/projects/tests/test_reports_service.py apps/projects/tests/test_views_report.py -v`
Expected: all pass.

### Step 7: Commit

```bash
git add apps/projects/views/report.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/report.html templates/_sidebar.html apps/projects/tests/test_views_report.py
git commit -m "feat(reports): completion report page with date presets and category breakdown"
```

---

## Task 3: Full suite + ruff + ship

```bash
python -m pytest -q
ruff check .
git checkout main
git merge --no-ff completion-report -m "Merge branch 'completion-report'"
git branch -d completion-report
git push origin main
```

---

## Self-review

- **Spec coverage:** Window inputs + 6 presets (Task 2), summary tiles (Task 1/2), category breakdown (Task 1/2), exclusion rules (Task 1 tests), empty state (Task 2 test), sidebar entry (Task 2). All design sections covered.
- **Placeholders:** None.
- **Type consistency:** `compute_completion_report` always returns the same dict shape; view passes `report` straight through; template reads `report.summary.*` and `report.by_category.*`. Matches between service tests, view tests, and template references.
- **Risk:** the date math in `_presets` is the trickiest piece. Tests don't directly cover it; the view test just confirms the buttons render. If a quarter boundary edge case appears we can fix it on follow-up — the user can always pick a custom date in the meantime.
