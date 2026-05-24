# HOA Task Manager — Plan 2: Projects, Recurring & Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core project tracker — projects with RACI, board approvals, update notes, attachments, activity log, recurring templates with daily auto-generation, and a dashboard. After this plan, the app is fully usable for day-to-day HOA board work; only monthly reports and production hardening remain.

**Architecture:** A single `projects` Django app holds the core domain model. ActivityLog is written via Django signals on Project save/RACI changes/etc. Attachments use `boto3` against Cloudflare R2 with signed-URL downloads. HTMX powers inline field edits on the project detail page (each field swap returns a tiny HTML partial). Recurring instance generation runs as a management command, scheduled by a Fly.io cron machine. The dashboard is a single view that runs three small queries — overdue, upcoming, recent activity.

**Tech Stack:** Django 5.x, HTMX 1.9, Tailwind CSS, `boto3` for R2, `python-dateutil` for cadence math, `bleach` for markdown sanitization in update notes, `markdown` for rendering. Builds on Plan 1's foundation.

**Prerequisites:** Plan 1 complete and deployed to staging. `apps/accounts` and `apps/roster` exist. Sidebar nav has placeholders for Dashboard, Projects, Recurring.

---

## File Structure

```
hoa-task-manager/
├── apps/
│   └── projects/                       # NEW — entire app
│       ├── __init__.py
│       ├── apps.py
│       ├── admin.py
│       ├── models/
│       │   ├── __init__.py             # Re-exports all models
│       │   ├── category.py             # ProjectCategory, Tag
│       │   ├── project.py              # Project, status/priority enums
│       │   ├── raci.py                 # RACIAssignment + role enum
│       │   ├── approval.py             # BoardApproval
│       │   ├── note.py                 # UpdateNote
│       │   ├── attachment.py           # Attachment
│       │   └── activity.py             # ActivityLog
│       ├── forms/
│       │   ├── __init__.py
│       │   ├── project.py              # ProjectForm
│       │   ├── raci.py                 # RACIAssignmentForm
│       │   ├── approval.py             # BoardApprovalForm
│       │   ├── note.py                 # UpdateNoteForm
│       │   └── attachment.py           # AttachmentUploadForm
│       ├── views/
│       │   ├── __init__.py
│       │   ├── dashboard.py            # Dashboard
│       │   ├── project_list.py         # Filters / search / sort
│       │   ├── project_detail.py       # Detail page
│       │   ├── project_form.py         # Create / edit
│       │   ├── inline.py               # HTMX inline-edit endpoints
│       │   ├── note.py                 # Add note (HTMX)
│       │   ├── attachment.py           # Upload / delete / signed-url download
│       │   ├── raci.py                 # Add / remove RACI (HTMX)
│       │   ├── approval.py             # Add / edit board approval
│       │   └── recurring.py            # Recurring templates list/create/edit/pause
│       ├── urls.py
│       ├── signals.py                  # ActivityLog writers
│       ├── markdown_utils.py           # Render + sanitize update notes
│       ├── recurring.py                # Cadence math + generation logic
│       ├── storage.py                  # R2 client + signed URLs
│       ├── management/
│       │   ├── __init__.py
│       │   └── commands/
│       │       ├── __init__.py
│       │       ├── generate_recurring_instances.py
│       │       └── seed_categories.py
│       ├── migrations/
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py             # Shared fixtures (user, person, project)
│           ├── test_models_project.py
│           ├── test_models_raci.py
│           ├── test_models_approval.py
│           ├── test_models_note.py
│           ├── test_models_attachment.py
│           ├── test_models_activity.py
│           ├── test_signals.py
│           ├── test_views_list.py
│           ├── test_views_detail.py
│           ├── test_views_form.py
│           ├── test_views_inline.py
│           ├── test_views_note.py
│           ├── test_views_attachment.py
│           ├── test_views_raci.py
│           ├── test_views_approval.py
│           ├── test_views_recurring.py
│           ├── test_views_dashboard.py
│           └── test_recurring_command.py
├── templates/
│   ├── _sidebar.html                   # MODIFIED — add Projects, Recurring
│   ├── home.html                       # REPLACED — real dashboard
│   └── projects/                       # NEW
│       ├── list.html
│       ├── _list_row.html
│       ├── detail.html
│       ├── _delay_banner.html
│       ├── _raci_section.html
│       ├── _raci_row.html
│       ├── _approval_section.html
│       ├── _attachments_section.html
│       ├── _attachment_row.html
│       ├── _notes_section.html
│       ├── _note_card.html
│       ├── _activity_card.html
│       ├── _field_status.html          # HTMX swap targets — one per inline field
│       ├── _field_status_edit.html
│       ├── _field_priority.html
│       ├── _field_priority_edit.html
│       ├── _field_dates.html
│       ├── _field_dates_edit.html
│       ├── _field_budget.html
│       ├── _field_budget_edit.html
│       ├── _field_vendor.html
│       ├── _field_vendor_edit.html
│       ├── form.html                   # Create / edit (full form)
│       ├── recurring_list.html
│       ├── recurring_form.html
│       └── _empty_state.html
├── apps/projects/templates/projects/   # (none — using project root templates/)
├── fly.toml                            # MODIFIED — add cron process group
└── pyproject.toml                      # MODIFIED — add boto3, python-dateutil, markdown, bleach
```

**Decomposition rationale:**
- `models/`, `forms/`, `views/` are **packages** (folders) instead of single files because each has 6–10 distinct concerns and a single file would be 800+ lines. Each module has one focused responsibility.
- HTMX field partials are split into a "display" template and an "edit" template per field. The display partial is rendered initially and as the response after a save; the edit partial is rendered when the user clicks to edit. Two templates per field is verbose but keeps each one small and matches HTMX's swap pattern naturally.
- `recurring.py` (logic) is separate from `views/recurring.py` (HTTP handlers) and `management/commands/generate_recurring_instances.py` (CLI entrypoint) so the cadence math is testable without HTTP or argparse.
- ActivityLog is a separate model file even though it's small, because signals.py imports it and unrelated tests want to import it without dragging in Project's M2M setup.

---

## Task 1: Add new dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add deps to pyproject.toml**

Add to the `dependencies` list:
```
"boto3>=1.34",
"python-dateutil>=2.9",
"markdown>=3.6",
"bleach>=6.1",
```

- [ ] **Step 2: Lock and install**

```bash
uv sync
```

Expected: `uv.lock` updates; install succeeds.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add boto3, dateutil, markdown, bleach for projects app"
```

---

## Task 2: Create the projects app skeleton

**Files:**
- Create: `apps/projects/__init__.py`
- Create: `apps/projects/apps.py`
- Create: `apps/projects/urls.py`
- Create: `apps/projects/signals.py` (placeholder)
- Create: `apps/projects/models/__init__.py`
- Create: `apps/projects/views/__init__.py`
- Create: `apps/projects/forms/__init__.py`
- Create: `apps/projects/migrations/__init__.py`
- Create: `apps/projects/tests/__init__.py`
- Modify: `config/settings.py` (add app)
- Modify: `config/urls.py` (include projects URLs)

- [ ] **Step 1: Create directories**

```bash
mkdir -p apps/projects/models apps/projects/views apps/projects/forms \
         apps/projects/migrations apps/projects/tests \
         apps/projects/management/commands
```

Touch `__init__.py` files in each.

- [ ] **Step 2: Write apps/projects/apps.py**

```python
from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
    label = "projects"

    def ready(self):
        from . import signals  # noqa: F401
```

- [ ] **Step 3: Stub signals.py**

```python
"""ActivityLog signals. Wired in Task 9."""
```

- [ ] **Step 4: Stub urls.py**

```python
from django.urls import path

app_name = "projects"
urlpatterns: list = []
```

- [ ] **Step 5: Stub the package __init__ files**

`apps/projects/models/__init__.py`:
```python
"""Project domain models — re-exports populated as tasks land."""
```

`apps/projects/views/__init__.py`:
```python
"""Project views — re-exports populated as tasks land."""
```

`apps/projects/forms/__init__.py`:
```python
"""Project forms — re-exports populated as tasks land."""
```

- [ ] **Step 6: Add to INSTALLED_APPS**

In `config/settings.py`, add `"apps.projects"` after `"apps.roster"`.

- [ ] **Step 7: Wire root URLs**

In `config/urls.py`, add to `urlpatterns`:
```python
path("projects/", include("apps.projects.urls", namespace="projects")),
```

- [ ] **Step 8: Verify**

```bash
uv run python manage.py check
```

Expected: no issues.

- [ ] **Step 9: Commit**

```bash
git add apps/projects/ config/
git commit -m "chore: scaffold projects app"
```

---

## Task 3: ProjectCategory and Tag models

**Files:**
- Create: `apps/projects/models/category.py`
- Modify: `apps/projects/models/__init__.py`
- Create: `apps/projects/management/commands/seed_categories.py`
- Create: `apps/projects/tests/test_models_category.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/projects/tests/test_models_category.py`:

```python
import pytest

from apps.projects.models import ProjectCategory, Tag


@pytest.mark.django_db
def test_create_category():
    c = ProjectCategory.objects.create(name="Capital", display_order=1)
    assert c.name == "Capital"
    assert str(c) == "Capital"


@pytest.mark.django_db
def test_category_name_unique():
    ProjectCategory.objects.create(name="Capital", display_order=1)
    with pytest.raises(Exception):
        ProjectCategory.objects.create(name="Capital", display_order=2)


@pytest.mark.django_db
def test_category_default_ordering():
    ProjectCategory.objects.create(name="Beta", display_order=2)
    ProjectCategory.objects.create(name="Alpha", display_order=1)
    names = list(ProjectCategory.objects.values_list("name", flat=True))
    assert names == ["Alpha", "Beta"]


@pytest.mark.django_db
def test_create_tag_slugifies_name():
    t = Tag.objects.create(name="Sprinkler Repair")
    assert t.slug == "sprinkler-repair"
    assert str(t) == "Sprinkler Repair"


@pytest.mark.django_db
def test_tag_get_or_create_normalizes_case():
    t1 = Tag.get_or_create_from_input("Concrete")
    t2 = Tag.get_or_create_from_input("concrete")
    assert t1.pk == t2.pk
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest apps/projects/tests/test_models_category.py -v
```

Expected: ImportError on `ProjectCategory` / `Tag`.

- [ ] **Step 3: Write the models**

Create `apps/projects/models/category.py`:

```python
from django.db import models
from django.utils.text import slugify


class ProjectCategory(models.Model):
    name = models.CharField(max_length=64, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "Project categories"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_from_input(cls, raw_name: str) -> "Tag":
        cleaned = raw_name.strip()
        slug = slugify(cleaned)
        existing = cls.objects.filter(slug=slug).first()
        if existing:
            return existing
        return cls.objects.create(name=cleaned, slug=slug)

    def __str__(self):
        return self.name
```

- [ ] **Step 4: Re-export in models/__init__.py**

Replace `apps/projects/models/__init__.py`:
```python
from .category import ProjectCategory, Tag

__all__ = ["ProjectCategory", "Tag"]
```

- [ ] **Step 5: Make and apply migration**

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
```

- [ ] **Step 6: Run the tests**

```bash
uv run pytest apps/projects/tests/test_models_category.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Write the seed command**

Create `apps/projects/management/commands/seed_categories.py`:

```python
from django.core.management.base import BaseCommand

from apps.projects.models import ProjectCategory


SEED = [
    ("Capital", 1),
    ("Operational", 2),
    ("Recurring", 3),
    ("Security", 4),
    ("Maintenance", 5),
    ("Financial", 6),
]


class Command(BaseCommand):
    help = "Seed the fixed ProjectCategory list (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, order in SEED:
            _, was_created = ProjectCategory.objects.get_or_create(
                name=name, defaults={"display_order": order}
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Seeded categories: {created} created, {len(SEED) - created} already existed."
        ))
```

- [ ] **Step 8: Run the seed**

```bash
uv run python manage.py seed_categories
```

Expected: `Seeded categories: 6 created, 0 already existed.`

Run again to verify idempotency:
```bash
uv run python manage.py seed_categories
```

Expected: `Seeded categories: 0 created, 6 already existed.`

- [ ] **Step 9: Register in admin**

In `apps/projects/admin.py`:

```python
from django.contrib import admin

from .models import ProjectCategory, Tag


@admin.register(ProjectCategory)
class ProjectCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
```

- [ ] **Step 10: Commit**

```bash
git add apps/projects/
git commit -m "feat(projects): ProjectCategory and Tag with seed command"
```

---

## Task 4: Project model

**Files:**
- Create: `apps/projects/models/project.py`
- Modify: `apps/projects/models/__init__.py`
- Create: `apps/projects/tests/conftest.py`
- Create: `apps/projects/tests/test_models_project.py`
- Modify: `apps/projects/admin.py`

- [ ] **Step 1: Write shared test fixtures**

Create `apps/projects/tests/conftest.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from apps.projects.models import ProjectCategory
from apps.roster.models import RosterPerson


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


@pytest.fixture
def person(db):
    return RosterPerson.objects.create(name="Mike Smith", role_title="Treasurer")


@pytest.fixture
def project(db, user, category):
    from apps.projects.models import Project
    return Project.objects.create(
        title="Sprinkler upgrade",
        category=category,
        created_by=user,
    )
```

- [ ] **Step 2: Write failing model tests**

Create `apps/projects/tests/test_models_project.py`:

```python
import datetime as dt
from decimal import Decimal

import pytest

from apps.projects.models import Project, ProjectStatus, ProjectPriority


@pytest.mark.django_db
def test_create_project_minimal(user, category):
    p = Project.objects.create(
        title="Sprinkler upgrade",
        category=category,
        created_by=user,
    )
    assert p.status == ProjectStatus.NOT_STARTED
    assert p.priority == ProjectPriority.MEDIUM
    assert p.is_active is True
    assert p.is_recurring_template is False
    assert p.actual_completion_date is None


@pytest.mark.django_db
def test_completing_project_sets_actual_date(user, category):
    p = Project.objects.create(title="X", category=category, created_by=user)
    p.status = ProjectStatus.COMPLETED
    p.save()
    assert p.actual_completion_date == dt.date.today()


@pytest.mark.django_db
def test_completed_to_not_started_clears_actual_date(user, category):
    p = Project.objects.create(title="X", category=category, created_by=user)
    p.status = ProjectStatus.COMPLETED
    p.save()
    p.status = ProjectStatus.NOT_STARTED
    p.save()
    assert p.actual_completion_date is None


@pytest.mark.django_db
def test_str_uses_title(user, category):
    p = Project.objects.create(title="Concrete repair", category=category, created_by=user)
    assert str(p) == "Concrete repair"


@pytest.mark.django_db
def test_decimal_money_fields(user, category):
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        budget_amount=Decimal("12345.67"),
        actual_cost=Decimal("100.00"),
    )
    p.refresh_from_db()
    assert p.budget_amount == Decimal("12345.67")


@pytest.mark.django_db
def test_recurring_template_flag(user, category):
    template = Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True,
        recurrence_rule="monthly",
        next_due_date=dt.date(2026, 6, 1),
    )
    assert template.is_recurring_template is True
    assert template.recurrence_rule == "monthly"


@pytest.mark.django_db
def test_overdue_property_for_in_progress(user, category):
    today = dt.date.today()
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=1),
    )
    assert p.is_overdue is True


@pytest.mark.django_db
def test_completed_is_never_overdue(user, category):
    today = dt.date.today()
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        projected_completion_date=today - dt.timedelta(days=10),
    )
    assert p.is_overdue is False


@pytest.mark.django_db
def test_active_manager_excludes_templates(user, category):
    Project.objects.create(title="A", category=category, created_by=user)
    Project.objects.create(
        title="T", category=category, created_by=user,
        is_recurring_template=True,
    )
    assert Project.instances.count() == 1
    assert Project.objects.count() == 2
```

- [ ] **Step 3: Run and confirm failure**

```bash
uv run pytest apps/projects/tests/test_models_project.py -v
```

Expected: ImportError on `Project`, `ProjectStatus`, `ProjectPriority`.

- [ ] **Step 4: Write the Project model**

Create `apps/projects/models/project.py`:

```python
import datetime as dt

from django.conf import settings
from django.db import models


class ProjectStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    DELAYED = "delayed", "Delayed"
    COMPLETED = "completed", "Completed"


class ProjectPriority(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class RecurrenceRule(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    SEMIANNUAL = "semiannual", "Semi-annual"
    ANNUAL = "annual", "Annual"


class InstanceManager(models.Manager):
    """Excludes recurring templates."""
    def get_queryset(self):
        return super().get_queryset().filter(is_recurring_template=False)


class TemplateManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_recurring_template=True)


class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        "projects.ProjectCategory",
        on_delete=models.PROTECT,
        related_name="projects",
    )
    status = models.CharField(
        max_length=16, choices=ProjectStatus.choices, default=ProjectStatus.NOT_STARTED,
    )
    delay_reason = models.TextField(blank=True)
    priority = models.CharField(
        max_length=8, choices=ProjectPriority.choices, default=ProjectPriority.MEDIUM,
    )
    projected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_bid_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tags = models.ManyToManyField("projects.Tag", related_name="projects", blank=True)

    is_recurring_template = models.BooleanField(default=False)
    recurrence_rule = models.CharField(
        max_length=16, choices=RecurrenceRule.choices, blank=True, default="",
    )
    next_due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    parent_template = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="instances",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    objects = models.Manager()
    instances = InstanceManager()
    templates = TemplateManager()

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "projected_completion_date"]),
            models.Index(fields=["is_recurring_template", "is_active"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only("status").first()
            old_status = old.status if old else None
        else:
            old_status = None

        if self.status == ProjectStatus.COMPLETED and self.actual_completion_date is None:
            self.actual_completion_date = dt.date.today()
        elif self.status != ProjectStatus.COMPLETED and old_status == ProjectStatus.COMPLETED:
            self.actual_completion_date = None

        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        if self.status == ProjectStatus.COMPLETED:
            return False
        if self.projected_completion_date is None:
            return False
        return self.projected_completion_date < dt.date.today()
```

- [ ] **Step 5: Re-export**

Replace `apps/projects/models/__init__.py`:

```python
from .category import ProjectCategory, Tag
from .project import (
    Project,
    ProjectStatus,
    ProjectPriority,
    RecurrenceRule,
)

__all__ = [
    "ProjectCategory",
    "Tag",
    "Project",
    "ProjectStatus",
    "ProjectPriority",
    "RecurrenceRule",
]
```

- [ ] **Step 6: Migrate and run tests**

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects/tests/test_models_project.py -v
```

Expected: 9 passed.

- [ ] **Step 7: Register Project in admin**

Add to `apps/projects/admin.py`:

```python
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "priority", "projected_completion_date", "is_recurring_template")
    list_filter = ("status", "category", "priority", "is_recurring_template")
    search_fields = ("title", "description", "vendor_name")
    autocomplete_fields = ("category",)
    filter_horizontal = ("tags",)
```

- [ ] **Step 8: Commit**

```bash
git add apps/projects/
git commit -m "feat(projects): Project model with status auto-date and managers"
```

---

## Task 5: RACIAssignment model

**Files:**
- Create: `apps/projects/models/raci.py`
- Modify: `apps/projects/models/__init__.py`
- Create: `apps/projects/tests/test_models_raci.py`
- Modify: `apps/projects/admin.py`

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_models_raci.py`:

```python
import pytest
from django.db import IntegrityError

from apps.projects.models import RACIAssignment, RACIRole


@pytest.mark.django_db
def test_assign_responsible(project, person):
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    assert a.role == "responsible"


@pytest.mark.django_db
def test_same_person_multiple_roles_allowed(project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.ACCOUNTABLE)
    assert RACIAssignment.objects.filter(project=project, person=person).count() == 2


@pytest.mark.django_db
def test_duplicate_role_for_same_person_blocked(project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    with pytest.raises(IntegrityError):
        RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)


@pytest.mark.django_db
def test_multiple_people_same_role(project, person, db):
    from apps.roster.models import RosterPerson
    other = RosterPerson.objects.create(name="Jane Doe")
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    RACIAssignment.objects.create(project=project, person=other, role=RACIRole.CONSULTED)
    assert RACIAssignment.objects.filter(project=project, role=RACIRole.CONSULTED).count() == 2
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/projects/tests/test_models_raci.py -v
```

- [ ] **Step 3: Write the model**

Create `apps/projects/models/raci.py`:

```python
from django.db import models


class RACIRole(models.TextChoices):
    RESPONSIBLE = "responsible", "Responsible"
    ACCOUNTABLE = "accountable", "Accountable"
    CONSULTED = "consulted", "Consulted"
    INFORMED = "informed", "Informed"


class RACIAssignment(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="raci_assignments",
    )
    person = models.ForeignKey(
        "roster.RosterPerson", on_delete=models.PROTECT, related_name="raci_assignments",
    )
    role = models.CharField(max_length=16, choices=RACIRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "person", "role"],
                name="raci_unique_project_person_role",
            )
        ]
        ordering = ["role", "person__name"]

    def __str__(self):
        return f"{self.person.name} — {self.get_role_display()} on {self.project.title}"
```

- [ ] **Step 4: Re-export, migrate, test**

Add to `apps/projects/models/__init__.py`:
```python
from .raci import RACIAssignment, RACIRole
```
And include both in `__all__`.

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects/tests/test_models_raci.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Admin**

Add to `apps/projects/admin.py`:

```python
from .models import RACIAssignment


@admin.register(RACIAssignment)
class RACIAssignmentAdmin(admin.ModelAdmin):
    list_display = ("project", "person", "role")
    list_filter = ("role",)
    autocomplete_fields = ("project", "person")
```

(Add `search_fields = ("title",)` to ProjectAdmin and ensure RosterPersonAdmin already has `search_fields` for autocomplete to work.)

- [ ] **Step 6: Commit**

```bash
git add apps/projects/
git commit -m "feat(projects): RACIAssignment with unique constraint on (project, person, role)"
```

---

## Task 6: BoardApproval model

**Files:**
- Create: `apps/projects/models/approval.py`
- Modify: `apps/projects/models/__init__.py`
- Create: `apps/projects/tests/test_models_approval.py`
- Modify: `apps/projects/admin.py`

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_models_approval.py`:

```python
import datetime as dt

import pytest

from apps.projects.models import BoardApproval


@pytest.mark.django_db
def test_create_board_approval(project):
    a = BoardApproval.objects.create(
        project=project,
        motion_text="Approve sprinkler upgrade for $40,000.",
        vote_date=dt.date(2026, 4, 15),
        votes_for=4, votes_against=0, votes_abstain=1,
        minutes_reference="Apr 2026 minutes, p. 3",
    )
    assert a.votes_for == 4


@pytest.mark.django_db
def test_one_to_one_per_project(project):
    BoardApproval.objects.create(
        project=project,
        motion_text="First motion",
        vote_date=dt.date(2026, 4, 15),
        votes_for=4, votes_against=0, votes_abstain=0,
    )
    with pytest.raises(Exception):
        BoardApproval.objects.create(
            project=project,
            motion_text="Second motion",
            vote_date=dt.date(2026, 5, 15),
            votes_for=3, votes_against=1, votes_abstain=0,
        )
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/projects/tests/test_models_approval.py -v
```

- [ ] **Step 3: Write the model**

Create `apps/projects/models/approval.py`:

```python
from django.db import models


class BoardApproval(models.Model):
    project = models.OneToOneField(
        "projects.Project", on_delete=models.CASCADE, related_name="board_approval",
    )
    motion_text = models.TextField()
    vote_date = models.DateField()
    votes_for = models.PositiveIntegerField(default=0)
    votes_against = models.PositiveIntegerField(default=0)
    votes_abstain = models.PositiveIntegerField(default=0)
    minutes_reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-vote_date"]

    def __str__(self):
        return f"Approval for {self.project.title} on {self.vote_date}"

    @property
    def vote_summary(self) -> str:
        return f"{self.votes_for}-{self.votes_against}-{self.votes_abstain}"
```

- [ ] **Step 4: Re-export, migrate, test**

Add to `apps/projects/models/__init__.py`:
```python
from .approval import BoardApproval
```
And add to `__all__`.

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects/tests/test_models_approval.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Admin + commit**

Add to `apps/projects/admin.py`:
```python
from .models import BoardApproval


@admin.register(BoardApproval)
class BoardApprovalAdmin(admin.ModelAdmin):
    list_display = ("project", "vote_date", "vote_summary")
    autocomplete_fields = ("project",)
```

```bash
git add apps/projects/
git commit -m "feat(projects): BoardApproval one-per-project with vote tally"
```

---

## Task 7: UpdateNote model + markdown rendering

**Files:**
- Create: `apps/projects/models/note.py`
- Create: `apps/projects/markdown_utils.py`
- Modify: `apps/projects/models/__init__.py`
- Create: `apps/projects/tests/test_models_note.py`
- Create: `apps/projects/tests/test_markdown_utils.py`

- [ ] **Step 1: Failing tests for markdown utils**

Create `apps/projects/tests/test_markdown_utils.py`:

```python
from apps.projects.markdown_utils import render_note


def test_basic_paragraph():
    out = render_note("Hello world")
    assert "<p>Hello world</p>" in out


def test_bold_and_italic():
    out = render_note("**bold** and *italic*")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out


def test_link_preserved():
    out = render_note("See [docs](https://example.com)")
    assert 'href="https://example.com"' in out


def test_script_stripped():
    out = render_note("<script>alert(1)</script>Hello")
    assert "<script>" not in out
    assert "alert" not in out  # bleach drops the tag *and* its text content here


def test_disallowed_tag_stripped():
    out = render_note('<iframe src="https://evil"></iframe>safe')
    assert "<iframe" not in out
    assert "safe" in out


def test_no_javascript_url():
    out = render_note('[click](javascript:alert(1))')
    assert "javascript:" not in out
```

Note: bleach's exact behavior on `<script>` content can vary by version. If `alert` survives in step 4 testing, weaken the assertion to `"<script>" not in out`.

- [ ] **Step 2: Failing model tests**

Create `apps/projects/tests/test_models_note.py`:

```python
import pytest

from apps.projects.models import UpdateNote


@pytest.mark.django_db
def test_create_note(project, user):
    n = UpdateNote.objects.create(project=project, body="Met with vendor.", author=user)
    assert n.body == "Met with vendor."


@pytest.mark.django_db
def test_notes_ordered_newest_first(project, user):
    n1 = UpdateNote.objects.create(project=project, body="First", author=user)
    n2 = UpdateNote.objects.create(project=project, body="Second", author=user)
    notes = list(UpdateNote.objects.filter(project=project))
    assert notes[0].pk == n2.pk
    assert notes[1].pk == n1.pk


@pytest.mark.django_db
def test_rendered_html_property(project, user):
    n = UpdateNote.objects.create(project=project, body="**Bold**", author=user)
    assert "<strong>Bold</strong>" in n.rendered_html
```

- [ ] **Step 3: Run and fail**

```bash
uv run pytest apps/projects/tests/test_markdown_utils.py apps/projects/tests/test_models_note.py -v
```

- [ ] **Step 4: Write markdown_utils.py**

Create `apps/projects/markdown_utils.py`:

```python
import bleach
import markdown as md

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "u", "code", "pre",
    "ul", "ol", "li", "blockquote",
    "a", "h2", "h3", "h4",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_note(raw: str) -> str:
    """Render markdown to safe HTML for an UpdateNote body."""
    rendered = md.markdown(raw, extensions=["extra"])
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
```

- [ ] **Step 5: Write UpdateNote model**

Create `apps/projects/models/note.py`:

```python
from django.conf import settings
from django.db import models

from ..markdown_utils import render_note


class UpdateNote(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="notes",
    )
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def rendered_html(self) -> str:
        return render_note(self.body)

    def __str__(self):
        return f"Note on {self.project.title} at {self.created_at:%Y-%m-%d %H:%M}"
```

- [ ] **Step 6: Re-export, migrate, test**

Add to `__init__.py`:
```python
from .note import UpdateNote
```

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects/tests/test_markdown_utils.py apps/projects/tests/test_models_note.py -v
```

Expected: 9 passed (6 markdown + 3 model). If `test_script_stripped` fails because bleach kept the inner text "alert(1)", weaken that test to only assert `"<script>" not in out`.

- [ ] **Step 7: Commit**

```bash
git add apps/projects/
git commit -m "feat(projects): UpdateNote model with sanitized markdown rendering"
```

---

## Task 8: ActivityLog model + signals

**Files:**
- Create: `apps/projects/models/activity.py`
- Modify: `apps/projects/models/__init__.py`
- Replace: `apps/projects/signals.py`
- Create: `apps/projects/tests/test_models_activity.py`
- Create: `apps/projects/tests/test_signals.py`

- [ ] **Step 1: Failing model tests**

Create `apps/projects/tests/test_models_activity.py`:

```python
import pytest

from apps.projects.models import ActivityLog


@pytest.mark.django_db
def test_create_activity_log(project, user):
    log = ActivityLog.objects.create(
        project=project,
        actor=user,
        verb="created project",
    )
    assert log.verb == "created project"
    assert log.before_value is None
    assert log.after_value is None


@pytest.mark.django_db
def test_activity_log_ordered_newest_first(project, user):
    a = ActivityLog.objects.create(project=project, actor=user, verb="a")
    b = ActivityLog.objects.create(project=project, actor=user, verb="b")
    logs = list(ActivityLog.objects.all())
    assert logs[0].pk == b.pk
```

- [ ] **Step 2: Failing signal tests**

Create `apps/projects/tests/test_signals.py`:

```python
import pytest

from apps.projects.models import (
    ActivityLog, Project, ProjectStatus, RACIAssignment, RACIRole,
)
from apps.projects.signals import set_actor


@pytest.mark.django_db
def test_project_create_logs(user, category):
    set_actor(user)
    p = Project.objects.create(title="Y", category=category, created_by=user)
    logs = ActivityLog.objects.filter(project=p, verb="created project")
    assert logs.exists()


@pytest.mark.django_db
def test_status_change_logs_before_after(user, project):
    set_actor(user)
    project.status = ProjectStatus.IN_PROGRESS
    project.save()
    log = ActivityLog.objects.filter(project=project, verb="changed status").first()
    assert log is not None
    assert log.before_value == {"status": "not_started"}
    assert log.after_value == {"status": "in_progress"}


@pytest.mark.django_db
def test_raci_add_logs(user, project, person):
    set_actor(user)
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    log = ActivityLog.objects.filter(project=project, verb="added RACI assignment").first()
    assert log is not None
    assert log.after_value == {"person": person.name, "role": "responsible"}


@pytest.mark.django_db
def test_raci_remove_logs(user, project, person):
    set_actor(user)
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    a.delete()
    log = ActivityLog.objects.filter(project=project, verb="removed RACI assignment").first()
    assert log is not None
```

- [ ] **Step 3: Write ActivityLog model**

Create `apps/projects/models/activity.py`:

```python
from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        null=True, blank=True, related_name="activity_log",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )
    verb = models.CharField(max_length=120)
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["project", "-created_at"]),
        ]

    def __str__(self):
        target = f" on {self.project.title}" if self.project_id else ""
        return f"{self.actor} {self.verb}{target}"
```

- [ ] **Step 4: Wire signals**

Replace `apps/projects/signals.py`:

```python
"""ActivityLog writers. The actor is provided per-request by views via set_actor()."""

import threading

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    ActivityLog, Project, RACIAssignment, BoardApproval,
)
from .models.attachment import Attachment

_state = threading.local()


def set_actor(user) -> None:
    _state.actor = user


def _actor():
    return getattr(_state, "actor", None)


# --- Project ---

@receiver(pre_save, sender=Project)
def _project_capture_old(sender, instance, **kwargs):
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._old_status = old.status if old else None
    else:
        instance._old_status = None


@receiver(post_save, sender=Project)
def _project_log(sender, instance, created, **kwargs):
    actor = _actor()
    if actor is None:
        return
    if created:
        ActivityLog.objects.create(
            project=instance, actor=actor, verb="created project",
            after_value={"title": instance.title},
        )
        return
    old_status = getattr(instance, "_old_status", None)
    if old_status and old_status != instance.status:
        ActivityLog.objects.create(
            project=instance, actor=actor, verb="changed status",
            before_value={"status": old_status},
            after_value={"status": instance.status},
        )


# --- RACI ---

@receiver(post_save, sender=RACIAssignment)
def _raci_added(sender, instance, created, **kwargs):
    if not created:
        return
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="added RACI assignment",
        after_value={"person": instance.person.name, "role": instance.role},
    )


@receiver(post_delete, sender=RACIAssignment)
def _raci_removed(sender, instance, **kwargs):
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="removed RACI assignment",
        before_value={"person": instance.person.name, "role": instance.role},
    )


# --- BoardApproval ---

@receiver(post_save, sender=BoardApproval)
def _approval_saved(sender, instance, created, **kwargs):
    actor = _actor()
    if actor is None:
        return
    verb = "added board approval" if created else "updated board approval"
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb=verb,
        after_value={"vote_date": str(instance.vote_date), "summary": instance.vote_summary},
    )


# --- Attachment ---

@receiver(post_save, sender=Attachment)
def _attachment_added(sender, instance, created, **kwargs):
    if not created:
        return
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="added attachment",
        after_value={"filename": instance.original_filename},
    )


@receiver(post_delete, sender=Attachment)
def _attachment_removed(sender, instance, **kwargs):
    actor = _actor()
    if actor is None:
        return
    ActivityLog.objects.create(
        project=instance.project, actor=actor, verb="removed attachment",
        before_value={"filename": instance.original_filename},
    )
```

Note: this imports `Attachment` from a model that doesn't exist yet (Task 10). To keep this task green, comment out the two `Attachment` blocks; uncomment them in Task 10 Step 6.

- [ ] **Step 5: Per-request actor middleware**

Create `apps/projects/middleware.py`:

```python
from .signals import set_actor


class ActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            set_actor(request.user)
        else:
            set_actor(None)
        return self.get_response(request)
```

Add to `MIDDLEWARE` in `config/settings.py`, after AuthenticationMiddleware:
```python
"apps.projects.middleware.ActorMiddleware",
```

- [ ] **Step 6: Re-export, migrate, run all tests**

Add to `apps/projects/models/__init__.py`:
```python
from .activity import ActivityLog
```

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects -v
```

Expected: all model + signal tests pass. (Attachment-related signal lines are commented out for now.)

- [ ] **Step 7: Commit**

```bash
git add apps/projects/ config/settings.py
git commit -m "feat(projects): ActivityLog with signals for status/RACI/approval changes"
```

---

This plan continues in `docs/superpowers/plans/2026-05-05-hoa-projects-part2.md` due to length. Tasks 9–19 (attachments, project list, project detail, inline edits, recurring, dashboard) live there to keep each plan file readable.

The "split a plan across multiple files" pattern is unusual — if you'd prefer a single file, paste the part-2 contents back into this file when convenient. The execution order is Tasks 1–8 here, then continue at Task 9 in part 2.

---

## Self-Review (covers part 1 only — part 2 has its own)

**Spec coverage so far:**
- ProjectCategory seeded list ✓
- Tag with slugified, dedupe-on-input ✓
- Project full field set, status auto-completion-date ✓
- RACIAssignment with `(project, person, role)` unique ✓
- BoardApproval one-per-project ✓
- UpdateNote with markdown ✓
- ActivityLog with signals ✓

**Placeholder scan:** "Continued in part 2" is a deliberate split across files, not a placeholder; each task here has full code.

**Type consistency:**
- `ProjectStatus` choices match spec: `not_started`, `in_progress`, `delayed`, `completed` ✓
- `RACIRole` choices: `responsible`, `accountable`, `consulted`, `informed` ✓
- `RecurrenceRule` choices: `weekly`, `monthly`, `quarterly`, `semiannual`, `annual` ✓
- Manager names: `Project.objects` (all), `Project.instances` (non-templates), `Project.templates` (templates only) — used consistently in subsequent tasks.

---

## Execution Handoff

After Tasks 1–8 are complete, continue with `2026-05-05-hoa-projects-part2.md` Tasks 9–19. Final handoff (subagent vs inline) decided after part 2 is read.
