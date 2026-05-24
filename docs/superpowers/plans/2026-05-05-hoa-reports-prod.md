# HOA Task Manager — Plan 3: Reports & Production Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the monthly board-report view (auto-summary + per-month override + copy-to-clipboard with formatting), wire continuous SQLite backups via litestream to Cloudflare R2, set up the production Fly.io app with tagged-release promotion, and harden polish items (error pages, smoke-test checklist).

**Architecture:** A new `reports` Django app holds the monthly close view. The auto-summary is computed live from `Project` + `BoardApproval` queries scoped to the displayed `year_month`. A `MonthlyReportSummary` row stores the user's edited override; "revert to auto" deletes the row. The copy button uses `navigator.clipboard.write()` with a `text/html` blob so paste targets (Word, Google Docs, Outlook) preserve inline styles. litestream runs as a sidecar inside the Fly machine, replicating `/data/db.sqlite3` to R2 continuously. Production is a separate Fly app (`hoa-task-manager`) with a tagged-release promotion workflow — staging deploys on `main`, prod deploys on a `v*` git tag.

**Tech Stack:** Django 5.x (existing), litestream (Go binary in the Docker image), Cloudflare R2 (separate bucket for backups), GitHub Actions for tag-based prod deploy. Builds on Plans 1 + 2.

**Prerequisites:** Plans 1 and 2 complete. Staging deploys cleanly. Projects, RACI, approvals, attachments, recurring, dashboard all working.

---

## File Structure

```
hoa-task-manager/
├── apps/
│   └── reports/                    # NEW
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py               # MonthlyReportSummary
│       ├── forms.py                # SummaryOverrideForm
│       ├── views.py                # monthly view + override save + revert
│       ├── urls.py
│       ├── period.py               # year_month parsing + month boundaries
│       ├── summary.py              # auto-summary text generator
│       ├── migrations/
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_period.py
│           ├── test_summary.py
│           ├── test_models.py
│           └── test_views.py
├── templates/
│   ├── _sidebar.html               # MODIFIED — add Reports
│   └── reports/
│       ├── monthly.html
│       ├── _stats_strip.html
│       ├── _section_completed.html
│       ├── _section_in_progress.html
│       ├── _section_approvals.html
│       └── _summary_block.html
├── static/
│   ├── js/
│   │   └── copy-report.js          # Clipboard copy with text/html
│   └── css/
│       └── input.css               # MODIFIED — add .report-* serif styles
├── litestream.yml                  # NEW — backup config
├── Dockerfile                      # MODIFIED — install litestream, run as supervisor
├── fly.toml                        # MODIFIED — staging app (litestream env added)
├── fly.production.toml             # NEW — production app config
├── .github/workflows/
│   ├── deploy-staging.yml          # MODIFIED — runs on main only (already does)
│   └── deploy-production.yml       # NEW — runs on v* tags
├── templates/
│   ├── 404.html                    # NEW
│   └── 500.html                    # NEW
└── docs/
    └── runbooks/                   # NEW — operational docs
        ├── deploy.md
        ├── restore-from-backup.md
        ├── reset-password.md
        └── pre-deploy-smoke-test.md
```

**Decomposition rationale:**
- The `reports` app has thin domain — one model, one view module — but the auto-summary logic (`summary.py`) and period math (`period.py`) are pure-function helpers worth isolating because they're heavily tested and reused if we add a PDF export later.
- `litestream.yml` lives at the repo root because it's process-level infra, not Django code.
- `fly.production.toml` is a separate file (vs. environment overlays) because the values genuinely differ — different app name, different secrets, different volume.

---

## Task 1: Scaffold the reports app

**Files:**
- Create: `apps/reports/{__init__,apps,urls,models,forms,views,period,summary}.py`
- Create: `apps/reports/migrations/__init__.py`
- Create: `apps/reports/tests/{__init__,conftest}.py`
- Modify: `config/settings.py` (add `apps.reports`)
- Modify: `config/urls.py` (include reports URLs)
- Modify: `templates/_sidebar.html` (add Reports link)

- [ ] **Step 1: Create directories and stubs**

```bash
mkdir -p apps/reports/migrations apps/reports/tests
```

Touch `__init__.py` in each. Stub each module:

`apps/reports/apps.py`:
```python
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reports"
    label = "reports"
```

`apps/reports/urls.py`:
```python
from django.urls import path

app_name = "reports"
urlpatterns: list = []
```

Empty placeholders for `models.py`, `forms.py`, `views.py`, `period.py`, `summary.py`.

- [ ] **Step 2: Add to INSTALLED_APPS**

In `config/settings.py`, append `"apps.reports"`.

- [ ] **Step 3: Wire root URLs**

In `config/urls.py`:
```python
path("reports/", include("apps.reports.urls", namespace="reports")),
```

- [ ] **Step 4: Sidebar link**

In `templates/_sidebar.html`, add after Recurring:
```html
<a href="{% url 'reports:monthly' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Reports</a>
```

(This URL doesn't resolve yet — fixed in Task 4.)

- [ ] **Step 5: Conftest**

Create `apps/reports/tests/conftest.py`:
```python
"""Reports test fixtures — re-uses fixtures from projects' conftest by importing.
We re-declare the user/category/project fixtures here (small enough) so reports
tests don't depend on apps.projects.tests being importable."""

import pytest
from django.contrib.auth import get_user_model

from apps.projects.models import ProjectCategory


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def category(db):
    return ProjectCategory.objects.create(name="Capital", display_order=1)
```

- [ ] **Step 6: Verify**

```bash
uv run python manage.py check
uv run pytest -v
```

Expected: existing tests still pass; no new failures.

- [ ] **Step 7: Commit**

```bash
git add apps/reports/ config/ templates/_sidebar.html
git commit -m "chore: scaffold reports app"
```

---

## Task 2: Period helpers (`period.py`) with TDD

**Files:**
- Replace: `apps/reports/period.py`
- Create: `apps/reports/tests/test_period.py`

- [ ] **Step 1: Failing tests**

Create `apps/reports/tests/test_period.py`:

```python
import datetime as dt

import pytest

from apps.reports.period import (
    parse_year_month, year_month_for, format_label,
    month_bounds, prev_month, next_month, recent_months,
)


def test_parse_valid():
    assert parse_year_month("2026-04") == (2026, 4)


def test_parse_default_to_current(monkeypatch):
    monkeypatch.setattr("apps.reports.period._today", lambda: dt.date(2026, 4, 15))
    assert parse_year_month(None) == (2026, 4)
    assert parse_year_month("") == (2026, 4)


def test_parse_invalid_falls_back_to_current(monkeypatch):
    monkeypatch.setattr("apps.reports.period._today", lambda: dt.date(2026, 4, 15))
    assert parse_year_month("garbage") == (2026, 4)
    assert parse_year_month("2026-13") == (2026, 4)


def test_year_month_for():
    assert year_month_for(2026, 4) == "2026-04"
    assert year_month_for(2026, 12) == "2026-12"


def test_format_label():
    assert format_label(2026, 4) == "April 2026"


def test_month_bounds():
    start, end = month_bounds(2026, 4)
    assert start == dt.date(2026, 4, 1)
    assert end == dt.date(2026, 4, 30)


def test_month_bounds_february_leap():
    _, end = month_bounds(2024, 2)
    assert end == dt.date(2024, 2, 29)


def test_month_bounds_february_non_leap():
    _, end = month_bounds(2026, 2)
    assert end == dt.date(2026, 2, 28)


def test_prev_month_wraps_year():
    assert prev_month(2026, 1) == (2025, 12)
    assert prev_month(2026, 5) == (2026, 4)


def test_next_month_wraps_year():
    assert next_month(2026, 12) == (2027, 1)
    assert next_month(2026, 5) == (2026, 6)


def test_recent_months_default_count(monkeypatch):
    monkeypatch.setattr("apps.reports.period._today", lambda: dt.date(2026, 5, 15))
    months = recent_months()
    assert months[0] == (2026, 5)
    assert months[-1][0] <= 2026
    assert len(months) == 12
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/reports/tests/test_period.py -v
```

- [ ] **Step 3: Implement**

Replace `apps/reports/period.py`:

```python
"""Period helpers for monthly reports."""

import calendar
import datetime as dt


def _today() -> dt.date:
    return dt.date.today()


def parse_year_month(raw: str | None) -> tuple[int, int]:
    """Parse 'YYYY-MM'. Falls back to current year/month for invalid input."""
    if raw:
        parts = raw.split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            year = int(parts[0])
            month = int(parts[1])
            if 1 <= month <= 12 and 1900 <= year <= 9999:
                return year, month
    today = _today()
    return today.year, today.month


def year_month_for(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def format_label(year: int, month: int) -> str:
    return dt.date(year, month, 1).strftime("%B %Y")


def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, last_day)


def prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def recent_months(count: int = 12) -> list[tuple[int, int]]:
    """Most-recent first, including current month."""
    today = _today()
    months = []
    y, m = today.year, today.month
    for _ in range(count):
        months.append((y, m))
        y, m = prev_month(y, m)
    return months
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest apps/reports/tests/test_period.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/reports/period.py apps/reports/tests/
git commit -m "feat(reports): period helpers (parsing, bounds, navigation)"
```

---

## Task 3: Auto-summary generator (`summary.py`) with TDD

**Files:**
- Replace: `apps/reports/summary.py`
- Create: `apps/reports/tests/test_summary.py`

- [ ] **Step 1: Failing tests**

Create `apps/reports/tests/test_summary.py`:

```python
import datetime as dt
from decimal import Decimal

import pytest

from apps.projects.models import (
    BoardApproval, Project, ProjectStatus, RACIAssignment, RACIRole,
)
from apps.reports.summary import (
    monthly_stats, completed_in_month, in_progress_highlights,
    approvals_in_month, auto_summary_text,
)


@pytest.fixture
def april(category, user):
    """Seed projects relevant to April 2026."""
    completed = Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
        budget_amount=Decimal("40000.00"), actual_cost=Decimal("38500.00"),
        vendor_name="ABC Sprinklers",
    )
    completed.status = ProjectStatus.COMPLETED
    completed.actual_completion_date = dt.date(2026, 4, 22)
    completed.save()
    BoardApproval.objects.create(
        project=completed, motion_text="Approve sprinkler upgrade for $40,000.",
        vote_date=dt.date(2026, 4, 5),
        votes_for=4, votes_against=0, votes_abstain=1,
        minutes_reference="Apr 2026 minutes, p. 3",
    )
    Project.objects.create(
        title="Pool resurfacing", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=dt.date(2026, 6, 1),
    )
    Project.objects.create(
        title="Concrete repair", category=category, created_by=user,
        status=ProjectStatus.DELAYED,
        delay_reason="Vendor delayed by weather.",
    )
    return None


@pytest.mark.django_db
def test_monthly_stats(april):
    stats = monthly_stats(2026, 4)
    assert stats["completed"] == 1
    assert stats["in_progress"] == 1
    assert stats["delayed"] == 1
    assert stats["approvals"] == 1
    assert stats["spent_capital"] == Decimal("38500.00")


@pytest.mark.django_db
def test_completed_in_month(april):
    items = completed_in_month(2026, 4)
    assert len(items) == 1
    assert items[0].title == "Sprinkler upgrade"


@pytest.mark.django_db
def test_in_progress_highlights_includes_delayed_with_reason(april):
    items = in_progress_highlights()
    titles = [p.title for p in items]
    assert "Pool resurfacing" in titles
    assert "Concrete repair" in titles


@pytest.mark.django_db
def test_approvals_in_month(april):
    items = approvals_in_month(2026, 4)
    assert len(items) == 1
    assert items[0].project.title == "Sprinkler upgrade"


@pytest.mark.django_db
def test_auto_summary_text_mentions_counts(april):
    txt = auto_summary_text(2026, 4)
    assert "1" in txt
    assert "April 2026" in txt


@pytest.mark.django_db
def test_auto_summary_handles_empty_month():
    txt = auto_summary_text(2025, 1)
    assert "No project activity" in txt
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/reports/tests/test_summary.py -v
```

- [ ] **Step 3: Implement**

Replace `apps/reports/summary.py`:

```python
"""Auto-summary computations for monthly board reports."""

from decimal import Decimal

from django.db.models import Sum

from apps.projects.models import (
    BoardApproval, Project, ProjectStatus,
)

from .period import format_label, month_bounds


def monthly_stats(year: int, month: int) -> dict:
    start, end = month_bounds(year, month)

    completed = Project.instances.filter(
        status=ProjectStatus.COMPLETED,
        actual_completion_date__gte=start,
        actual_completion_date__lte=end,
    ).count()

    in_progress = Project.instances.filter(status=ProjectStatus.IN_PROGRESS).count()
    delayed = Project.instances.filter(status=ProjectStatus.DELAYED).count()

    approvals = BoardApproval.objects.filter(
        vote_date__gte=start, vote_date__lte=end,
    ).count()

    capital_spend = Project.instances.filter(
        status=ProjectStatus.COMPLETED,
        actual_completion_date__gte=start,
        actual_completion_date__lte=end,
        category__name="Capital",
    ).aggregate(total=Sum("actual_cost"))["total"] or Decimal("0")

    return {
        "completed": completed,
        "in_progress": in_progress,
        "delayed": delayed,
        "approvals": approvals,
        "spent_capital": capital_spend,
    }


def completed_in_month(year: int, month: int):
    start, end = month_bounds(year, month)
    return list(
        Project.instances
            .filter(
                status=ProjectStatus.COMPLETED,
                actual_completion_date__gte=start,
                actual_completion_date__lte=end,
            )
            .select_related("category", "board_approval")
            .order_by("category__display_order", "title")
    )


def in_progress_highlights():
    return list(
        Project.instances
            .filter(status__in=[ProjectStatus.IN_PROGRESS, ProjectStatus.DELAYED])
            .select_related("category")
            .order_by("status", "title")
    )


def approvals_in_month(year: int, month: int):
    start, end = month_bounds(year, month)
    return list(
        BoardApproval.objects
            .filter(vote_date__gte=start, vote_date__lte=end)
            .select_related("project")
            .order_by("vote_date")
    )


def auto_summary_text(year: int, month: int) -> str:
    label = format_label(year, month)
    stats = monthly_stats(year, month)
    if (stats["completed"] == 0 and stats["approvals"] == 0
            and stats["in_progress"] == 0 and stats["delayed"] == 0):
        return f"No project activity recorded for {label}."

    parts = [f"In {label}, the board completed {stats['completed']} project(s)"]
    if stats["spent_capital"]:
        parts.append(f" with ${stats['spent_capital']:,.0f} in capital spend")
    parts.append(
        f", recorded {stats['approvals']} board approval(s), "
        f"and is tracking {stats['in_progress']} in-progress and "
        f"{stats['delayed']} delayed project(s)."
    )
    return "".join(parts)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest apps/reports/tests/test_summary.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/reports/summary.py apps/reports/tests/test_summary.py
git commit -m "feat(reports): auto-summary stats and text generator"
```

---

## Task 4: MonthlyReportSummary model + view

**Files:**
- Replace: `apps/reports/models.py`
- Replace: `apps/reports/forms.py`
- Replace: `apps/reports/views.py`
- Replace: `apps/reports/urls.py`
- Create: `apps/reports/tests/test_models.py`
- Create: `apps/reports/tests/test_views.py`

- [ ] **Step 1: Failing model tests**

Create `apps/reports/tests/test_models.py`:

```python
import pytest

from apps.reports.models import MonthlyReportSummary


@pytest.mark.django_db
def test_create_summary(user):
    s = MonthlyReportSummary.objects.create(
        year_month="2026-04",
        override_text="Custom summary for April.",
        updated_by=user,
    )
    assert s.year_month == "2026-04"


@pytest.mark.django_db
def test_year_month_unique(user):
    MonthlyReportSummary.objects.create(
        year_month="2026-04", override_text="A", updated_by=user,
    )
    with pytest.raises(Exception):
        MonthlyReportSummary.objects.create(
            year_month="2026-04", override_text="B", updated_by=user,
        )
```

- [ ] **Step 2: Failing view tests**

Create `apps/reports/tests/test_views.py`:

```python
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus
from apps.reports.models import MonthlyReportSummary


@pytest.mark.django_db
def test_monthly_view_renders_for_current_month(auth_client):
    response = auth_client.get(reverse("reports:monthly"))
    assert response.status_code == 200
    assert b"Monthly report" in response.content


@pytest.mark.django_db
def test_monthly_view_with_explicit_month(auth_client):
    response = auth_client.get(reverse("reports:monthly") + "?month=2026-04")
    assert response.status_code == 200
    assert b"April 2026" in response.content


@pytest.mark.django_db
def test_save_override(auth_client, user):
    response = auth_client.post(
        reverse("reports:save_override") + "?month=2026-04",
        {"override_text": "My custom summary."},
    )
    assert response.status_code == 302
    s = MonthlyReportSummary.objects.get(year_month="2026-04")
    assert s.override_text == "My custom summary."


@pytest.mark.django_db
def test_revert_to_auto(auth_client, user):
    MonthlyReportSummary.objects.create(
        year_month="2026-04", override_text="X", updated_by=user,
    )
    response = auth_client.post(reverse("reports:revert") + "?month=2026-04")
    assert response.status_code == 302
    assert not MonthlyReportSummary.objects.filter(year_month="2026-04").exists()


@pytest.mark.django_db
def test_completed_section_shows_project(auth_client, user, category):
    p = Project.objects.create(title="DoneProj", category=category, created_by=user)
    p.status = ProjectStatus.COMPLETED
    p.actual_completion_date = dt.date(2026, 4, 10)
    p.save()
    response = auth_client.get(reverse("reports:monthly") + "?month=2026-04")
    assert b"DoneProj" in response.content


@pytest.mark.django_db
def test_override_text_shown_when_present(auth_client, user):
    MonthlyReportSummary.objects.create(
        year_month="2026-04",
        override_text="Definitely a custom summary.",
        updated_by=user,
    )
    response = auth_client.get(reverse("reports:monthly") + "?month=2026-04")
    assert b"Definitely a custom summary" in response.content
```

- [ ] **Step 3: Run and fail**

```bash
uv run pytest apps/reports/tests/test_models.py apps/reports/tests/test_views.py -v
```

- [ ] **Step 4: Model**

Replace `apps/reports/models.py`:

```python
from django.conf import settings
from django.db import models


class MonthlyReportSummary(models.Model):
    """Per-month override of the auto-generated report summary blurb."""
    year_month = models.CharField(max_length=7, unique=True, help_text="e.g. '2026-04'")
    override_text = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-year_month"]

    def __str__(self):
        return f"Override<{self.year_month}>"
```

- [ ] **Step 5: Form**

Replace `apps/reports/forms.py`:

```python
from django import forms

from .models import MonthlyReportSummary


class SummaryOverrideForm(forms.ModelForm):
    class Meta:
        model = MonthlyReportSummary
        fields = ["override_text"]
        widgets = {
            "override_text": forms.Textarea(attrs={
                "class": "input", "rows": 4,
                "placeholder": "Override the auto-generated summary…",
            }),
        }
```

- [ ] **Step 6: Views**

Replace `apps/reports/views.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import SummaryOverrideForm
from .models import MonthlyReportSummary
from .period import (
    format_label, parse_year_month, prev_month, next_month,
    recent_months, year_month_for,
)
from .summary import (
    approvals_in_month, auto_summary_text, completed_in_month,
    in_progress_highlights, monthly_stats,
)


@login_required
def monthly(request):
    year, month = parse_year_month(request.GET.get("month"))
    ym = year_month_for(year, month)

    override = MonthlyReportSummary.objects.filter(year_month=ym).first()
    summary_text = override.override_text if override else auto_summary_text(year, month)
    form = SummaryOverrideForm(initial={"override_text": summary_text})

    return render(request, "reports/monthly.html", {
        "year": year,
        "month": month,
        "ym": ym,
        "label": format_label(year, month),
        "stats": monthly_stats(year, month),
        "completed": completed_in_month(year, month),
        "in_progress": in_progress_highlights(),
        "approvals": approvals_in_month(year, month),
        "summary_text": summary_text,
        "is_override": override is not None,
        "form": form,
        "month_options": recent_months(24),
        "format_label": format_label,
        "year_month_for": year_month_for,
        "prev_ym": year_month_for(*prev_month(year, month)),
        "next_ym": year_month_for(*next_month(year, month)),
    })


@login_required
@require_http_methods(["POST"])
def save_override(request):
    year, month = parse_year_month(request.GET.get("month"))
    ym = year_month_for(year, month)
    text = request.POST.get("override_text", "").strip()
    if not text:
        messages.error(request, "Override cannot be empty. Use 'Revert to auto' instead.")
        return redirect(f"{request.path.rsplit('/', 1)[0]}/?month={ym}")
    obj, _ = MonthlyReportSummary.objects.update_or_create(
        year_month=ym,
        defaults={"override_text": text, "updated_by": request.user},
    )
    messages.success(request, "Summary saved.")
    return redirect(f"/reports/?month={ym}")


@login_required
@require_http_methods(["POST"])
def revert(request):
    year, month = parse_year_month(request.GET.get("month"))
    ym = year_month_for(year, month)
    MonthlyReportSummary.objects.filter(year_month=ym).delete()
    messages.success(request, "Reverted to auto-generated summary.")
    return redirect(f"/reports/?month={ym}")
```

- [ ] **Step 7: URLs**

Replace `apps/reports/urls.py`:

```python
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.monthly, name="monthly"),
    path("save/", views.save_override, name="save_override"),
    path("revert/", views.revert, name="revert"),
]
```

- [ ] **Step 8: Migrate**

```bash
uv run python manage.py makemigrations reports
uv run python manage.py migrate
```

- [ ] **Step 9: Commit (template comes in Task 5)**

The view tests will fail at this step because the template doesn't exist yet. Skip the test step here; we'll run them after Task 5.

```bash
git add apps/reports/
git commit -m "feat(reports): MonthlyReportSummary model + monthly view"
```

---

## Task 5: Monthly report template + serif print styles

**Files:**
- Create: `templates/reports/monthly.html`
- Create: `templates/reports/_stats_strip.html`
- Create: `templates/reports/_summary_block.html`
- Create: `templates/reports/_section_completed.html`
- Create: `templates/reports/_section_in_progress.html`
- Create: `templates/reports/_section_approvals.html`
- Modify: `static/css/input.css` (add `.report-*` classes)

- [ ] **Step 1: Add report-typography classes**

Append to `static/css/input.css`:

```css
@layer components {
  .report-content { @apply font-serif text-base text-gray-900 leading-relaxed; }
  .report-content h2 { @apply font-bold text-lg mt-6 mb-2; }
  .report-content h3 { @apply font-semibold text-base mt-4 mb-1; }
  .report-content ul { @apply list-disc ml-6 my-2; }
  .report-content li { @apply mb-1; }
  .report-content p { @apply my-2; }
}
```

Rebuild Tailwind:
```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css
```

- [ ] **Step 2: Stats strip**

Create `templates/reports/_stats_strip.html`:

```html
{% load humanize %}
<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
  <div class="bg-white rounded-lg shadow p-3"><div class="text-xs uppercase text-gray-500">Completed</div><div class="text-2xl font-semibold">{{ stats.completed }}</div></div>
  <div class="bg-white rounded-lg shadow p-3"><div class="text-xs uppercase text-gray-500">In progress</div><div class="text-2xl font-semibold">{{ stats.in_progress }}</div></div>
  <div class="bg-white rounded-lg shadow p-3"><div class="text-xs uppercase text-gray-500">Delayed</div><div class="text-2xl font-semibold {% if stats.delayed %}text-red-700{% endif %}">{{ stats.delayed }}</div></div>
  <div class="bg-white rounded-lg shadow p-3"><div class="text-xs uppercase text-gray-500">Approvals</div><div class="text-2xl font-semibold">{{ stats.approvals }}</div></div>
  <div class="bg-white rounded-lg shadow p-3"><div class="text-xs uppercase text-gray-500">Spent (capital)</div><div class="text-2xl font-semibold">${{ stats.spent_capital|floatformat:0|intcomma }}</div></div>
</div>
```

- [ ] **Step 3: Summary block**

Create `templates/reports/_summary_block.html`:

```html
<section class="bg-white rounded-lg shadow p-5 mb-6">
  <div class="flex items-center justify-between mb-2">
    <h2 class="text-sm font-semibold text-gray-500 uppercase">Summary</h2>
    {% if is_override %}
      <form method="post" action="{% url 'reports:revert' %}?month={{ ym }}">
        {% csrf_token %}
        <button class="text-xs text-blue-600 hover:underline">Revert to auto</button>
      </form>
    {% endif %}
  </div>
  <form method="post" action="{% url 'reports:save_override' %}?month={{ ym }}">
    {% csrf_token %}
    {{ form.override_text }}
    <div class="flex gap-2 mt-2">
      <button type="submit" class="btn-secondary text-xs">Save override</button>
      <span class="text-xs text-gray-500 self-center">
        {% if is_override %}Showing your edited summary.{% else %}Auto-generated.{% endif %}
      </span>
    </div>
  </form>
</section>
```

- [ ] **Step 4: Completed section**

Create `templates/reports/_section_completed.html`:

```html
{% load humanize %}
<section class="report-content mb-6">
  <h2>Completed This Month</h2>
  {% regroup completed by category as by_category %}
  {% for group in by_category %}
    <h3>{{ group.grouper.name }}</h3>
    <ul>
      {% for p in group.list %}
        <li>
          <strong>{{ p.title }}</strong>
          {% if p.actual_cost %} — ${{ p.actual_cost|floatformat:0|intcomma }}{% if p.budget_amount %} (budget ${{ p.budget_amount|floatformat:0|intcomma }}){% endif %}{% endif %}
          {% if p.vendor_name %}, vendor: {{ p.vendor_name }}{% endif %}
          {% if p.board_approval %} — approved {{ p.board_approval.vote_date }} ({{ p.board_approval.vote_summary }}){% if p.board_approval.minutes_reference %}, {{ p.board_approval.minutes_reference }}{% endif %}{% endif %}
        </li>
      {% endfor %}
    </ul>
  {% empty %}
    <p>No projects completed this month.</p>
  {% endfor %}
</section>
```

- [ ] **Step 5: In-progress section**

Create `templates/reports/_section_in_progress.html`:

```html
<section class="report-content mb-6">
  <h2>In Progress Highlights</h2>
  {% if in_progress %}
  <ul>
    {% for p in in_progress %}
      <li>
        <strong>{{ p.title }}</strong> — {{ p.get_status_display }}
        {% if p.projected_completion_date %} (target {{ p.projected_completion_date }}){% endif %}
        {% if p.status == 'delayed' and p.delay_reason %}<br><em>Delayed:</em> {{ p.delay_reason }}{% endif %}
      </li>
    {% endfor %}
  </ul>
  {% else %}<p>No projects currently in progress.</p>{% endif %}
</section>
```

- [ ] **Step 6: Approvals section**

Create `templates/reports/_section_approvals.html`:

```html
<section class="report-content mb-6">
  <h2>Board Approvals This Month</h2>
  {% if approvals %}
  <ul>
    {% for a in approvals %}
      <li>
        <strong>{{ a.project.title }}</strong> — voted {{ a.vote_date }}, {{ a.vote_summary }} (for-against-abstain)<br>
        Motion: {{ a.motion_text }}
        {% if a.minutes_reference %}<br><em>{{ a.minutes_reference }}</em>{% endif %}
      </li>
    {% endfor %}
  </ul>
  {% else %}<p>No board approvals this month.</p>{% endif %}
</section>
```

- [ ] **Step 7: Main monthly template**

Create `templates/reports/monthly.html`:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Monthly report — {{ label }}{% endblock %}
{% block extra_head %}<script src="{% static 'js/copy-report.js' %}" defer></script>{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Monthly report — {{ label }}</h1>
  <div class="flex gap-2 items-center">
    <form method="get" class="flex items-center gap-2">
      <select name="month" class="input" onchange="this.form.submit()">
        {% for y, m in month_options %}
          <option value="{{ year_month_for|default:'' }}{{ y }}-{{ m|stringformat:'02d' }}"
            {% if y == year and m == month %}selected{% endif %}>{{ format_label|default:'' }}{{ y }}-{{ m|stringformat:'02d' }} · {{ y }} {{ m }}</option>
        {% endfor %}
      </select>
    </form>
    <a href="?month={{ prev_ym }}" class="btn-secondary text-xs">‹ Prev</a>
    <a href="?month={{ next_ym }}" class="btn-secondary text-xs">Next ›</a>
    <button id="copy-report-btn" class="btn-primary text-xs"
      data-target="report-body">Copy report text</button>
  </div>
</div>

{% include "reports/_stats_strip.html" %}

{% include "reports/_summary_block.html" %}

<div id="report-body" class="bg-white rounded-lg shadow p-6">
  <div class="report-content">
    <h2 style="font-family: Georgia, serif; font-weight: bold; font-size: 18pt;">HOA Project Report — {{ label }}</h2>
    <p>{{ summary_text|linebreaksbr }}</p>
  </div>
  {% include "reports/_section_completed.html" %}
  {% include "reports/_section_in_progress.html" %}
  {% include "reports/_section_approvals.html" %}
</div>
{% endblock %}
```

The month dropdown above is awkward because Django templates can't call multi-arg helpers cleanly. Replace it with a server-side rendered list. Refactor: in `views.py`, build the option list as `[{ "ym": "2026-04", "label": "April 2026" }, ...]` and pass it instead. Update the template:

In `views.py monthly()`, replace the `month_options` line with:

```python
"month_options": [
    {"ym": year_month_for(y, m), "label": format_label(y, m)}
    for y, m in recent_months(24)
],
```

And drop `format_label` / `year_month_for` from the context (no longer needed in template).

In the template, replace the `<select>` with:

```html
<select name="month" class="input" onchange="this.form.submit()">
  {% for opt in month_options %}
    <option value="{{ opt.ym }}" {% if opt.ym == ym %}selected{% endif %}>{{ opt.label }}</option>
  {% endfor %}
</select>
```

- [ ] **Step 8: Run tests**

```bash
uv run pytest apps/reports -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add apps/reports/views.py templates/reports/ static/css/input.css static/css/output.css
git commit -m "feat(reports): monthly report layout with stats, summary, sections"
```

---

## Task 6: Copy-to-clipboard with formatted HTML

**Files:**
- Create: `static/js/copy-report.js`

- [ ] **Step 1: Write the script**

Create `static/js/copy-report.js`:

```javascript
(function () {
  const btn = document.getElementById("copy-report-btn");
  if (!btn) return;

  btn.addEventListener("click", async function () {
    const targetId = btn.getAttribute("data-target");
    const node = document.getElementById(targetId);
    if (!node) return;

    // Wrap in a div so the clipboard preserves outer styling
    const wrapper = document.createElement("div");
    wrapper.style.fontFamily = "Georgia, serif";
    wrapper.style.fontSize = "11pt";
    wrapper.style.lineHeight = "1.5";
    wrapper.innerHTML = node.innerHTML;

    const html = wrapper.outerHTML;
    const text = node.innerText;

    try {
      if (navigator.clipboard && window.ClipboardItem) {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([text], { type: "text/plain" }),
          }),
        ]);
      } else {
        await navigator.clipboard.writeText(text);
      }
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = "Copy report text"; }, 2000);
    } catch (err) {
      console.error("Copy failed:", err);
      btn.textContent = "Copy failed — try again";
      setTimeout(() => { btn.textContent = "Copy report text"; }, 2500);
    }
  });
})();
```

- [ ] **Step 2: Manual test**

Rebuild Tailwind, deploy locally, navigate to `/reports/`. Click "Copy report text". Paste into Word or Google Docs — verify headings are bold, lists render as bullets, paragraphs separate.

There's no automated test for clipboard JS — note this in the smoke-test runbook (Task 11).

- [ ] **Step 3: Commit**

```bash
git add static/js/copy-report.js
git commit -m "feat(reports): copy-to-clipboard with formatted HTML payload"
```

---

## Task 7: Error pages and empty-state polish

**Files:**
- Create: `templates/404.html`
- Create: `templates/500.html`

- [ ] **Step 1: Write 404**

Create `templates/404.html`:

```html
{% extends "base.html" %}
{% block title %}Page not found{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto text-center py-12">
  <h1 class="text-3xl font-semibold text-gray-900 mb-2">Page not found</h1>
  <p class="text-gray-600 mb-6">The link may be wrong, or the project may have been deleted.</p>
  <a href="{% url 'home' %}" class="btn-primary">Back to dashboard</a>
</div>
{% endblock %}
{% block unauth_content %}
<div class="text-center">
  <h1 class="text-3xl font-semibold text-gray-900 mb-2">Page not found</h1>
  <a href="{% url 'accounts:login' %}" class="text-blue-600 hover:underline">Sign in</a>
</div>
{% endblock %}
```

- [ ] **Step 2: Write 500**

Create `templates/500.html`:

```html
{% extends "base.html" %}
{% block title %}Server error{% endblock %}
{% block content %}
<div class="max-w-lg mx-auto text-center py-12">
  <h1 class="text-3xl font-semibold text-gray-900 mb-2">Something went wrong</h1>
  <p class="text-gray-600 mb-6">We're looking into it. Try again in a moment.</p>
  <a href="{% url 'home' %}" class="btn-primary">Back to dashboard</a>
</div>
{% endblock %}
{% block unauth_content %}
<div class="text-center">
  <h1 class="text-3xl font-semibold text-gray-900 mb-2">Something went wrong</h1>
</div>
{% endblock %}
```

- [ ] **Step 3: Verify Django picks them up**

In production (DEBUG=False), Django uses these automatically. Verify locally by setting `DEBUG=False` and `ALLOWED_HOSTS=*` in env, then visit a non-existent URL:

```bash
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=* DJANGO_SECRET_KEY=test \
  uv run python manage.py runserver
```

Visit `http://127.0.0.1:8000/no-such-page/`. Expected: the 404 template renders.

- [ ] **Step 4: Commit**

```bash
git add templates/404.html templates/500.html
git commit -m "feat: friendly 404 / 500 error pages"
```

---

## Task 8: litestream for continuous SQLite backup

**Files:**
- Create: `litestream.yml`
- Modify: `Dockerfile`
- Modify: `fly.toml` (env vars for litestream)

- [ ] **Step 1: Write litestream.yml**

Create `litestream.yml`:

```yaml
dbs:
  - path: /data/db.sqlite3
    replicas:
      - type: s3
        endpoint: ${LITESTREAM_R2_ENDPOINT}
        bucket: ${LITESTREAM_R2_BUCKET}
        path: db.sqlite3
        region: auto
        access-key-id: ${LITESTREAM_R2_ACCESS_KEY_ID}
        secret-access-key: ${LITESTREAM_R2_SECRET_ACCESS_KEY}
        retention: 168h         # keep 7 days of WAL segments
        sync-interval: 10s
```

- [ ] **Step 2: Modify Dockerfile to include litestream**

In `Dockerfile`'s runtime stage, before the `EXPOSE`/`CMD`, add:

```dockerfile
# Install litestream
RUN curl -sLo /tmp/litestream.tar.gz \
    https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.tar.gz \
    && tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin/ \
    && rm /tmp/litestream.tar.gz \
    && chmod +x /usr/local/bin/litestream

COPY litestream.yml /etc/litestream.yml
```

Replace the existing `CMD` with a small entrypoint script that:
1. Restores from R2 if `/data/db.sqlite3` doesn't exist
2. Runs `migrate`
3. Starts litestream + gunicorn under one process via `litestream replicate -exec`

Create `entrypoint.sh` at repo root:

```bash
#!/bin/sh
set -e

# Only run for the app process group
if [ "$FLY_PROCESS_GROUP" = "app" ] || [ -z "$FLY_PROCESS_GROUP" ]; then
  if [ ! -f /data/db.sqlite3 ]; then
    echo "Restoring database from R2 (if a replica exists)…"
    litestream restore -if-replica-exists -config /etc/litestream.yml /data/db.sqlite3 || true
  fi

  uv run python manage.py migrate --noinput

  exec litestream replicate -config /etc/litestream.yml \
    -exec "uv run gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"
fi

# Cron process group runs the management command and exits
if [ "$FLY_PROCESS_GROUP" = "cron" ]; then
  exec uv run python manage.py generate_recurring_instances
fi

echo "Unknown FLY_PROCESS_GROUP: $FLY_PROCESS_GROUP"
exit 1
```

Add to Dockerfile (before `EXPOSE`):

```dockerfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
```

Replace `CMD` with:
```dockerfile
CMD ["/entrypoint.sh"]
```

- [ ] **Step 3: Update fly.toml process commands**

Replace the `[processes]` block in `fly.toml` to use the entrypoint:

```toml
[processes]
  app = "/entrypoint.sh"
  cron = "/entrypoint.sh"
```

(The script branches on `FLY_PROCESS_GROUP`.)

- [ ] **Step 4: Set litestream secrets**

Create a separate R2 bucket for backups (e.g., `hoa-backups`). Then:

```bash
fly secrets set \
  LITESTREAM_R2_ENDPOINT="https://<account>.r2.cloudflarestorage.com" \
  LITESTREAM_R2_BUCKET=hoa-backups \
  LITESTREAM_R2_ACCESS_KEY_ID=... \
  LITESTREAM_R2_SECRET_ACCESS_KEY=... \
  --app hoa-task-manager-staging
```

- [ ] **Step 5: Deploy and verify**

```bash
fly deploy --app hoa-task-manager-staging
fly logs --app hoa-task-manager-staging
```

Expected log lines: `litestream replicate ...`, `gunicorn ...`, periodic `replicating ...` messages.

Verify the bucket has objects:
```bash
# Use Cloudflare dashboard, or aws CLI configured for R2
aws s3 --endpoint-url https://<account>.r2.cloudflarestorage.com ls s3://hoa-backups/db.sqlite3/
```

- [ ] **Step 6: Test restore**

(Don't actually destroy staging — test on a fresh app, or skip and document the restore command in the runbook.)

```bash
# On a fresh machine with /data empty:
litestream restore -config /etc/litestream.yml /data/db.sqlite3
```

- [ ] **Step 7: Commit**

```bash
git add litestream.yml Dockerfile entrypoint.sh fly.toml
git commit -m "ops: litestream continuous SQLite backup to R2"
```

---

## Task 9: Production Fly app + tagged-release deploy

**Files:**
- Create: `fly.production.toml`
- Create: `.github/workflows/deploy-production.yml`
- Modify: `.github/workflows/deploy-staging.yml` (no functional change — just verify it stays main-only)

- [ ] **Step 1: Create the production Fly app**

```bash
fly apps create hoa-task-manager
fly volumes create data --region iad --size 1 --app hoa-task-manager
```

- [ ] **Step 2: Write fly.production.toml**

Create `fly.production.toml`. Identical to `fly.toml` but with prod values:

```toml
app = "hoa-task-manager"
primary_region = "iad"

[build]

[env]
  DJANGO_DEBUG = "False"
  DJANGO_ALLOWED_HOSTS = "hoa-task-manager.fly.dev"
  DJANGO_CSRF_TRUSTED_ORIGINS = "https://hoa-task-manager.fly.dev"
  DJANGO_DB_PATH = "/data/db.sqlite3"

[mounts]
  source = "data"
  destination = "/data"

[processes]
  app = "/entrypoint.sh"
  cron = "/entrypoint.sh"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
  processes = ["app"]

[[http_service]]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/accounts/login/"
```

Note: prod has `min_machines_running = 1` (no cold starts), staging stays at 0.

- [ ] **Step 3: Set production secrets**

```bash
fly secrets set \
  DJANGO_SECRET_KEY="$(uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
  R2_ENDPOINT_URL="..." \
  R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." \
  R2_BUCKET="hoa-attachments-prod" \
  LITESTREAM_R2_ENDPOINT="..." \
  LITESTREAM_R2_BUCKET="hoa-backups-prod" \
  LITESTREAM_R2_ACCESS_KEY_ID="..." \
  LITESTREAM_R2_SECRET_ACCESS_KEY="..." \
  --app hoa-task-manager
```

(Use a separate R2 bucket per environment for both attachments and backups.)

- [ ] **Step 4: First production deploy (manual)**

```bash
fly deploy --config fly.production.toml --app hoa-task-manager
fly ssh console --app hoa-task-manager -C "uv run python manage.py createsuperuser"
```

Sign in at `https://hoa-task-manager.fly.dev`. Smoke-test (Task 11).

- [ ] **Step 5: Schedule production cron**

```bash
fly machine run . --schedule daily --process-group cron --app hoa-task-manager
```

- [ ] **Step 6: Production deploy token**

```bash
fly tokens create deploy --app hoa-task-manager
```

In GitHub Settings → Secrets, add `FLY_API_TOKEN_PRODUCTION` with this value.

- [ ] **Step 7: Production deploy workflow**

Create `.github/workflows/deploy-production.yml`:

```yaml
name: Deploy to production

on:
  push:
    tags: ["v*"]

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    concurrency:
      group: deploy-production
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - name: Deploy
        run: flyctl deploy --config fly.production.toml --app hoa-task-manager --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN_PRODUCTION }}
```

- [ ] **Step 8: Test the tag-release flow**

```bash
git tag v0.1.0
git push origin v0.1.0
```

Watch GitHub Actions. The production workflow should run; staging should not.

- [ ] **Step 9: Commit (tag command itself doesn't go in a commit)**

```bash
git add fly.production.toml .github/workflows/deploy-production.yml
git commit -m "ops: production Fly app with tag-based release deploy"
```

---

## Task 10: Operational runbooks

**Files:**
- Create: `docs/runbooks/deploy.md`
- Create: `docs/runbooks/restore-from-backup.md`
- Create: `docs/runbooks/reset-password.md`
- Create: `docs/runbooks/pre-deploy-smoke-test.md`

These are short, copy-paste docs the user will follow when doing operational work. Each one is one task step — copy the contents below verbatim.

- [ ] **Step 1: deploy.md**

Create `docs/runbooks/deploy.md`:

```markdown
# Deploying

## Staging
Auto-deploys on every push to `main` once CI passes.

Manual:
```
fly deploy --app hoa-task-manager-staging
```

## Production
Tag-driven. To release:

```
git tag v0.1.0
git push origin v0.1.0
```

The `deploy-production.yml` workflow handles the rest.

To roll back, deploy a previous image:

```
fly releases --app hoa-task-manager
fly deploy --image registry.fly.io/hoa-task-manager:deployment-XXXX --app hoa-task-manager
```
```

- [ ] **Step 2: restore-from-backup.md**

Create `docs/runbooks/restore-from-backup.md`:

```markdown
# Restoring from a litestream backup

## Verify backups exist
List the bucket:
```
aws s3 --endpoint-url $LITESTREAM_R2_ENDPOINT ls s3://$LITESTREAM_R2_BUCKET/db.sqlite3/
```

## Restore in place (last-resort)
SSH into the running machine:
```
fly ssh console --app hoa-task-manager
```

Inside:
```
# Stop gunicorn (this kills the machine; fly will restart it)
pkill -TERM gunicorn

# Move existing DB aside
mv /data/db.sqlite3 /data/db.sqlite3.bak

# Restore
litestream restore -config /etc/litestream.yml /data/db.sqlite3
```

The machine restarts and the entrypoint runs `migrate`.

## Restore to a specific point in time

```
litestream restore -timestamp 2026-04-15T18:00:00Z \
  -config /etc/litestream.yml /data/db.sqlite3
```
```

- [ ] **Step 3: reset-password.md**

Create `docs/runbooks/reset-password.md`:

```markdown
# Resetting a user's password

There's no email-based reset in v1. Reset via Django:

```
fly ssh console --app hoa-task-manager -C \
  "uv run python manage.py changepassword <username>"
```

Or directly in the Django admin at `/admin/auth/user/`.
```

- [ ] **Step 4: pre-deploy-smoke-test.md**

Create `docs/runbooks/pre-deploy-smoke-test.md`:

```markdown
# Pre-deploy smoke test

Before tagging a release, run this on staging:

1. Log out, then log in as your normal user.
2. Dashboard renders without errors.
3. Click into a project; click "edit" on status — change to In Progress, save. Verify it persists.
4. Add a note with **bold** markdown. Verify it renders bold.
5. Upload a small PDF. Click the link and verify the download works.
6. Delete the test attachment. Verify it disappears.
7. Add a RACI assignment. Remove it.
8. Visit `/recurring/`; pause a template; resume it.
9. Visit `/reports/`; switch months; click "Copy report text"; paste into a Word doc and verify formatting.
10. Visit `/admin/`; verify you can list projects and roster people.
11. Log out.

All green → safe to tag a release.

## CI catches the basics — this is for things tests can't catch
- Visual regressions
- Browser clipboard behavior
- R2 connectivity from the deployed environment
- Email-as-username login flow end-to-end
```

- [ ] **Step 5: Commit**

```bash
git add docs/runbooks/
git commit -m "docs: operational runbooks for deploy, restore, reset, smoke test"
```

---

## Task 11: End-to-end smoke pass + tag v0.1.0

- [ ] **Step 1: Run the full test suite locally**

```bash
uv run pytest -v
```

Expected: every test passes. No skipped, no warnings about deprecated Django APIs.

- [ ] **Step 2: Run the staging smoke checklist**

Follow `docs/runbooks/pre-deploy-smoke-test.md` against `https://hoa-task-manager-staging.fly.dev`. Note any issues; fix and re-deploy before tagging.

- [ ] **Step 3: Tag and push**

```bash
git tag v0.1.0
git push origin v0.1.0
```

- [ ] **Step 4: Watch the production deploy**

GitHub Actions → `Deploy to production` → green. Then visit `https://hoa-task-manager.fly.dev` and run the smoke checklist again on prod. Create your first user via SSH if you haven't yet:

```bash
fly ssh console --app hoa-task-manager -C "uv run python manage.py createsuperuser"
```

- [ ] **Step 5: Verify litestream is replicating in prod**

```bash
fly logs --app hoa-task-manager | grep litestream
```

Expected: periodic `replicating` log lines. List the prod backup bucket to confirm objects exist.

- [ ] **Step 6: Done.**

The app is in production with continuous backups, monthly board reports, and a deploy pipeline. Document the prod URL and the first user's credentials in your password manager. Don't commit them.

---

## Self-Review

**Spec coverage (sections 4 partial, 5 partial, 7 partial, 8 partial, 10 full, 11 N/A):**
- MonthlyReportSummary model (year_month unique, override_text, updated_at, updated_by) ✓
- Auto-summary blurb when no override ✓
- Override edit form + revert button ✓
- Stats strip (Completed / In Progress / Delayed / Approvals / Spent capital) ✓
- Sections: Completed (grouped by category, with cost/budget/vendor/approval), In Progress highlights with delay reason, Board Approvals with motion + tally + minutes ref ✓
- Copy report text button preserves serif formatting via `text/html` clipboard write ✓
- Time zones: model unchanged from spec — UTC storage, display via user's profile.timezone (rendering uses `{{ ... |date:'Y-m-d' }}` which is timezone-naive on `DateField` and timezone-aware on `DateTimeField`; activity timestamps will need {% load tz %}{% timezone user.profile.timezone %} blocks if drift becomes noticeable — flagged as a fast-follow polish item).
- HTTPS via Fly ✓ (Plans 1+3)
- litestream continuous backup ✓
- Free-tier sizing (`shared-cpu-1x`, 256MB) ✓
- 404/500 templates ✓
- Empty states (already in plans 1 and 2; reports has its own "No projects completed this month" / "No board approvals this month" copy in section partials) ✓

**Placeholder scan:** None. Each command, secret name, and code block is concrete.

**Type consistency:**
- `MonthlyReportSummary.year_month` is the canonical "YYYY-MM" string format. `period.year_month_for(year, month)` produces it. URLs accept `?month=YYYY-MM`. Templates use `{{ ym }}`.
- `auto_summary_text(year, month)`, `monthly_stats(year, month)`, `completed_in_month(year, month)`, `approvals_in_month(year, month)`, `in_progress_highlights()` — all consistent integer-pair signatures (with one exception: in_progress is global state, not month-scoped, matching spec).
- Process group names `app` and `cron` consistent across `fly.toml`, `fly.production.toml`, and `entrypoint.sh`.
- Secret names `LITESTREAM_R2_*` and `R2_*` (for attachments) are distinct — no accidental collision.

**Known polish items handed off as fast-follows (not in scope):**
- Per-user timezone display for ActivityLog timestamps. Currently UTC.
- Email password reset (per spec, requires Resend/SendGrid; deferred).
- PDF export of monthly report (spec § 11).
- Custom domain via Cloudflare Registrar (spec § 10).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-hoa-reports-prod.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — run tasks in this session with checkpoints.

Which approach?
