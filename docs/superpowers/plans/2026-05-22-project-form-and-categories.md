# Project Form & Category Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app category management page, collapse the project form's budget/vendor fields into a native `<details>` section, and show the delay-reason field only when status is Delayed.

**Architecture:** Three independent UX refinements to the existing `projects` app. No schema changes. Feature 1 adds a new view module (`apps/projects/views/category.py`), a form (`apps/projects/forms/category.py`), a template, and four URL routes — built incrementally so the template is always valid. Feature 2 extracts a per-field template partial and wraps the four financial fields in a native HTML `<details>` element. Feature 3 adds a small vanilla-JS file that toggles the delay-reason field's container. The server-side `delay_reason`-required-when-delayed rule is unchanged.

**Tech Stack:** Django 5.0.x, pytest-django, ruff, Tailwind CSS (standalone CLI — `output.css` is committed and must be rebuilt when templates change).

---

## File Structure

**New files:**
- `apps/projects/views/category.py` — the four category-management views (list, add, rename, delete).
- `apps/projects/forms/category.py` — `ProjectCategoryForm` (a one-field ModelForm).
- `templates/projects/category_list.html` — the category management page.
- `templates/projects/_form_field.html` — a reusable partial that renders one bound form field (label + widget + help + errors).
- `static/js/delay-reason-toggle.js` — toggles the delay-reason container based on the status `<select>`.
- `apps/projects/tests/test_seed_categories.py` — tests for the `seed_categories` command.
- `apps/projects/tests/test_views_category.py` — tests for the category-management views.

**Modified files:**
- `apps/projects/management/commands/seed_categories.py` — add the "Misc" entry.
- `apps/projects/views/__init__.py` — re-export the four new category views.
- `apps/projects/forms/__init__.py` — re-export `ProjectCategoryForm`.
- `apps/projects/urls.py` — add four category-page routes.
- `apps/projects/forms/project.py` — add the `FINANCIAL_FIELD_NAMES` class attribute.
- `apps/projects/views/project_form.py` — pass the `financial_section_open` context flag.
- `templates/projects/form.html` — restructure into the partial + `<details>` grouping + delay-reason hook.
- `templates/accounts/profile.html` — add the "Manage project categories" link.
- `apps/projects/tests/test_views_form.py` — add tests for the `<details>` section and the JS hooks.
- `static/css/output.css` — rebuilt by the Tailwind CLI (final task).

---

## Task 1: Add "Misc" to the seed_categories command

**Files:**
- Modify: `apps/projects/management/commands/seed_categories.py:5-12`
- Test: `apps/projects/tests/test_seed_categories.py` (create)

- [ ] **Step 1: Write the failing test**

Create `apps/projects/tests/test_seed_categories.py`:

```python
import pytest
from django.core.management import call_command

from apps.projects.models import ProjectCategory


@pytest.mark.django_db
def test_seed_creates_seven_categories_including_misc():
    call_command("seed_categories")
    assert ProjectCategory.objects.count() == 7
    assert ProjectCategory.objects.filter(name="Misc", display_order=7).exists()


@pytest.mark.django_db
def test_seed_is_idempotent():
    call_command("seed_categories")
    call_command("seed_categories")
    assert ProjectCategory.objects.count() == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/projects/tests/test_seed_categories.py -v`
Expected: FAIL — `test_seed_creates_seven_categories_including_misc` fails because the command seeds only six categories (count is 6, no "Misc").

- [ ] **Step 3: Add the "Misc" entry**

In `apps/projects/management/commands/seed_categories.py`, change the `SEED` list to include a seventh entry:

```python
SEED = [
    ("Capital", 1),
    ("Operational", 2),
    ("Recurring", 3),
    ("Security", 4),
    ("Maintenance", 5),
    ("Financial", 6),
    ("Misc", 7),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest apps/projects/tests/test_seed_categories.py -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/projects/management/commands/seed_categories.py apps/projects/tests/test_seed_categories.py
git commit -m "feat(categories): add Misc to the seed_categories command"
```

---

## Task 2: Category management page — read-only list with project counts

This task creates the page, its single read-only view, the URL route, and the "Manage project categories" link on the Account page. The add/rename/delete controls are added in Tasks 3-5; the template here is deliberately limited to what works with only the `category_list` route defined, so it never references an undefined URL name.

**Files:**
- Create: `apps/projects/views/category.py`
- Create: `templates/projects/category_list.html`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py:8-12`
- Modify: `templates/accounts/profile.html:21-23`
- Test: `apps/projects/tests/test_views_category.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `apps/projects/tests/test_views_category.py`:

```python
import pytest
from django.urls import reverse

from apps.projects.models import Project


@pytest.mark.django_db
def test_category_list_requires_login(client):
    response = client.get(reverse("projects:category_list"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_category_list_renders(auth_client, category):
    response = auth_client.get(reverse("projects:category_list"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_category_list_shows_project_counts(auth_client, category, user):
    Project.objects.create(title="P1", category=category, created_by=user)
    Project.objects.create(title="P2", category=category, created_by=user)
    response = auth_client.get(reverse("projects:category_list"))
    row = next(c for c in response.context["categories"] if c.pk == category.pk)
    assert row.project_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: FAIL — `NoReverseMatch` for `projects:category_list` (route does not exist).

- [ ] **Step 3: Create the category view module**

Create `apps/projects/views/category.py`:

```python
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from ..models import ProjectCategory


def _categories_with_counts():
    """All categories, each annotated with how many projects reference it."""
    return ProjectCategory.objects.annotate(project_count=Count("projects"))


@login_required
def category_list(request):
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
    })
```

- [ ] **Step 4: Re-export the view**

Add to `apps/projects/views/__init__.py` (keep the file's alphabetical-ish grouping; place after the `attachment` imports):

```python
from .category import category_list as category_list
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, add this route to `urlpatterns` immediately after the `path("<int:pk>/edit/", ...)` line:

```python
    path("categories/", views.category_list, name="category_list"),
```

- [ ] **Step 6: Create the page template**

Create `templates/projects/category_list.html`:

```html
{% extends "base.html" %}
{% block title %}Project categories — HOA Task Manager{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-2xl font-semibold text-gray-900">Project categories</h1>
  <a href="{% url 'accounts:profile' %}" class="text-blue-600 hover:underline text-sm">← Back to Account</a>
</div>

<div class="bg-white rounded-lg shadow overflow-hidden max-w-2xl">
  <table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50 text-xs uppercase text-gray-500">
      <tr>
        <th class="px-4 py-3 text-left">Category</th>
        <th class="px-4 py-3 text-left">Projects</th>
        <th class="px-4 py-3"></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-100">
      {% for category in categories %}
      <tr>
        <td class="px-4 py-3 text-sm text-gray-900">{{ category.name }}</td>
        <td class="px-4 py-3 text-sm text-gray-700">{{ category.project_count }}</td>
        <td class="px-4 py-3 text-right"></td>
      </tr>
      {% empty %}
      <tr><td colspan="3" class="px-4 py-8 text-center text-gray-400">No categories yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 7: Add the Account-page link**

In `templates/accounts/profile.html`, replace the closing block (the `<hr>` and the single "Change password" anchor) so both links appear:

```html
  <hr class="my-6">
  <div class="flex flex-wrap gap-2">
    <a href="{% url 'accounts:password_change' %}" class="btn-secondary">Change password</a>
    <a href="{% url 'projects:category_list' %}" class="btn-secondary">Manage project categories</a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: PASS — all three tests green.

- [ ] **Step 9: Commit**

```bash
git add apps/projects/views/category.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/category_list.html templates/accounts/profile.html apps/projects/tests/test_views_category.py
git commit -m "feat(categories): category management page with project counts"
```

---

## Task 3: Add a category

Adds the inline "+ Add category" form. New categories get `display_order` = current max + 1. A blank or duplicate name is rejected with an inline form error.

**Files:**
- Create: `apps/projects/forms/category.py`
- Modify: `apps/projects/forms/__init__.py`
- Modify: `apps/projects/views/category.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Modify: `templates/projects/category_list.html`
- Test: `apps/projects/tests/test_views_category.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_category.py`:

```python
from apps.projects.models import ProjectCategory


@pytest.mark.django_db
def test_category_add_creates(auth_client):
    response = auth_client.post(reverse("projects:category_add"), {"name": "Landscaping"})
    assert response.status_code == 302
    assert ProjectCategory.objects.filter(name="Landscaping").exists()


@pytest.mark.django_db
def test_category_add_sets_next_display_order(auth_client, category):
    # the `category` fixture has display_order=1
    auth_client.post(reverse("projects:category_add"), {"name": "Landscaping"})
    new = ProjectCategory.objects.get(name="Landscaping")
    assert new.display_order == 2


@pytest.mark.django_db
def test_category_add_rejects_blank(auth_client):
    response = auth_client.post(reverse("projects:category_add"), {"name": ""})
    assert response.status_code == 200
    assert response.context["add_form"].errors
    assert ProjectCategory.objects.filter(name="").count() == 0


@pytest.mark.django_db
def test_category_add_rejects_duplicate(auth_client, category):
    response = auth_client.post(reverse("projects:category_add"), {"name": category.name})
    assert response.status_code == 200
    assert response.context["add_form"].errors
    assert ProjectCategory.objects.filter(name=category.name).count() == 1
```

Note: `import pytest` and `from django.urls import reverse` are already at the top of the file from Task 2. The `from apps.projects.models import Project` line is also already there — add `ProjectCategory` to that existing import instead of duplicating it:

```python
from apps.projects.models import Project, ProjectCategory
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: FAIL — `NoReverseMatch` for `projects:category_add`.

- [ ] **Step 3: Create the category form**

Create `apps/projects/forms/category.py`:

```python
from django import forms

from ..models import ProjectCategory


class ProjectCategoryForm(forms.ModelForm):
    class Meta:
        model = ProjectCategory
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Category name"}),
        }
```

- [ ] **Step 4: Re-export the form**

Add to `apps/projects/forms/__init__.py` (alphabetical order — after the `approval` import):

```python
from .category import ProjectCategoryForm as ProjectCategoryForm
```

- [ ] **Step 5: Add the `category_add` view and pass `add_form` to the list**

Replace the full contents of `apps/projects/views/category.py` with:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import redirect, render

from ..forms import ProjectCategoryForm
from ..models import ProjectCategory


def _categories_with_counts():
    """All categories, each annotated with how many projects reference it."""
    return ProjectCategory.objects.annotate(project_count=Count("projects"))


@login_required
def category_list(request):
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
        "add_form": ProjectCategoryForm(),
    })


@login_required
def category_add(request):
    if request.method != "POST":
        return redirect("projects:category_list")
    form = ProjectCategoryForm(request.POST)
    if form.is_valid():
        category = form.save(commit=False)
        max_order = ProjectCategory.objects.aggregate(m=Max("display_order"))["m"] or 0
        category.display_order = max_order + 1
        category.save()
        messages.success(request, f"Added category “{category.name}”.")
        return redirect("projects:category_list")
    # Invalid: re-render the page with the bound form so errors appear inline.
    return render(request, "projects/category_list.html", {
        "categories": _categories_with_counts(),
        "add_form": form,
    })
```

- [ ] **Step 6: Re-export the new view**

Add to `apps/projects/views/__init__.py`:

```python
from .category import category_add as category_add
```

- [ ] **Step 7: Add the URL route**

In `apps/projects/urls.py`, add immediately after the `path("categories/", ...)` line:

```python
    path("categories/add/", views.category_add, name="category_add"),
```

- [ ] **Step 8: Add the inline add form to the template**

In `templates/projects/category_list.html`, insert this `<form>` block between the header `<div>` and the `<div class="bg-white rounded-lg shadow overflow-hidden max-w-2xl">` table block:

```html
<form method="post" action="{% url 'projects:category_add' %}"
      class="bg-white rounded-lg shadow p-4 mb-6 flex items-end gap-3 max-w-2xl">
  {% csrf_token %}
  <div class="flex-1">
    <label class="label" for="{{ add_form.name.id_for_label }}">Add category</label>
    {{ add_form.name }}
    {% if add_form.name.errors %}
      <p class="text-sm text-red-700 mt-1">{{ add_form.name.errors|join:", " }}</p>
    {% endif %}
  </div>
  <button type="submit" class="btn-primary">+ Add</button>
</form>
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: PASS — all category tests green.

- [ ] **Step 10: Commit**

```bash
git add apps/projects/forms/category.py apps/projects/forms/__init__.py apps/projects/views/category.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/category_list.html apps/projects/tests/test_views_category.py
git commit -m "feat(categories): add categories from the management page"
```

---

## Task 4: Rename a category

Each row gets an inline rename form. A blank name, or a name duplicating another category, is rejected with a Django message; otherwise the rename succeeds.

**Files:**
- Modify: `apps/projects/views/category.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Modify: `templates/projects/category_list.html`
- Test: `apps/projects/tests/test_views_category.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_category.py`:

```python
@pytest.mark.django_db
def test_category_rename(auth_client, category):
    response = auth_client.post(
        reverse("projects:category_rename", args=[category.pk]),
        {"name": "Capital Projects"},
    )
    assert response.status_code == 302
    category.refresh_from_db()
    assert category.name == "Capital Projects"


@pytest.mark.django_db
def test_category_rename_rejects_blank(auth_client, category):
    auth_client.post(
        reverse("projects:category_rename", args=[category.pk]),
        {"name": "   "},
    )
    category.refresh_from_db()
    assert category.name == "Capital"


@pytest.mark.django_db
def test_category_rename_rejects_duplicate(auth_client, category):
    other = ProjectCategory.objects.create(name="Operational", display_order=2)
    auth_client.post(
        reverse("projects:category_rename", args=[other.pk]),
        {"name": "Capital"},
    )
    other.refresh_from_db()
    assert other.name == "Operational"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: FAIL — `NoReverseMatch` for `projects:category_rename`.

- [ ] **Step 3: Add the `category_rename` view**

Append this view to `apps/projects/views/category.py` (the `get_object_or_404` import is needed — update the `django.shortcuts` import line at the top of the file to `from django.shortcuts import get_object_or_404, redirect, render`):

```python
@login_required
def category_rename(request, pk):
    if request.method != "POST":
        return redirect("projects:category_list")
    category = get_object_or_404(ProjectCategory, pk=pk)
    new_name = request.POST.get("name", "").strip()
    if not new_name:
        messages.error(request, "Category name cannot be blank.")
    elif ProjectCategory.objects.exclude(pk=pk).filter(name=new_name).exists():
        messages.error(request, f"A category named “{new_name}” already exists.")
    else:
        category.name = new_name
        category.save()
        messages.success(request, "Category renamed.")
    return redirect("projects:category_list")
```

- [ ] **Step 4: Re-export the new view**

Add to `apps/projects/views/__init__.py`:

```python
from .category import category_rename as category_rename
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, add immediately after the `path("categories/add/", ...)` line:

```python
    path("categories/<int:pk>/rename/", views.category_rename, name="category_rename"),
```

- [ ] **Step 6: Replace the plain name cell with a rename form**

In `templates/projects/category_list.html`, replace the category-name `<td>`:

```html
        <td class="px-4 py-3 text-sm text-gray-900">{{ category.name }}</td>
```

with an inline rename form:

```html
        <td class="px-4 py-3">
          <form method="post" action="{% url 'projects:category_rename' category.pk %}"
                class="flex gap-2 items-center">
            {% csrf_token %}
            <input type="text" name="name" value="{{ category.name }}" class="input">
            <button type="submit" class="btn-secondary">Rename</button>
          </form>
        </td>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: PASS — all category tests green.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/views/category.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/category_list.html apps/projects/tests/test_views_category.py
git commit -m "feat(categories): rename categories from the management page"
```

---

## Task 5: Delete a category

A category with zero projects shows a Delete button; an in-use category shows "in use by N project(s)" instead. The view catches `ProtectedError` as a defensive backstop.

**Files:**
- Modify: `apps/projects/views/category.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Modify: `templates/projects/category_list.html`
- Test: `apps/projects/tests/test_views_category.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_category.py`:

```python
@pytest.mark.django_db
def test_category_delete_unused(auth_client, category):
    response = auth_client.post(reverse("projects:category_delete", args=[category.pk]))
    assert response.status_code == 302
    assert not ProjectCategory.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
def test_category_delete_in_use_is_blocked(auth_client, category, user):
    Project.objects.create(title="P1", category=category, created_by=user)
    response = auth_client.post(reverse("projects:category_delete", args=[category.pk]))
    assert response.status_code == 302
    assert ProjectCategory.objects.filter(pk=category.pk).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: FAIL — `NoReverseMatch` for `projects:category_delete`.

- [ ] **Step 3: Add the `category_delete` view**

Append this view to `apps/projects/views/category.py`. Add `from django.db.models.deletion import ProtectedError` to the imports at the top of the file:

```python
@login_required
def category_delete(request, pk):
    if request.method != "POST":
        return redirect("projects:category_list")
    category = get_object_or_404(ProjectCategory, pk=pk)
    try:
        name = category.name
        category.delete()
        messages.success(request, f"Deleted category “{name}”.")
    except ProtectedError:
        messages.error(request, "Cannot delete a category that is in use by projects.")
    return redirect("projects:category_list")
```

- [ ] **Step 4: Re-export the new view**

Add to `apps/projects/views/__init__.py`:

```python
from .category import category_delete as category_delete
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, add immediately after the `path("categories/<int:pk>/rename/", ...)` line:

```python
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
```

- [ ] **Step 6: Add the delete control to the template**

In `templates/projects/category_list.html`, replace the empty action `<td>`:

```html
        <td class="px-4 py-3 text-right"></td>
```

with a conditional delete control:

```html
        <td class="px-4 py-3 text-right">
          {% if category.project_count %}
            <span class="text-xs text-gray-400">in use by {{ category.project_count }} project{{ category.project_count|pluralize }}</span>
          {% else %}
            <form method="post" action="{% url 'projects:category_delete' category.pk %}">
              {% csrf_token %}
              <button type="submit" class="text-sm text-red-700 hover:underline">Delete</button>
            </form>
          {% endif %}
        </td>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_category.py -v`
Expected: PASS — all category tests green.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/views/category.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/category_list.html apps/projects/tests/test_views_category.py
git commit -m "feat(categories): delete unused categories from the management page"
```

---

## Task 6: Collapsible "Budget & vendor details" section on the project form

The four financial/vendor fields move into a native `<details>` element. The section is collapsed on the create form, and open on the edit form when the project already has any financial data. A reusable `_form_field.html` partial renders each field so the loop and the `<details>` block share one rendering.

**Files:**
- Create: `templates/projects/_form_field.html`
- Modify: `apps/projects/forms/project.py`
- Modify: `apps/projects/views/project_form.py`
- Modify: `templates/projects/form.html`
- Test: `apps/projects/tests/test_views_form.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_form.py` (add `from decimal import Decimal` to the top of the file):

```python
@pytest.mark.django_db
def test_create_form_financial_section_collapsed(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    content = response.content.decode()
    assert "<details" in content
    assert "<details open" not in content


@pytest.mark.django_db
def test_edit_form_financial_section_open_when_data_present(auth_client, project):
    project.budget_amount = Decimal("1500.00")
    project.save()
    response = auth_client.get(reverse("projects:edit", args=[project.pk]))
    assert "<details open" in response.content.decode()


@pytest.mark.django_db
def test_edit_form_financial_section_collapsed_when_no_data(auth_client, project):
    response = auth_client.get(reverse("projects:edit", args=[project.pk]))
    assert "<details open" not in response.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_form.py -v`
Expected: FAIL — no `<details>` element is rendered yet.

- [ ] **Step 3: Add `FINANCIAL_FIELD_NAMES` to the form**

In `apps/projects/forms/project.py`, add a class attribute to `ProjectForm` (place it directly above the `tags_text` field declaration):

```python
class ProjectForm(forms.ModelForm):
    FINANCIAL_FIELD_NAMES = (
        "budget_amount", "actual_cost", "vendor_name", "vendor_bid_amount",
    )

    tags_text = forms.CharField(
```

- [ ] **Step 4: Pass `financial_section_open` from the form views**

Replace the full contents of `apps/projects/views/project_form.py` with:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ProjectForm
from ..models import Project


def _has_financial_data(project):
    """True when the project already has any budget/vendor value set."""
    return bool(
        project.budget_amount is not None
        or project.actual_cost is not None
        or project.vendor_name
        or project.vendor_bid_amount is not None
    )


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
    return render(request, "projects/form.html", {
        "form": form,
        "project": None,
        "financial_section_open": False,
    })


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
    return render(request, "projects/form.html", {
        "form": form,
        "project": project,
        "financial_section_open": _has_financial_data(project),
    })
```

- [ ] **Step 5: Create the per-field partial**

Create `templates/projects/_form_field.html`:

```html
<div>
  <label class="label" for="{{ field.id_for_label }}">
    {{ field.label }}{% if field.field.required %} *{% endif %}
  </label>
  {{ field }}
  {% if field.help_text %}<p class="text-xs text-gray-500 mt-1">{{ field.help_text }}</p>{% endif %}
  {% if field.errors %}<p class="text-sm text-red-700 mt-1">{{ field.errors|join:", " }}</p>{% endif %}
</div>
```

- [ ] **Step 6: Restructure the project form template**

Replace the full contents of `templates/projects/form.html` with:

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
    {% if field.name in form.FINANCIAL_FIELD_NAMES %}
      {# rendered inside the <details> section below #}
    {% elif field.name == "delay_reason" %}
      <div id="delay-reason-field">{% include "projects/_form_field.html" %}</div>
    {% else %}
      {% include "projects/_form_field.html" %}
    {% endif %}
  {% endfor %}

  <details {% if financial_section_open %}open{% endif %}
           class="border border-gray-200 rounded-lg p-4">
    <summary class="cursor-pointer text-sm font-medium text-gray-700">
      Budget &amp; vendor details (optional)
    </summary>
    <div class="space-y-4 mt-4">
      {% for field in form %}
        {% if field.name in form.FINANCIAL_FIELD_NAMES %}
          {% include "projects/_form_field.html" %}
        {% endif %}
      {% endfor %}
    </div>
  </details>

  <div class="flex gap-2 pt-4">
    <button type="submit" class="btn-primary">Save</button>
    <a href="{% if project %}{% url 'projects:detail' project.pk %}{% else %}{% url 'projects:list' %}{% endif %}"
       class="btn-secondary">Cancel</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_form.py -v`
Expected: PASS — the three new tests plus the existing form-view tests are all green.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/forms/project.py apps/projects/views/project_form.py templates/projects/_form_field.html templates/projects/form.html apps/projects/tests/test_views_form.py
git commit -m "feat(projects): collapse budget/vendor fields into a details section"
```

---

## Task 7: Delay-reason field appears only when status is Delayed

A small vanilla-JS file toggles the visibility of the `#delay-reason-field` container (created in Task 6) based on the status `<select>`. With JavaScript disabled the field stays visible — the server-side requirement in `ProjectForm.clean()` is unchanged and remains the source of truth.

**Files:**
- Create: `static/js/delay-reason-toggle.js`
- Modify: `templates/projects/form.html`
- Test: `apps/projects/tests/test_views_form.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_form.py`:

```python
@pytest.mark.django_db
def test_create_form_has_delay_reason_js_hooks(auth_client, category):
    """The status select and delay-reason container expose the ids the
    toggle script targets; a regression that removes a hook is caught here."""
    response = auth_client.get(reverse("projects:create"))
    content = response.content.decode()
    assert 'id="id_status"' in content
    assert 'id="delay-reason-field"' in content


@pytest.mark.django_db
def test_create_form_loads_the_toggle_script(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    assert "js/delay-reason-toggle.js" in response.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_form.py::test_create_form_loads_the_toggle_script -v`
Expected: FAIL — the form template does not reference the script. (`test_create_form_has_delay_reason_js_hooks` already passes — the hooks were added in Task 6.)

- [ ] **Step 3: Create the toggle script**

Create `static/js/delay-reason-toggle.js`:

```javascript
// Shows the delay-reason field only when the project status is "Delayed".
// Progressive enhancement: with JS disabled the field stays visible and the
// server-side validation in ProjectForm.clean() still enforces the rule.
(function () {
  "use strict";

  function syncVisibility() {
    var status = document.getElementById("id_status");
    var container = document.getElementById("delay-reason-field");
    if (!status || !container) {
      return;
    }
    container.style.display = status.value === "delayed" ? "" : "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var status = document.getElementById("id_status");
    if (status) {
      status.addEventListener("change", syncVisibility);
    }
    syncVisibility();
  });
})();
```

- [ ] **Step 4: Load the script from the form template**

In `templates/projects/form.html`, add `{% load static %}` on the second line (immediately after `{% extends "base.html" %}`), and add the script tag immediately before the closing `{% endblock %}`:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}{% if project %}Edit {{ project.title }}{% else %}New project{% endif %}{% endblock %}
```

```html
<script src="{% static 'js/delay-reason-toggle.js' %}"></script>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_form.py -v`
Expected: PASS — all form-view tests green.

- [ ] **Step 6: Verify the server-side rule is unchanged**

Run: `python -m pytest apps/projects/tests/test_forms_project.py -v`
Expected: PASS — the existing `delay_reason`-required-when-delayed tests still pass (this feature is purely client-side; no `clean()` change was made).

- [ ] **Step 7: Commit**

```bash
git add static/js/delay-reason-toggle.js templates/projects/form.html apps/projects/tests/test_views_form.py
git commit -m "feat(projects): show delay reason only when status is Delayed"
```

---

## Task 8: Rebuild the Tailwind CSS bundle

PythonAnywhere has no build step, so `static/css/output.css` is committed and must be regenerated whenever templates change. Tasks 2-7 added new templates and class combinations.

**Files:**
- Modify: `static/css/output.css` (regenerated)

- [ ] **Step 1: Rebuild the CSS bundle**

Run from the repo root (the Tailwind binary is gitignored — on Windows it is `bin/tailwindcss.exe`, on Linux `bin/tailwindcss-linux-x64`):

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
```

Expected: the command reports a "Done" line and writes `static/css/output.css`.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest`
Expected: PASS — all tests green (the prior ~133 plus the tests added in this plan).

- [ ] **Step 3: Run the linter**

Run: `ruff check .`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add static/css/output.css
git commit -m "build: rebuild Tailwind CSS for category page and form changes"
```

---

## Self-Review

**1. Spec coverage:**
- Feature 1 — category management page: Task 2 (list + counts + Account link), Task 3 (add, with display_order = max+1, inline error on blank/duplicate), Task 4 (rename), Task 5 (delete-only-when-unused, "in use by N" label, `ProtectedError` backstop). Seed change ("Misc", display_order 7, idempotent): Task 1. `@login_required` on all views: present in every category view. ✓
- Feature 2 — collapsible budget/vendor section: Task 6 (`<details>`, collapsed on create, `<details open>` on edit with financial data, `financial_section_open` flag, no JS). ✓
- Feature 3 — conditional delay-reason field: Task 7 (vanilla-JS file under `static/js/`, runs on load + on status change; server-side rule unchanged, verified in Task 7 Step 6). ✓
- Spec §8 testing — per-category counts (Task 2), seven categories incl. Misc + idempotent (Task 1), `<details>` collapsed/open states (Task 6), JS hooks present (Task 7). ✓
- Spec §9 out of scope — category reordering, soft-archive, detail-page budget display: none introduced. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Every code step shows complete code. The only `{# ... #}` in the plan is an intentional Django template comment in the rendered output (Task 6 Step 6), not a plan placeholder.

**3. Type consistency:** `_categories_with_counts()` defined in Task 2, reused in Task 3 — same signature. `project_count` annotation name used consistently in the view, template, and tests. `FINANCIAL_FIELD_NAMES` defined in Task 6 Step 3, referenced in `form.html` Step 6. `financial_section_open` set by both form views (Task 6 Step 4) and read in `form.html`. `#delay-reason-field` / `#id_status` ids: created in Task 6's template, targeted by the Task 7 script and asserted by Task 7 tests. URL names (`category_list`, `category_add`, `category_rename`, `category_delete`) are consistent between `urls.py`, views' `redirect()` calls, templates, and tests.

Note on incremental view files: `apps/projects/views/category.py` is rewritten in full in Task 3 Step 5 (adding `messages`/`Max` imports and `category_add`), then appended to in Tasks 4 and 5. Task 4 Step 3 and Task 5 Step 3 each call out the exact import line to update — no import is left missing.
