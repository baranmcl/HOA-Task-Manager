# Notes Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the project detail page's notes section so notes can be edited, deleted (with confirmation), and pinned, and so attribution shows the linked roster person's name instead of the email.

**Architecture:** Two new columns on `UpdateNote` (`is_pinned`, `updated_at`) plus a partial unique constraint enforcing one pinned note per project. Five new HTMX endpoints (`edit`, `show`, `save`, `delete`, `pin`) mirror the existing inline-editor pattern in `apps/projects/views/inline.py` (status/priority/dates/budget/vendor). Templates are updated additively — `_note_card.html` gains Edit / Delete / Pin buttons, an "(edited)" indicator, and a pinned-state visual treatment; `_notes_list_swap.html` already exists and is reused for the delete/pin/add swap targets.

**Tech Stack:** Django 5.0.x, HTMX 1.9.x (already loaded via `base.html`), pytest-django, ruff, Tailwind CSS standalone (`static/css/output.css` is committed and must be rebuilt at the end).

---

## File Structure

**New files:**
- `templates/projects/_note_edit_form.html` — inline edit form (textarea + Save + Cancel) HTMX-swapped into a note card. Self-contained partial; uses `{{ n }}` for the note being edited.
- One auto-generated migration: `apps/projects/migrations/00XX_note_pin_and_updated_at.py` (number assigned by `makemigrations`).

**Modified files:**
- `apps/projects/models/note.py` — add `is_pinned`, `updated_at`, `is_edited` property; update `Meta.ordering`; add the partial unique constraint.
- `apps/projects/views/note.py` — add `note_edit`, `note_show`, `note_save`, `note_delete`, `note_pin`, plus a `_render_card` helper. The existing `note_add` is unchanged.
- `apps/projects/views/__init__.py` — re-export the five new views.
- `apps/projects/views/project_detail.py` — extend `prefetch_related` to `notes__author__profile__roster_person`.
- `apps/projects/urls.py` — add five new routes.
- `templates/projects/_note_card.html` — display_name, edited indicator, Edit / Delete / Pin buttons, 📌 badge, amber border when pinned.
- `apps/projects/tests/test_models_note.py` — pin uniqueness + ordering tests, plus `is_edited` property tests.
- `apps/projects/tests/test_views_note.py` — extensive new coverage for edit/show/save/delete/pin endpoints, display name rendering, login-required checks.
- `static/css/output.css` — rebuilt by Tailwind at the end.

---

## Task 1: Schema — `is_pinned`, `updated_at`, ordering, partial unique constraint

Foundation. Two new fields on `UpdateNote`, an ordering change, a per-project partial unique constraint, and an `is_edited` property to keep the template logic simple.

**Files:**
- Modify: `apps/projects/models/note.py`
- Create: `apps/projects/migrations/00XX_note_pin_and_updated_at.py` (auto-generated)
- Test: `apps/projects/tests/test_models_note.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_models_note.py`:

```python
import datetime as dt
from time import sleep

from django.db import IntegrityError
from django.utils import timezone

from apps.projects.models import Project


@pytest.mark.django_db
def test_pinned_note_is_unique_per_project(project, user):
    UpdateNote.objects.create(project=project, body="First", author=user, is_pinned=True)
    with pytest.raises(IntegrityError):
        UpdateNote.objects.create(project=project, body="Second", author=user, is_pinned=True)


@pytest.mark.django_db
def test_pinned_notes_on_different_projects_dont_conflict(category, user):
    p1 = Project.objects.create(title="P1", category=category, created_by=user)
    p2 = Project.objects.create(title="P2", category=category, created_by=user)
    UpdateNote.objects.create(project=p1, body="One", author=user, is_pinned=True)
    UpdateNote.objects.create(project=p2, body="Two", author=user, is_pinned=True)
    # Both succeed — no IntegrityError.
    assert UpdateNote.objects.filter(is_pinned=True).count() == 2


@pytest.mark.django_db
def test_pinned_note_appears_first_in_ordering(project, user):
    older_unpinned = UpdateNote.objects.create(project=project, body="Older", author=user)
    UpdateNote.objects.create(project=project, body="Newer", author=user)
    # Pin the older one; it should jump to position 0.
    UpdateNote.objects.filter(pk=older_unpinned.pk).update(is_pinned=True)
    notes = list(UpdateNote.objects.filter(project=project))
    assert notes[0].body == "Older"


@pytest.mark.django_db
def test_is_edited_false_on_fresh_note(project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    note.refresh_from_db()
    assert note.is_edited is False


@pytest.mark.django_db
def test_is_edited_true_after_save_with_delay(project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    # Bump updated_at to be 5 seconds ahead of created_at.
    UpdateNote.objects.filter(pk=note.pk).update(
        updated_at=note.created_at + dt.timedelta(seconds=5),
    )
    note.refresh_from_db()
    assert note.is_edited is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_models_note.py -v`
Expected: FAIL — `is_pinned` field doesn't exist; `is_edited` property doesn't exist.

- [ ] **Step 3: Add the fields, ordering, constraint, and property**

Replace the full contents of `apps/projects/models/note.py` with:

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
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_pinned", "-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(is_pinned=True),
                name="unique_pinned_note_per_project",
            ),
        ]

    def __str__(self):
        return f"Note on {self.project.title} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def rendered_html(self) -> str:
        return render_note(self.body)

    @property
    def is_edited(self) -> bool:
        """True when the note has been edited at least ~1 second after creation.

        Both `created_at` (auto_now_add) and `updated_at` (auto_now) are set
        on insert, but at slightly different moments — they may differ by a
        few microseconds. The 1-second tolerance ignores that initial gap.
        """
        if self.updated_at is None or self.created_at is None:
            return False
        return (self.updated_at - self.created_at).total_seconds() > 1
```

- [ ] **Step 4: Generate the migration**

Run: `python manage.py makemigrations projects`
Expected: creates `apps/projects/migrations/00XX_note_pin_and_updated_at.py` (the number will be whatever's next in sequence) containing operations for `AddField(is_pinned)`, `AddField(updated_at)`, `AlterModelOptions` (ordering), and `AddConstraint`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_models_note.py -v`
Expected: PASS — all 5 new tests green plus the existing 3.

- [ ] **Step 6: Run the existing test suite to confirm no regressions**

Run: `python -m pytest apps/projects/tests/ -q`
Expected: All tests green.

- [ ] **Step 7: Commit**

```bash
git add apps/projects/models/note.py apps/projects/migrations/ apps/projects/tests/test_models_note.py
git commit -m "feat(projects): UpdateNote pin and updated_at with partial unique constraint"
```

---

## Task 2: Display name in the note card (+ prefetch extension)

Switch `_note_card.html` to use `display_name` instead of email, and extend the detail view's prefetch so we don't introduce an N+1.

**Files:**
- Modify: `templates/projects/_note_card.html`
- Modify: `apps/projects/views/project_detail.py`
- Test: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/projects/tests/test_views_note.py` (add `from apps.roster.models import RosterPerson` to the imports if not present):

```python
from apps.roster.models import RosterPerson


@pytest.mark.django_db
def test_note_card_renders_linked_roster_name_on_detail_page(auth_client, project, user):
    """When the note's author has a linked RosterPerson, the detail page must
    render that person's name in the note card — not the user's email.
    """
    person = RosterPerson.objects.create(name="Casey Carter")
    user.profile.roster_person = person
    user.profile.save()
    UpdateNote.objects.create(project=project, body="Hello", author=user)

    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    content = response.content.decode()
    assert "Casey Carter" in content
    assert user.email not in content.split('<section class="bg-white rounded-lg shadow p-5">')[-2]
```

(The split is a defensive way to bound the email-absence check to the notes section; if it's brittle on your version of the template, simplify to `assert user.email not in content` once you've confirmed no other UI element on the detail page renders the email.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/projects/tests/test_views_note.py::test_note_card_renders_linked_roster_name_on_detail_page -v`
Expected: FAIL — the card currently renders `n.author.email`, not the roster person's name.

- [ ] **Step 3: Update the note card template**

In `templates/projects/_note_card.html`, replace:

```html
  <div class="text-xs text-gray-500 mb-1">{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.email|default:n.author.username }}</div>
```

with:

```html
  <div class="text-xs text-gray-500 mb-1">{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</div>
```

- [ ] **Step 4: Extend prefetch_related in the detail view**

In `apps/projects/views/project_detail.py`, the queryset currently includes:

```python
    project = get_object_or_404(
        Project.objects.select_related("category", "board_approval", "created_by").prefetch_related(
            "raci_assignments__person",
            "tags",
            "notes__author",
            "attachments__uploaded_by",
        ),
        pk=pk,
    )
```

Update the `notes__author` entry to `notes__author__profile__roster_person`:

```python
    project = get_object_or_404(
        Project.objects.select_related("category", "board_approval", "created_by").prefetch_related(
            "raci_assignments__person",
            "tags",
            "notes__author__profile__roster_person",
            "attachments__uploaded_by",
        ),
        pk=pk,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v`
Expected: PASS — the new test plus the existing two (`test_add_note`, `test_add_empty_note_rejected`).

- [ ] **Step 6: Commit**

```bash
git add templates/projects/_note_card.html apps/projects/views/project_detail.py apps/projects/tests/test_views_note.py
git commit -m "feat(notes): render linked roster name in note attribution"
```

---

## Task 3: Inline edit endpoints (edit / show / save)

Mirror the existing inline-edit pattern in `apps/projects/views/inline.py` — GET edit returns the form, GET show returns the read-only card (for Cancel), POST save persists and returns the read-only card.

**Files:**
- Modify: `apps/projects/views/note.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Create: `templates/projects/_note_edit_form.html`
- Modify: `templates/projects/_note_card.html`
- Test: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_note.py`:

```python
@pytest.mark.django_db
def test_note_edit_returns_form_with_prefilled_body(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Original body", author=user)
    response = auth_client.get(reverse("projects:note_edit", args=[note.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Original body" in content
    assert 'name="body"' in content


@pytest.mark.django_db
def test_note_show_returns_read_only_card(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Read me", author=user)
    response = auth_client.get(reverse("projects:note_show", args=[note.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Read me" in content
    # The read-only card does NOT contain a textarea.
    assert "<textarea" not in content


@pytest.mark.django_db
def test_note_save_updates_body_and_keeps_author(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Old body", author=user)
    response = auth_client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "New body"},
    )
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.body == "New body"
    assert note.author == user  # author is immutable on edit


@pytest.mark.django_db
def test_note_save_with_empty_body_returns_400(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Keep me", author=user)
    response = auth_client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "   "},
    )
    assert response.status_code == 400
    note.refresh_from_db()
    assert note.body == "Keep me"  # unchanged


@pytest.mark.django_db
def test_note_edit_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.get(reverse("projects:note_edit", args=[note.pk]))
    assert response.status_code == 302  # redirect to login


@pytest.mark.django_db
def test_note_save_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "new"},
    )
    assert response.status_code == 302
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v -k "edit or show or save"`
Expected: FAIL — `NoReverseMatch` for the new URL names.

- [ ] **Step 3: Add the inline-edit views to `apps/projects/views/note.py`**

Replace the full contents of `apps/projects/views/note.py` with:

```python
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import UpdateNoteForm
from ..models import Project, UpdateNote


def _render_card(request, note):
    return render(request, "projects/_note_card.html", {
        "n": note, "project": note.project,
    })


def _render_notes_list(request, project):
    return render(request, "projects/_notes_list_swap.html", {"project": project})


@login_required
@require_http_methods(["POST"])
def note_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = UpdateNoteForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(", ".join(form.errors.get("body", [])))
    note = form.save(commit=False)
    note.project = project
    note.author = request.user
    note.save()
    return _render_notes_list(request, project)


@login_required
def note_edit(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    return render(request, "projects/_note_edit_form.html", {
        "n": note, "project": note.project,
    })


@login_required
def note_show(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    return _render_card(request, note)


@login_required
@require_http_methods(["POST"])
def note_save(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    form = UpdateNoteForm(request.POST, instance=note)
    if not form.is_valid():
        return HttpResponseBadRequest(", ".join(form.errors.get("body", [])))
    form.save()
    return _render_card(request, note)
```

Note: `_render_notes_list` is added now even though `note_add` is the only caller in this task — Tasks 4 and 5 will reuse it.

- [ ] **Step 4: Re-export the new views**

In `apps/projects/views/__init__.py`, the existing line `from .note import note_add as note_add` stays. Add three more:

```python
from .note import note_edit as note_edit
from .note import note_save as note_save
from .note import note_show as note_show
```

- [ ] **Step 5: Add the URL routes**

In `apps/projects/urls.py`, the existing line `path("<int:pk>/note/", views.note_add, name="note_add"),` stays. Add three routes immediately after it:

```python
    path("note/<int:pk>/edit/", views.note_edit, name="note_edit"),
    path("note/<int:pk>/show/", views.note_show, name="note_show"),
    path("note/<int:pk>/save/", views.note_save, name="note_save"),
```

(Note the URL shape: `note/<pk>/...` rather than `<int:pk>/note/...` — `pk` here is the note's pk, not the project's pk. This matches the `attachment/<int:pk>/...` and `raci/<int:pk>/...` patterns elsewhere in this URL conf.)

- [ ] **Step 6: Create the inline edit form partial**

Create `templates/projects/_note_edit_form.html`:

```html
<li class="border-l-2 border-gray-200 pl-3" id="note-card-{{ n.pk }}">
  <form hx-post="{% url 'projects:note_save' n.pk %}"
        hx-target="closest li" hx-swap="outerHTML"
        class="space-y-2">
    {% csrf_token %}
    <textarea name="body" rows="3" class="input" required>{{ n.body }}</textarea>
    <div class="flex gap-2">
      <button type="submit" class="btn-primary text-xs">Save</button>
      <button type="button" class="btn-secondary text-xs"
              hx-get="{% url 'projects:note_show' n.pk %}"
              hx-target="closest li" hx-swap="outerHTML">Cancel</button>
    </div>
  </form>
</li>
```

- [ ] **Step 7: Add the Edit button to the note card**

In `templates/projects/_note_card.html`, replace the full contents with:

```html
<li class="border-l-2 border-gray-200 pl-3" id="note-card-{{ n.pk }}">
  <div class="text-xs text-gray-500 mb-1 flex items-center gap-2">
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</span>
    <button class="text-blue-700 hover:underline"
            hx-get="{% url 'projects:note_edit' n.pk %}"
            hx-target="closest li" hx-swap="outerHTML">Edit</button>
  </div>
  <div class="prose prose-sm text-gray-800">{{ n.rendered_html|safe }}</div>
</li>
```

(Delete/Pin buttons, the edited indicator, and the pinned visual treatment are added in subsequent tasks. This step adds only the Edit button.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v`
Expected: PASS — all new edit/show/save tests green, existing tests still green.

- [ ] **Step 9: Commit**

```bash
git add apps/projects/views/note.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/_note_edit_form.html templates/projects/_note_card.html apps/projects/tests/test_views_note.py
git commit -m "feat(notes): inline edit endpoints (edit/show/save)"
```

---

## Task 4: Delete endpoint with HTMX `hx-confirm`

A single POST endpoint that removes the note and returns the rebuilt notes list. The Delete button uses HTMX's `hx-confirm` attribute for the native browser confirmation dialog.

**Files:**
- Modify: `apps/projects/views/note.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Modify: `templates/projects/_note_card.html`
- Test: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_note.py`:

```python
@pytest.mark.django_db
def test_note_delete_removes_the_row(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Goodbye", author=user)
    response = auth_client.post(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 200
    assert not UpdateNote.objects.filter(pk=note.pk).exists()


@pytest.mark.django_db
def test_note_delete_returns_rebuilt_notes_list(auth_client, project, user):
    UpdateNote.objects.create(project=project, body="Keep me", author=user)
    note_to_delete = UpdateNote.objects.create(
        project=project, body="Delete me", author=user,
    )
    response = auth_client.post(
        reverse("projects:note_delete", args=[note_to_delete.pk]),
    )
    content = response.content.decode()
    assert "Keep me" in content
    assert "Delete me" not in content


@pytest.mark.django_db
def test_note_delete_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_note_delete_rejects_get(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 405
    assert UpdateNote.objects.filter(pk=note.pk).exists()  # still there
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v -k "delete"`
Expected: FAIL — `NoReverseMatch` for `projects:note_delete`.

- [ ] **Step 3: Add the delete view**

Append to `apps/projects/views/note.py`:

```python
@login_required
@require_http_methods(["POST"])
def note_delete(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    project = note.project
    note.delete()
    return _render_notes_list(request, project)
```

- [ ] **Step 4: Re-export the view**

Add to `apps/projects/views/__init__.py`:

```python
from .note import note_delete as note_delete
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, immediately after the `note/<int:pk>/save/` route:

```python
    path("note/<int:pk>/delete/", views.note_delete, name="note_delete"),
```

- [ ] **Step 6: Add the Delete button to the note card**

In `templates/projects/_note_card.html`, the current file (after Task 3) reads:

```html
<li class="border-l-2 border-gray-200 pl-3" id="note-card-{{ n.pk }}">
  <div class="text-xs text-gray-500 mb-1 flex items-center gap-2">
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</span>
    <button class="text-blue-700 hover:underline"
            hx-get="{% url 'projects:note_edit' n.pk %}"
            hx-target="closest li" hx-swap="outerHTML">Edit</button>
  </div>
  <div class="prose prose-sm text-gray-800">{{ n.rendered_html|safe }}</div>
</li>
```

Add a Delete button next to Edit. Replace the file contents with:

```html
<li class="border-l-2 border-gray-200 pl-3" id="note-card-{{ n.pk }}">
  <div class="text-xs text-gray-500 mb-1 flex items-center gap-2">
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</span>
    <button class="text-blue-700 hover:underline"
            hx-get="{% url 'projects:note_edit' n.pk %}"
            hx-target="closest li" hx-swap="outerHTML">Edit</button>
    <button class="text-red-700 hover:underline"
            hx-post="{% url 'projects:note_delete' n.pk %}"
            hx-target="#notes-list-{{ project.pk }}" hx-swap="outerHTML"
            hx-confirm="Delete this note? This can't be undone.">Delete</button>
  </div>
  <div class="prose prose-sm text-gray-800">{{ n.rendered_html|safe }}</div>
</li>
```

The Delete button's `hx-confirm` attribute triggers the browser's native confirmation dialog. The `hx-target="#notes-list-{{ project.pk }}"` and `hx-swap="outerHTML"` mean the delete response (the rebuilt `<ul>`) replaces the whole notes list.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v`
Expected: PASS — all delete tests green, all earlier tests still green.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/views/note.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/_note_card.html apps/projects/tests/test_views_note.py
git commit -m "feat(notes): delete endpoint with hx-confirm warning"
```

---

## Task 5: Pin / Unpin endpoint

Single POST endpoint that toggles `is_pinned`. When pinning, any other pinned note on the same project is unpinned first — inside a single transaction so the partial unique constraint is never violated.

**Files:**
- Modify: `apps/projects/views/note.py`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Modify: `templates/projects/_note_card.html`
- Test: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_note.py`:

```python
@pytest.mark.django_db
def test_note_pin_pins_an_unpinned_note(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.is_pinned is True


@pytest.mark.django_db
def test_note_pin_unpins_when_already_pinned(auth_client, project, user):
    note = UpdateNote.objects.create(
        project=project, body="x", author=user, is_pinned=True,
    )
    response = auth_client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.is_pinned is False


@pytest.mark.django_db
def test_pinning_a_new_note_unpins_the_previous_one(auth_client, project, user):
    """Pinning Note B must atomically unpin Note A. The partial unique
    constraint would otherwise raise IntegrityError."""
    note_a = UpdateNote.objects.create(
        project=project, body="A", author=user, is_pinned=True,
    )
    note_b = UpdateNote.objects.create(project=project, body="B", author=user)

    response = auth_client.post(reverse("projects:note_pin", args=[note_b.pk]))
    assert response.status_code == 200

    note_a.refresh_from_db()
    note_b.refresh_from_db()
    assert note_a.is_pinned is False
    assert note_b.is_pinned is True


@pytest.mark.django_db
def test_note_pin_does_not_bump_updated_at(auth_client, project, user):
    """Pin/unpin is metadata, not content — it should not register as an edit."""
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    original_updated_at = note.updated_at

    auth_client.post(reverse("projects:note_pin", args=[note.pk]))

    note.refresh_from_db()
    assert note.updated_at == original_updated_at


@pytest.mark.django_db
def test_note_pin_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_note_pin_rejects_get(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 405
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v -k "pin"`
Expected: FAIL — `NoReverseMatch` for `projects:note_pin`.

- [ ] **Step 3: Add the pin view**

Append to `apps/projects/views/note.py`. First, add `from django.db import transaction` to the imports at the top:

```python
from django.db import transaction
```

Then add the view at the bottom of the file:

```python
@login_required
@require_http_methods(["POST"])
def note_pin(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    project = note.project
    with transaction.atomic():
        if note.is_pinned:
            # Unpin via raw .update() to avoid bumping updated_at (which
            # would falsely register the action as an edit).
            UpdateNote.objects.filter(pk=note.pk).update(is_pinned=False)
        else:
            # Unpin any currently pinned note on this project first, so the
            # partial unique constraint is never violated.
            UpdateNote.objects.filter(
                project=project, is_pinned=True,
            ).update(is_pinned=False)
            UpdateNote.objects.filter(pk=note.pk).update(is_pinned=True)
    return _render_notes_list(request, project)
```

- [ ] **Step 4: Re-export the view**

Add to `apps/projects/views/__init__.py`:

```python
from .note import note_pin as note_pin
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, immediately after the `note/<int:pk>/delete/` route:

```python
    path("note/<int:pk>/pin/", views.note_pin, name="note_pin"),
```

- [ ] **Step 6: Add the Pin button + pin visual treatment to the note card**

In `templates/projects/_note_card.html`, replace the contents with this (which adds the Pin/Unpin button to the action row, the 📌 badge in the timestamp line, and an amber-border when pinned):

```html
<li class="{% if n.is_pinned %}border-l-2 border-amber-300{% else %}border-l-2 border-gray-200{% endif %} pl-3" id="note-card-{{ n.pk }}">
  <div class="text-xs text-gray-500 mb-1 flex items-center gap-2">
    {% if n.is_pinned %}<span title="Pinned">📌</span>{% endif %}
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</span>
    <button class="text-blue-700 hover:underline"
            hx-get="{% url 'projects:note_edit' n.pk %}"
            hx-target="closest li" hx-swap="outerHTML">Edit</button>
    <button class="text-blue-700 hover:underline"
            hx-post="{% url 'projects:note_pin' n.pk %}"
            hx-target="#notes-list-{{ project.pk }}" hx-swap="outerHTML">{% if n.is_pinned %}Unpin{% else %}Pin{% endif %}</button>
    <button class="text-red-700 hover:underline"
            hx-post="{% url 'projects:note_delete' n.pk %}"
            hx-target="#notes-list-{{ project.pk }}" hx-swap="outerHTML"
            hx-confirm="Delete this note? This can't be undone.">Delete</button>
  </div>
  <div class="prose prose-sm text-gray-800">{{ n.rendered_html|safe }}</div>
</li>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v`
Expected: PASS — all pin tests green, all earlier tests still green.

- [ ] **Step 8: Commit**

```bash
git add apps/projects/views/note.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/_note_card.html apps/projects/tests/test_views_note.py
git commit -m "feat(notes): pin endpoint with auto-unpin of prior pinned note"
```

---

## Task 6: "(edited)" indicator in the card

Show an italic "(edited)" next to the timestamp when the note's `is_edited` property is True. Property already exists from Task 1; this task adds the template hook and a render test.

**Files:**
- Modify: `templates/projects/_note_card.html`
- Test: `apps/projects/tests/test_views_note.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_note.py`:

```python
import datetime as dt


@pytest.mark.django_db
def test_edited_indicator_absent_on_fresh_note(auth_client, project, user):
    UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert "(edited)" not in response.content.decode()


@pytest.mark.django_db
def test_edited_indicator_present_after_edit(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    # Bump updated_at to 5 seconds after created_at so `is_edited` is True.
    UpdateNote.objects.filter(pk=note.pk).update(
        updated_at=note.created_at + dt.timedelta(seconds=5),
    )
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert "(edited)" in response.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v -k "edited_indicator"`
Expected: FAIL — the template doesn't render "(edited)" anywhere yet.

- [ ] **Step 3: Add the indicator to the note card**

In `templates/projects/_note_card.html`, replace the `<span>` that renders the timestamp + author with a version that also renders the indicator when `n.is_edited` is True:

Current:
```html
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}</span>
```

New:
```html
    <span>{{ n.created_at|date:"M j, Y · g:i A" }} · {{ n.author.profile.display_name }}{% if n.is_edited %} <span class="italic text-gray-400">(edited)</span>{% endif %}</span>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_note.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add templates/projects/_note_card.html apps/projects/tests/test_views_note.py
git commit -m "feat(notes): show (edited) indicator when a note has been changed"
```

---

## Task 7: Rebuild Tailwind CSS and run the full suite

PythonAnywhere has no build step, so `static/css/output.css` is committed and must be regenerated whenever new utility classes appear in templates. This task adds `border-amber-300` (from the pinned-note treatment) and `italic` (from the edited indicator) — neither is used elsewhere in the codebase, so a rebuild is required.

**Files:** none directly; rebuilds `static/css/output.css`.

- [ ] **Step 1: Verify which utilities are missing**

Run:

```bash
grep -oE '\.border-amber-300\{|\.italic\{' static/css/output.css | sort -u
```

Expected: zero or one line (whichever utilities are already present). If both lines appear, skip Steps 2-3.

- [ ] **Step 2: Rebuild the CSS bundle**

Run from the repo root (Windows binary path; substitute the Linux binary if running on Linux):

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
```

Expected: a "Done" line and a regenerated `static/css/output.css`.

- [ ] **Step 3: Verify both utilities are now present**

Run:

```bash
grep -oE '\.border-amber-300\{|\.italic\{' static/css/output.css | sort -u
```

Expected: both lines appear.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS — all tests green (the existing suite plus the ~20 new tests across this plan).

- [ ] **Step 5: Run the linter**

Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 6: Commit**

```bash
git add static/css/output.css
git commit -m "build: rebuild Tailwind CSS for notes pin and edited indicator"
```

---

## Self-Review

**1. Spec coverage:**
- §3 Feature 1 (display_name in note attribution) → Task 2. ✓
- §4 Feature 2 (pin one note per project): model change → Task 1; pin endpoint → Task 5; UI → Task 5. ✓
- §5 Feature 3 (inline edit + updated_at + "(edited)" indicator): model change → Task 1; edit/show/save endpoints → Task 3; indicator → Task 6. ✓
- §6 Feature 4 (delete with hx-confirm) → Task 4. ✓
- §7 Schema summary (is_pinned, updated_at, ordering, partial unique constraint) → Task 1. ✓
- §8 Components & files: every file listed is touched by exactly one task (with the model in Task 1, views/note.py grown across Tasks 3/4/5, the note card grown across Tasks 2/3/4/5/6). ✓
- §9 Error handling: pinning while another is pinned → Task 5 Step 1 third test; empty body → Task 3 Step 1 fourth test; deleting a pinned note removes the pin status → covered indirectly by Task 4 (the row is gone). ✓
- §10 Testing: each bullet in the spec is satisfied by at least one named test in Tasks 1-6.
- §11 Out of scope: reproduced in the spec; not built. ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"similar to Task N"/"add appropriate error handling". The `00XX` in the migration filename is intentional and Step 4 of Task 1 explains it. Every code step contains complete code.

**3. Type consistency:**
- `is_pinned` (boolean), `updated_at` (DateTimeField), `is_edited` (property returning bool) — same names used in Tasks 1, 5, 6.
- `_render_card(request, note)` and `_render_notes_list(request, project)` helpers defined in Task 3 Step 3; consumed in Tasks 4 (delete) and 5 (pin) with the same signatures.
- The HTMX swap targets are consistent: edit form swaps the single `<li>` (`closest li`); delete and pin swap the whole `<ul>` (`#notes-list-{project_pk}`).
- URL names (`projects:note_edit`, `projects:note_show`, `projects:note_save`, `projects:note_delete`, `projects:note_pin`) used consistently between `urls.py`, view `redirect`/`reverse` calls (none in this plan), templates, and tests.
- The `_render_notes_list` helper is added in Task 3 even though only Task 4 + 5 use its outer-list shape (Task 3's note_add already used the equivalent inline render). Acceptable — the helper provides a single source of truth for "what to return after a list-changing mutation."
