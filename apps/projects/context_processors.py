"""Template context processors for the projects app.

Currently exports `back_navigation` — inspects the HTTP Referer header,
maps the previous URL to a friendly label, and exposes `back_url` +
`back_label` so templates can render a "← Back to {label}" link
without per-view boilerplate.

The user-facing intent: clicking into a project from the dashboard,
board, calendar, etc., should be reversible with one click rather than
forcing a sidebar round trip. The context processor does the routing
inference once per request; templates branch on `if back_url`.
"""
from urllib.parse import urlparse

from django.urls import Resolver404, resolve

# Map a Django URL name (with namespace) to the human label shown in the
# "← Back to <label>" link. Pages NOT in this map don't get a back link
# rendered — the table is the allowlist.
_BACK_LABELS = {
    "home": "Dashboard",
    "projects:list": "Projects",
    "projects:board": "Board",
    "projects:calendar": "Calendar",
    "projects:calendar_at": "Calendar",
    "projects:recurring_list": "Recurring",
    "projects:report": "Reports",
    "projects:search": "Search results",
    "roster:list": "Roster",
    "roster:group_list": "Groups",
    "roster:group_detail": "Group",
    "accounts:profile": "Account",
    "help": "Help",
}


def back_navigation(request):
    """Returns {'back_url': str, 'back_label': str} for use in templates.

    Both values are empty strings when no usable Referer is available.
    Templates should branch with {% if back_url %}.
    """
    referer = request.META.get("HTTP_REFERER", "")
    if not referer:
        return {"back_url": "", "back_label": ""}

    try:
        parsed = urlparse(referer)
    except (ValueError, AttributeError):
        return {"back_url": "", "back_label": ""}

    # Same-origin only — reject Referers from other sites for safety.
    # An empty netloc (path-only Referer) is treated as same-origin too.
    if parsed.netloc and parsed.netloc != request.get_host():
        return {"back_url": "", "back_label": ""}

    path = parsed.path
    if not path or path == request.path:
        # Don't suggest "back" to the page the user is already on.
        return {"back_url": "", "back_label": ""}

    try:
        match = resolve(path)
    except Resolver404:
        return {"back_url": "", "back_label": ""}

    if match.namespace:
        route_name = f"{match.namespace}:{match.url_name}"
    else:
        route_name = match.url_name or ""

    label = _BACK_LABELS.get(route_name)
    if label is None:
        return {"back_url": "", "back_label": ""}

    return {"back_url": referer, "back_label": label}
