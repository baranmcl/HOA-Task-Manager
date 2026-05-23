# HOA Task Manager — People-Centric Views — Design

**Date:** 2026-05-22
**Author:** Project owner (Baran) + Claude
**Status:** Draft for owner review

---

## 1. Background

After the first hands-on use of the category-management refinements, the owner
identified that the tool is project-centric but not yet **person-centric**. RACI
assignments exist in the data model but are awkward to set, hard to filter on,
and don't shape the dashboard. Tags are entered on the form but never surface
again. Recurring task instances are generated correctly but fall into a
dashboard blind spot. This design adds the connective tissue.

Seven related refinements, all confined to the `accounts` and `projects` apps,
to the dashboard, the project create form, and the project list. One small
schema change (a single nullable FK). Committees and detail-page activity
history are explicitly deferred.

## 2. Feature 1 — Profile↔Roster link

A new `roster_person` field on `UserProfile` connects a login account to the
person it represents on the board roster. This is the foundation that makes
"my tasks" a coherent concept for every other feature in this spec.

**Model change.** Add to `apps.accounts.models.UserProfile`:

```python
roster_person = models.OneToOneField(
    "roster.RosterPerson",
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name="profile",
)
```

- `OneToOneField` because each login user maps to at most one roster entry, and
  vice versa. (Baran-the-user and Baran-the-roster-row are the same person.)
- `SET_NULL` because deleting a roster row should never cascade-delete an
  account. The dashboard's "no link" banner handles the unlinked state.
- `null=True, blank=True` so the field is genuinely optional — existing
  installs have unlinked users on the day this ships.

**Migration:** auto-generated; nullable; no data migration needed.

**UI.** Extend the existing `ProfileForm` (which today edits `timezone`) to
also edit `roster_person`. New row in the Account page form: a `<select>` of
active `RosterPerson`s plus a "— none —" option. Submit handler unchanged
(`ProfileForm.save()` covers both fields).

## 3. Feature 2 — Responsible on the project create form

A single optional **Responsible** `<select>` appears on the create form,
positioned between Category and Status. It is NOT shown on the edit form.

**Form change.** Add a non-model `initial_responsible` `ModelChoiceField` to
`ProjectForm`, queryset = `RosterPerson.active.all()`, `required=False`. The
field is removed from `self.fields` in `__init__` when `self.instance.pk` is
set (i.e., on edit). The new template structure handles all four cases:
field present + on create form, field present + populated, field absent + on
edit form, field absent + unpopulated.

**View change.** In `views.project_form.create`, after the project is saved
(but before the m2m-with-tags save) and only if the form's
`cleaned_data.get("initial_responsible")` is truthy, create one
`RACIAssignment(project=project, person=…, role=RACIRole.RESPONSIBLE)`.

**Why not on edit too?** RACI on an existing project is a multi-row situation
(possibly multiple Responsibles, four roles). A single dropdown on the edit
form can't represent that without ambiguous semantics (replace? add? show
which one?). Editing RACI stays on the detail page's inline widget. The
create-form field is purely an initialization convenience.

## 4. Feature 3 — Filter the project list by RACI role

The project list already supports `?person=<id>`. Add `?role=<role>` so the
common question "which projects am I Responsible for?" becomes one click.

**View change.** In `views.project_list.list_view`:

- New `role = request.GET.get("role")` parameter, validated against
  `dict(RACIRole.choices)`.
- When both `person` and `role` are set, replace the current
  `raci_assignments__person_id=…` filter with a single combined filter
  `raci_assignments__person_id=…, raci_assignments__role=…` (one `.filter()`
  call so Django joins to the same row).
- When only `role` is set (no person), filter `raci_assignments__role=…`.
- When only `person` is set, existing behavior is unchanged.

`distinct()` is already applied for the person filter and stays applied.

**UI.** A new "Role" `<select>` next to the existing "Person" select in the
list page's filter bar. Options: "Any role" plus the four RACI roles. Empty
or "any" → no role filter.

## 5. Feature 4 — Dashboard: person filter + default to "me"

The dashboard becomes person-aware. By default it shows the linked user's
work; an explicit dropdown switches to a different person or to "all people".

**Query parameter conventions:**

- `?person` absent → automatic: filter to `request.user.profile.roster_person`
  if linked; otherwise show everyone (no filter).
- `?person=all` → explicit "show everyone" (overrides the auto-default).
- `?person=<id>` → filter to that specific roster person.

**Filter logic.** Each of the four cards, the Overdue list, the Upcoming list,
and the Recent activity feed is scoped to projects where the chosen person
has *any* RACI role (not just Responsible — being Accountable, Consulted, or
Informed still counts as "on your plate"). The filter on querysets is
`Q(raci_assignments__person=…)` with `.distinct()`.

**UI.** A "Showing tasks for:" dropdown above the four stat cards. Options:
"All people" (selected when `?person=all`), each active roster person
(selected when their id matches), and a "(me)" label appended to the
linked person's name so the user always knows which is theirs.

**Unlinked-user banner.** If `request.user.profile.roster_person` is `None`,
render a single-line banner above the dashboard cards: *"Link your account to
a roster person in [**Account**] to see only your tasks."* The banner is not
dismissable — it disappears the moment the user sets the link. The dashboard
behaves as "all people" until linked.

**ActivityLog scoping.** The Recent activity feed becomes
`ActivityLog.objects.filter(project__raci_assignments__person=…).distinct()`
when a person filter is active — i.e., activity on the person's projects,
not activity *by* the person. (Activity actors are `User`s; the dashboard
filter is by `RosterPerson`. Activity by-actor would require all RosterPersons
to also be Users, which isn't the model today.)

## 6. Feature 5 — "Recurring — coming up" panel

A new dashboard section surfaces not-started recurring instances regardless of
their date, closing the gap where a monthly instance generated weeks ago sits
invisible until its due date enters the 14-day Upcoming window.

**Query.**

```python
Project.instances.filter(
    status=ProjectStatus.NOT_STARTED,
    parent_template__isnull=False,
).select_related("parent_template").order_by("projected_completion_date")[:10]
```

- Filtered to instances (the `instances` manager already excludes templates).
- Only `NOT_STARTED` — once the user changes status, the instance leaves this
  panel and starts showing up in the In Progress count card as usual.
- `parent_template__isnull=False` — the panel is specifically for
  recurring-generated work, not one-offs the user happened to leave
  not-started.
- Respects the dashboard's person filter (Feature 4).
- Cap at 10 to keep the panel scannable.

**UI.** A panel below the existing Overdue / Upcoming row, captioned
**"Recurring — coming up"**, with rows showing the instance title (linked to
the detail page), the `projected_completion_date`, and a small "from
*<template title>*" hint so the user knows which schedule produced it.

**No card count.** Deliberately no "Recurring" stat card — the four existing
cards stay focused on the date/status axes; the new panel is a list, not a
count.

## 7. Feature 6 — Tag pills on the project list

Tags are entered on the form and displayed on the detail page today, but the
list page ignores them. Adding a small pill column makes them useful at scan
time.

**View change.** Add `"tags"` to the existing
`prefetch_related("raci_assignments__person", "tags")` call in
`views.project_list.list_view` to avoid an N+1.

**Template change.** In the list-row template, render a small set of
`#tagname` pills using the existing `.pill bg-gray-100` styling already used
on the detail page. Pills wrap; no truncation (the rare project with 10 tags
is the user's own choice).

## 8. Feature 7 — Filter the project list by tag

A `?tag=<slug>` query parameter filters the list to projects bearing that tag.

**View change.** In `views.project_list.list_view`:

```python
tag_slug = request.GET.get("tag", "").strip()
if tag_slug:
    qs = qs.filter(tags__slug=tag_slug).distinct()
```

**UI.** A "Tag" `<select>` in the filter bar, populated from all `Tag` rows
ordered alphabetically. Empty option labeled "Any tag". Single-tag filter
only in v1 — multi-tag AND-match (`?tag=a,b`) is deferred.

**Why a dropdown.** With the current tag count (handful), a `<select>` is
simplest. If the user accumulates ~50+ tags later, swap in a `<datalist>`
autocomplete or a tag-management page — both are easy follow-ups and not
needed today.

## 9. Data model

One field added to one existing model:

- `apps.accounts.models.UserProfile.roster_person` — nullable OneToOne to
  `roster.RosterPerson`, `on_delete=SET_NULL`, `related_name="profile"`.

No other schema changes. Everything else is view, form, template, and
URL-routing work.

## 10. Components & files (approximate)

- **Modified:** `apps/accounts/models.py` (+`roster_person` FK);
  `apps/accounts/forms.py` (extend `ProfileForm` to include the new field);
  `templates/accounts/profile.html` (render the new field).
- **Modified:** `apps/projects/forms/project.py` (add
  `initial_responsible` field, conditional removal on edit);
  `apps/projects/views/project_form.py` (create-flow RACI insert).
- **Modified:** `apps/projects/views/project_list.py` (role, tag filters;
  extend prefetch); `templates/projects/list.html` and its row partial (role
  dropdown, tag dropdown, tag pill column).
- **Modified:** `apps/projects/views/dashboard.py` (person filter resolution,
  apply filter to all four cards + two lists + activity feed; query for the
  recurring panel); `templates/home.html` (person dropdown, unlinked banner,
  recurring panel).
- **New tests** under `apps/projects/tests/` and one under
  `apps/accounts/tests/`.
- **New migration:** `apps/accounts/migrations/000N_userprofile_roster_person.py`
  (auto-generated).

## 11. Error handling

- **Unlinked user on dashboard:** banner is shown, no filter applied; works
  fine. No exceptions raised.
- **Linked roster person deleted later:** `SET_NULL` reverts the link
  silently. Dashboard reverts to the unlinked-banner state on next request.
- **Invalid query params** (`?role=bogus`, `?person=999`, `?tag=nonexistent`):
  each filter validates and silently falls back — the existing list-view code
  does this already for the `status`/`category`/`person` filters; the new
  `role` and `tag` filters follow the same pattern.
- **Archived roster person chosen as Responsible:** the create form's
  `initial_responsible` queryset uses `RosterPerson.active` so archived
  people are filtered out at the source. If a now-archived person had been
  RACI'd on a project earlier, that historical assignment is preserved
  (`RosterPerson.archive` doesn't cascade).
- **`initial_responsible` on a project that already has a Responsible:** the
  field only appears on the create form, where there cannot be a prior
  Responsible — so the additive-vs-replace question never arises.

## 12. Testing

- **Feature 1:** `UserProfile.roster_person` round-trips; `SET_NULL` on roster
  delete; the Account form saves the new field.
- **Feature 2:** create form GET shows `initial_responsible`; edit form GET
  does not; a valid POST with `initial_responsible` set creates one
  `RACIAssignment(role=RESPONSIBLE)`; a valid POST with the field blank
  creates none.
- **Feature 3:** `?role=responsible` alone filters by role; `?person=X` alone
  preserves existing behavior; `?person=X&role=responsible` matches only
  Responsible-for-X (not Consulted-for-X). The combined-filter regression
  case — Mike is Responsible on P1 and Consulted on P2; Laurel is
  Responsible on P2 — must return only P1 when querying "Mike, Responsible",
  not both P1 and P2.
- **Feature 4:** unlinked user → banner present, no filter applied; linked
  user → `?person` absent defaults to that person; `?person=all` overrides;
  `?person=<other-id>` switches; each of the four card counts honors the
  filter; the activity feed honors the filter.
- **Feature 5:** a freshly generated monthly instance (NOT_STARTED,
  parent_template set, projected date 30 days out) appears in the panel; a
  user-created (not recurring) not-started project does NOT appear; the
  person filter scopes the panel; instances move out of the panel when
  status changes to IN_PROGRESS.
- **Feature 6:** the list-row template renders one pill per tag; no pill
  block when the project has no tags; the query count does not grow with
  the number of projects (prefetch sanity check via
  `django.test.utils.CaptureQueriesContext`).
- **Feature 7:** `?tag=<slug>` returns only projects with that tag; an
  unknown slug returns the empty queryset (not an error); the filter
  composes with `?status`, `?category`, `?person`, `?role`, and `?q`.

## 13. Out of scope

- **Committees** (named groups of RosterPersons assignable to a RACI role in
  one click). Documented as a future extension; no model groundwork needed
  today. A future spec will likely add a `Committee(name, members M2M)` and
  a "Manage committees" page reached from the Account screen, mirroring the
  category-management page pattern.
- **Tag-management page** (rename, merge, delete tags). Tags are
  self-managed via the form today; if typos accumulate, this becomes the
  next spec.
- **Tag autocomplete or multi-tag AND-match** on the list filter.
  Single-tag dropdown is v1.
- **Detail-page activity history and editable notes** (Batch B in the
  brainstorming session). Separate spec.
- **Filtering by date range, by created-by user, or by attachment presence.**
  Not requested.
- **Persisting filter selections across sessions / saved-filter sets.** Not
  requested; the URL is the filter, the user can bookmark.
- **Multi-person Responsible on the create form.** Single Responsible is v1;
  multi-select would be approached via committees later.
