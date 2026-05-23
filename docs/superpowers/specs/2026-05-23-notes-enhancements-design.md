# HOA Task Manager — Notes Enhancements — Design

**Date:** 2026-05-23
**Author:** Project owner (Baran) + Claude
**Status:** Approved, ready for implementation planning

---

## 1. Background

The project detail page already has a Notes section: a textarea to add an
`UpdateNote`, followed by a chronological list of past notes rendered from
markdown. The model is small (`project`, `body`, `author`, `created_at`) and
append-only — no edit, no delete.

The owner wants notes to do more work as the project's living record:
- **Anchor context.** A pinned note serves as the "what is this project"
  description, so a board member opening a project for the first time can
  understand it without digging through 20 historical updates.
- **Latest-update visibility.** Subsequent notes remain a chronological
  record of what's happening, what's been done, what's planned.
- **Maintenance.** Notes get edited (fix a typo, add context) and
  occasionally deleted (wrote in the wrong project, redundant). Deletes
  need a confirmation guardrail.
- **Honest attribution.** Notes should display the linked roster person's
  name (e.g. "McLean Baran"), not the raw email address — same fix already
  applied to the dashboard activity feed.

All four refinements are confined to `apps/projects`. One small schema
change (two columns + one partial unique constraint), one new form, three
new HTMX endpoints, one new template partial, plus template updates.

## 2. Scope

**In scope:**
- Switch `_note_card.html` to render `display_name` instead of email.
- Add `UpdateNote.is_pinned` (boolean) with a partial unique constraint
  enforcing one pinned note per project.
- Add `UpdateNote.updated_at` (auto_now) so we can show an "(edited)"
  indicator.
- New HTMX endpoints: `notes/<pk>/edit/`, `notes/<pk>/show/`,
  `notes/<pk>/save/`, `notes/<pk>/delete/`, `notes/<pk>/pin/`.
- Update the inline-edit form, the note card (Edit / Delete / Pin
  buttons, pin badge, edited indicator), and the section template
  (pinned at the top, regular below).
- Tests covering each endpoint, the unique constraint, the display-name
  rendering, and the edit/delete UX.

**Out of scope:**
- **Author-only edit/delete permissions.** Any authenticated user can
  edit or delete any note. Matches the flat single-role auth model used
  elsewhere. A future change can restrict if needed.
- **Edit history / versioning.** Editing a note overwrites the previous
  text. No diff log, no "see previous versions". The audit trail is
  the original author + creation timestamp + the edited indicator.
- **Tracking the editor's identity.** Only the original `author` is
  shown. Adding `edited_by` would clutter the card and the schema for
  marginal value at HOA scale.
- **Writing note edits/deletes to ActivityLog.** Notes are themselves
  the activity for project content; doubling-up would be noise.
- **Multiple pinned notes per project.** Exactly one or zero.
- **Soft delete.** Deletes are hard. The HTMX confirmation dialog is the
  safety net.
- **Reordering of unpinned notes.** They stay chronological (newest
  first).

## 3. Feature 1 — Display name in note attribution

The card currently renders:

```html
<div>... · {{ n.author.email|default:n.author.username }}</div>
```

Switch to:

```html
<div>... · {{ n.author.profile.display_name }}</div>
```

`UserProfile.display_name` (added in commit `a71118f`) returns the linked
`RosterPerson.name` if set, otherwise the user's email, otherwise the
username. Same property already in use on the dashboard activity feed,
the project detail page Activity panel, and the dashboard Recent activity.

**N+1 prevention.** The detail view's `prefetch_related` already includes
`notes__author`. Extend it to `notes__author__profile__roster_person`.

## 4. Feature 2 — Pin one note per project

### Model change

Add a boolean to `apps.projects.models.note.UpdateNote`:

```python
is_pinned = models.BooleanField(default=False)
```

Enforce at most one pinned note per project via a partial unique
constraint:

```python
class Meta:
    ordering = ["-is_pinned", "-created_at", "-pk"]
    constraints = [
        models.UniqueConstraint(
            fields=["project"],
            condition=models.Q(is_pinned=True),
            name="unique_pinned_note_per_project",
        ),
    ]
```

The `ordering` change puts the pinned note (if any) at the top, then
falls back to existing chronological order.

### Pin endpoint

`POST notes/<pk>/pin/` — toggles the note's `is_pinned` state.

Pinning a previously-unpinned note must first unpin any other pinned note
on the same project (in a single transaction so the unique constraint is
never violated):

```python
@login_required
@require_http_methods(["POST"])
def note_pin(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    project = note.project
    with transaction.atomic():
        if note.is_pinned:
            note.is_pinned = False
        else:
            UpdateNote.objects.filter(
                project=project, is_pinned=True,
            ).update(is_pinned=False)
            note.is_pinned = True
        note.save(update_fields=["is_pinned", "updated_at"])
    return _render_notes_list(request, project)
```

`update_fields` is the only safe way to save without bumping
`updated_at` for a pin/unpin (we don't want pinning to count as an edit
for the "(edited)" indicator). Specifically, including `updated_at` in
`update_fields` while NOT including it on the underlying field's
`auto_now`-skipping save... wait, that's not how it works. The clean
approach: explicitly set `note.updated_at = note.updated_at` (no-op) or
use `.update()` directly. Simplest: use `UpdateNote.objects.filter(pk=note.pk).update(is_pinned=...)`
which bypasses `auto_now` entirely.

Re-writing for clarity:

```python
def note_pin(request, pk):
    note = get_object_or_404(UpdateNote, pk=pk)
    project = note.project
    with transaction.atomic():
        if note.is_pinned:
            UpdateNote.objects.filter(pk=note.pk).update(is_pinned=False)
        else:
            UpdateNote.objects.filter(
                project=project, is_pinned=True,
            ).update(is_pinned=False)
            UpdateNote.objects.filter(pk=note.pk).update(is_pinned=True)
    return _render_notes_list(request, project)
```

Using `.update()` avoids both `auto_now` bumps and `save()` signals, which
is the right behavior for a pin (it's metadata, not content).

### UI

Each note card has a **Pin** button (text changes to **Unpin** when the
note is currently pinned). The pinned note renders with:
- A 📌 leading the timestamp/author line.
- A subtle amber left-border (`border-amber-300`) instead of the default
  gray, so it's visually obvious without dominating the layout. Amber
  palette matches the existing unlinked-banner.

The Notes section renders pinned first (via the new model ordering),
then chronological. If no note is pinned, the layout is unchanged from
today.

## 5. Feature 3 — Edit notes inline (HTMX)

### Model change

Add an `updated_at` field for the "(edited)" indicator:

```python
updated_at = models.DateTimeField(auto_now=True)
```

### Endpoints

Three endpoints mirroring the project's existing inline-edit pattern
(`status_edit/show/save`, `priority_edit/show/save`, etc.):

- `GET notes/<pk>/edit/` — returns the inline edit form (a textarea
  prefilled with the current body, plus Save and Cancel buttons),
  swapped into the note card via HTMX.
- `GET notes/<pk>/show/` — returns the read-only note card. Used by the
  Cancel button to revert without saving.
- `POST notes/<pk>/save/` — validates and saves the new body, then
  returns the read-only note card.

All three return a single `<li>` (the rebuilt card), so the HTMX swap
target is `closest li` with `outerHTML`.

### Form

Reuse the existing `UpdateNoteForm` (body-only, non-empty validation).
The same form class powers both the create flow and the edit flow.

### "(edited)" indicator

In `_note_card.html`, show a small italic "(edited)" next to the
timestamp when `updated_at - created_at > 5 seconds` (a tolerance to
ignore the initial create write, which sets both timestamps to nearly
the same moment).

```django
{{ n.created_at|date:"M j, Y · g:i A" }}
{% if n.updated_at|timesince:n.created_at != "0 minutes" %}<span class="italic text-gray-400">(edited)</span>{% endif %}
```

(The `timesince` filter rounds to minutes, so subsecond delays from the
initial create don't trigger the indicator. A second-level threshold
would require a custom filter; minute-level is good enough.)

### Permissions

`@login_required` only. Any authenticated user can edit any note. The
original `author` field is **not** mutated by edits — attribution stays
honest.

## 6. Feature 4 — Delete notes with warning

### Endpoint

`POST notes/<pk>/delete/` — deletes the note and returns the rebuilt
notes list (so the deleted card disappears).

### UI

The Delete button on each note card uses HTMX's `hx-confirm` attribute,
which triggers the browser's native confirmation dialog before sending
the request:

```html
<button hx-post="{% url 'projects:note_delete' n.pk %}"
        hx-target="#notes-list-{{ project.pk }}"
        hx-swap="outerHTML"
        hx-confirm="Delete this note? This can't be undone."
        class="text-xs text-red-700 hover:underline">Delete</button>
```

No JavaScript is needed beyond HTMX itself, no modal component to
maintain. The native dialog is keyboard-accessible by default.

### Permissions

Same as edit: `@login_required` only. Any authenticated user can delete
any note.

### What happens to a pinned note that's deleted?

The note (and its `is_pinned=True` row) is gone. The project simply has
no pinned note until someone pins another. No automatic "promote the
next note" magic — explicit user action only.

## 7. Data model summary

Two new fields on `UpdateNote`, plus one constraint:

```python
class UpdateNote(models.Model):
    project = models.ForeignKey(...)         # unchanged
    body = models.TextField()                # unchanged
    author = models.ForeignKey(...)          # unchanged
    created_at = models.DateTimeField(auto_now_add=True)  # unchanged
    is_pinned = models.BooleanField(default=False)        # NEW
    updated_at = models.DateTimeField(auto_now=True)      # NEW

    class Meta:
        ordering = ["-is_pinned", "-created_at", "-pk"]   # changed (was ["-created_at", "-pk"])
        constraints = [
            models.UniqueConstraint(                       # NEW
                fields=["project"],
                condition=models.Q(is_pinned=True),
                name="unique_pinned_note_per_project",
            ),
        ]
```

One auto-generated migration: `apps/projects/migrations/00XX_note_pin_and_updated_at.py`.

## 8. Components & files

**New:**
- `apps/projects/views/note.py` — extended with `note_edit`,
  `note_show`, `note_save`, `note_delete`, `note_pin` plus a
  `_render_notes_list` helper.
- `templates/projects/_note_edit_form.html` — inline edit form
  partial (textarea + Save/Cancel).
- Tests in `apps/projects/tests/test_views_note.py` extended.

**Modified:**
- `apps/projects/models/note.py` — add `is_pinned`, `updated_at`,
  ordering, unique constraint.
- `apps/projects/views/__init__.py` — re-export the 4 new views.
- `apps/projects/urls.py` — 5 new routes.
- `apps/projects/views/project_detail.py` — extend `prefetch_related`
  to include `notes__author__profile__roster_person`.
- `templates/projects/_note_card.html` — display_name, edited
  indicator, Edit / Delete / Pin buttons, pin badge, amber border when
  pinned.
- `templates/projects/_notes_section.html` — already iterates
  `project.notes.all`; no change needed because the model's new
  ordering puts pinned first.
- `apps/projects/tests/test_models_note.py` — add pin uniqueness and
  ordering tests.

**Auto-generated:**
- `apps/projects/migrations/00XX_note_pin_and_updated_at.py`.

## 9. Error handling

- **Pinning a second note** while another is pinned: the view unpins the
  first in the same transaction, so the unique constraint is never
  violated. Tested explicitly.
- **Empty body on edit save**: `UpdateNoteForm.clean_body()` already
  rejects empty/whitespace-only bodies; the same validation runs on
  both create and edit. HTMX returns the form with the validation error
  message rendered inline.
- **Edit a note that was deleted in a parallel session**:
  `get_object_or_404` returns 404, HTMX leaves the page alone. The
  user's next interaction refreshes their view.
- **Delete a pinned note**: the row (and its pin status) is removed.
  The project has no pinned note until someone pins another. No
  automatic promotion.

## 10. Testing

- **Model**:
  - The unique constraint raises `IntegrityError` when two notes on the
    same project are pinned via raw `.objects.create(is_pinned=True)`
    calls.
  - Notes on *different* projects can both be pinned simultaneously
    (the constraint is per-project, not global).
  - Ordering: pinned note appears first regardless of `created_at`.

- **Views**:
  - `note_edit` returns the edit form HTML, including the prefilled
    body.
  - `note_save` updates the body, leaves the original `author`
    unchanged, bumps `updated_at`.
  - `note_save` with empty body returns the edit form with validation
    error.
  - `note_delete` removes the row and returns the rebuilt notes list.
  - `note_pin` on an unpinned note pins it and unpins any previously
    pinned note on the same project.
  - `note_pin` on a pinned note unpins it.
  - All five endpoints require login (`@login_required`).
  - All four mutation endpoints (`save`, `delete`, `pin`) reject GET
    via `@require_http_methods(["POST"])` — except `edit` and `show`,
    which are GET-only.

- **Template**:
  - `_note_card.html` renders `display_name` (assert the linked
    person's name appears in the response).
  - The "(edited)" indicator is absent on a freshly-created note and
    present after an edit.
  - The pin badge (📌) and amber border are present for a pinned note
    and absent for an unpinned one.

## 11. Out of scope (recap)

Listed in §2; reproducing here for the contract:
- No author-only permission restrictions.
- No edit history / versioning.
- No `edited_by` field.
- No ActivityLog entries for note operations.
- No soft delete.
- No reordering beyond pinned-first + chronological.
- No multiple pins per project.

## 12. Cost & risk

- **Schema risk**: low. Two nullable-equivalent columns (`is_pinned`
  defaults to False, `updated_at` is `auto_now`); migration is
  trivially reversible.
- **UI risk**: low. The inline-edit/show/save pattern is identical to
  the four existing inline editors on the detail page (`status`,
  `priority`, `dates`, `budget`, `vendor`).
- **Data risk**: hard delete is the user's explicit choice. The
  pre-delete confirmation is a single HTMX attribute.
- **Performance**: one extra prefetch (`notes__author__profile__roster_person`)
  on the detail view. Linear with notes count; no N+1.
