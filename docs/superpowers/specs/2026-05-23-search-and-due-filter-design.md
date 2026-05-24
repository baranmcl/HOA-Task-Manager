# HOA Task Manager — Full-Text Search + `?due=` Filter — Design

**Date:** 2026-05-23
**Author:** Project owner (Baran) + Claude
**Status:** Approved, ready for implementation planning

---

## 1. Background

Two independent improvements bundled for one shipping cycle:

**Search.** As the tool accumulates history — old notes, completed
projects, vendor names in descriptions — being able to find "that
thing we discussed three months ago" becomes the difference between
"we have the data" and "the data may as well not exist." There's no
search today; the existing project-list `?q=` filter only matches
project title/description.

**`?due=` filter on the project list.** The calendar's "+N more"
overflow link on busy days points at `/projects/?due=YYYY-MM-DD`, but
the list view ignores the parameter. Wiring up that filter closes the
loop and gives the user a way to drill into a day's projects.

Both touch the same area of the codebase (`apps/projects/views/`,
`templates/`, `apps/projects/urls.py`), so they ship together. No
schema changes for either.

## 2. Scope

**In scope:**
- Naive `icontains` full-text search across `Project.title`,
  `Project.description`, and `UpdateNote.body`.
- A new `/search/?q=...` page rendering results grouped by project.
- A small search input in the sidebar that submits to that page.
- Result page shows matching notes as snippets under each project,
  with the search term highlighted (using a small template tag).
- A `?due=YYYY-MM-DD` filter on the project list view.
- A "Due: <date> — clear" pill on the list page when the filter is
  active.
- Tests for each behavior.

**Out of scope:**
- **SQLite FTS5 / `django-watson` / any real full-text search**
  library. At HOA scale (`<100` projects, `<500` notes) `icontains`
  is faster than the indexing overhead would be. Documented here so
  a future contributor doesn't think it was forgotten.
- **Ranking by relevance.** Result groups are ordered by a simple
  heuristic (title match → description match → notes match), not by
  TF-IDF or BM25. Within a group, results are newest-first.
- **Search across activity log entries.** The verbs ("changed status")
  are too generic to be useful as search hits; the specifics live in
  JSON dicts that are awkward to grep textually. If someone genuinely
  needs to find "when did Mike change the status of the sprinkler
  project," the project's activity panel already shows it once they
  navigate there.
- **Search across attachment filenames or RACI assignments.** Not
  asked for. Easy to add later as separate result groups.
- **Search-as-you-type / autocomplete.** Submit-on-Enter only.
- **Multi-word phrase queries (`"vendor quote"`).** A query string is
  treated as one substring; `vendor quote` searches for the literal
  six-character string, NOT (vendor OR quote). Documented so users
  understand the model.
- **Person filter on the search page.** Search answers "find this
  thing" not "what's on my plate." Keeping it global avoids confusion
  about why a search for "sprinkler" returns nothing when filtered to
  someone who isn't assigned to the sprinkler project.
- **A `?due_after=` / `?due_before=` range filter** on the project
  list. Only exact-date `?due=` lands now.
- **A UI input** for `?due=` on the list page. The calendar overflow
  link is the only producer; a manual date-picker on the list would
  duplicate what the calendar already does well.
- **Search results pagination.** At HOA scale a list of all matches
  fits on one page. Add pagination if it ever becomes painful.

## 3. Feature 1 — Full-text search

### Algorithm

For a non-empty query `q` (trimmed of whitespace), the search view runs:

1. **Project title match:** `Project.instances.filter(title__icontains=q)`.
2. **Project description match:** `Project.instances.filter(description__icontains=q)`, excluding any project already in the title-match set.
3. **Note body match:** `UpdateNote.objects.filter(body__icontains=q).select_related("project")`, grouped by project, excluding projects already returned.

Results render in the same order: title matches first, then
description-only matches, then note-only matches. Within each group,
newest first by `updated_at`.

`Project.instances` is the existing manager that excludes recurring
templates — search never returns templates (they're schedule
definitions, not work to find later).

### URL

```
/projects/search/?q=<query>
```

Empty `q` → renders the page with a friendly empty state and no
results. No 400, no redirect.

### View

A new function-based view `search_view` in
`apps/projects/views/search.py`:

```python
@login_required
def search_view(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return render(request, "projects/search.html", {"q": "", "results": []})
    # … run the three-step search, build a list of {project, matched_notes} dicts
```

The view returns context shaped for the template:

```python
{
    "q": "the query",
    "results": [
        {
            "project": <Project>,
            "match_reason": "title" | "description" | "notes",
            "matched_notes": [<UpdateNote>, …],  # only set when match_reason="notes"
        },
        …
    ],
}
```

`match_reason` lets the template label why a project is in the result
(useful when the matching content isn't visible in the title).

### Sidebar entry point

`templates/_sidebar.html` gains a small search input near the top of
the nav. Submits via GET to `projects:search`. The full sidebar after
this change:

```html
<aside class="w-56 shrink-0 bg-white border-r border-gray-200 px-4 py-6 hidden md:block">
  <div class="text-lg font-semibold text-gray-900 mb-4">HOA Tasks</div>
  <form method="get" action="{% url 'projects:search' %}" class="mb-4">
    <input type="search" name="q" placeholder="🔎 Search…"
           class="w-full text-sm rounded border border-gray-300 px-2 py-1">
  </form>
  <nav class="space-y-1 text-sm">
    … (existing links)
  </nav>
</aside>
```

The placeholder uses the magnifying-glass emoji `🔎` — no Tailwind
icon library needed.

### Result template

`templates/projects/search.html` extends `base.html`. The page has:

- A heading "Search results for '<query>'" (or just "Search" when no
  query).
- A result list — one card per project group, showing:
  - Project title (linked to detail), category pill, status pill.
  - If matched by description: the description snippet with the term
    highlighted.
  - If matched by notes: each matching note rendered as a snippet
    (first ~200 chars of body, with the term highlighted), linked to
    the project detail (anchored to the note when an anchor is
    implemented; for now, just to `projects:detail`).
- An empty state when no results: "No matches for '<query>'."
- An empty-query state: "Search projects, notes, and descriptions."

### Search-term highlight

A small Django template tag `highlight` wraps occurrences of the
query in a `<mark class="bg-yellow-200">` element. Lives in a new
`apps/projects/templatetags/search_extras.py` module. The tag is
case-insensitive, escapes user input properly (uses Django's
`mark_safe` only on the final assembled string), and preserves the
original casing of the matched text.

```django
{% load search_extras %}
{{ note.body|highlight:q }}
```

The implementation uses `re.split` with a case-insensitive pattern
that captures the match (so we can re-render it inside the `<mark>`).

## 4. Feature 2 — `?due=YYYY-MM-DD` filter on the project list

### View change

In `apps/projects/views/project_list.py`, parse the `due` param and
apply the filter:

```python
due_raw = request.GET.get("due", "").strip()
due_filter = None
if due_raw:
    try:
        due_filter = dt.date.fromisoformat(due_raw)
        qs = qs.filter(projected_completion_date=due_filter)
    except ValueError:
        due_filter = None  # invalid — silently ignore, same as ?role=bogus
```

Pass `due_filter` (a `date` or `None`) to the template context.

### Template change

`templates/projects/list.html` gains a small pill at the top of the
results (above the table but below the filter bar) when `due_filter`
is set:

```html
{% if due_filter %}
  <div class="mb-3 text-sm">
    <span class="pill bg-blue-100 text-blue-800">Due: {{ due_filter|date:"M j, Y" }}</span>
    <a href="?" class="text-blue-600 hover:underline ml-2">clear</a>
  </div>
{% endif %}
```

The clear link is `?` (empty query string) — wipes the filter without
preserving other current filters. Acceptable for a one-off drill-in
from the calendar where the user got there by following a link, not
by composing a filter set.

## 5. Data model

**No schema changes** for either feature.

## 6. Components & files

**New files:**
- `apps/projects/views/search.py` — `search_view` + helpers.
- `apps/projects/templatetags/__init__.py` — empty package marker
  (the templatetags dir may not yet exist).
- `apps/projects/templatetags/search_extras.py` — `highlight`
  template tag.
- `templates/projects/search.html` — search-results page.
- `apps/projects/tests/test_views_search.py` — tests for the search
  view + the `highlight` tag.

**Modified files:**
- `apps/projects/views/__init__.py` — re-export `search_view`.
- `apps/projects/urls.py` — add `search/` route.
- `apps/projects/views/project_list.py` — apply `due` filter.
- `apps/projects/tests/test_views_list_filters.py` — add `due` filter
  tests.
- `templates/_sidebar.html` — add the search input.
- `templates/projects/list.html` — add the "Due: <date> — clear" pill
  when active.
- `static/css/output.css` — rebuilt if any new utility class slips in
  (likely none; `bg-yellow-200` may need to be picked up).

## 7. Error handling

- **Empty `q`**: page renders with empty state; no error.
- **`q` containing only whitespace**: same as empty after `.strip()`.
- **`q` containing regex special characters** (`*`, `?`, `.`, `[`,
  `]`): not interpreted as regex — passed verbatim to
  `__icontains`, which does literal substring matching at the DB
  level. The `highlight` template tag escapes special regex chars
  via `re.escape(q)` before building its split pattern.
- **`q` containing HTML-ish characters** (`<script>`, `"`, `&`): Django
  template auto-escapes `{{ q }}` and the `highlight` tag escapes the
  non-match segments via `conditional_escape` before assembly. The
  final `mark_safe` is applied only to the assembled string with
  `<mark>` tags inserted.
- **`?due=` with malformed date** (e.g. `?due=tomorrow`): caught by
  `dt.date.fromisoformat()`'s `ValueError`, silently ignored; the
  list shows all projects.

## 8. Testing

### Search

- **Empty query** renders the page with no results and no error
  message.
- **Non-empty query with no matches** renders "No matches for 'foo'".
- **Title match**: a project whose title contains the query appears
  in the result list with `match_reason="title"`.
- **Description match**: a project whose description (but not title)
  contains the query appears with `match_reason="description"`.
- **Note match**: a note whose body (but not parent project's
  title/description) contains the query appears as a note match, with
  the parent project listed once.
- **A project matched by both title and notes** appears once, under
  `match_reason="title"` — title trumps notes.
- **Recurring templates are excluded** (the manager filter).
- **Login required**: anonymous → 302 to login.
- **Case-insensitive**: searching for "SPRINKLER" matches a project
  titled "Sprinkler upgrade".

### `highlight` template tag

- **Match in middle of text**: `highlight("Met with vendor", "vendor")`
  returns `Met with <mark class="bg-yellow-200">vendor</mark>`.
- **Case insensitive**: `highlight("Met with Vendor", "vendor")`
  preserves the original casing `Vendor` inside the `<mark>` tag.
- **Multiple matches**: `highlight("vendor vendor", "vendor")` wraps
  both occurrences.
- **HTML in text is escaped**: `highlight("<b>vendor</b>", "vendor")`
  doesn't render bold — `<` and `>` are escaped, the literal `<b>`
  appears as text. The `<mark>` itself is the only HTML.
- **Special regex chars in query**: `highlight("a.b.c", ".")` wraps
  each literal `.` — regex semantics are NOT used.
- **Empty query**: returns the original text unchanged (no
  wrapping).

### `?due=` filter

- **Valid date**: `?due=2026-05-15` returns only projects whose
  `projected_completion_date == 2026-05-15`.
- **Invalid date**: `?due=tomorrow` returns all projects (filter
  silently ignored).
- **No `?due=` param**: returns all projects (no filter applied).
- **Pill renders**: when `?due=` is valid, the list page contains
  "Due: <formatted date>" and a "clear" link pointing to `?`.

## 9. Performance

`icontains` does a database-level `LIKE '%query%'`, which is a
sequential scan. For `<100` projects and `<500` notes this completes
in well under 10ms.

If the dataset ever grows to thousands of notes, the natural upgrade
path is:
1. Add a SQLite FTS5 virtual table that mirrors `UpdateNote.body`.
2. Replace the third query with a join to the FTS5 table.
3. Keep the title/description queries on the main table (they're tiny).

Documented here for the future; not needed now.

## 10. Security

- **XSS via search query**: every interpolation of `q` in the template
  uses Django's auto-escaping (except the `highlight` filter's output,
  which uses `mark_safe` only after explicit escaping of the
  non-match segments).
- **XSS via note body**: notes are already rendered as Markdown via
  `render_note()`, which uses `bleach` to allow only a safe subset of
  HTML. The `highlight` tag, when applied to a Markdown-rendered
  note, wraps `<mark>` around already-escaped content — safe.
- **No SQL injection**: `__icontains` parameterizes through the ORM.

## 11. Cost & risk

- **Schema risk**: zero (no schema change).
- **UX risk**: the sidebar search input takes up vertical space —
  about 40 pixels. Acceptable; the sidebar has room.
- **Performance risk**: zero at current scale; documented upgrade path
  if the dataset grows.
- **Code risk**: the `highlight` template tag is the only piece doing
  HTML assembly with `mark_safe`. Tests cover the escape behavior
  explicitly.

## 12. Open decisions for owner sign-off

None. All defaults are listed above.
