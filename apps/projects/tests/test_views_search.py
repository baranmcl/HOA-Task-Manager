"""Tests for the search view and its supporting template tag."""
import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.projects.models import Project, UpdateNote


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
    # Project title appears exactly once in the result-card heading.
    # (It may appear other places in the page — e.g. inside the search input
    # placeholder — so count occurrences in just the result cards. Simplest:
    # ensure we got one project section, not two.)
    assert content.count('Sprinkler upgrade</a>') == 1


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
def test_search_excludes_recurring_templates_via_note_match(
    auth_client, user, category,
):
    """Notes attached to a recurring template must NOT pull the template
    into search results. Step-3 of the search guards this explicitly with
    project__is_recurring_template=False so the template-exclusion invariant
    holds across all three match tiers.
    """
    template = Project.objects.create(
        title="Quarterly template", category=category, created_by=user,
        is_recurring_template=True,
    )
    UpdateNote.objects.create(
        project=template, author=user,
        body="This note mentions sprinklers but lives on a template.",
    )
    response = auth_client.get(reverse("projects:search") + "?q=sprinklers")
    content = response.content.decode()
    assert "Quarterly template" not in content


@pytest.mark.django_db
def test_search_requires_login(client):
    response = client.get(reverse("projects:search"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_sidebar_includes_search_input(auth_client):
    """Any logged-in page renders the sidebar; the search input must
    exist and submit to projects:search."""
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert reverse("projects:search") in content
    assert 'type="search"' in content
