# HOA Task Manager — Plan 2 Part 2: Attachments, Views, Recurring, Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Continues from:** `2026-05-05-hoa-projects.md` Tasks 1–8. Models, ActivityLog, and signals are in place. This file picks up at Task 9 (Attachment + R2) and runs through Task 19 (Dashboard).

---

## Task 9: Attachment model + R2 storage helper

**Files:**
- Create: `apps/projects/models/attachment.py`
- Create: `apps/projects/storage.py`
- Modify: `apps/projects/models/__init__.py`
- Modify: `apps/projects/signals.py` (uncomment Attachment blocks)
- Modify: `config/settings.py` (R2 env vars)
- Create: `apps/projects/tests/test_models_attachment.py`
- Create: `apps/projects/tests/test_storage.py`

- [ ] **Step 1: Failing model test**

Create `apps/projects/tests/test_models_attachment.py`:

```python
import pytest

from apps.projects.models import Attachment


@pytest.mark.django_db
def test_create_attachment(project, user):
    a = Attachment.objects.create(
        project=project,
        file_key="projects/1/abc123.pdf",
        original_filename="quote.pdf",
        content_type="application/pdf",
        size_bytes=120_000,
        uploaded_by=user,
    )
    assert a.original_filename == "quote.pdf"
    assert str(a) == "quote.pdf"


@pytest.mark.django_db
def test_attachment_human_size(project, user):
    a = Attachment.objects.create(
        project=project, file_key="x", original_filename="x", content_type="application/pdf",
        size_bytes=1_500_000, uploaded_by=user,
    )
    assert a.human_size == "1.5 MB"


@pytest.mark.django_db
def test_project_attachment_total_bytes(project, user):
    Attachment.objects.create(
        project=project, file_key="x1", original_filename="a", content_type="application/pdf",
        size_bytes=1_000_000, uploaded_by=user,
    )
    Attachment.objects.create(
        project=project, file_key="x2", original_filename="b", content_type="application/pdf",
        size_bytes=2_000_000, uploaded_by=user,
    )
    assert Attachment.total_bytes_for_project(project) == 3_000_000
```

- [ ] **Step 2: Failing storage tests**

Create `apps/projects/tests/test_storage.py`:

```python
from apps.projects.storage import build_object_key, validate_upload, AttachmentValidationError

import pytest


def test_build_object_key_includes_project_id():
    key = build_object_key(project_id=42, filename="quote.pdf")
    assert key.startswith("projects/42/")
    assert key.endswith(".pdf")


def test_build_object_key_unique_per_call():
    a = build_object_key(project_id=1, filename="x.pdf")
    b = build_object_key(project_id=1, filename="x.pdf")
    assert a != b


def test_validate_upload_size_limit():
    with pytest.raises(AttachmentValidationError, match="exceeds 10 MB"):
        validate_upload(filename="x.pdf", content_type="application/pdf",
                        size_bytes=11 * 1024 * 1024, project_total=0)


def test_validate_upload_project_limit():
    with pytest.raises(AttachmentValidationError, match="50 MB project"):
        validate_upload(filename="x.pdf", content_type="application/pdf",
                        size_bytes=1_000_000,
                        project_total=50 * 1024 * 1024)


def test_validate_upload_disallowed_type():
    with pytest.raises(AttachmentValidationError, match="not allowed"):
        validate_upload(filename="x.exe", content_type="application/x-msdownload",
                        size_bytes=1000, project_total=0)


def test_validate_upload_allowed_types():
    for ct in [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        validate_upload(filename="x", content_type=ct, size_bytes=100, project_total=0)
```

- [ ] **Step 3: Run and fail**

```bash
uv run pytest apps/projects/tests/test_models_attachment.py apps/projects/tests/test_storage.py -v
```

- [ ] **Step 4: Write storage.py**

Create `apps/projects/storage.py`:

```python
import os
import secrets
from pathlib import Path

import boto3
from botocore.client import Config
from django.conf import settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

PER_FILE_LIMIT = 10 * 1024 * 1024
PER_PROJECT_LIMIT = 50 * 1024 * 1024


class AttachmentValidationError(Exception):
    pass


def build_object_key(project_id: int, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    token = secrets.token_hex(8)
    return f"projects/{project_id}/{token}{ext}"


def validate_upload(
    *, filename: str, content_type: str, size_bytes: int, project_total: int,
) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AttachmentValidationError(
            f"Files of type {content_type} are not allowed. "
            "Allowed: PDF, JPG, PNG, DOCX, XLSX."
        )
    if size_bytes > PER_FILE_LIMIT:
        raise AttachmentValidationError(
            "File exceeds 10 MB per-file limit."
        )
    if project_total + size_bytes > PER_PROJECT_LIMIT:
        raise AttachmentValidationError(
            "Adding this file would exceed the 50 MB project total."
        )


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_fileobj(fileobj, key: str, content_type: str) -> None:
    _client().upload_fileobj(
        Fileobj=fileobj,
        Bucket=settings.R2_BUCKET,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def signed_download_url(key: str, *, filename: str, expires_in: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires_in,
    )


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.R2_BUCKET, Key=key)
```

- [ ] **Step 5: Add R2 settings**

Append to `config/settings.py`:

```python
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
```

- [ ] **Step 6: Write Attachment model**

Create `apps/projects/models/attachment.py`:

```python
from django.conf import settings
from django.db import models


class Attachment(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="attachments",
    )
    file_key = models.CharField(max_length=400)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename

    @property
    def human_size(self) -> str:
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                if unit == "B":
                    return f"{int(size)} B"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    @classmethod
    def total_bytes_for_project(cls, project) -> int:
        return cls.objects.filter(project=project).aggregate(
            total=models.Sum("size_bytes")
        )["total"] or 0
```

- [ ] **Step 7: Re-export, migrate, uncomment signals, test**

Add to `apps/projects/models/__init__.py`:
```python
from .attachment import Attachment
```

Uncomment the Attachment-related blocks in `apps/projects/signals.py` from Task 8.

```bash
uv run python manage.py makemigrations projects
uv run python manage.py migrate
uv run pytest apps/projects -v
```

Expected: all green. Storage tests don't actually hit R2 — they test pure logic.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/ config/settings.py
git commit -m "feat(projects): Attachment model with R2 storage helpers and validation"
```

---

## Task 10: Project create/edit form

**Files:**
- Create: `apps/projects/forms/project.py`
- Modify: `apps/projects/forms/__init__.py`
- Create: `apps/projects/views/project_form.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/form.html`
- Create: `apps/projects/tests/test_forms_project.py`
- Create: `apps/projects/tests/test_views_form.py`

- [ ] **Step 1: Failing form tests**

Create `apps/projects/tests/test_forms_project.py`:

```python
import datetime as dt

import pytest

from apps.projects.forms import ProjectForm
from apps.projects.models import ProjectStatus


@pytest.mark.django_db
def test_form_valid_minimal(category):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.NOT_STARTED, "priority": "medium",
        "description": "", "tags_text": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_form_delayed_requires_reason(category):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.DELAYED, "priority": "medium",
        "description": "", "tags_text": "",
        "delay_reason": "",
    })
    assert not form.is_valid()
    assert "delay_reason" in form.errors


@pytest.mark.django_db
def test_form_creates_tags_from_input(category, user):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.NOT_STARTED, "priority": "medium",
        "description": "", "tags_text": "concrete, sprinklers",
    })
    assert form.is_valid(), form.errors
    project = form.save(commit=False)
    project.created_by = user
    project.save()
    form.save_m2m_with_tags(project)
    tag_names = sorted(project.tags.values_list("name", flat=True))
    assert tag_names == ["concrete", "sprinklers"]
```

- [ ] **Step 2: Failing view tests**

Create `apps/projects/tests/test_views_form.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_create_get_renders(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_create_post_creates_project(auth_client, category):
    response = auth_client.post(reverse("projects:create"), {
        "title": "New Project",
        "category": category.pk,
        "status": "not_started",
        "priority": "medium",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    assert Project.objects.filter(title="New Project").exists()


@pytest.mark.django_db
def test_edit_post_updates(auth_client, project):
    response = auth_client.post(reverse("projects:edit", args=[project.pk]), {
        "title": "Renamed",
        "category": project.category_id,
        "status": "not_started",
        "priority": "high",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.title == "Renamed"
    assert project.priority == "high"
```

- [ ] **Step 3: Run and fail**

```bash
uv run pytest apps/projects/tests/test_forms_project.py apps/projects/tests/test_views_form.py -v
```

- [ ] **Step 4: Write the form**

Create `apps/projects/forms/project.py`:

```python
from django import forms

from ..models import Project, ProjectStatus, Tag


_INPUT = {"class": "input"}
_TEXTAREA = {"class": "input", "rows": 4}


class ProjectForm(forms.ModelForm):
    tags_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**_INPUT, "placeholder": "concrete, sprinklers"}),
        help_text="Comma-separated tags. Created automatically.",
    )

    class Meta:
        model = Project
        fields = [
            "title", "description", "category", "status", "delay_reason",
            "priority", "projected_completion_date",
            "budget_amount", "actual_cost", "vendor_name", "vendor_bid_amount",
        ]
        widgets = {
            "title": forms.TextInput(attrs=_INPUT),
            "description": forms.Textarea(attrs=_TEXTAREA),
            "category": forms.Select(attrs=_INPUT),
            "status": forms.Select(attrs=_INPUT),
            "delay_reason": forms.Textarea(attrs={**_TEXTAREA, "rows": 2}),
            "priority": forms.Select(attrs=_INPUT),
            "projected_completion_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "budget_amount": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
            "actual_cost": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
            "vendor_name": forms.TextInput(attrs=_INPUT),
            "vendor_bid_amount": forms.NumberInput(attrs={**_INPUT, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            existing = ", ".join(self.instance.tags.values_list("name", flat=True))
            self.fields["tags_text"].initial = existing

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == ProjectStatus.DELAYED:
            if not cleaned.get("delay_reason", "").strip():
                self.add_error("delay_reason", "A reason is required when status is Delayed.")
        return cleaned

    def save_m2m_with_tags(self, project: Project):
        raw = self.cleaned_data.get("tags_text", "")
        names = [n.strip() for n in raw.split(",") if n.strip()]
        tags = [Tag.get_or_create_from_input(n) for n in names]
        project.tags.set(tags)
```

- [ ] **Step 5: Re-export form**

Replace `apps/projects/forms/__init__.py`:
```python
from .project import ProjectForm
__all__ = ["ProjectForm"]
```

- [ ] **Step 6: Write the view**

Create `apps/projects/views/project_form.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ProjectForm
from ..models import Project


@login_required
def create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m_with_tags(project)
            messages.success(request, "Project created.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, "projects/form.html", {"form": form, "project": None})


@login_required
def edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            form.save_m2m_with_tags(project)
            messages.success(request, "Saved.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "projects/form.html", {"form": form, "project": project})
```

- [ ] **Step 7: Re-export view, wire URLs**

Add to `apps/projects/views/__init__.py`:
```python
from .project_form import create, edit
```

Replace `apps/projects/urls.py`:
```python
from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("new/", views.create, name="create"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    # detail and list added in Tasks 11–12
]
```

- [ ] **Step 8: Write the form template**

Create `templates/projects/form.html`:

```html
{% extends "base.html" %}
{% block title %}{% if project %}Edit {{ project.title }}{% else %}New project{% endif %}{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">
  {% if project %}Edit {{ project.title }}{% else %}New project{% endif %}
</h1>

<form method="post" class="bg-white rounded-lg shadow p-6 max-w-3xl space-y-4">
  {% csrf_token %}
  {% for field in form %}
    <div>
      <label class="label" for="{{ field.id_for_label }}">
        {{ field.label }}{% if field.field.required %} *{% endif %}
      </label>
      {{ field }}
      {% if field.help_text %}<p class="text-xs text-gray-500 mt-1">{{ field.help_text }}</p>{% endif %}
      {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
    </div>
  {% endfor %}
  <div class="flex gap-2 pt-4">
    <button type="submit" class="btn-primary">Save</button>
    <a href="{% if project %}{% url 'projects:detail' project.pk %}{% else %}{% url 'projects:list' %}{% endif %}"
       class="btn-secondary">Cancel</a>
  </div>
</form>
{% endblock %}
```

The template references `projects:list` and `projects:detail` which don't exist yet — Tasks 11–12 wire them. Form posts will work in this task; the Cancel link will 500 until Task 12.

- [ ] **Step 9: Run tests**

```bash
uv run pytest apps/projects/tests/test_forms_project.py apps/projects/tests/test_views_form.py -v
```

The `test_create_post_creates_project` test will fail on the redirect to `projects:detail` (NoReverseMatch). For now, change the view's redirect target to `projects:edit` and update the test accordingly; flip back to `projects:detail` in Task 12 Step 7.

Cleaner alternative: skip the form view tests until Task 12 with `@pytest.mark.skip(reason="Wired in Task 12")`.

- [ ] **Step 10: Commit**

```bash
git add apps/projects/ templates/projects/form.html
git commit -m "feat(projects): create/edit form with tag input and delay-reason validation"
```

---

## Task 11: Project list with filters / search / sort

**Files:**
- Create: `apps/projects/views/project_list.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/list.html`
- Create: `templates/projects/_list_row.html`
- Create: `templates/projects/_empty_state.html`
- Create: `apps/projects/tests/test_views_list.py`
- Modify: `templates/_sidebar.html` (add Projects link)

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_views_list.py`:

```python
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_list_excludes_completed_by_default(auth_client, user, category):
    Project.objects.create(title="Active", category=category, created_by=user)
    Project.objects.create(
        title="DoneOne", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:list"))
    assert response.status_code == 200
    assert b"Active" in response.content
    assert b"DoneOne" not in response.content


@pytest.mark.django_db
def test_list_excludes_templates(auth_client, user, category):
    Project.objects.create(title="Plain", category=category, created_by=user)
    Project.objects.create(
        title="Template", category=category, created_by=user,
        is_recurring_template=True,
    )
    response = auth_client.get(reverse("projects:list"))
    assert b"Plain" in response.content
    assert b"Template" not in response.content


@pytest.mark.django_db
def test_list_status_filter(auth_client, user, category):
    Project.objects.create(title="A", category=category, created_by=user)
    Project.objects.create(
        title="B", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    response = auth_client.get(reverse("projects:list") + "?status=in_progress")
    assert b"A" not in response.content
    assert b"B" in response.content


@pytest.mark.django_db
def test_list_search_by_title(auth_client, user, category):
    Project.objects.create(title="Sprinkler", category=category, created_by=user)
    Project.objects.create(title="Concrete", category=category, created_by=user)
    response = auth_client.get(reverse("projects:list") + "?q=spr")
    assert b"Sprinkler" in response.content
    assert b"Concrete" not in response.content


@pytest.mark.django_db
def test_list_sort_by_due_date(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="Later", category=category, created_by=user,
        projected_completion_date=today + dt.timedelta(days=20),
    )
    Project.objects.create(
        title="Sooner", category=category, created_by=user,
        projected_completion_date=today + dt.timedelta(days=5),
    )
    response = auth_client.get(reverse("projects:list") + "?sort=due")
    body = response.content.decode()
    assert body.index("Sooner") < body.index("Later")


@pytest.mark.django_db
def test_list_show_completed(auth_client, user, category):
    Project.objects.create(
        title="DoneOne", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:list") + "?show_completed=1")
    assert b"DoneOne" in response.content


@pytest.mark.django_db
def test_list_empty_state(auth_client):
    response = auth_client.get(reverse("projects:list"))
    assert response.status_code == 200
    assert b"No projects yet" in response.content
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/projects/tests/test_views_list.py -v
```

- [ ] **Step 3: Write the view**

Create `apps/projects/views/project_list.py`:

```python
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from ..models import Project, ProjectCategory, ProjectStatus
from apps.roster.models import RosterPerson


SORT_CHOICES = {
    "updated": "-updated_at",
    "due": "projected_completion_date",
    "priority": "priority",
    "title": "title",
}


@login_required
def list_view(request):
    qs = Project.instances.select_related("category").prefetch_related(
        "raci_assignments__person", "tags",
    )

    show_completed = request.GET.get("show_completed") == "1"
    if not show_completed:
        qs = qs.exclude(status=ProjectStatus.COMPLETED)

    status = request.GET.get("status")
    if status in dict(ProjectStatus.choices):
        qs = qs.filter(status=status)

    cat_id = request.GET.get("category")
    if cat_id and cat_id.isdigit():
        qs = qs.filter(category_id=int(cat_id))

    person_id = request.GET.get("person")
    if person_id and person_id.isdigit():
        qs = qs.filter(raci_assignments__person_id=int(person_id)).distinct()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    sort_key = request.GET.get("sort", "updated")
    order_field = SORT_CHOICES.get(sort_key, "-updated_at")
    if order_field == "projected_completion_date":
        # Django sqlite: place NULLs last via a synthetic boolean column
        qs = qs.extra(
            select={"_no_due": "projected_completion_date IS NULL"}
        ).order_by("_no_due", "projected_completion_date")
    else:
        qs = qs.order_by(order_field)

    return render(request, "projects/list.html", {
        "projects": qs,
        "categories": ProjectCategory.objects.all(),
        "people": RosterPerson.active.all(),
        "selected_status": status or "",
        "selected_category": cat_id or "",
        "selected_person": person_id or "",
        "selected_sort": sort_key,
        "show_completed": show_completed,
        "q": q,
        "status_choices": ProjectStatus.choices,
    })
```

- [ ] **Step 4: Re-export, wire URL**

Add to `apps/projects/views/__init__.py`:
```python
from .project_list import list_view
```

In `apps/projects/urls.py`, add to top of `urlpatterns`:
```python
path("", views.list_view, name="list"),
```

- [ ] **Step 5: Write list template**

Create `templates/projects/list.html`:

```html
{% extends "base.html" %}
{% block title %}Projects — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Projects</h1>
  <a href="{% url 'projects:create' %}" class="btn-primary">+ New project</a>
</div>

<form method="get" class="bg-white rounded-lg shadow p-4 mb-6 grid grid-cols-1 md:grid-cols-6 gap-3 text-sm">
  <input name="q" value="{{ q }}" placeholder="Search…" class="input md:col-span-2">
  <select name="status" class="input">
    <option value="">All statuses</option>
    {% for value, label in status_choices %}
      <option value="{{ value }}" {% if selected_status == value %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <select name="category" class="input">
    <option value="">All categories</option>
    {% for c in categories %}
      <option value="{{ c.pk }}" {% if selected_category == c.pk|stringformat:"s" %}selected{% endif %}>{{ c.name }}</option>
    {% endfor %}
  </select>
  <select name="person" class="input">
    <option value="">Any person</option>
    {% for p in people %}
      <option value="{{ p.pk }}" {% if selected_person == p.pk|stringformat:"s" %}selected{% endif %}>{{ p.name }}</option>
    {% endfor %}
  </select>
  <select name="sort" class="input">
    <option value="updated" {% if selected_sort == "updated" %}selected{% endif %}>Recently updated</option>
    <option value="due" {% if selected_sort == "due" %}selected{% endif %}>Due date</option>
    <option value="priority" {% if selected_sort == "priority" %}selected{% endif %}>Priority</option>
    <option value="title" {% if selected_sort == "title" %}selected{% endif %}>Title</option>
  </select>
  <div class="md:col-span-6 flex items-center gap-4">
    <label class="text-gray-700"><input type="checkbox" name="show_completed" value="1"
      {% if show_completed %}checked{% endif %}> Show completed</label>
    <button type="submit" class="btn-secondary ml-auto">Apply</button>
  </div>
</form>

{% if projects %}
<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="min-w-full divide-y divide-gray-200 text-sm">
    <thead class="bg-gray-50 text-xs uppercase text-gray-500">
      <tr>
        <th class="w-1 px-2 py-2"></th>
        <th class="px-3 py-2 text-left">Title</th>
        <th class="px-3 py-2 text-left">Category</th>
        <th class="px-3 py-2 text-left">Status</th>
        <th class="px-3 py-2 text-left">RACI</th>
        <th class="px-3 py-2 text-left">Due</th>
        <th class="px-3 py-2 text-left">Budget / Actual</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-100">
      {% for p in projects %}{% include "projects/_list_row.html" %}{% endfor %}
    </tbody>
  </table>
</div>
{% else %}
{% include "projects/_empty_state.html" %}
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Write row partial**

Create `templates/projects/_list_row.html`:

```html
{% load humanize %}
<tr>
  <td class="px-2 py-3">
    <span class="inline-block w-2 h-2 rounded-full
      {% if p.priority == 'high' %}bg-red-500
      {% elif p.priority == 'medium' %}bg-amber-500
      {% else %}bg-gray-300{% endif %}"
      title="Priority: {{ p.get_priority_display }}"></span>
  </td>
  <td class="px-3 py-3">
    <a href="{% url 'projects:detail' p.pk %}" class="text-blue-700 font-medium hover:underline">{{ p.title }}</a>
    <div class="text-xs text-gray-500">
      {{ p.notes.count }} note{{ p.notes.count|pluralize }} · {{ p.attachments.count }} file{{ p.attachments.count|pluralize }}
    </div>
  </td>
  <td class="px-3 py-3"><span class="pill bg-gray-100 text-gray-700">{{ p.category.name }}</span></td>
  <td class="px-3 py-3">
    <span class="pill
      {% if p.status == 'completed' %}bg-green-100 text-green-800
      {% elif p.status == 'delayed' %}bg-red-100 text-red-800
      {% elif p.status == 'in_progress' %}bg-blue-100 text-blue-800
      {% else %}bg-gray-100 text-gray-700{% endif %}">{{ p.get_status_display }}</span>
  </td>
  <td class="px-3 py-3 text-xs text-gray-700">
    {% for a in p.raci_assignments.all|dictsort:"role" %}
      {{ a.role|first|upper }}: {{ a.person.name|truncatechars:18 }}{% if not forloop.last %} · {% endif %}
    {% empty %}<span class="text-gray-400">—</span>{% endfor %}
  </td>
  <td class="px-3 py-3 text-sm
    {% if p.is_overdue %}text-red-700 font-medium{% endif %}">
    {{ p.projected_completion_date|default:"—" }}
  </td>
  <td class="px-3 py-3 text-sm text-gray-700">
    {% if p.budget_amount %}${{ p.budget_amount|floatformat:0|intcomma }}{% else %}—{% endif %}
    {% if p.actual_cost %} / ${{ p.actual_cost|floatformat:0|intcomma }}{% endif %}
  </td>
</tr>
```

- [ ] **Step 7: Empty state**

Create `templates/projects/_empty_state.html`:

```html
<div class="bg-white rounded-lg shadow p-8 text-center">
  <p class="text-gray-500 mb-4">No projects yet — create your first one.</p>
  <a href="{% url 'projects:create' %}" class="btn-primary">+ New project</a>
</div>
```

- [ ] **Step 8: Add humanize to INSTALLED_APPS**

In `config/settings.py`, append `"django.contrib.humanize"` to `INSTALLED_APPS`.

- [ ] **Step 9: Add Projects link to sidebar**

Edit `templates/_sidebar.html`, add this nav link after Dashboard:

```html
<a href="{% url 'projects:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Projects</a>
```

- [ ] **Step 10: Run tests**

```bash
uv run pytest apps/projects/tests/test_views_list.py -v
```

Expected: 7 passed. Test asserting `notes.count` etc. won't break because counts default to 0.

- [ ] **Step 11: Commit**

```bash
git add apps/projects/ templates/ config/settings.py
git commit -m "feat(projects): list view with search, filters, sort, empty state"
```

---

## Task 12: Project detail page (read-only render)

**Files:**
- Create: `apps/projects/views/project_detail.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/detail.html`
- Create: `templates/projects/_delay_banner.html`
- Create: `templates/projects/_raci_section.html`
- Create: `templates/projects/_raci_row.html`
- Create: `templates/projects/_approval_section.html`
- Create: `templates/projects/_attachments_section.html`
- Create: `templates/projects/_attachment_row.html`
- Create: `templates/projects/_notes_section.html`
- Create: `templates/projects/_note_card.html`
- Create: `templates/projects/_activity_card.html`
- Create field display partials (see Step 6)
- Create: `apps/projects/tests/test_views_detail.py`

- [ ] **Step 1: Failing test**

Create `apps/projects/tests/test_views_detail.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import ProjectStatus


@pytest.mark.django_db
def test_detail_renders(auth_client, project):
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert response.status_code == 200
    assert project.title.encode() in response.content


@pytest.mark.django_db
def test_detail_shows_delay_banner(auth_client, project):
    project.status = ProjectStatus.DELAYED
    project.delay_reason = "Vendor is on vacation"
    project.save()
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert b"Delayed" in response.content
    assert b"Vendor is on vacation" in response.content


@pytest.mark.django_db
def test_detail_404_for_missing(auth_client):
    response = auth_client.get(reverse("projects:detail", args=[999999]))
    assert response.status_code == 404
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/projects/tests/test_views_detail.py -v
```

- [ ] **Step 3: Write the view**

Create `apps/projects/views/project_detail.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.roster.models import RosterPerson

from ..models import (
    ActivityLog, Project, ProjectCategory, ProjectStatus, ProjectPriority,
    RACIRole,
)


@login_required
def detail(request, pk):
    project = get_object_or_404(
        Project.objects
            .select_related("category", "board_approval", "created_by")
            .prefetch_related(
                "raci_assignments__person",
                "tags",
                "notes__author",
                "attachments__uploaded_by",
            ),
        pk=pk,
    )
    activity = ActivityLog.objects.filter(project=project).select_related("actor")[:30]
    available_people = RosterPerson.active.exclude(
        raci_assignments__project=project,
    ).distinct()
    return render(request, "projects/detail.html", {
        "project": project,
        "activity": activity,
        "raci_role_choices": RACIRole.choices,
        "status_choices": ProjectStatus.choices,
        "priority_choices": ProjectPriority.choices,
        "available_people": available_people,
    })
```

- [ ] **Step 4: Re-export, wire URL**

Add to `apps/projects/views/__init__.py`:
```python
from .project_detail import detail
```

In `apps/projects/urls.py`:
```python
path("<int:pk>/", views.detail, name="detail"),
```

(Restore the redirect target in `views/project_form.py` to `projects:detail` if you changed it in Task 10.)

- [ ] **Step 5: Write detail.html**

Create `templates/projects/detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ project.title }} — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-start justify-between mb-4">
  <div>
    <h1 class="text-2xl font-semibold text-gray-900">{{ project.title }}</h1>
    <div class="mt-1 text-sm text-gray-500">
      <span class="pill bg-gray-100 text-gray-700">{{ project.category.name }}</span>
      {% for tag in project.tags.all %}<span class="pill bg-gray-100 text-gray-700 ml-1">#{{ tag.name }}</span>{% endfor %}
    </div>
  </div>
  <a href="{% url 'projects:edit' project.pk %}" class="btn-secondary">Edit details</a>
</div>

{% include "projects/_delay_banner.html" %}

<div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
  <div class="lg:col-span-7 space-y-6">
    <section class="bg-white rounded-lg shadow p-5">
      <h2 class="text-sm font-semibold text-gray-500 uppercase mb-2">Description</h2>
      <p class="text-gray-800 whitespace-pre-wrap">{{ project.description|default:"—" }}</p>
    </section>

    <section class="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4 text-sm">
      <div>
        <h3 class="text-xs uppercase text-gray-500 mb-1">Status</h3>
        {% include "projects/_field_status.html" %}
      </div>
      <div>
        <h3 class="text-xs uppercase text-gray-500 mb-1">Priority</h3>
        {% include "projects/_field_priority.html" %}
      </div>
      <div class="col-span-2">
        <h3 class="text-xs uppercase text-gray-500 mb-1">Dates</h3>
        {% include "projects/_field_dates.html" %}
      </div>
      <div class="col-span-2">
        <h3 class="text-xs uppercase text-gray-500 mb-1">Budget</h3>
        {% include "projects/_field_budget.html" %}
      </div>
      <div class="col-span-2">
        <h3 class="text-xs uppercase text-gray-500 mb-1">Vendor</h3>
        {% include "projects/_field_vendor.html" %}
      </div>
    </section>

    {% include "projects/_raci_section.html" %}
    {% include "projects/_approval_section.html" %}
    {% include "projects/_attachments_section.html" %}
  </div>

  <div class="lg:col-span-5 space-y-6">
    {% include "projects/_notes_section.html" %}

    <section class="bg-white rounded-lg shadow p-5">
      <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Activity</h2>
      <ul class="space-y-2">
        {% for log in activity %}{% include "projects/_activity_card.html" %}{% empty %}
          <li class="text-sm text-gray-400">No activity yet.</li>
        {% endfor %}
      </ul>
    </section>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Write the field display partials**

Each field has a "display" partial (this task) and an "edit" partial (Task 13). For Task 12, the display partials only need to render the value with a clickable affordance — no interactivity yet.

Create `templates/projects/_field_status.html`:

```html
<div id="field-status-{{ project.pk }}" class="flex items-center gap-2">
  <span class="pill
    {% if project.status == 'completed' %}bg-green-100 text-green-800
    {% elif project.status == 'delayed' %}bg-red-100 text-red-800
    {% elif project.status == 'in_progress' %}bg-blue-100 text-blue-800
    {% else %}bg-gray-100 text-gray-700{% endif %}">{{ project.get_status_display }}</span>
  <button type="button"
    hx-get="{% url 'projects:inline_status_edit' project.pk %}"
    hx-target="#field-status-{{ project.pk }}"
    hx-swap="outerHTML"
    class="text-xs text-blue-600 hover:underline">edit</button>
</div>
```

Create `templates/projects/_field_priority.html`:

```html
<div id="field-priority-{{ project.pk }}" class="flex items-center gap-2">
  <span class="text-gray-800">{{ project.get_priority_display }}</span>
  <button type="button"
    hx-get="{% url 'projects:inline_priority_edit' project.pk %}"
    hx-target="#field-priority-{{ project.pk }}"
    hx-swap="outerHTML"
    class="text-xs text-blue-600 hover:underline">edit</button>
</div>
```

Create `templates/projects/_field_dates.html`:

```html
<div id="field-dates-{{ project.pk }}" class="flex items-center gap-3">
  <span class="text-gray-800">
    Projected: {{ project.projected_completion_date|default:"—" }}
    {% if project.actual_completion_date %} · Completed: {{ project.actual_completion_date }}{% endif %}
  </span>
  <button type="button"
    hx-get="{% url 'projects:inline_dates_edit' project.pk %}"
    hx-target="#field-dates-{{ project.pk }}"
    hx-swap="outerHTML"
    class="text-xs text-blue-600 hover:underline">edit</button>
</div>
```

Create `templates/projects/_field_budget.html`:

```html
{% load humanize %}
<div id="field-budget-{{ project.pk }}" class="flex items-center gap-3">
  <span class="text-gray-800">
    {% if project.budget_amount %}${{ project.budget_amount|floatformat:2|intcomma }}{% else %}— budget{% endif %}
    /
    {% if project.actual_cost %}${{ project.actual_cost|floatformat:2|intcomma }}{% else %}— actual{% endif %}
  </span>
  <button type="button"
    hx-get="{% url 'projects:inline_budget_edit' project.pk %}"
    hx-target="#field-budget-{{ project.pk }}"
    hx-swap="outerHTML"
    class="text-xs text-blue-600 hover:underline">edit</button>
</div>
```

Create `templates/projects/_field_vendor.html`:

```html
{% load humanize %}
<div id="field-vendor-{{ project.pk }}" class="flex items-center gap-3">
  <span class="text-gray-800">
    {{ project.vendor_name|default:"—" }}
    {% if project.vendor_bid_amount %} (bid ${{ project.vendor_bid_amount|floatformat:2|intcomma }}){% endif %}
  </span>
  <button type="button"
    hx-get="{% url 'projects:inline_vendor_edit' project.pk %}"
    hx-target="#field-vendor-{{ project.pk }}"
    hx-swap="outerHTML"
    class="text-xs text-blue-600 hover:underline">edit</button>
</div>
```

(All `inline_*_edit` URLs are wired in Task 13. The buttons render but are non-functional in Task 12.)

- [ ] **Step 7: Write delay banner**

Create `templates/projects/_delay_banner.html`:

```html
{% if project.status == 'delayed' %}
<div class="mb-4 rounded-lg bg-red-50 border border-red-200 p-4">
  <div class="font-semibold text-red-900 mb-1">Delayed</div>
  <p class="text-red-800 text-sm whitespace-pre-wrap">{{ project.delay_reason|default:"No reason provided." }}</p>
</div>
{% endif %}
```

- [ ] **Step 8: Write RACI / approval / attachments / notes / activity partials**

Create `templates/projects/_raci_section.html`:

```html
<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">RACI</h2>
  <ul id="raci-list-{{ project.pk }}" class="space-y-1 mb-3">
    {% for a in project.raci_assignments.all %}{% include "projects/_raci_row.html" %}{% empty %}
      <li class="text-sm text-gray-400">No assignments yet.</li>
    {% endfor %}
  </ul>
  <form hx-post="{% url 'projects:raci_add' project.pk %}"
        hx-target="#raci-list-{{ project.pk }}"
        hx-swap="outerHTML"
        class="flex gap-2 text-sm">
    {% csrf_token %}
    <select name="person" class="input flex-1">
      <option value="">Select person…</option>
      {% for p in available_people %}<option value="{{ p.pk }}">{{ p.name }}</option>{% endfor %}
    </select>
    <select name="role" class="input">
      {% for value, label in raci_role_choices %}
        <option value="{{ value }}">{{ label }}</option>
      {% endfor %}
    </select>
    <button type="submit" class="btn-secondary">Add</button>
  </form>
</section>
```

Create `templates/projects/_raci_row.html`:

```html
<li class="flex items-center justify-between text-sm">
  <span>
    <span class="pill bg-gray-100 text-gray-700 mr-2">{{ a.role|first|upper }}</span>
    {{ a.person.name }}{% if a.person.archived %} <span class="text-xs text-gray-400">(archived)</span>{% endif %}
  </span>
  <button type="button"
    hx-post="{% url 'projects:raci_remove' a.pk %}"
    hx-target="#raci-list-{{ project.pk }}"
    hx-swap="outerHTML"
    hx-confirm="Remove this assignment?"
    class="text-xs text-red-600 hover:underline">remove</button>
</li>
```

Create `templates/projects/_approval_section.html`:

```html
<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Board approval</h2>
  {% if project.board_approval %}
    <dl class="text-sm space-y-1">
      <div class="flex"><dt class="w-32 text-gray-500">Motion</dt><dd class="text-gray-800 whitespace-pre-wrap">{{ project.board_approval.motion_text }}</dd></div>
      <div class="flex"><dt class="w-32 text-gray-500">Vote date</dt><dd class="text-gray-800">{{ project.board_approval.vote_date }}</dd></div>
      <div class="flex"><dt class="w-32 text-gray-500">Tally</dt><dd class="text-gray-800">{{ project.board_approval.vote_summary }} (for-against-abstain)</dd></div>
      {% if project.board_approval.minutes_reference %}
      <div class="flex"><dt class="w-32 text-gray-500">Minutes</dt><dd class="text-gray-800">{{ project.board_approval.minutes_reference }}</dd></div>
      {% endif %}
    </dl>
    <a href="{% url 'projects:approval_edit' project.pk %}" class="text-xs text-blue-600 hover:underline mt-3 inline-block">Edit approval</a>
  {% else %}
    <p class="text-sm text-gray-400 mb-2">No board approval recorded.</p>
    <a href="{% url 'projects:approval_add' project.pk %}" class="btn-secondary text-xs">+ Record approval</a>
  {% endif %}
</section>
```

Create `templates/projects/_attachments_section.html`:

```html
<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Attachments</h2>
  <ul id="attachments-list-{{ project.pk }}" class="space-y-2 mb-3">
    {% for f in project.attachments.all %}{% include "projects/_attachment_row.html" %}{% empty %}
      <li class="text-sm text-gray-400">No files attached.</li>
    {% endfor %}
  </ul>
  <form hx-post="{% url 'projects:attachment_upload' project.pk %}"
        hx-encoding="multipart/form-data"
        hx-target="#attachments-list-{{ project.pk }}"
        hx-swap="outerHTML"
        class="flex gap-2 text-sm items-center">
    {% csrf_token %}
    <input type="file" name="file" required class="text-xs">
    <button type="submit" class="btn-secondary">Upload</button>
  </form>
  <p class="text-xs text-gray-500 mt-2">Limits: 10 MB / file, 50 MB / project. PDF, JPG, PNG, DOCX, XLSX.</p>
</section>
```

Create `templates/projects/_attachment_row.html`:

```html
<li class="flex items-center justify-between text-sm">
  <a href="{% url 'projects:attachment_download' f.pk %}" class="text-blue-700 hover:underline">{{ f.original_filename }}</a>
  <span class="text-xs text-gray-500">{{ f.human_size }} ·
    <button type="button"
      hx-post="{% url 'projects:attachment_delete' f.pk %}"
      hx-target="#attachments-list-{{ project.pk }}"
      hx-swap="outerHTML"
      hx-confirm="Delete {{ f.original_filename|escapejs }}?"
      class="text-red-600 hover:underline">delete</button>
  </span>
</li>
```

Create `templates/projects/_notes_section.html`:

```html
<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Notes</h2>
  <form hx-post="{% url 'projects:note_add' project.pk %}"
        hx-target="#notes-list-{{ project.pk }}"
        hx-swap="outerHTML"
        class="mb-4">
    {% csrf_token %}
    <textarea name="body" rows="3" class="input mb-2" placeholder="Add a note (markdown supported)…" required></textarea>
    <button type="submit" class="btn-primary text-xs">Add note</button>
  </form>
  <ul id="notes-list-{{ project.pk }}" class="space-y-3">
    {% for n in project.notes.all %}{% include "projects/_note_card.html" %}{% empty %}
      <li class="text-sm text-gray-400">No notes yet.</li>
    {% endfor %}
  </ul>
</section>
```

Create `templates/projects/_note_card.html`:

```html
<li class="border-l-2 border-gray-200 pl-3">
  <div class="text-xs text-gray-500 mb-1">{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.email|default:n.author.username }}</div>
  <div class="prose prose-sm text-gray-800">{{ n.rendered_html|safe }}</div>
</li>
```

Create `templates/projects/_activity_card.html`:

```html
<li class="text-sm text-gray-700">
  <span class="text-gray-500">{{ log.created_at|date:"M j · g:i A" }}</span> —
  <strong>{{ log.actor.email|default:log.actor.username }}</strong> {{ log.verb }}
  {% if log.before_value or log.after_value %}
    <span class="text-xs text-gray-500">
      {% if log.before_value %}({{ log.before_value }} → {{ log.after_value }}){% else %}({{ log.after_value }}){% endif %}
    </span>
  {% endif %}
</li>
```

- [ ] **Step 9: Run tests**

```bash
uv run pytest apps/projects/tests/test_views_detail.py -v
```

The page renders but every `hx-get`/`hx-post` URL still 404s — fixed in Tasks 13–17. The detail tests don't follow links, so they pass.

Expected: 3 passed.

- [ ] **Step 10: Commit**

```bash
git add apps/projects/ templates/projects/
git commit -m "feat(projects): detail page with sections (HTMX endpoints land in 13-17)"
```

---

## Task 13: HTMX inline-edit endpoints

**Files:**
- Create: `apps/projects/views/inline.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create edit partials (one per field, parallel to display partials)
- Create: `apps/projects/tests/test_views_inline.py`

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_views_inline.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, ProjectStatus


@pytest.mark.django_db
def test_status_edit_form_renders(auth_client, project):
    response = auth_client.get(reverse("projects:inline_status_edit", args=[project.pk]))
    assert response.status_code == 200
    assert b"<select" in response.content


@pytest.mark.django_db
def test_status_save_updates_and_logs(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_status_save", args=[project.pk]),
        {"status": "in_progress"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.status == "in_progress"
    assert ActivityLog.objects.filter(project=project, verb="changed status").exists()


@pytest.mark.django_db
def test_status_save_delayed_requires_reason(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_status_save", args=[project.pk]),
        {"status": "delayed", "delay_reason": ""},
    )
    assert response.status_code == 400
    project.refresh_from_db()
    assert project.status != ProjectStatus.DELAYED


@pytest.mark.django_db
def test_priority_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_priority_save", args=[project.pk]),
        {"priority": "high"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.priority == "high"


@pytest.mark.django_db
def test_dates_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_dates_save", args=[project.pk]),
        {"projected_completion_date": "2026-12-01"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert str(project.projected_completion_date) == "2026-12-01"


@pytest.mark.django_db
def test_budget_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_budget_save", args=[project.pk]),
        {"budget_amount": "5000.00", "actual_cost": "2500.00"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert str(project.budget_amount) == "5000.00"


@pytest.mark.django_db
def test_vendor_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_vendor_save", args=[project.pk]),
        {"vendor_name": "ABC Inc", "vendor_bid_amount": "10000.00"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.vendor_name == "ABC Inc"
```

- [ ] **Step 2: Run and fail**

```bash
uv run pytest apps/projects/tests/test_views_inline.py -v
```

- [ ] **Step 3: Write the inline view module**

Create `apps/projects/views/inline.py`:

```python
import datetime as dt
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..models import Project, ProjectStatus, ProjectPriority


def _render_field(request, project, partial: str):
    return render(request, f"projects/{partial}", {"project": project})


@login_required
def status_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, "projects/_field_status_edit.html", {
        "project": project, "status_choices": ProjectStatus.choices,
    })


@login_required
@require_http_methods(["POST"])
def status_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    new_status = request.POST.get("status", "")
    if new_status not in dict(ProjectStatus.choices):
        return HttpResponseBadRequest("Invalid status")
    delay_reason = request.POST.get("delay_reason", "").strip()
    if new_status == ProjectStatus.DELAYED and not delay_reason:
        return HttpResponseBadRequest("delay_reason is required")
    project.status = new_status
    if new_status == ProjectStatus.DELAYED:
        project.delay_reason = delay_reason
    project.save()
    return _render_field(request, project, "_field_status.html")


@login_required
def priority_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, "projects/_field_priority_edit.html", {
        "project": project, "priority_choices": ProjectPriority.choices,
    })


@login_required
@require_http_methods(["POST"])
def priority_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    new_priority = request.POST.get("priority", "")
    if new_priority not in dict(ProjectPriority.choices):
        return HttpResponseBadRequest("Invalid priority")
    project.priority = new_priority
    project.save()
    return _render_field(request, project, "_field_priority.html")


@login_required
def dates_edit(request, pk):
    return render(request, "projects/_field_dates_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def dates_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    raw = request.POST.get("projected_completion_date", "").strip()
    if raw:
        try:
            project.projected_completion_date = dt.date.fromisoformat(raw)
        except ValueError:
            return HttpResponseBadRequest("Invalid date")
    else:
        project.projected_completion_date = None
    project.save()
    return _render_field(request, project, "_field_dates.html")


def _parse_decimal(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return "INVALID"


@login_required
def budget_edit(request, pk):
    return render(request, "projects/_field_budget_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def budget_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    b = _parse_decimal(request.POST.get("budget_amount", ""))
    a = _parse_decimal(request.POST.get("actual_cost", ""))
    if b == "INVALID" or a == "INVALID":
        return HttpResponseBadRequest("Invalid amount")
    project.budget_amount = b
    project.actual_cost = a
    project.save()
    return _render_field(request, project, "_field_budget.html")


@login_required
def vendor_edit(request, pk):
    return render(request, "projects/_field_vendor_edit.html", {
        "project": get_object_or_404(Project, pk=pk),
    })


@login_required
@require_http_methods(["POST"])
def vendor_save(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.vendor_name = request.POST.get("vendor_name", "").strip()
    bid = _parse_decimal(request.POST.get("vendor_bid_amount", ""))
    if bid == "INVALID":
        return HttpResponseBadRequest("Invalid amount")
    project.vendor_bid_amount = bid
    project.save()
    return _render_field(request, project, "_field_vendor.html")
```

- [ ] **Step 4: Edit partials — one per field**

Create `templates/projects/_field_status_edit.html`:

```html
<form id="field-status-{{ project.pk }}"
      hx-post="{% url 'projects:inline_status_save' project.pk %}"
      hx-target="this" hx-swap="outerHTML"
      class="flex flex-col gap-2">
  <select name="status" class="input">
    {% for value, label in status_choices %}
      <option value="{{ value }}" {% if project.status == value %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <textarea name="delay_reason" rows="2" placeholder="Reason if Delayed…"
    class="input">{{ project.delay_reason }}</textarea>
  <div class="flex gap-2">
    <button type="submit" class="btn-primary text-xs">Save</button>
    <button type="button" class="btn-secondary text-xs"
      hx-get="{% url 'projects:inline_status_show' project.pk %}"
      hx-target="this"
      hx-swap="outerHTML closest form">Cancel</button>
  </div>
</form>
```

Wait — the cancel button needs to swap the WHOLE form. Use `hx-target="#field-status-{{ project.pk }}"` and `hx-swap="outerHTML"`. Add a `_show` URL that returns the display partial (Step 6).

Replace the form with:

```html
<form id="field-status-{{ project.pk }}"
      hx-post="{% url 'projects:inline_status_save' project.pk %}"
      hx-target="#field-status-{{ project.pk }}" hx-swap="outerHTML"
      class="flex flex-col gap-2">
  <select name="status" class="input">
    {% for value, label in status_choices %}
      <option value="{{ value }}" {% if project.status == value %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <textarea name="delay_reason" rows="2" placeholder="Reason if Delayed…" class="input">{{ project.delay_reason }}</textarea>
  <div class="flex gap-2">
    <button type="submit" class="btn-primary text-xs">Save</button>
    <button type="button" class="btn-secondary text-xs"
      hx-get="{% url 'projects:inline_status_show' project.pk %}"
      hx-target="#field-status-{{ project.pk }}" hx-swap="outerHTML">Cancel</button>
  </div>
</form>
```

Create `templates/projects/_field_priority_edit.html`:

```html
<form id="field-priority-{{ project.pk }}"
      hx-post="{% url 'projects:inline_priority_save' project.pk %}"
      hx-target="#field-priority-{{ project.pk }}" hx-swap="outerHTML"
      class="flex gap-2">
  <select name="priority" class="input">
    {% for value, label in priority_choices %}
      <option value="{{ value }}" {% if project.priority == value %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  <button type="submit" class="btn-primary text-xs">Save</button>
  <button type="button" class="btn-secondary text-xs"
    hx-get="{% url 'projects:inline_priority_show' project.pk %}"
    hx-target="#field-priority-{{ project.pk }}" hx-swap="outerHTML">Cancel</button>
</form>
```

Create `templates/projects/_field_dates_edit.html`:

```html
<form id="field-dates-{{ project.pk }}"
      hx-post="{% url 'projects:inline_dates_save' project.pk %}"
      hx-target="#field-dates-{{ project.pk }}" hx-swap="outerHTML"
      class="flex gap-2 items-center">
  <input type="date" name="projected_completion_date"
    value="{{ project.projected_completion_date|date:'Y-m-d' }}" class="input">
  <button type="submit" class="btn-primary text-xs">Save</button>
  <button type="button" class="btn-secondary text-xs"
    hx-get="{% url 'projects:inline_dates_show' project.pk %}"
    hx-target="#field-dates-{{ project.pk }}" hx-swap="outerHTML">Cancel</button>
</form>
```

Create `templates/projects/_field_budget_edit.html`:

```html
<form id="field-budget-{{ project.pk }}"
      hx-post="{% url 'projects:inline_budget_save' project.pk %}"
      hx-target="#field-budget-{{ project.pk }}" hx-swap="outerHTML"
      class="flex gap-2 items-center">
  <input type="number" step="0.01" name="budget_amount" placeholder="Budget"
    value="{{ project.budget_amount|default_if_none:'' }}" class="input">
  <input type="number" step="0.01" name="actual_cost" placeholder="Actual"
    value="{{ project.actual_cost|default_if_none:'' }}" class="input">
  <button type="submit" class="btn-primary text-xs">Save</button>
  <button type="button" class="btn-secondary text-xs"
    hx-get="{% url 'projects:inline_budget_show' project.pk %}"
    hx-target="#field-budget-{{ project.pk }}" hx-swap="outerHTML">Cancel</button>
</form>
```

Create `templates/projects/_field_vendor_edit.html`:

```html
<form id="field-vendor-{{ project.pk }}"
      hx-post="{% url 'projects:inline_vendor_save' project.pk %}"
      hx-target="#field-vendor-{{ project.pk }}" hx-swap="outerHTML"
      class="flex gap-2 items-center">
  <input type="text" name="vendor_name" placeholder="Vendor name"
    value="{{ project.vendor_name }}" class="input">
  <input type="number" step="0.01" name="vendor_bid_amount" placeholder="Bid"
    value="{{ project.vendor_bid_amount|default_if_none:'' }}" class="input">
  <button type="submit" class="btn-primary text-xs">Save</button>
  <button type="button" class="btn-secondary text-xs"
    hx-get="{% url 'projects:inline_vendor_show' project.pk %}"
    hx-target="#field-vendor-{{ project.pk }}" hx-swap="outerHTML">Cancel</button>
</form>
```

- [ ] **Step 5: "Show" endpoints for cancel buttons**

Add to `apps/projects/views/inline.py`:

```python
@login_required
def status_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_status.html")


@login_required
def priority_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_priority.html")


@login_required
def dates_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_dates.html")


@login_required
def budget_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_budget.html")


@login_required
def vendor_show(request, pk):
    return _render_field(request, get_object_or_404(Project, pk=pk), "_field_vendor.html")
```

- [ ] **Step 6: Wire URLs**

Add to `apps/projects/views/__init__.py`:
```python
from .inline import (
    status_edit, status_save, status_show,
    priority_edit, priority_save, priority_show,
    dates_edit, dates_save, dates_show,
    budget_edit, budget_save, budget_show,
    vendor_edit, vendor_save, vendor_show,
)
```

In `apps/projects/urls.py`, add:

```python
path("<int:pk>/inline/status/edit/", views.status_edit, name="inline_status_edit"),
path("<int:pk>/inline/status/show/", views.status_show, name="inline_status_show"),
path("<int:pk>/inline/status/save/", views.status_save, name="inline_status_save"),
path("<int:pk>/inline/priority/edit/", views.priority_edit, name="inline_priority_edit"),
path("<int:pk>/inline/priority/show/", views.priority_show, name="inline_priority_show"),
path("<int:pk>/inline/priority/save/", views.priority_save, name="inline_priority_save"),
path("<int:pk>/inline/dates/edit/", views.dates_edit, name="inline_dates_edit"),
path("<int:pk>/inline/dates/show/", views.dates_show, name="inline_dates_show"),
path("<int:pk>/inline/dates/save/", views.dates_save, name="inline_dates_save"),
path("<int:pk>/inline/budget/edit/", views.budget_edit, name="inline_budget_edit"),
path("<int:pk>/inline/budget/show/", views.budget_show, name="inline_budget_show"),
path("<int:pk>/inline/budget/save/", views.budget_save, name="inline_budget_save"),
path("<int:pk>/inline/vendor/edit/", views.vendor_edit, name="inline_vendor_edit"),
path("<int:pk>/inline/vendor/show/", views.vendor_show, name="inline_vendor_show"),
path("<int:pk>/inline/vendor/save/", views.vendor_save, name="inline_vendor_save"),
```

- [ ] **Step 7: Tests pass**

```bash
uv run pytest apps/projects/tests/test_views_inline.py -v
```

Expected: 7 passed.

- [ ] **Step 8: Manual smoke test**

Rebuild Tailwind. On the project detail page, click "edit" next to each field, change the value, save. Verify the cell updates without a full page refresh.

- [ ] **Step 9: Commit**

```bash
git add apps/projects/ templates/projects/
git commit -m "feat(projects): HTMX inline edit for status/priority/dates/budget/vendor"
```

---

## Task 14: Update notes — add via HTMX

**Files:**
- Create: `apps/projects/forms/note.py`
- Create: `apps/projects/views/note.py`
- Modify: `apps/projects/forms/__init__.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_views_note.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import UpdateNote


@pytest.mark.django_db
def test_add_note(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "Met with vendor."},
    )
    assert response.status_code == 200
    assert UpdateNote.objects.filter(project=project, body="Met with vendor.").exists()


@pytest.mark.django_db
def test_add_empty_note_rejected(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "  "},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Form**

Create `apps/projects/forms/note.py`:

```python
from django import forms

from ..models import UpdateNote


class UpdateNoteForm(forms.ModelForm):
    class Meta:
        model = UpdateNote
        fields = ["body"]

    def clean_body(self):
        body = self.cleaned_data.get("body", "")
        if not body.strip():
            raise forms.ValidationError("Note body cannot be empty.")
        return body
```

Add to `apps/projects/forms/__init__.py`:
```python
from .note import UpdateNoteForm
```

- [ ] **Step 3: View**

Create `apps/projects/views/note.py`:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import UpdateNoteForm
from ..models import Project


@login_required
@require_http_methods(["POST"])
def add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = UpdateNoteForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(", ".join(form.errors.get("body", [])))
    note = form.save(commit=False)
    note.project = project
    note.author = request.user
    note.save()
    return render(request, "projects/_notes_list_swap.html", {"project": project})
```

Create `templates/projects/_notes_list_swap.html`:

```html
<ul id="notes-list-{{ project.pk }}" class="space-y-3">
  {% for n in project.notes.all %}{% include "projects/_note_card.html" %}{% empty %}
    <li class="text-sm text-gray-400">No notes yet.</li>
  {% endfor %}
</ul>
```

- [ ] **Step 4: Wire URL**

Add to `apps/projects/views/__init__.py`:
```python
from .note import add as note_add
```

In `apps/projects/urls.py`:
```python
path("<int:pk>/note/", views.note_add, name="note_add"),
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest apps/projects/tests/test_views_note.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/projects/ templates/projects/
git commit -m "feat(projects): HTMX add-note endpoint with empty-body validation"
```

---

## Task 15: Attachment upload / delete / signed-URL download

**Files:**
- Create: `apps/projects/views/attachment.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/_attachments_list_swap.html`
- Create: `apps/projects/tests/test_views_attachment.py`

- [ ] **Step 1: Failing tests (mock R2)**

Create `apps/projects/tests/test_views_attachment.py`:

```python
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.projects.models import Attachment


@pytest.fixture(autouse=True)
def stub_r2(monkeypatch):
    """Replace R2 calls with no-ops so tests don't need network."""
    from apps.projects import storage
    monkeypatch.setattr(storage, "upload_fileobj", lambda *a, **k: None)
    monkeypatch.setattr(storage, "delete_object", lambda key: None)
    monkeypatch.setattr(storage, "signed_download_url",
        lambda key, *, filename, expires_in=300: f"https://example.com/{key}")


@pytest.mark.django_db
def test_upload_pdf(auth_client, project):
    f = SimpleUploadedFile("quote.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 200
    assert Attachment.objects.filter(project=project, original_filename="quote.pdf").exists()


@pytest.mark.django_db
def test_upload_disallowed_type_rejected(auth_client, project):
    f = SimpleUploadedFile("script.exe", b"bin", content_type="application/x-msdownload")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 400
    assert b"not allowed" in response.content


@pytest.mark.django_db
def test_upload_too_large_rejected(auth_client, project, monkeypatch):
    from apps.projects import storage
    monkeypatch.setattr(storage, "PER_FILE_LIMIT", 100)
    f = SimpleUploadedFile("big.pdf", b"x" * 200, content_type="application/pdf")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 400
    assert b"10 MB" in response.content or b"per-file" in response.content


@pytest.mark.django_db
def test_delete_attachment(auth_client, project, user):
    a = Attachment.objects.create(
        project=project, file_key="x", original_filename="x.pdf",
        content_type="application/pdf", size_bytes=100, uploaded_by=user,
    )
    response = auth_client.post(reverse("projects:attachment_delete", args=[a.pk]))
    assert response.status_code == 200
    assert not Attachment.objects.filter(pk=a.pk).exists()


@pytest.mark.django_db
def test_download_redirects_to_signed_url(auth_client, project, user):
    a = Attachment.objects.create(
        project=project, file_key="key123", original_filename="x.pdf",
        content_type="application/pdf", size_bytes=100, uploaded_by=user,
    )
    response = auth_client.get(reverse("projects:attachment_download", args=[a.pk]))
    assert response.status_code == 302
    assert "key123" in response.url
```

- [ ] **Step 2: View**

Create `apps/projects/views/attachment.py`:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .. import storage
from ..models import Attachment, Project


@login_required
@require_http_methods(["POST"])
def upload(request, pk):
    project = get_object_or_404(Project, pk=pk)
    file = request.FILES.get("file")
    if file is None:
        return HttpResponseBadRequest("No file provided.")
    project_total = Attachment.total_bytes_for_project(project)
    try:
        storage.validate_upload(
            filename=file.name,
            content_type=file.content_type or "",
            size_bytes=file.size,
            project_total=project_total,
        )
    except storage.AttachmentValidationError as e:
        return HttpResponseBadRequest(str(e))
    key = storage.build_object_key(project_id=project.pk, filename=file.name)
    storage.upload_fileobj(file, key, file.content_type or "application/octet-stream")
    Attachment.objects.create(
        project=project,
        file_key=key,
        original_filename=file.name,
        content_type=file.content_type or "",
        size_bytes=file.size,
        uploaded_by=request.user,
    )
    return render(request, "projects/_attachments_list_swap.html", {"project": project})


@login_required
@require_http_methods(["POST"])
def delete(request, pk):
    a = get_object_or_404(Attachment, pk=pk)
    project = a.project
    storage.delete_object(a.file_key)
    a.delete()
    return render(request, "projects/_attachments_list_swap.html", {"project": project})


@login_required
def download(request, pk):
    a = get_object_or_404(Attachment, pk=pk)
    url = storage.signed_download_url(a.file_key, filename=a.original_filename)
    return redirect(url)
```

Create `templates/projects/_attachments_list_swap.html`:

```html
<ul id="attachments-list-{{ project.pk }}" class="space-y-2 mb-3">
  {% for f in project.attachments.all %}{% include "projects/_attachment_row.html" %}{% empty %}
    <li class="text-sm text-gray-400">No files attached.</li>
  {% endfor %}
</ul>
```

- [ ] **Step 3: Wire URLs**

Add to `apps/projects/views/__init__.py`:
```python
from .attachment import upload as attachment_upload, delete as attachment_delete, download as attachment_download
```

In `apps/projects/urls.py`:
```python
path("<int:pk>/attachment/upload/", views.attachment_upload, name="attachment_upload"),
path("attachment/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
path("attachment/<int:pk>/download/", views.attachment_download, name="attachment_download"),
```

- [ ] **Step 4: Tests**

```bash
uv run pytest apps/projects/tests/test_views_attachment.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/projects/ templates/projects/
git commit -m "feat(projects): attachment upload/delete/signed-URL download via R2"
```

---

## Task 16: RACI add / remove + Board approval add/edit

**Files:**
- Create: `apps/projects/views/raci.py`
- Create: `apps/projects/views/approval.py`
- Create: `apps/projects/forms/approval.py`
- Modify: `apps/projects/views/__init__.py`, `forms/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/_raci_list_swap.html`
- Create: `templates/projects/approval_form.html`
- Create: `apps/projects/tests/test_views_raci.py`
- Create: `apps/projects/tests/test_views_approval.py`

- [ ] **Step 1: RACI tests**

Create `apps/projects/tests/test_views_raci.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import RACIAssignment, RACIRole


@pytest.mark.django_db
def test_add_raci(auth_client, project, person):
    response = auth_client.post(
        reverse("projects:raci_add", args=[project.pk]),
        {"person": person.pk, "role": RACIRole.RESPONSIBLE},
    )
    assert response.status_code == 200
    assert RACIAssignment.objects.filter(project=project, person=person).exists()


@pytest.mark.django_db
def test_add_duplicate_role_rejected(auth_client, project, person):
    RACIAssignment.objects.create(project=project, person=person, role=RACIRole.RESPONSIBLE)
    response = auth_client.post(
        reverse("projects:raci_add", args=[project.pk]),
        {"person": person.pk, "role": RACIRole.RESPONSIBLE},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_remove_raci(auth_client, project, person):
    a = RACIAssignment.objects.create(project=project, person=person, role=RACIRole.CONSULTED)
    response = auth_client.post(reverse("projects:raci_remove", args=[a.pk]))
    assert response.status_code == 200
    assert not RACIAssignment.objects.filter(pk=a.pk).exists()
```

- [ ] **Step 2: RACI view**

Create `apps/projects/views/raci.py`:

```python
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.roster.models import RosterPerson

from ..models import Project, RACIAssignment, RACIRole


def _render_list(request, project):
    return render(request, "projects/_raci_list_swap.html", {
        "project": project,
        "raci_role_choices": RACIRole.choices,
        "available_people": RosterPerson.active.exclude(
            raci_assignments__project=project,
        ).distinct(),
    })


@login_required
@require_http_methods(["POST"])
def add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    person_id = request.POST.get("person", "").strip()
    role = request.POST.get("role", "")
    if not person_id.isdigit() or role not in dict(RACIRole.choices):
        return HttpResponseBadRequest("Invalid person or role")
    person = get_object_or_404(RosterPerson, pk=int(person_id))
    if person.archived:
        return HttpResponseBadRequest("Cannot assign archived person to a new role.")
    try:
        RACIAssignment.objects.create(project=project, person=person, role=role)
    except IntegrityError:
        return HttpResponseBadRequest("That person is already in that role.")
    return _render_list(request, project)


@login_required
@require_http_methods(["POST"])
def remove(request, pk):
    a = get_object_or_404(RACIAssignment, pk=pk)
    project = a.project
    a.delete()
    return _render_list(request, project)
```

Create `templates/projects/_raci_list_swap.html`:

```html
<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">RACI</h2>
  <ul id="raci-list-{{ project.pk }}" class="space-y-1 mb-3">
    {% for a in project.raci_assignments.all %}{% include "projects/_raci_row.html" %}{% empty %}
      <li class="text-sm text-gray-400">No assignments yet.</li>
    {% endfor %}
  </ul>
  <form hx-post="{% url 'projects:raci_add' project.pk %}"
        hx-target="closest section" hx-swap="outerHTML"
        class="flex gap-2 text-sm">
    {% csrf_token %}
    <select name="person" class="input flex-1">
      <option value="">Select person…</option>
      {% for p in available_people %}<option value="{{ p.pk }}">{{ p.name }}</option>{% endfor %}
    </select>
    <select name="role" class="input">
      {% for value, label in raci_role_choices %}<option value="{{ value }}">{{ label }}</option>{% endfor %}
    </select>
    <button type="submit" class="btn-secondary">Add</button>
  </form>
</section>
```

Adjust `_raci_row.html` to swap the parent section instead of just the list:
- Change `hx-target="#raci-list-{{ project.pk }}"` → `hx-target="closest section"`
- Change `hx-swap="outerHTML"` (already present)

And update the original `_raci_section.html` form `hx-target` similarly.

- [ ] **Step 3: Approval tests**

Create `apps/projects/tests/test_views_approval.py`:

```python
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import BoardApproval


@pytest.mark.django_db
def test_add_approval(auth_client, project):
    response = auth_client.post(
        reverse("projects:approval_add", args=[project.pk]),
        {
            "motion_text": "Approve $40k for sprinklers.",
            "vote_date": "2026-04-15",
            "votes_for": 4, "votes_against": 0, "votes_abstain": 1,
            "minutes_reference": "Apr 2026, p. 3",
        },
    )
    assert response.status_code == 302
    assert BoardApproval.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_edit_approval(auth_client, project):
    BoardApproval.objects.create(
        project=project, motion_text="Old", vote_date=dt.date(2026, 4, 15),
        votes_for=3, votes_against=2, votes_abstain=0,
    )
    response = auth_client.post(
        reverse("projects:approval_edit", args=[project.pk]),
        {
            "motion_text": "New motion",
            "vote_date": "2026-05-15",
            "votes_for": 5, "votes_against": 0, "votes_abstain": 0,
        },
    )
    assert response.status_code == 302
    project.board_approval.refresh_from_db()
    assert project.board_approval.motion_text == "New motion"
```

- [ ] **Step 4: Approval form + view**

Create `apps/projects/forms/approval.py`:

```python
from django import forms

from ..models import BoardApproval

_INPUT = {"class": "input"}


class BoardApprovalForm(forms.ModelForm):
    class Meta:
        model = BoardApproval
        fields = ["motion_text", "vote_date", "votes_for", "votes_against",
                  "votes_abstain", "minutes_reference"]
        widgets = {
            "motion_text": forms.Textarea(attrs={**_INPUT, "rows": 3}),
            "vote_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
            "votes_for": forms.NumberInput(attrs=_INPUT),
            "votes_against": forms.NumberInput(attrs=_INPUT),
            "votes_abstain": forms.NumberInput(attrs=_INPUT),
            "minutes_reference": forms.TextInput(attrs=_INPUT),
        }
```

Add to `apps/projects/forms/__init__.py`:
```python
from .approval import BoardApprovalForm
```

Create `apps/projects/views/approval.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import BoardApprovalForm
from ..models import BoardApproval, Project


@login_required
def add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if hasattr(project, "board_approval"):
        return redirect("projects:approval_edit", pk=project.pk)
    if request.method == "POST":
        form = BoardApprovalForm(request.POST)
        if form.is_valid():
            approval = form.save(commit=False)
            approval.project = project
            approval.save()
            messages.success(request, "Board approval recorded.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = BoardApprovalForm()
    return render(request, "projects/approval_form.html", {"form": form, "project": project, "is_new": True})


@login_required
def edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    approval = get_object_or_404(BoardApproval, project=project)
    if request.method == "POST":
        form = BoardApprovalForm(request.POST, instance=approval)
        if form.is_valid():
            form.save()
            messages.success(request, "Approval updated.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = BoardApprovalForm(instance=approval)
    return render(request, "projects/approval_form.html", {"form": form, "project": project, "is_new": False})
```

Create `templates/projects/approval_form.html`:

```html
{% extends "base.html" %}
{% block title %}{% if is_new %}Add{% else %}Edit{% endif %} approval — {{ project.title }}{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">
  {% if is_new %}Record board approval{% else %}Edit board approval{% endif %}
</h1>
<form method="post" class="bg-white rounded-lg shadow p-6 max-w-2xl space-y-4">
  {% csrf_token %}
  {% for field in form %}
    <div>
      <label class="label" for="{{ field.id_for_label }}">{{ field.label }}</label>
      {{ field }}
      {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
    </div>
  {% endfor %}
  <div class="flex gap-2 pt-2">
    <button type="submit" class="btn-primary">Save</button>
    <a href="{% url 'projects:detail' project.pk %}" class="btn-secondary">Cancel</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 5: Wire URLs**

Add to `apps/projects/views/__init__.py`:
```python
from .raci import add as raci_add, remove as raci_remove
from .approval import add as approval_add, edit as approval_edit
```

In `apps/projects/urls.py`:
```python
path("<int:pk>/raci/add/", views.raci_add, name="raci_add"),
path("raci/<int:pk>/remove/", views.raci_remove, name="raci_remove"),
path("<int:pk>/approval/add/", views.approval_add, name="approval_add"),
path("<int:pk>/approval/edit/", views.approval_edit, name="approval_edit"),
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest apps/projects/tests/test_views_raci.py apps/projects/tests/test_views_approval.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add apps/projects/ templates/projects/
git commit -m "feat(projects): RACI add/remove + board approval add/edit"
```

---

## Task 17: Recurring templates page + management command

**Files:**
- Create: `apps/projects/recurring.py` (cadence math)
- Create: `apps/projects/management/commands/generate_recurring_instances.py`
- Create: `apps/projects/forms/recurring.py`
- Create: `apps/projects/views/recurring.py`
- Modify: `apps/projects/forms/__init__.py`, `views/__init__.py`, `urls.py`
- Create: `templates/projects/recurring_list.html`
- Create: `templates/projects/recurring_form.html`
- Create: `apps/projects/tests/test_recurring.py` (cadence math)
- Create: `apps/projects/tests/test_recurring_command.py`
- Create: `apps/projects/tests/test_views_recurring.py`
- Modify: `templates/_sidebar.html`

- [ ] **Step 1: Failing cadence-math tests**

Create `apps/projects/tests/test_recurring.py`:

```python
import datetime as dt

import pytest

from apps.projects.recurring import advance, suffix_for


@pytest.mark.parametrize("rule,start,expected", [
    ("weekly", dt.date(2026, 5, 5), dt.date(2026, 5, 12)),
    ("monthly", dt.date(2026, 5, 5), dt.date(2026, 6, 5)),
    ("monthly", dt.date(2026, 1, 31), dt.date(2026, 2, 28)),
    ("quarterly", dt.date(2026, 5, 5), dt.date(2026, 8, 5)),
    ("semiannual", dt.date(2026, 5, 5), dt.date(2026, 11, 5)),
    ("annual", dt.date(2026, 5, 5), dt.date(2027, 5, 5)),
])
def test_advance(rule, start, expected):
    assert advance(rule, start) == expected


@pytest.mark.parametrize("rule,date,expected", [
    ("weekly", dt.date(2026, 4, 6), "Week of 2026-04-06"),
    ("monthly", dt.date(2026, 4, 1), "April 2026"),
    ("quarterly", dt.date(2026, 4, 1), "Q2 2026"),
    ("quarterly", dt.date(2026, 7, 1), "Q3 2026"),
    ("semiannual", dt.date(2026, 1, 1), "H1 2026"),
    ("semiannual", dt.date(2026, 7, 1), "H2 2026"),
    ("annual", dt.date(2026, 4, 1), "2026"),
])
def test_suffix(rule, date, expected):
    assert suffix_for(rule, date) == expected
```

- [ ] **Step 2: Cadence module**

Create `apps/projects/recurring.py`:

```python
import datetime as dt

from dateutil.relativedelta import relativedelta


def advance(rule: str, start: dt.date) -> dt.date:
    if rule == "weekly":
        return start + dt.timedelta(weeks=1)
    if rule == "monthly":
        return start + relativedelta(months=1)
    if rule == "quarterly":
        return start + relativedelta(months=3)
    if rule == "semiannual":
        return start + relativedelta(months=6)
    if rule == "annual":
        return start + relativedelta(years=1)
    raise ValueError(f"Unknown rule: {rule}")


def suffix_for(rule: str, date: dt.date) -> str:
    if rule == "weekly":
        return f"Week of {date.isoformat()}"
    if rule == "monthly":
        return f"{date.strftime('%B')} {date.year}"
    if rule == "quarterly":
        q = (date.month - 1) // 3 + 1
        return f"Q{q} {date.year}"
    if rule == "semiannual":
        h = 1 if date.month <= 6 else 2
        return f"H{h} {date.year}"
    if rule == "annual":
        return f"{date.year}"
    raise ValueError(f"Unknown rule: {rule}")
```

```bash
uv run pytest apps/projects/tests/test_recurring.py -v
```

Expected: all parametrized cases pass.

- [ ] **Step 3: Failing command tests**

Create `apps/projects/tests/test_recurring_command.py`:

```python
import datetime as dt
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.projects.models import (
    Project, RACIAssignment, RACIRole, RecurrenceRule,
)


@pytest.fixture
def template(user, category, person):
    t = Project.objects.create(
        title="Financial review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 5, 1),
    )
    RACIAssignment.objects.create(project=t, person=person, role=RACIRole.RESPONSIBLE)
    return t


@pytest.mark.django_db
def test_generates_one_instance_when_due(template):
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")

    template.refresh_from_db()
    instance = Project.instances.filter(parent_template=template).first()
    assert instance is not None
    assert instance.title == "Financial review — May 2026"
    assert instance.is_recurring_template is False
    raci = instance.raci_assignments.first()
    assert raci is not None
    assert template.next_due_date == dt.date(2026, 6, 1)


@pytest.mark.django_db
def test_idempotent_in_same_day(template):
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
        call_command("generate_recurring_instances")

    assert Project.instances.filter(parent_template=template).count() == 1


@pytest.mark.django_db
def test_catches_up_after_missed_cycles(template):
    template.next_due_date = dt.date(2026, 2, 1)
    template.save()
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
    template.refresh_from_db()
    assert Project.instances.filter(parent_template=template).count() == 4
    assert template.next_due_date == dt.date(2026, 6, 1)


@pytest.mark.django_db
def test_paused_template_skipped(template):
    template.is_active = False
    template.save()
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 6, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
    assert Project.instances.filter(parent_template=template).count() == 0
```

- [ ] **Step 4: Management command**

Create `apps/projects/management/commands/generate_recurring_instances.py`:

```python
import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import (
    Project, ProjectStatus, RACIAssignment,
)
from apps.projects.recurring import advance, suffix_for


class Command(BaseCommand):
    help = "Generate Project instances from active recurring templates whose next_due_date is today or earlier."

    def handle(self, *args, **options):
        today = dt.date.today()
        templates = Project.templates.filter(
            is_active=True,
            next_due_date__lte=today,
        )
        total = 0
        for template in templates:
            total += self._catch_up(template, today)
        self.stdout.write(self.style.SUCCESS(f"Generated {total} instance(s)."))

    @transaction.atomic
    def _catch_up(self, template: Project, today: dt.date) -> int:
        if not template.recurrence_rule or not template.next_due_date:
            return 0
        count = 0
        while template.next_due_date and template.next_due_date <= today:
            self._make_instance(template, template.next_due_date)
            template.next_due_date = advance(template.recurrence_rule, template.next_due_date)
            count += 1
        template.save()
        return count

    def _make_instance(self, template: Project, due: dt.date) -> Project:
        suffix = suffix_for(template.recurrence_rule, due)
        title = f"{template.title} — {suffix}"
        next_due = advance(template.recurrence_rule, due)

        instance = Project.objects.create(
            title=title,
            description=template.description,
            category=template.category,
            status=ProjectStatus.NOT_STARTED,
            priority=template.priority,
            projected_completion_date=next_due,
            is_recurring_template=False,
            is_active=True,
            parent_template=template,
            created_by=template.created_by,
        )
        instance.tags.set(template.tags.all())
        for raci in template.raci_assignments.all():
            RACIAssignment.objects.create(
                project=instance, person=raci.person, role=raci.role,
            )
        return instance
```

```bash
uv run pytest apps/projects/tests/test_recurring_command.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Recurring template form + views**

Create `apps/projects/forms/recurring.py`:

```python
from django import forms

from ..models import Project, RecurrenceRule


_INPUT = {"class": "input"}
_TEXTAREA = {"class": "input", "rows": 4}


class RecurringTemplateForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "category", "priority",
                  "recurrence_rule", "next_due_date", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs=_INPUT),
            "description": forms.Textarea(attrs=_TEXTAREA),
            "category": forms.Select(attrs=_INPUT),
            "priority": forms.Select(attrs=_INPUT),
            "recurrence_rule": forms.Select(attrs=_INPUT),
            "next_due_date": forms.DateInput(attrs={**_INPUT, "type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("recurrence_rule"):
            self.add_error("recurrence_rule", "Required for recurring templates.")
        if not cleaned.get("next_due_date"):
            self.add_error("next_due_date", "Required for recurring templates.")
        return cleaned
```

Add to `forms/__init__.py`:
```python
from .recurring import RecurringTemplateForm
```

Create `apps/projects/views/recurring.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import RecurringTemplateForm
from ..models import Project


@login_required
def list_view(request):
    templates = Project.templates.select_related("category").order_by("title")
    return render(request, "projects/recurring_list.html", {"templates": templates})


@login_required
def create(request):
    if request.method == "POST":
        form = RecurringTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.is_recurring_template = True
            template.created_by = request.user
            template.save()
            messages.success(request, "Recurring template created.")
            return redirect("projects:recurring_list")
    else:
        form = RecurringTemplateForm()
    return render(request, "projects/recurring_form.html", {"form": form, "template": None})


@login_required
def edit(request, pk):
    template = get_object_or_404(Project, pk=pk, is_recurring_template=True)
    if request.method == "POST":
        form = RecurringTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("projects:recurring_list")
    else:
        form = RecurringTemplateForm(instance=template)
    return render(request, "projects/recurring_form.html", {"form": form, "template": template})


@login_required
def toggle(request, pk):
    if request.method != "POST":
        return redirect("projects:recurring_list")
    template = get_object_or_404(Project, pk=pk, is_recurring_template=True)
    template.is_active = not template.is_active
    template.save()
    messages.success(request, ("Resumed" if template.is_active else "Paused") + f" {template.title}")
    return redirect("projects:recurring_list")
```

Add to `views/__init__.py`:
```python
from .recurring import list_view as recurring_list, create as recurring_create, edit as recurring_edit, toggle as recurring_toggle
```

In `urls.py`:
```python
path("recurring/", views.recurring_list, name="recurring_list"),
path("recurring/new/", views.recurring_create, name="recurring_create"),
path("recurring/<int:pk>/edit/", views.recurring_edit, name="recurring_edit"),
path("recurring/<int:pk>/toggle/", views.recurring_toggle, name="recurring_toggle"),
```

- [ ] **Step 6: Templates**

Create `templates/projects/recurring_list.html`:

```html
{% extends "base.html" %}
{% block title %}Recurring — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Recurring templates</h1>
  <a href="{% url 'projects:recurring_create' %}" class="btn-primary">+ New template</a>
</div>

{% if templates %}
<div class="bg-white rounded-lg shadow overflow-hidden">
<table class="min-w-full divide-y divide-gray-200 text-sm">
  <thead class="bg-gray-50 text-xs uppercase text-gray-500">
    <tr>
      <th class="px-3 py-2 text-left">Title</th>
      <th class="px-3 py-2 text-left">Cadence</th>
      <th class="px-3 py-2 text-left">Next due</th>
      <th class="px-3 py-2 text-left">Status</th>
      <th class="px-3 py-2"></th>
    </tr>
  </thead>
  <tbody class="divide-y divide-gray-100">
    {% for t in templates %}
      <tr>
        <td class="px-3 py-3"><a class="text-blue-700 hover:underline" href="{% url 'projects:recurring_edit' t.pk %}">{{ t.title }}</a></td>
        <td class="px-3 py-3">{{ t.get_recurrence_rule_display }}</td>
        <td class="px-3 py-3">{{ t.next_due_date|default:"—" }}</td>
        <td class="px-3 py-3">{% if t.is_active %}<span class="pill bg-green-100 text-green-800">Active</span>{% else %}<span class="pill bg-gray-200 text-gray-700">Paused</span>{% endif %}</td>
        <td class="px-3 py-3 text-right">
          <form method="post" action="{% url 'projects:recurring_toggle' t.pk %}" class="inline">
            {% csrf_token %}
            <button class="text-xs text-blue-600 hover:underline">{% if t.is_active %}Pause{% else %}Resume{% endif %}</button>
          </form>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
</div>
{% else %}
<div class="bg-white rounded-lg shadow p-8 text-center">
  <p class="text-gray-500 mb-4">No recurring templates yet.</p>
  <a href="{% url 'projects:recurring_create' %}" class="btn-primary">+ Create your first template</a>
</div>
{% endif %}
{% endblock %}
```

Create `templates/projects/recurring_form.html`:

```html
{% extends "base.html" %}
{% block title %}{% if template %}Edit{% else %}New{% endif %} recurring template{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">
  {% if template %}Edit {{ template.title }}{% else %}New recurring template{% endif %}
</h1>
<form method="post" class="bg-white rounded-lg shadow p-6 max-w-2xl space-y-4">
  {% csrf_token %}
  {% for field in form %}
    <div>
      <label class="label" for="{{ field.id_for_label }}">{{ field.label }}</label>
      {% if field.name == "is_active" %}
        <label class="flex items-center gap-2 text-sm"><input type="checkbox" name="is_active" {% if form.is_active.value %}checked{% endif %}> Active (will generate instances)</label>
      {% else %}
        {{ field }}
      {% endif %}
      {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
    </div>
  {% endfor %}
  <div class="flex gap-2 pt-2">
    <button type="submit" class="btn-primary">Save</button>
    <a href="{% url 'projects:recurring_list' %}" class="btn-secondary">Cancel</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 7: View tests**

Create `apps/projects/tests/test_views_recurring.py`:

```python
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, RecurrenceRule


@pytest.mark.django_db
def test_list_renders_only_templates(auth_client, user, category):
    Project.objects.create(title="Plain", category=category, created_by=user)
    Project.objects.create(
        title="Template", category=category, created_by=user,
        is_recurring_template=True, recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 6, 1),
    )
    response = auth_client.get(reverse("projects:recurring_list"))
    assert b"Template" in response.content
    assert b"Plain" not in response.content


@pytest.mark.django_db
def test_create_template(auth_client, category):
    response = auth_client.post(reverse("projects:recurring_create"), {
        "title": "Monthly review",
        "description": "",
        "category": category.pk,
        "priority": "medium",
        "recurrence_rule": "monthly",
        "next_due_date": "2026-06-01",
        "is_active": "on",
    })
    assert response.status_code == 302
    assert Project.templates.filter(title="Monthly review").exists()


@pytest.mark.django_db
def test_pause_template(auth_client, user, category):
    t = Project.objects.create(
        title="X", category=category, created_by=user,
        is_recurring_template=True, recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 6, 1), is_active=True,
    )
    response = auth_client.post(reverse("projects:recurring_toggle", args=[t.pk]))
    assert response.status_code == 302
    t.refresh_from_db()
    assert t.is_active is False
```

```bash
uv run pytest apps/projects/tests/test_views_recurring.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Sidebar link**

Add to `templates/_sidebar.html` after Projects:
```html
<a href="{% url 'projects:recurring_list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Recurring</a>
```

- [ ] **Step 9: Commit**

```bash
git add apps/projects/ templates/
git commit -m "feat(projects): recurring templates CRUD + idempotent generator command"
```

---

## Task 18: Fly.io cron for daily generator

**Files:**
- Modify: `fly.toml`
- Create: `Dockerfile.cron` (optional — see step 1)
- Modify: `Dockerfile` (already supports the command)

- [ ] **Step 1: Add a cron process group**

Single Dockerfile, two process groups in `fly.toml`. Replace `fly.toml` `[processes]` (add a section) and `[[vm]]` (one per process):

```toml
[processes]
  app = "uv run gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"
  cron = "uv run python manage.py generate_recurring_instances"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
  processes = ["app"]

[[http_service]]
  internal_port = 8000
  force_https = true
  processes = ["app"]
```

Remove the old `CMD` from the Dockerfile (or leave it — `fly.toml` `[processes]` overrides it for `app`).

- [ ] **Step 2: Schedule the cron**

Fly's "scheduled machines" feature runs a process group on a cron expression. Use `fly machine run` to create a one-shot machine, OR use Fly's `[[machines]]` declaration. Fly's recommended pattern as of 2026 is **scheduled machines via the `--schedule` flag**:

```bash
fly machine run . --schedule daily --process-group cron --app hoa-task-manager-staging
```

This creates a machine that runs the `cron` process every 24 hours. Verify with:

```bash
fly machine list --app hoa-task-manager-staging
```

You should see two machines: one for `app`, one for `cron` (with a "scheduled" badge). The cron machine starts, runs the command, and exits.

If the `--schedule` flag is unavailable in the deployer's `flyctl` version, fall back to a separate Fly app with `[[services]]` removed and a periodic command — but that's more complex. The single-app process-group pattern is preferred.

- [ ] **Step 3: Verify the command runs**

Manually:
```bash
fly ssh console --app hoa-task-manager-staging --process-group cron -C "uv run python manage.py generate_recurring_instances"
```

Expected: `Generated N instance(s).` Verify in the staging UI that any due templates produced instances.

- [ ] **Step 4: Commit**

```bash
git add fly.toml Dockerfile
git commit -m "deploy: add cron process group for daily generator"
```

---

## Task 19: Dashboard

**Files:**
- Create: `apps/projects/views/dashboard.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `config/urls.py` (replace home view with projects.dashboard)
- Replace: `templates/home.html` (or create new and remove old)
- Create: `apps/projects/tests/test_views_dashboard.py`

- [ ] **Step 1: Failing tests**

Create `apps/projects/tests/test_views_dashboard.py`:

```python
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_dashboard_renders(auth_client):
    response = auth_client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Dashboard" in response.content


@pytest.mark.django_db
def test_dashboard_shows_overdue(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="OldOverdue", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=5),
    )
    response = auth_client.get(reverse("home"))
    assert b"OldOverdue" in response.content


@pytest.mark.django_db
def test_dashboard_excludes_templates(auth_client, user, category):
    Project.objects.create(
        title="TemplateOnly", category=category, created_by=user,
        is_recurring_template=True,
    )
    response = auth_client.get(reverse("home"))
    assert b"TemplateOnly" not in response.content
```

- [ ] **Step 2: View**

Create `apps/projects/views/dashboard.py`:

```python
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from ..models import ActivityLog, Project, ProjectStatus


@login_required
def dashboard(request):
    today = dt.date.today()
    horizon = today + dt.timedelta(days=14)
    base = Project.instances.exclude(status=ProjectStatus.COMPLETED)

    overdue = list(base.filter(projected_completion_date__lt=today)
                       .order_by("projected_completion_date")[:20])
    upcoming = list(base.filter(
        projected_completion_date__gte=today,
        projected_completion_date__lte=horizon,
    ).order_by("projected_completion_date")[:20])

    in_progress_count = base.filter(status=ProjectStatus.IN_PROGRESS).count()

    first_of_month = today.replace(day=1)
    done_this_month = Project.instances.filter(
        status=ProjectStatus.COMPLETED,
        actual_completion_date__gte=first_of_month,
    ).count()

    activity = ActivityLog.objects.select_related("actor", "project")[:10]

    return render(request, "home.html", {
        "stats": {
            "overdue": len(overdue),
            "upcoming": len(upcoming),
            "in_progress": in_progress_count,
            "done_this_month": done_this_month,
        },
        "overdue": overdue,
        "upcoming": upcoming,
        "activity": activity,
    })
```

- [ ] **Step 3: Wire URL — replace the placeholder home view**

In `config/urls.py`, remove the existing `home` view and import from projects:

```python
from apps.projects.views.dashboard import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("roster/", include("apps.roster.urls", namespace="roster")),
    path("projects/", include("apps.projects.urls", namespace="projects")),
    path("", dashboard, name="home"),
]
```

- [ ] **Step 4: Replace home.html with the dashboard layout**

Replace `templates/home.html`:

```html
{% extends "base.html" %}
{% load humanize %}
{% block title %}Dashboard — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-6">Dashboard</h1>

<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Overdue</div>
    <div class="text-3xl font-semibold {% if stats.overdue %}text-red-700{% endif %}">{{ stats.overdue }}</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Upcoming (14d)</div>
    <div class="text-3xl font-semibold">{{ stats.upcoming }}</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">In progress</div>
    <div class="text-3xl font-semibold">{{ stats.in_progress }}</div>
  </div>
  <div class="bg-white rounded-lg shadow p-4">
    <div class="text-xs uppercase text-gray-500">Done this month</div>
    <div class="text-3xl font-semibold">{{ stats.done_this_month }}</div>
  </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
  <section class="bg-white rounded-lg shadow p-5">
    <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Overdue</h2>
    {% if overdue %}
      <ul class="divide-y divide-gray-100">
        {% for p in overdue %}
        <li class="py-2 flex items-center justify-between text-sm">
          <a class="text-blue-700 hover:underline" href="{% url 'projects:detail' p.pk %}">{{ p.title }}</a>
          <span class="text-red-700">{{ p.projected_completion_date }}</span>
        </li>
        {% endfor %}
      </ul>
    {% else %}<p class="text-gray-400 text-sm">Nothing overdue. Nice.</p>{% endif %}
  </section>

  <section class="bg-white rounded-lg shadow p-5">
    <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Upcoming (next 14 days)</h2>
    {% if upcoming %}
      <ul class="divide-y divide-gray-100">
        {% for p in upcoming %}
        <li class="py-2 flex items-center justify-between text-sm">
          <a class="text-blue-700 hover:underline" href="{% url 'projects:detail' p.pk %}">{{ p.title }}</a>
          <span class="text-gray-700">{{ p.projected_completion_date }}</span>
        </li>
        {% endfor %}
      </ul>
    {% else %}<p class="text-gray-400 text-sm">Nothing on deck.</p>{% endif %}
  </section>
</div>

<section class="bg-white rounded-lg shadow p-5">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Recent activity</h2>
  <ul class="space-y-2 text-sm">
    {% for log in activity %}
      <li>
        <span class="text-gray-500">{{ log.created_at|date:"M j · g:i A" }}</span> —
        <strong>{{ log.actor.email|default:log.actor.username }}</strong> {{ log.verb }}
        {% if log.project %}on <a class="text-blue-700 hover:underline" href="{% url 'projects:detail' log.project.pk %}">{{ log.project.title }}</a>{% endif %}
      </li>
    {% empty %}<li class="text-gray-400">No activity yet.</li>{% endfor %}
  </ul>
</section>
{% endblock %}
```

- [ ] **Step 5: Tests + manual smoke**

```bash
uv run pytest apps/projects/tests/test_views_dashboard.py -v
```

Expected: 3 passed. Then full run:

```bash
uv run pytest -v
```

All green.

- [ ] **Step 6: Commit + deploy**

```bash
git add apps/projects/ config/urls.py templates/home.html
git commit -m "feat(projects): dashboard with stats, overdue/upcoming, recent activity"
git push origin main
```

Watch the deploy land on staging. Manually click through: log in, create project, change status, add note, upload PDF, view dashboard, view recurring, pause/resume a template.

---

## Self-Review (Plan 2 part 2)

**Spec coverage:**
- Attachment model with R2 storage, validation, signed URLs ✓
- Project list with filters, search, sort, default-excludes-completed-and-templates ✓
- Project detail two-column layout, RACI/approval/attachments/notes/activity ✓
- Inline HTMX edit for status/priority/dates/budget/vendor ✓
- Delay banner when status=delayed ✓
- Notes with markdown ✓ (rendering happens via `rendered_html` property)
- RACI add/remove with archived-blocked-from-new ✓
- Board approval add/edit, one-per-project ✓
- Recurring templates CRUD + pause + idempotent generator ✓
- Cron process group on Fly ✓
- Dashboard with 4-card strip + overdue/upcoming + activity ✓

**Placeholder scan:** None. The split into part 1 / part 2 is structural, not a TODO.

**Type consistency:**
- All URL names match between view re-exports, urls.py, and templates: `projects:list`, `projects:detail`, `projects:create`, `projects:edit`, `projects:inline_*_edit`, `projects:inline_*_save`, `projects:inline_*_show`, `projects:raci_add`, `projects:raci_remove`, `projects:approval_add`, `projects:approval_edit`, `projects:attachment_upload`, `projects:attachment_delete`, `projects:attachment_download`, `projects:note_add`, `projects:recurring_list`, `projects:recurring_create`, `projects:recurring_edit`, `projects:recurring_toggle`.
- `Project.instances` excludes templates, used by list/dashboard.
- `Project.templates` is templates-only, used by recurring_list and the cron command.
- HTMX swap targets always use `id="field-{kind}-{pk}"` and the partial that swaps in carries the same id.

**Spec items deferred to Plan 3:**
- Monthly report view, MonthlyReportSummary, copy-to-clipboard
- litestream backups
- Production Fly app (this Plan 2 deploys to staging only — same staging app from Plan 1)
- Tagged-release promotion to prod

---

## Execution Handoff

Plan complete (parts 1 + 2). Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — run tasks in this session with checkpoints.

Tasks 1–8 from `2026-05-05-hoa-projects.md`, then Tasks 9–19 from this file. Which approach?
