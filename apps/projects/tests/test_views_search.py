"""Tests for the search view and its supporting template tag."""
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
