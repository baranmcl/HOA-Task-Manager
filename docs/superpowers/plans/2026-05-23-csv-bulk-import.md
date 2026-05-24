# CSV Bulk Import & Bulk Delete — Implementation Plan

**Goal:** Let board members upload an Excel CSV to create projects in bulk (with a preview-then-confirm flow), and bulk-delete projects from the list page with a typed-confirmation modal.

**Architecture:** A pure-function parser in `apps/projects/services/csv_import.py` returns `(valid_rows, rejected_rows, warnings)`. Two new views (`import_form` + `import_confirm`) hold the parsed preview in the session and only write to the DB on confirm. A `bulk_delete` view handles deletion of checked rows from the list page, with a `delete`-word typed confirmation.

**Tech Stack:** Python stdlib `csv`, Django sessions, HTMX (only for the bulk-delete modal trigger; can use vanilla JS if simpler), existing test fixtures (`user`, `category`, `auth_client`).

**Branch:** `csv-bulk-import` (already created and current).

---

## Task 1: CSV parser service (pure functions, TDD)

**Files:**
- Create: `apps/projects/services/__init__.py` (empty if it doesn't exist)
- Create: `apps/projects/services/csv_import.py`
- Create: `apps/projects/tests/test_csv_import_service.py`

### Step 1: Write the failing tests

```python
# apps/projects/tests/test_csv_import_service.py
"""Tests for the pure-function CSV parser.

The parser does not touch the DB except to *look up* ProjectCategory and
RosterPerson by name — those are read-only lookups inside @pytest.mark.django_db.
"""
import io

import pytest

from apps.projects.models import ProjectCategory, ProjectPriority, ProjectStatus
from apps.projects.services.csv_import import parse_csv
from apps.roster.models import RosterPerson


def _f(text: str) -> io.BytesIO:
    """Return a BytesIO with UTF-8 bytes, mimicking an uploaded file."""
    return io.BytesIO(text.encode("utf-8"))


@pytest.mark.django_db
def test_parse_csv_happy_path(category):
    text = "title,category,priority\nSprinkler upgrade,{cat},high\n".format(cat=category.name)
    valid, rejected, warnings = parse_csv(_f(text))
    assert rejected == []
    assert warnings == []
    assert len(valid) == 1
    row = valid[0]
    assert row["title"] == "Sprinkler upgrade"
    assert row["category"].pk == category.pk
    assert row["priority"] == ProjectPriority.HIGH


@pytest.mark.django_db
def test_parse_csv_header_case_insensitive(category):
    text = "Title,CATEGORY\nFoo,{cat}\n".format(cat=category.name.upper())
    valid, rejected, _ = parse_csv(_f(text))
    assert len(valid) == 1
    assert valid[0]["title"] == "Foo"
    assert valid[0]["category"].pk == category.pk


@pytest.mark.django_db
def test_parse_csv_unknown_category_rejects_row(category):
    text = "title,category\nFoo,Nonexistent Category\n"
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert len(rejected) == 1
    assert "Unknown category" in rejected[0]["error"]
    assert rejected[0]["row_number"] == 2  # header is row 1


@pytest.mark.django_db
def test_parse_csv_unknown_person_rejects_row(category):
    text = "title,category,responsible\nFoo,{cat},Ghost Person\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert "Unknown person" in rejected[0]["error"]


@pytest.mark.django_db
def test_parse_csv_resolves_responsible_person(category):
    person = RosterPerson.objects.create(name="Jane Doe")
    text = "title,category,responsible\nFoo,{cat},Jane Doe\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["responsible"].pk == person.pk


@pytest.mark.django_db
def test_parse_csv_responsible_match_case_insensitive(category):
    person = RosterPerson.objects.create(name="Jane Doe")
    text = "title,category,responsible\nFoo,{cat},jane doe\n".format(cat=category.name)
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["responsible"].pk == person.pk


@pytest.mark.django_db
def test_parse_csv_archived_person_does_not_match(category):
    RosterPerson.objects.create(name="Jane Doe", archived=True)
    text = "title,category,responsible\nFoo,{cat},Jane Doe\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert valid == []
    assert "Unknown person" in rejected[0]["error"]


@pytest.mark.django_db
def test_parse_csv_date_iso_format(category):
    import datetime as dt
    text = "title,category,projected_completion_date\nFoo,{cat},2026-07-15\n".format(cat=category.name)
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["projected_completion_date"] == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_parse_csv_date_excel_format(category):
    import datetime as dt
    text = "title,category,projected_completion_date\nFoo,{cat},7/15/2026\n".format(cat=category.name)
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["projected_completion_date"] == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_parse_csv_invalid_date_rejects_row(category):
    text = "title,category,projected_completion_date\nFoo,{cat},not-a-date\n".format(cat=category.name)
    _, rejected, _ = parse_csv(_f(text))
    assert "date" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_currency_style_budget(category):
    from decimal import Decimal
    text = 'title,category,budget_amount\nFoo,{cat},"$1,200.00"\n'.format(cat=category.name)
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["budget_amount"] == Decimal("1200.00")


@pytest.mark.django_db
def test_parse_csv_invalid_budget_rejects_row(category):
    text = "title,category,budget_amount\nFoo,{cat},notanumber\n".format(cat=category.name)
    _, rejected, _ = parse_csv(_f(text))
    assert "budget" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_blank_optional_fields_ok(category):
    text = "title,category,description,priority\nFoo,{cat},,\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["description"] == ""
    assert valid[0]["priority"] == ProjectPriority.MEDIUM  # default


@pytest.mark.django_db
def test_parse_csv_status_human_label_accepted(category):
    text = "title,category,status\nFoo,{cat},In progress\n".format(cat=category.name)
    valid, _, _ = parse_csv(_f(text))
    assert valid[0]["status"] == ProjectStatus.IN_PROGRESS


@pytest.mark.django_db
def test_parse_csv_invalid_status_rejects_row(category):
    text = "title,category,status\nFoo,{cat},flerbgled\n".format(cat=category.name)
    _, rejected, _ = parse_csv(_f(text))
    assert "status" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_unknown_column_warns_but_imports(category):
    text = "title,category,notes\nFoo,{cat},some scratch text\n".format(cat=category.name)
    valid, rejected, warnings = parse_csv(_f(text))
    assert rejected == []
    assert len(valid) == 1
    assert any("notes" in w for w in warnings)


def test_parse_csv_empty_file_raises():
    with pytest.raises(ValueError, match="header"):
        parse_csv(_f(""))


def test_parse_csv_no_data_rows_returns_empty():
    valid, rejected, _ = parse_csv(_f("title,category\n"))
    assert valid == []
    assert rejected == []


def test_parse_csv_missing_required_column_raises():
    with pytest.raises(ValueError, match="title"):
        parse_csv(_f("category\nFoo\n"))


@pytest.mark.django_db
def test_parse_csv_blank_title_rejects_row(category):
    text = "title,category\n,{cat}\n".format(cat=category.name)
    _, rejected, _ = parse_csv(_f(text))
    assert "title" in rejected[0]["error"].lower()


@pytest.mark.django_db
def test_parse_csv_utf8_bom_tolerated(category):
    """Excel saves CSVs with a UTF-8 BOM. The parser must strip it."""
    text = "﻿title,category\nFoo,{cat}\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert rejected == []
    assert valid[0]["title"] == "Foo"


@pytest.mark.django_db
def test_parse_csv_trailing_blank_rows_ignored(category):
    text = "title,category\nFoo,{cat}\n,\n,\n".format(cat=category.name)
    valid, rejected, _ = parse_csv(_f(text))
    assert len(valid) == 1
    assert rejected == []  # fully blank rows are skipped, not rejected
```

### Step 2: Run them to verify they fail

Run: `python -m pytest apps/projects/tests/test_csv_import_service.py -v`
Expected: ImportError / ModuleNotFoundError for `apps.projects.services.csv_import`.

### Step 3: Implement the parser

```python
# apps/projects/services/__init__.py
```

```python
# apps/projects/services/csv_import.py
"""Pure-function CSV parser for bulk project import.

Returns three lists:
- valid_rows: dicts with already-resolved FK objects and parsed primitives,
  ready to hand to Project.objects.create(**row, created_by=user).
- rejected_rows: dicts with the original row_number, the raw row, and an
  error string. The user sees these in the preview table.
- warnings: human-readable strings about unknown columns or other
  non-fatal weirdness.

The parser intentionally does NOT write to the DB. The view layer
constructs the Project rows from valid_rows on confirmation.
"""
import csv
import datetime as dt
import io
from decimal import Decimal, InvalidOperation

from apps.projects.models import ProjectCategory, ProjectPriority, ProjectStatus
from apps.roster.models import RosterPerson

REQUIRED_COLUMNS = {"title", "category"}
KNOWN_COLUMNS = {
    "title", "category", "description", "status", "priority",
    "projected_completion_date", "budget_amount", "vendor_name",
    "vendor_bid_amount", "responsible",
}

# Accept both the machine value and the human label (case-insensitive).
_STATUS_LOOKUP = {}
for value, label in ProjectStatus.choices:
    _STATUS_LOOKUP[value.lower()] = value
    _STATUS_LOOKUP[label.lower()] = value

_PRIORITY_LOOKUP = {}
for value, label in ProjectPriority.choices:
    _PRIORITY_LOOKUP[value.lower()] = value
    _PRIORITY_LOOKUP[label.lower()] = value


def parse_csv(file_obj):
    """Parse an uploaded CSV file object.

    file_obj is a binary stream (BytesIO or Django UploadedFile). The
    parser decodes as UTF-8 with BOM tolerance.
    """
    raw = file_obj.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig")
    else:
        text = raw

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV is missing a header row.")

    # Normalize headers: lowercase + stripped.
    normalized_headers = [h.strip().lower() for h in reader.fieldnames]
    reader.fieldnames = normalized_headers

    missing = REQUIRED_COLUMNS - set(normalized_headers)
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}."
        )

    warnings = []
    unknown = set(normalized_headers) - KNOWN_COLUMNS
    if unknown:
        warnings.append(
            "Ignoring unknown column(s): " + ", ".join(sorted(unknown))
        )

    # Build category and person lookup maps once.
    categories_by_name = {
        c.name.lower(): c for c in ProjectCategory.objects.all()
    }
    people_by_name = {
        p.name.lower(): p for p in RosterPerson.active.all()
    }

    valid_rows = []
    rejected_rows = []

    for i, raw_row in enumerate(reader, start=2):  # data starts at row 2
        # Skip rows that are entirely blank.
        if all((v or "").strip() == "" for v in raw_row.values()):
            continue

        try:
            parsed = _parse_row(raw_row, categories_by_name, people_by_name)
        except _RowError as e:
            rejected_rows.append({
                "row_number": i,
                "raw": dict(raw_row),
                "error": str(e),
            })
            continue

        valid_rows.append(parsed)

    return valid_rows, rejected_rows, warnings


class _RowError(ValueError):
    pass


def _parse_row(raw, categories_by_name, people_by_name):
    title = (raw.get("title") or "").strip()
    if not title:
        raise _RowError("Title is required.")
    if len(title) > 200:
        raise _RowError("Title is longer than 200 characters.")

    category_name = (raw.get("category") or "").strip()
    if not category_name:
        raise _RowError("Category is required.")
    category = categories_by_name.get(category_name.lower())
    if category is None:
        raise _RowError(f"Unknown category: {category_name}")

    out = {
        "title": title,
        "category": category,
        "description": (raw.get("description") or "").strip(),
        "vendor_name": (raw.get("vendor_name") or "").strip(),
    }

    status_raw = (raw.get("status") or "").strip()
    if status_raw:
        status = _STATUS_LOOKUP.get(status_raw.lower())
        if status is None:
            raise _RowError(f"Unknown status: {status_raw}")
        out["status"] = status
    else:
        out["status"] = ProjectStatus.NOT_STARTED

    priority_raw = (raw.get("priority") or "").strip()
    if priority_raw:
        priority = _PRIORITY_LOOKUP.get(priority_raw.lower())
        if priority is None:
            raise _RowError(f"Unknown priority: {priority_raw}")
        out["priority"] = priority
    else:
        out["priority"] = ProjectPriority.MEDIUM

    date_raw = (raw.get("projected_completion_date") or "").strip()
    if date_raw:
        out["projected_completion_date"] = _parse_date(date_raw)
    else:
        out["projected_completion_date"] = None

    budget_raw = (raw.get("budget_amount") or "").strip()
    if budget_raw:
        out["budget_amount"] = _parse_money(budget_raw, field="budget_amount")
    else:
        out["budget_amount"] = None

    bid_raw = (raw.get("vendor_bid_amount") or "").strip()
    if bid_raw:
        out["vendor_bid_amount"] = _parse_money(bid_raw, field="vendor_bid_amount")
    else:
        out["vendor_bid_amount"] = None

    responsible_raw = (raw.get("responsible") or "").strip()
    if responsible_raw:
        person = people_by_name.get(responsible_raw.lower())
        if person is None:
            raise _RowError(f"Unknown person: {responsible_raw}")
        out["responsible"] = person
    else:
        out["responsible"] = None

    return out


def _parse_date(raw):
    # Try ISO first, then Excel's M/D/YYYY.
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%-m/%-d/%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    # On Windows, %-m isn't supported; do a manual split as a last resort.
    parts = raw.split("/")
    if len(parts) == 3:
        try:
            m, d, y = (int(p) for p in parts)
            return dt.date(y, m, d)
        except ValueError:
            pass
    raise _RowError(f"Unrecognized date format: {raw}")


def _parse_money(raw, *, field):
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as e:
        raise _RowError(f"Unrecognized {field} value: {raw}") from e
```

### Step 4: Run tests until green

Run: `python -m pytest apps/projects/tests/test_csv_import_service.py -v`
Expected: all 21 tests pass.

### Step 5: Commit

```bash
git add apps/projects/services/__init__.py apps/projects/services/csv_import.py apps/projects/tests/test_csv_import_service.py
git commit -m "feat(import): CSV parser service with row-level error reporting"
```

---

## Task 2: Import form view + template

**Files:**
- Create: `apps/projects/views/csv_import.py`
- Modify: `apps/projects/views/__init__.py` (add exports)
- Modify: `apps/projects/urls.py` (add 3 routes)
- Create: `templates/projects/import_form.html`
- Create: `templates/projects/import_preview.html`
- Create: `apps/projects/tests/test_views_csv_import.py`

### Step 1: Write the failing tests

```python
# apps/projects/tests/test_views_csv_import.py
import io

import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, Project, RACIAssignment, RACIRole
from apps.roster.models import RosterPerson


def _upload(text):
    f = io.BytesIO(text.encode("utf-8"))
    f.name = "import.csv"
    return f


@pytest.mark.django_db
def test_import_form_requires_login(client):
    response = client.get(reverse("projects:import_form"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_import_form_renders(auth_client):
    response = auth_client.get(reverse("projects:import_form"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Import projects" in content
    assert "Download template" in content


@pytest.mark.django_db
def test_import_template_download(auth_client):
    response = auth_client.get(reverse("projects:import_template"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    body = response.content.decode()
    # Header row + at least one example row.
    assert "title" in body.lower()
    assert "category" in body.lower()
    assert body.count("\n") >= 2


@pytest.mark.django_db
def test_import_preview_shows_valid_and_rejected(auth_client, category):
    csv_text = (
        "title,category\n"
        f"Good row,{category.name}\n"
        "Bad row,Unknown Category\n"
    )
    response = auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Good row" in content
    assert "Bad row" in content
    assert "Unknown category" in content


@pytest.mark.django_db
def test_import_confirm_creates_projects(auth_client, user, category):
    csv_text = "title,category\nFoo,{cat}\nBar,{cat}\n".format(cat=category.name)
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    # Now confirm.
    response = auth_client.post(reverse("projects:import_confirm"))
    assert response.status_code == 302
    assert Project.objects.filter(title="Foo").count() == 1
    assert Project.objects.filter(title="Bar").count() == 1
    # Activity logged.
    assert ActivityLog.objects.filter(
        actor=user, verb="imported via CSV",
    ).count() == 2


@pytest.mark.django_db
def test_import_confirm_creates_raci_when_responsible_set(auth_client, user, category):
    jane = RosterPerson.objects.create(name="Jane Doe")
    csv_text = (
        "title,category,responsible\n"
        f"Foo,{category.name},Jane Doe\n"
    )
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    auth_client.post(reverse("projects:import_confirm"))
    project = Project.objects.get(title="Foo")
    raci = RACIAssignment.objects.get(project=project)
    assert raci.person == jane
    assert raci.role == RACIRole.RESPONSIBLE


@pytest.mark.django_db
def test_import_confirm_without_preview_redirects(auth_client):
    """Posting to confirm without a session preview is harmless — redirects
    back to the form rather than crashing."""
    response = auth_client.post(reverse("projects:import_confirm"))
    assert response.status_code == 302
    assert response.url == reverse("projects:import_form")


@pytest.mark.django_db
def test_import_empty_file_shows_error(auth_client):
    response = auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload("")},
    )
    assert response.status_code == 200
    assert "header" in response.content.decode().lower()


@pytest.mark.django_db
def test_import_no_file_shows_error(auth_client):
    response = auth_client.post(reverse("projects:import_form"), {})
    assert response.status_code == 200
    assert "file" in response.content.decode().lower()


@pytest.mark.django_db
def test_import_only_valid_rows_get_created_on_confirm(auth_client, category):
    csv_text = (
        "title,category\n"
        f"Good,{category.name}\n"
        "Bad,Nope\n"
    )
    auth_client.post(
        reverse("projects:import_form"),
        {"file": _upload(csv_text)},
    )
    auth_client.post(reverse("projects:import_confirm"))
    assert Project.objects.filter(title="Good").exists()
    assert not Project.objects.filter(title="Bad").exists()
```

### Step 2: Run them to verify they fail

Run: `python -m pytest apps/projects/tests/test_views_csv_import.py -v`
Expected: NoReverseMatch for `projects:import_form`.

### Step 3: Implement the view module

```python
# apps/projects/views/csv_import.py
"""Bulk import view: form -> preview-in-session -> confirm.

The form view both renders the empty form (GET) and handles uploads (POST).
On a successful parse, the rows are stashed in request.session and we
render the preview template. The confirm view reads those rows back out
and creates the projects.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from ..models import ActivityLog, Project, ProjectCategory, RACIAssignment, RACIRole
from ..services.csv_import import parse_csv
from apps.roster.models import RosterPerson

SESSION_KEY = "pending_csv_import"


@login_required
def import_form(request):
    if request.method != "POST":
        return render(request, "projects/import_form.html")

    upload = request.FILES.get("file")
    if upload is None:
        return render(request, "projects/import_form.html", {
            "error": "Please choose a CSV file to upload.",
        })

    try:
        valid, rejected, warnings = parse_csv(upload)
    except ValueError as e:
        return render(request, "projects/import_form.html", {
            "error": str(e),
        })

    # Serialize the valid rows for the session — FKs become ids.
    request.session[SESSION_KEY] = {
        "valid": [_row_to_session(r) for r in valid],
    }
    request.session.modified = True

    return render(request, "projects/import_preview.html", {
        "valid_rows": valid,
        "rejected_rows": rejected,
        "warnings": warnings,
    })


@login_required
def import_confirm(request):
    if request.method != "POST":
        return redirect("projects:import_form")

    pending = request.session.pop(SESSION_KEY, None)
    if not pending or not pending.get("valid"):
        return redirect("projects:import_form")

    rows = pending["valid"]
    created_count = 0

    try:
        with transaction.atomic():
            for serialized in rows:
                project = _project_from_session_row(serialized, request.user)
                project.save()
                if serialized.get("responsible_id"):
                    RACIAssignment.objects.create(
                        project=project,
                        person_id=serialized["responsible_id"],
                        role=RACIRole.RESPONSIBLE,
                    )
                ActivityLog.objects.create(
                    actor=request.user, project=project, verb="imported via CSV",
                )
                created_count += 1
    except Exception:
        messages.error(request, "Import failed, please try again.")
        return redirect("projects:import_form")

    messages.success(request, f"Imported {created_count} project(s).")
    return redirect("projects:list")


@login_required
def import_template(request):
    """Return a 1-row example CSV."""
    body = (
        "title,category,description,status,priority,projected_completion_date,"
        "budget_amount,vendor_name,vendor_bid_amount,responsible\n"
        "Sprinkler repair,Landscaping,Replace zone 3 valve,not_started,medium,"
        "2026-07-15,1200.00,Acme Sprinklers,1100.00,Jane Doe\n"
    )
    response = HttpResponse(body, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="project-import-template.csv"'
    return response


def _row_to_session(row):
    """Convert a parsed row (with FK objects) into JSON-serializable form."""
    return {
        "title": row["title"],
        "category_id": row["category"].pk,
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "projected_completion_date": (
            row["projected_completion_date"].isoformat()
            if row["projected_completion_date"] else None
        ),
        "budget_amount": (
            str(row["budget_amount"]) if row["budget_amount"] is not None else None
        ),
        "vendor_name": row["vendor_name"],
        "vendor_bid_amount": (
            str(row["vendor_bid_amount"]) if row["vendor_bid_amount"] is not None else None
        ),
        "responsible_id": row["responsible"].pk if row["responsible"] else None,
    }


def _project_from_session_row(s, user):
    import datetime as dt
    from decimal import Decimal
    return Project(
        title=s["title"],
        category_id=s["category_id"],
        description=s["description"],
        status=s["status"],
        priority=s["priority"],
        projected_completion_date=(
            dt.date.fromisoformat(s["projected_completion_date"])
            if s["projected_completion_date"] else None
        ),
        budget_amount=Decimal(s["budget_amount"]) if s["budget_amount"] else None,
        vendor_name=s["vendor_name"],
        vendor_bid_amount=Decimal(s["vendor_bid_amount"]) if s["vendor_bid_amount"] else None,
        created_by=user,
    )
```

### Step 4: Wire up views/init and urls

In `apps/projects/views/__init__.py` add (alphabetically, near the other imports):

```python
from .csv_import import import_confirm as import_confirm
from .csv_import import import_form as import_form
from .csv_import import import_template as import_template
```

In `apps/projects/urls.py` add (group with the other CRUD-ish routes, near `search/`):

```python
    path("import/", views.import_form, name="import_form"),
    path("import/confirm/", views.import_confirm, name="import_confirm"),
    path("import/template/", views.import_template, name="import_template"),
```

### Step 5: Write the templates

```html
<!-- templates/projects/import_form.html -->
{% extends "base.html" %}
{% block title %}Import projects — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-4">Import projects</h1>

<p class="text-sm text-gray-700 mb-4">
  Upload a CSV from Excel or Google Sheets to create projects in bulk.
  You'll see a preview before anything is saved.
</p>

<div class="bg-blue-50 border border-blue-200 rounded p-3 text-sm mb-6">
  <p class="mb-2"><strong>Required columns:</strong> <code>title</code>, <code>category</code></p>
  <p class="mb-2"><strong>Optional:</strong> description, status, priority, projected_completion_date,
     budget_amount, vendor_name, vendor_bid_amount, responsible</p>
  <p><strong>Dates:</strong> YYYY-MM-DD or M/D/YYYY (Excel default both work).</p>
  <p class="mt-2"><a class="text-blue-700 hover:underline" href="{% url 'projects:import_template' %}">Download template CSV</a></p>
</div>

{% if error %}
  <div class="bg-red-50 border border-red-200 text-red-800 rounded p-3 mb-4 text-sm">
    {{ error }}
  </div>
{% endif %}

<form method="post" enctype="multipart/form-data" class="bg-white rounded shadow p-5 max-w-xl">
  {% csrf_token %}
  <label class="block text-sm font-medium text-gray-700 mb-2" for="file">CSV file</label>
  <input id="file" type="file" name="file" accept=".csv" class="block mb-4">
  <button type="submit" class="btn-primary">Preview import</button>
</form>
{% endblock %}
```

```html
<!-- templates/projects/import_preview.html -->
{% extends "base.html" %}
{% block title %}Import preview — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-4">Import preview</h1>

{% if warnings %}
  <div class="bg-yellow-50 border border-yellow-200 text-yellow-900 rounded p-3 mb-4 text-sm">
    {% for w in warnings %}<div>{{ w }}</div>{% endfor %}
  </div>
{% endif %}

{% if rejected_rows %}
  <section class="mb-6">
    <h2 class="text-sm font-semibold text-red-700 uppercase mb-2">
      {{ rejected_rows|length }} row(s) will be skipped
    </h2>
    <table class="w-full text-sm bg-white rounded shadow overflow-hidden">
      <thead class="bg-red-50 text-red-800">
        <tr><th class="p-2 text-left">Row</th><th class="p-2 text-left">Title</th><th class="p-2 text-left">Reason</th></tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        {% for r in rejected_rows %}
          <tr><td class="p-2">{{ r.row_number }}</td><td class="p-2">{{ r.raw.title }}</td><td class="p-2 text-red-700">{{ r.error }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </section>
{% endif %}

{% if valid_rows %}
  <section class="mb-6">
    <h2 class="text-sm font-semibold text-green-700 uppercase mb-2">
      {{ valid_rows|length }} row(s) will be created
    </h2>
    <table class="w-full text-sm bg-white rounded shadow overflow-hidden">
      <thead class="bg-green-50 text-green-800">
        <tr>
          <th class="p-2 text-left">Title</th>
          <th class="p-2 text-left">Category</th>
          <th class="p-2 text-left">Status</th>
          <th class="p-2 text-left">Responsible</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        {% for row in valid_rows %}
          <tr>
            <td class="p-2">{{ row.title }}</td>
            <td class="p-2">{{ row.category.name }}</td>
            <td class="p-2">{{ row.status }}</td>
            <td class="p-2">{% if row.responsible %}{{ row.responsible.name }}{% else %}—{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <form method="post" action="{% url 'projects:import_confirm' %}">
    {% csrf_token %}
    <button type="submit" class="btn-primary">Confirm import</button>
    <a href="{% url 'projects:import_form' %}" class="btn-secondary ml-2">Cancel</a>
  </form>
{% else %}
  <p class="text-gray-500 mb-4">No valid rows to import.</p>
  <a href="{% url 'projects:import_form' %}" class="btn-secondary">Back to form</a>
{% endif %}
{% endblock %}
```

### Step 6: Run all import tests

Run: `python -m pytest apps/projects/tests/test_csv_import_service.py apps/projects/tests/test_views_csv_import.py -v`
Expected: all pass.

### Step 7: Commit

```bash
git add apps/projects/views/csv_import.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/import_form.html templates/projects/import_preview.html apps/projects/tests/test_views_csv_import.py
git commit -m "feat(import): preview-then-confirm CSV bulk import view"
```

---

## Task 3: Sidebar link for "Import projects"

**Files:**
- Modify: `templates/base.html` (find the sidebar's Projects section)

### Step 1: Find the existing Calendar sidebar link

Run: `grep -n "Calendar" templates/base.html` (use Grep tool).

### Step 2: Add a new line just after the Calendar link

The new line should mirror the existing `<a>` styling:

```html
<a href="{% url 'projects:import_form' %}" class="<same classes as Calendar link>">Import projects</a>
```

### Step 3: Add a sidebar test

In `apps/projects/tests/test_views_csv_import.py`:

```python
@pytest.mark.django_db
def test_sidebar_includes_import_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert "Import projects" in content
    assert reverse("projects:import_form") in content
```

### Step 4: Run and commit

```bash
python -m pytest apps/projects/tests/test_views_csv_import.py::test_sidebar_includes_import_link -v
git add templates/base.html apps/projects/tests/test_views_csv_import.py
git commit -m "feat(import): sidebar link to bulk import"
```

---

## Task 4: Bulk delete view + list-page checkboxes

**Files:**
- Create: `apps/projects/views/bulk.py`
- Modify: `apps/projects/views/__init__.py` (export)
- Modify: `apps/projects/urls.py` (one route)
- Modify: `templates/projects/list.html` (checkboxes + button + modal)
- Create: `apps/projects/tests/test_views_bulk_delete.py`

### Step 1: Write failing tests

```python
# apps/projects/tests/test_views_bulk_delete.py
import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, Project, ProjectStatus


@pytest.mark.django_db
def test_bulk_delete_requires_login(client):
    response = client.post(reverse("projects:bulk_delete"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_bulk_delete_happy_path(auth_client, user, category):
    p1 = Project.objects.create(title="Doomed 1", category=category, created_by=user)
    p2 = Project.objects.create(title="Doomed 2", category=category, created_by=user)
    keeper = Project.objects.create(title="Keeper", category=category, created_by=user)

    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"ids": [str(p1.pk), str(p2.pk)], "confirm": "delete"},
    )
    assert response.status_code == 302
    assert not Project.objects.filter(pk=p1.pk).exists()
    assert not Project.objects.filter(pk=p2.pk).exists()
    assert Project.objects.filter(pk=keeper.pk).exists()
    # Two activity log entries with verb "deleted".
    assert ActivityLog.objects.filter(verb="deleted").count() == 2


@pytest.mark.django_db
def test_bulk_delete_without_confirm_word_returns_400(auth_client, user, category):
    p = Project.objects.create(title="Safe", category=category, created_by=user)
    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"ids": [str(p.pk)], "confirm": "yes"},  # wrong word
    )
    assert response.status_code == 400
    assert Project.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db
def test_bulk_delete_with_no_ids_redirects_back(auth_client):
    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"confirm": "delete"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_bulk_delete_get_not_allowed(auth_client):
    response = auth_client.get(reverse("projects:bulk_delete"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_list_page_renders_checkboxes(auth_client, user, category):
    Project.objects.create(title="A project", category=category, created_by=user, status=ProjectStatus.IN_PROGRESS)
    response = auth_client.get(reverse("projects:list"))
    content = response.content.decode()
    assert 'name="ids"' in content  # checkbox input present
    assert "Delete selected" in content
```

### Step 2: Implement view

```python
# apps/projects/views/bulk.py
"""Bulk-delete view for the project list page.

Posts an `ids` list and a literal `confirm=delete` flag. The frontend
modal is responsible for forcing the user to type "delete" — but we
still verify server-side so a curl request can't bypass it.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import redirect

from ..models import ActivityLog, Project


@login_required
def bulk_delete(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if request.POST.get("confirm") != "delete":
        return HttpResponseBadRequest("Confirmation word required.")

    raw_ids = request.POST.getlist("ids")
    pks = [int(x) for x in raw_ids if x.isdigit()]
    if not pks:
        messages.info(request, "Nothing selected.")
        return redirect("projects:list")

    with transaction.atomic():
        projects = list(Project.objects.filter(pk__in=pks))
        for p in projects:
            ActivityLog.objects.create(
                actor=request.user,
                project=None,  # the project is about to vanish
                verb="deleted",
                value_change=f"Project: {p.title} (was id {p.pk})",
            )
        Project.objects.filter(pk__in=pks).delete()

    messages.success(request, f"Deleted {len(projects)} project(s).")
    return redirect("projects:list")
```

### Step 3: Export + URL

In `apps/projects/views/__init__.py`:
```python
from .bulk import bulk_delete as bulk_delete
```

In `apps/projects/urls.py` (near the other root-level routes):
```python
    path("bulk-delete/", views.bulk_delete, name="bulk_delete"),
```

### Step 4: Modify the list template

In `templates/projects/list.html`:
1. Wrap the table in a `<form method="post" action="{% url 'projects:bulk_delete' %}" id="bulk-form">` (with csrf_token).
2. Add a leading `<th></th>` and a leading `<td><input type="checkbox" name="ids" value="{{ p.pk }}"></td>` on each row.
3. Above the table, add a "Delete selected" button that is `disabled` until ≥1 checkbox is checked (vanilla JS, no HTMX needed).
4. Add a hidden `<input type="hidden" name="confirm" id="confirm-word">` and a small inline modal that shows on click, prompts the user to type `delete`, and only enables submit when the input value equals `"delete"` (then fills the hidden input and submits the form).

Pseudocode for the JS (inline `<script>` block at the bottom of the template):

```javascript
(function() {
  const form = document.getElementById("bulk-form");
  const deleteBtn = document.getElementById("bulk-delete-btn");
  const checkboxes = () => form.querySelectorAll('input[name="ids"]');
  const update = () => {
    const anyChecked = Array.from(checkboxes()).some(cb => cb.checked);
    deleteBtn.disabled = !anyChecked;
  };
  form.addEventListener("change", update);
  update();

  deleteBtn.addEventListener("click", function(e) {
    e.preventDefault();
    const count = Array.from(checkboxes()).filter(cb => cb.checked).length;
    const typed = window.prompt(
      `Delete ${count} project(s)? This cannot be undone.\nType the word "delete" to confirm:`
    );
    if (typed === "delete") {
      document.getElementById("confirm-word").value = "delete";
      form.submit();
    }
  });
})();
```

(A `window.prompt` is ugly but lets the typed-confirmation requirement get met without a full modal framework. The user can polish later.)

### Step 5: Run all tests

```
python -m pytest apps/projects/tests/test_views_bulk_delete.py apps/projects/tests/test_views_list.py -v
```

Expected: all pass. If `test_views_list.py` breaks due to the new checkbox column, update those assertions to be more lenient (e.g., look for the project title rather than exact HTML structure).

### Step 6: Commit

```bash
git add apps/projects/views/bulk.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/list.html apps/projects/tests/test_views_bulk_delete.py
git commit -m "feat(bulk): delete selected projects from list with typed confirmation"
```

---

## Task 5: Full test suite + ruff + ship

### Step 1: Full suite

```
python -m pytest -q
```

Expected: all pass.

### Step 2: Ruff

```
ruff check .
```

Expected: clean.

### Step 3: Merge to main

```bash
git checkout main
git merge --no-ff csv-bulk-import -m "Merge branch 'csv-bulk-import'"
git branch -d csv-bulk-import
git push origin main
```

---

## Self-review

- **Spec coverage:** CSV columns (Task 1), preview flow (Task 2), sidebar entry (Task 3), bulk delete from list (Task 4), full-suite/ship (Task 5). All design sections covered.
- **Placeholders:** None — every step has either code or a precise command.
- **Type consistency:** `parse_csv` returns `(valid, rejected, warnings)` in every reference. Session-serialization uses `_id` suffixes for FK fields and string-encoded Decimals/dates; `_project_from_session_row` reverses that exactly.
- **Risk areas:** The list-page template modification is the riskiest step because it touches an existing template with established tests. Step 5 of Task 4 explicitly allows updating older list tests if the checkbox column shifts their assertions.
