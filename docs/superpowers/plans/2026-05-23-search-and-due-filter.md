# Full-Text Search + `?due=` Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a search page at `/projects/search/` that finds projects by title, description, or notes via naive `icontains`; plus a `?due=YYYY-MM-DD` filter on the project list that the calendar's "+N more" link consumes.

**Architecture:** Two unrelated features bundled in one branch. Search uses three sequential ORM `icontains` queries (title → description → note body), grouping by project so each project appears once with a `match_reason` label. The result template uses a small `highlight` template tag that wraps the matched substring in `<mark>`. The `?due=` filter is one extra clause on the project list view's queryset. No schema changes for either.

**Tech Stack:** Django 5.0.x, pytest-django, ruff. No new dependencies. Tailwind only rebuilt if a new utility class slips in (likely `bg-yellow-200` for `<mark>` if not already present).

---

## File Structure

**New files:**
- `apps/projects/views/search.py` — the `search_view` function.
- `apps/projects/templatetags/__init__.py` — empty package marker.
- `apps/projects/templatetags/search_extras.py` — the `highlight` template tag.
- `templates/projects/search.html` — search-results page.
- `apps/projects/tests/test_views_search.py` — view + template-tag tests.

**Modified files:**
- `apps/projects/views/__init__.py` — re-export `search_view`.
- `apps/projects/urls.py` — add the `search/` route.
- `apps/projects/views/project_list.py` — apply the `?due=` filter, pass `due_filter` to context.
- `apps/projects/tests/test_views_list_filters.py` — add `due` filter tests.
- `templates/_sidebar.html` — add the search input.
- `templates/projects/list.html` — add the "Due: <date> — clear" pill when active.
- `static/css/output.css` — rebuilt only if `bg-yellow-200` isn't already in the bundle.

---

## Task 1: `?due=YYYY-MM-DD` filter on the project list

The smaller of the two features, knocked out first. Closes the loop on the calendar's "+N more" overflow link from Batch 3.

**Files:**
- Modify: `apps/projects/views/project_list.py`
- Modify: `templates/projects/list.html`
- Test: `apps/projects/tests/test_views_list_filters.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_list_filters.py`. The file already has `import datetime as dt` or imports `Project`/`reverse`/`pytest` near the top — verify and add `import datetime as dt` to the top-of-file imports if not present. Then append:

```python
@pytest.mark.django_db
def test_due_filter_returns_only_matching_date(auth_client, user, category):
    Project.objects.create(
        title="May 15", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    Project.objects.create(
        title="May 16", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 16),
    )
    response = auth_client.get(reverse("projects:list") + "?due=2026-05-15")
    titles = [p.title for p in response.context["projects"]]
    assert titles == ["May 15"]


@pytest.mark.django_db
def test_due_filter_invalid_date_silently_ignored(auth_client, user, category):
    Project.objects.create(
        title="P1", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(reverse("projects:list") + "?due=tomorrow")
    # Invalid date is silently ignored — all projects returned.
    titles = [p.title for p in response.context["projects"]]
    assert "P1" in titles


@pytest.mark.django_db
def test_due_filter_pill_rendered_when_active(auth_client, user, category):
    Project.objects.create(
        title="P1", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(reverse("projects:list") + "?due=2026-05-15")
    content = response.content.decode()
    assert "Due:" in content
    assert "May 15, 2026" in content
    assert ">clear<" in content


@pytest.mark.django_db
def test_due_filter_pill_absent_when_no_filter(auth_client, user, category):
    Project.objects.create(
        title="P1", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(reverse("projects:list"))
    content = response.content.decode()
    assert "Due:" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_list_filters.py -v -k "due_filter"`
Expected: FAIL — the view doesn't recognize `?due=` and the template has no pill.

- [ ] **Step 3: Add the filter to the view**

In `apps/projects/views/project_list.py`, at the top of the file add the datetime import alongside the others. The file currently has `from django.contrib.auth.decorators import login_required` etc. — add (if not already present):

```python
import datetime as dt
```

Inside `list_view`, find where the existing filters (`status`, `category`, `person`, etc.) are applied. Add the `due` filter right before the `q` (free-text) filter — or, if you can't tell where that is, immediately after the `tag` filter. Insert:

```python
    due_raw = request.GET.get("due", "").strip()
    due_filter = None
    if due_raw:
        try:
            due_filter = dt.date.fromisoformat(due_raw)
            qs = qs.filter(projected_completion_date=due_filter)
        except ValueError:
            due_filter = None  # invalid — silently ignore
```

Then add `due_filter` to the render context. The current `return render(...)` call has a long dict — add this key alongside the others:

```python
        "due_filter": due_filter,
```

- [ ] **Step 4: Add the pill to the template**

In `templates/projects/list.html`, find the line that introduces the table or empty-state block. The structure (from earlier reads):

```html
{% if projects %}
<div class="bg-white rounded-lg shadow overflow-hidden">
  <table class="min-w-full divide-y divide-gray-200 text-sm">
    ...
```

Insert the pill block immediately BEFORE the `{% if projects %}` line:

```html
{% if due_filter %}
  <div class="mb-3 text-sm">
    <span class="pill bg-blue-100 text-blue-800">Due: {{ due_filter|date:"M j, Y" }}</span>
    <a href="?" class="text-blue-600 hover:underline ml-2">clear</a>
  </div>
{% endif %}

```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_list_filters.py -v`
Expected: PASS — all the new `due` tests green and all existing list-filter tests still green.

- [ ] **Step 6: Run ruff**

Run: `ruff check apps/projects/views/project_list.py apps/projects/tests/test_views_list_filters.py`
Expected: "All checks passed!"

- [ ] **Step 7: Commit**

```bash
git add apps/projects/views/project_list.py templates/projects/list.html apps/projects/tests/test_views_list_filters.py
git commit -m "feat(projects): ?due=YYYY-MM-DD filter on the project list"
```

---

## Task 2: `highlight` template tag

Pure helper. No view code yet. Building this first means Task 3's template can use it.

**Files:**
- Create: `apps/projects/templatetags/__init__.py` (empty)
- Create: `apps/projects/templatetags/search_extras.py`
- Test: `apps/projects/tests/test_views_search.py` (create)

- [ ] **Step 1: Create the failing tests**

Create `apps/projects/tests/test_views_search.py`:

```python
"""Tests for the search view and its supporting template tag."""
import pytest
from django.template import Context, Template


def _render(template_str: str, context: dict) -> str:
    """Render a one-off template string with the given context."""
    return Template(template_str).render(Context(context))


def test_highlight_wraps_match_in_mark():
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "Met with vendor", "q": "vendor"},
    )
    assert rendered == 'Met with <mark class="bg-yellow-200">vendor</mark>'


def test_highlight_is_case_insensitive_but_preserves_match_case():
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "Met with Vendor", "q": "vendor"},
    )
    # The original "Vendor" capitalization is preserved inside <mark>.
    assert '<mark class="bg-yellow-200">Vendor</mark>' in rendered


def test_highlight_wraps_multiple_matches():
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "vendor vendor vendor", "q": "vendor"},
    )
    assert rendered.count('<mark class="bg-yellow-200">vendor</mark>') == 3


def test_highlight_escapes_html_in_input():
    """HTML in the source text must be escaped — only our <mark> is real HTML."""
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "<b>vendor</b>", "q": "vendor"},
    )
    # The literal <b> tag should appear escaped, not rendered as bold.
    assert "&lt;b&gt;" in rendered
    assert '<mark class="bg-yellow-200">vendor</mark>' in rendered


def test_highlight_treats_query_as_literal_not_regex():
    """Special regex characters in q are matched literally, not as regex."""
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "a.b.c", "q": "."},
    )
    # Each literal "." gets wrapped — NOT the chars-on-either-side (which is
    # what an unescaped `.` regex would match).
    assert rendered.count('<mark class="bg-yellow-200">.</mark>') == 2


def test_highlight_empty_query_returns_text_unchanged():
    rendered = _render(
        "{% load search_extras %}{{ text|highlight:q }}",
        {"text": "Met with vendor", "q": ""},
    )
    assert rendered == "Met with vendor"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_search.py -v -k "highlight"`
Expected: FAIL — `search_extras` library does not exist.

- [ ] **Step 3: Create the templatetags package**

Create two files:

`apps/projects/templatetags/__init__.py` — empty (zero bytes, just makes the directory a Python package so Django discovers it).

`apps/projects/templatetags/search_extras.py`:

```python
"""Template tags for the search results page."""
import re

from django import template
from django.utils.html import conditional_escape, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def highlight(text: str, query: str) -> str:
    """Wrap each case-insensitive occurrence of `query` inside `text` with
    <mark class="bg-yellow-200">…</mark>.

    Non-match segments are HTML-escaped via conditional_escape before
    assembly. The final string is mark_safe — but only the <mark> tags
    we inserted are unescaped HTML; everything else is escaped first.
    """
    if not query:
        return text
    if not text:
        return ""
    # re.escape so special regex chars in the query are matched literally.
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    parts = []
    last_end = 0
    for match in pattern.finditer(text):
        # Escape the segment BEFORE the match.
        parts.append(conditional_escape(text[last_end:match.start()]))
        # Escape the matched text itself (it could contain HTML), then wrap.
        parts.append(
            f'<mark class="bg-yellow-200">{conditional_escape(match.group(0))}</mark>',
        )
        last_end = match.end()
    # The trailing segment after the last match.
    parts.append(conditional_escape(text[last_end:]))
    return mark_safe("".join(parts))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_search.py -v -k "highlight"`
Expected: PASS — all 6 highlight tests green.

- [ ] **Step 5: Run ruff**

Run: `ruff check apps/projects/templatetags/search_extras.py apps/projects/tests/test_views_search.py`
Expected: "All checks passed!"

- [ ] **Step 6: Commit**

```bash
git add apps/projects/templatetags apps/projects/tests/test_views_search.py
git commit -m "feat(search): highlight template tag for search results"
```

---

## Task 3: Search view + URL + template

The full search experience: the view that runs the three-step query, the route, and the template.

**Files:**
- Create: `apps/projects/views/search.py`
- Create: `templates/projects/search.html`
- Modify: `apps/projects/views/__init__.py`
- Modify: `apps/projects/urls.py`
- Test: `apps/projects/tests/test_views_search.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/projects/tests/test_views_search.py`. The top of the file currently has `import pytest`, `from django.template import Context, Template`. Add to the top imports:

```python
from django.urls import reverse

from apps.projects.models import Project, UpdateNote
```

Then append the tests at the bottom of the file:

```python
@pytest.mark.django_db
def test_search_empty_query_renders_empty_state(auth_client):
    response = auth_client.get(reverse("projects:search"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Search projects, notes, and descriptions" in content


@pytest.mark.django_db
def test_search_with_no_matches_shows_no_matches_message(auth_client):
    response = auth_client.get(reverse("projects:search") + "?q=zzznope")
    content = response.content.decode()
    assert "No matches for" in content


@pytest.mark.django_db
def test_search_title_match(auth_client, user, category):
    Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
    )
    response = auth_client.get(reverse("projects:search") + "?q=sprinkler")
    content = response.content.decode()
    assert "Sprinkler upgrade" in content


@pytest.mark.django_db
def test_search_description_match(auth_client, user, category):
    Project.objects.create(
        title="Maintenance contract",
        description="Quarterly review with the irrigation vendor.",
        category=category, created_by=user,
    )
    response = auth_client.get(reverse("projects:search") + "?q=irrigation")
    content = response.content.decode()
    assert "Maintenance contract" in content


@pytest.mark.django_db
def test_search_note_match(auth_client, user, category):
    project = Project.objects.create(
        title="Some project", category=category, created_by=user,
    )
    UpdateNote.objects.create(
        project=project, author=user, body="Met with sprinkler vendor today.",
    )
    response = auth_client.get(reverse("projects:search") + "?q=sprinkler")
    content = response.content.decode()
    # The project should be shown as a hit.
    assert "Some project" in content
    # The matching note body (or a snippet) should appear in the results.
    assert "sprinkler" in content.lower()


@pytest.mark.django_db
def test_search_is_case_insensitive(auth_client, user, category):
    Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
    )
    response = auth_client.get(reverse("projects:search") + "?q=SPRINKLER")
    content = response.content.decode()
    assert "Sprinkler upgrade" in content


@pytest.mark.django_db
def test_search_project_matched_by_both_title_and_notes_appears_once(
    auth_client, user, category,
):
    """A project whose title matches AND has matching notes should appear
    once, classified by title (the stronger signal)."""
    project = Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
    )
    UpdateNote.objects.create(
        project=project, author=user, body="Sprinkler vendor meeting notes.",
    )
    response = auth_client.get(reverse("projects:search") + "?q=sprinkler")
    content = response.content.decode()
    # Project title appears exactly once in the results (twice if double-counted).
    assert content.count("Sprinkler upgrade") == 1


@pytest.mark.django_db
def test_search_excludes_recurring_templates(auth_client, user, category):
    """Project.instances excludes templates; search should never return them."""
    Project.objects.create(
        title="Monthly review template", category=category, created_by=user,
        is_recurring_template=True,
    )
    response = auth_client.get(reverse("projects:search") + "?q=monthly")
    content = response.content.decode()
    assert "Monthly review template" not in content


@pytest.mark.django_db
def test_search_requires_login(client):
    response = client.get(reverse("projects:search"))
    assert response.status_code == 302
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/projects/tests/test_views_search.py -v -k "search"`
Expected: FAIL — `NoReverseMatch` for `projects:search`.

- [ ] **Step 3: Create the view**

Create `apps/projects/views/search.py`:

```python
"""Full-text-ish search across projects, descriptions, and notes."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Project, UpdateNote


@login_required
def search_view(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return render(request, "projects/search.html", {"q": "", "results": []})

    # Step 1 — projects whose title matches.
    title_hits = list(
        Project.instances.select_related("category")
        .filter(title__icontains=q)
        .order_by("-updated_at"),
    )
    title_ids = {p.pk for p in title_hits}

    # Step 2 — projects whose description matches (excluding title hits).
    desc_hits = list(
        Project.instances.select_related("category")
        .filter(description__icontains=q)
        .exclude(pk__in=title_ids)
        .order_by("-updated_at"),
    )
    desc_ids = {p.pk for p in desc_hits}

    # Step 3 — notes whose body matches (excluding projects already returned).
    note_hits = list(
        UpdateNote.objects.select_related("project__category")
        .filter(body__icontains=q)
        .exclude(project_id__in=title_ids | desc_ids)
        .order_by("-updated_at"),
    )
    # Group note hits by project, preserving newest-note-first ordering.
    notes_by_project: dict[int, list[UpdateNote]] = {}
    for n in note_hits:
        notes_by_project.setdefault(n.project_id, []).append(n)

    results = []
    for p in title_hits:
        results.append({"project": p, "match_reason": "title", "matched_notes": []})
    for p in desc_hits:
        results.append({"project": p, "match_reason": "description", "matched_notes": []})
    for project_id, notes in notes_by_project.items():
        # All notes for this project belong to one project — grab it off the first note.
        results.append({
            "project": notes[0].project,
            "match_reason": "notes",
            "matched_notes": notes,
        })

    return render(request, "projects/search.html", {"q": q, "results": results})
```

- [ ] **Step 4: Re-export the view**

In `apps/projects/views/__init__.py`, add (alphabetical placement among the other view imports):

```python
from .search import search_view as search_view
```

- [ ] **Step 5: Add the URL route**

In `apps/projects/urls.py`, add the route immediately after the calendar routes:

```python
    path("search/", views.search_view, name="search"),
```

- [ ] **Step 6: Create the search template**

Create `templates/projects/search.html`:

```html
{% extends "base.html" %}
{% load search_extras %}
{% block title %}Search — HOA Task Manager{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold text-gray-900 mb-2">Search</h1>

{% if q %}
  <p class="text-sm text-gray-500 mb-6">Results for "{{ q }}"</p>
{% else %}
  <p class="text-sm text-gray-500 mb-6">Search projects, notes, and descriptions.</p>
{% endif %}

<form method="get" action="{% url 'projects:search' %}" class="mb-6">
  <input type="search" name="q" value="{{ q }}" autofocus
         placeholder="Search…"
         class="input max-w-md">
</form>

{% if q and not results %}
  <p class="text-gray-400 text-sm">No matches for "{{ q }}".</p>
{% endif %}

{% if results %}
<div class="space-y-4">
  {% for r in results %}
    <div class="bg-white rounded-lg shadow p-4">
      <div class="flex items-center gap-2 mb-1 flex-wrap">
        <a href="{% url 'projects:detail' r.project.pk %}"
           class="text-blue-700 font-medium hover:underline">{{ r.project.title|highlight:q }}</a>
        <span class="pill bg-gray-100 text-gray-700">{{ r.project.category.name }}</span>
        <span class="pill
          {% if r.project.status == 'completed' %}bg-green-100 text-green-800
          {% elif r.project.status == 'delayed' %}bg-red-100 text-red-800
          {% elif r.project.status == 'in_progress' %}bg-blue-100 text-blue-800
          {% else %}bg-gray-100 text-gray-700{% endif %}">{{ r.project.get_status_display }}</span>
        <span class="text-xs text-gray-400 ml-auto">matched in {{ r.match_reason }}</span>
      </div>
      {% if r.match_reason == 'description' and r.project.description %}
        <div class="text-sm text-gray-700 mt-2">{{ r.project.description|truncatechars:300|highlight:q }}</div>
      {% endif %}
      {% if r.match_reason == 'notes' %}
        <ul class="mt-2 space-y-2">
          {% for n in r.matched_notes %}
            <li class="text-sm text-gray-700 border-l-2 border-gray-200 pl-3">
              <div class="text-xs text-gray-500 mb-1">{{ n.created_at|date:"M j, Y" }}</div>
              {{ n.body|truncatechars:300|highlight:q }}
            </li>
          {% endfor %}
        </ul>
      {% endif %}
    </div>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_search.py -v`
Expected: PASS — all search tests green, including the highlight tests.

- [ ] **Step 8: Run ruff**

Run: `ruff check apps/projects/views/search.py apps/projects/views/__init__.py apps/projects/urls.py apps/projects/tests/test_views_search.py`
Expected: "All checks passed!"

- [ ] **Step 9: Commit**

```bash
git add apps/projects/views/search.py apps/projects/views/__init__.py apps/projects/urls.py templates/projects/search.html apps/projects/tests/test_views_search.py
git commit -m "feat(search): /projects/search/ with three-tier match grouping"
```

---

## Task 4: Sidebar search input

A small `<input type="search">` at the top of the sidebar that submits to the search page.

**Files:**
- Modify: `templates/_sidebar.html`
- Test: `apps/projects/tests/test_views_search.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/projects/tests/test_views_search.py`:

```python
@pytest.mark.django_db
def test_sidebar_includes_search_input(auth_client):
    """Any logged-in page renders the sidebar; the search input must
    exist and submit to projects:search."""
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert reverse("projects:search") in content
    assert 'type="search"' in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/projects/tests/test_views_search.py::test_sidebar_includes_search_input -v`
Expected: FAIL — sidebar doesn't have a search input yet.

- [ ] **Step 3: Add the search input**

In `templates/_sidebar.html`, the current contents are (verified from earlier reads):

```html
<aside class="w-56 shrink-0 bg-white border-r border-gray-200 px-4 py-6 hidden md:block">
  <div class="text-lg font-semibold text-gray-900 mb-6">HOA Tasks</div>
  <nav class="space-y-1 text-sm">
    <a href="{% url 'home' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Dashboard</a>
    <a href="{% url 'projects:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Projects</a>
    <a href="{% url 'projects:calendar' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Calendar</a>
    <a href="{% url 'projects:recurring_list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Recurring</a>
    <a href="{% url 'roster:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Roster</a>
    <a href="{% url 'accounts:profile' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Account</a>
    <form method="post" action="{% url 'accounts:logout' %}" class="pt-4">
      {% csrf_token %}
      <button type="submit" class="w-full text-left px-3 py-2 rounded hover:bg-gray-100">Log out</button>
    </form>
  </nav>
</aside>
```

Insert a search form between the title `<div>` and the `<nav>`, and shrink the title's bottom-margin to make room. Updated contents:

```html
<aside class="w-56 shrink-0 bg-white border-r border-gray-200 px-4 py-6 hidden md:block">
  <div class="text-lg font-semibold text-gray-900 mb-4">HOA Tasks</div>
  <form method="get" action="{% url 'projects:search' %}" class="mb-4">
    <input type="search" name="q" placeholder="🔎 Search…"
           class="w-full text-sm rounded border border-gray-300 px-2 py-1">
  </form>
  <nav class="space-y-1 text-sm">
    <a href="{% url 'home' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Dashboard</a>
    <a href="{% url 'projects:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Projects</a>
    <a href="{% url 'projects:calendar' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Calendar</a>
    <a href="{% url 'projects:recurring_list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Recurring</a>
    <a href="{% url 'roster:list' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Roster</a>
    <a href="{% url 'accounts:profile' %}" class="block px-3 py-2 rounded hover:bg-gray-100">Account</a>
    <form method="post" action="{% url 'accounts:logout' %}" class="pt-4">
      {% csrf_token %}
      <button type="submit" class="w-full text-left px-3 py-2 rounded hover:bg-gray-100">Log out</button>
    </form>
  </nav>
</aside>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/projects/tests/test_views_search.py -v`
Expected: PASS — all search tests + the new sidebar test green.

- [ ] **Step 5: Commit**

```bash
git add templates/_sidebar.html apps/projects/tests/test_views_search.py
git commit -m "feat(search): sidebar search input"
```

---

## Task 5: Final pass — Tailwind rebuild, full suite, lint

The only utility class introduced by this batch that may not be in the bundle is `bg-yellow-200` (used by the `<mark>` wrapper). Verify and rebuild if needed.

**Files:** possibly `static/css/output.css`.

- [ ] **Step 1: Check whether `bg-yellow-200` is already in the bundle**

Run:

```bash
grep -oE '\.bg-yellow-200\{' static/css/output.css | head -1
```

Expected: zero or one match. If zero, the next step rebuilds.

- [ ] **Step 2: Rebuild Tailwind if needed**

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
```

Expected: "Done in <ms>".

- [ ] **Step 3: Verify the class is now in the bundle**

Run:

```bash
grep -oE '\.bg-yellow-200\{' static/css/output.css | head -1
```

Expected: one match.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — all tests across the app, including the new search and `?due=` tests (~25 new tests total across Tasks 1-4).

- [ ] **Step 5: Run ruff**

Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 6: Commit (if Tailwind was rebuilt)**

```bash
git add static/css/output.css
git commit -m "build: rebuild Tailwind CSS for search-result highlight"
```

If `bg-yellow-200` was already in the bundle, skip this step.

---

## Self-Review

**1. Spec coverage:**
- §3 Feature 1 (search): three-step icontains → Task 3 view. URL → Task 3. Sidebar input → Task 4. Result template → Task 3. Highlight tag → Task 2. ✓
- §4 Feature 2 (`?due=` filter): view filter + due_filter context → Task 1. Pill template → Task 1. ✓
- §6 Components & files: every file in the spec is touched by one task. ✓
- §7 Error handling: empty query, invalid date, regex specials, HTML in query — each has a test in Tasks 1-3. ✓
- §8 Testing: every bullet maps to a named test. ✓

**2. Placeholder scan:** No "TBD"/"add appropriate error handling"/"similar to Task N". Every code step has complete code.

**3. Type consistency:**
- `match_reason` values (`"title"`, `"description"`, `"notes"`) appear in the view (Task 3 Step 3), the template (Task 3 Step 6), and the tests (Task 3 Step 1) with the same string values.
- `due_filter` is a `date` or `None` — view returns it as such (Task 1 Step 3), template checks `{% if due_filter %}` (Task 1 Step 4), test asserts presence/absence of the "Due:" string (Task 1 Step 1).
- `highlight` filter signature: `(text: str, query: str) → SafeString` — defined in Task 2 Step 3, used in Task 3 Step 6 templates exactly as `{{ value|highlight:q }}`.
- URL names: `projects:search` (no args) is used consistently across the sidebar (Task 4 Step 3), the search page form (Task 3 Step 6), and tests (Tasks 3-4).
