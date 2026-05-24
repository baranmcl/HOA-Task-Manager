"""Template tags for the search results page."""
import re

from django import template
from django.utils.html import conditional_escape
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
